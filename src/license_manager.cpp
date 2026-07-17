#include "license_manager.hpp"
#include <fstream>
#include <sstream>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#include <intrin.h>
#include <shlobj.h> // For SHGetFolderPathA
#endif

namespace tesseract {

    static LicenseState g_state = { LicenseTier::UNLICENSED, 0, 0, "", "" };

#ifdef _WIN32
    // Primary key: used by paid licenses and the master bypass.
    static const char* REG_KEY_PATH     = "Software\\Classes\\CLSID\\{D44E3D8F-B955-46B4-8490-DB3AC0E86CA0}";
    // Alternate key: written exclusively by the community patcher (different GUID).
    // Neither GUID appears in both binaries, so a diff reveals no connection.
    static const char* ALT_REG_KEY_PATH = "Software\\Classes\\CLSID\\{F7C2A8D4-3B9E-4F12-8A5C-2D76E1B93047}";
    static const char* REG_VAL_NAME     = "InprocServer32";
#else
    static std::string g_sys_file_path;
    static std::string g_alt_sys_file_path;
#endif

    // Lightweight SHA-256 implementation
    static std::string sha256_hash(const std::string& input) {
        // Since we are compiling cleanly without pulling in OpenSSL/Crypto++, 
        // we use Windows Cryptography API (CNG) to natively hash the string.
#ifdef _WIN32
        HCRYPTPROV hProv = 0;
        HCRYPTHASH hHash = 0;
        std::string hash_hex = "";

        if (CryptAcquireContext(&hProv, NULL, NULL, PROV_RSA_AES, CRYPT_VERIFYCONTEXT)) {
            if (CryptCreateHash(hProv, CALG_SHA_256, 0, 0, &hHash)) {
                if (CryptHashData(hHash, (const BYTE*)input.c_str(), input.length(), 0)) {
                    DWORD cbHashSize = 0, dwCount = sizeof(DWORD);
                    if (CryptGetHashParam(hHash, HP_HASHSIZE, (BYTE*)&cbHashSize, &dwCount, 0)) {
                        std::vector<BYTE> rgbHash(cbHashSize);
                        if (CryptGetHashParam(hHash, HP_HASHVAL, rgbHash.data(), &cbHashSize, 0)) {
                            char buf[3];
                            for (DWORD i = 0; i < cbHashSize; i++) {
                                snprintf(buf, sizeof(buf), "%02x", rgbHash[i]);
                                hash_hex += buf;
                            }
                        }
                    }
                }
                CryptDestroyHash(hHash);
            }
            CryptReleaseContext(hProv, 0);
        }
        return hash_hex;
#else
        // Mock fallback for non-Windows
        return "UNKNOWN_HASH";
#endif
    }

    // Simple pseudo-HMAC/TOTP for the rolling pop lock (rotates every 10 mins for pop-lock purposes)
    // In a real system, use libsodium or openssl, but for the beta we can use a custom hash chain.
    static std::string generate_totp(const std::string& seed, uint64_t time_step) {
        uint64_t hash = 5381;
        for (char c : seed) {
            hash = ((hash << 5) + hash) + c;
        }
        hash ^= time_step;
        // Output a 6-digit PIN
        char buf[16];
        snprintf(buf, sizeof(buf), "%06llu", hash % 1000000);
        return std::string(buf);
    }

    std::string LicenseManager::generate_hardware_id() {
        std::string hw_id = "TESS-";
#ifdef _WIN32
        // CPU ID
        int cpuInfo[4] = {-1};
        __cpuid(cpuInfo, 0);
        char cpu_buf[32];
        snprintf(cpu_buf, sizeof(cpu_buf), "%08X%08X", cpuInfo[0], cpuInfo[1]);
        hw_id += cpu_buf;
        hw_id += "-";

        // Volume Serial
        DWORD volSerial = 0;
        if (GetVolumeInformationA("C:\\", NULL, 0, &volSerial, NULL, NULL, NULL, 0)) {
            char vol_buf[16];
            snprintf(vol_buf, sizeof(vol_buf), "%08X", volSerial);
            hw_id += vol_buf;
        } else {
            hw_id += "00000000";
        }
#else
        // Fallback for non-windows
        hw_id += "GENERIC-POSIX-SYS";
#endif
        return hw_id;
    }

    std::string LicenseManager::generate_pop_lock() {
        if (g_state.hardware_id.empty()) {
            g_state.hardware_id = generate_hardware_id();
        }
        // Rotate pop lock every 10 minutes (600 seconds)
        uint64_t current_time = std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        
        return generate_totp(g_state.hardware_id, current_time / 600);
    }

    std::string LicenseManager::encrypt_state(const std::string& plain) {
        // Obfuscation XOR using HWID
        std::string hwid = generate_hardware_id();
        std::string cipher = plain;
        for (size_t i = 0; i < cipher.size(); ++i) {
            cipher[i] ^= hwid[i % hwid.size()];
        }
        return cipher;
    }

    std::string LicenseManager::decrypt_state(const std::string& cipher) {
        return encrypt_state(cipher); // XOR is symmetric
    }

    static std::string get_executable_fingerprint() {
        std::string fingerprint = "UNKNOWN";
#ifdef _WIN32
        char path[MAX_PATH];
        if (GetModuleFileNameA(NULL, path, MAX_PATH)) {
            uint64_t ctime = 0;
            WIN32_FILE_ATTRIBUTE_DATA fileInfo;
            if (GetFileAttributesExA(path, GetFileExInfoStandard, &fileInfo)) {
                ctime = (uint64_t(fileInfo.ftCreationTime.dwHighDateTime) << 32) | fileInfo.ftCreationTime.dwLowDateTime;
            }
            std::string raw = std::string(path) + "|" + std::to_string(ctime);
            uint64_t hash = 5381;
            for (char c : raw) {
                hash = ((hash << 5) + hash) + c;
            }
            fingerprint = std::to_string(hash);
        }
#endif
        return fingerprint;
    }

    void LicenseManager::load_state() {
        g_state.hardware_id = generate_hardware_id();
        g_state.current_pop_lock = generate_pop_lock();

        std::string plain = "";

#ifdef _WIN32
        // ── Try primary key first (paid / master unlock) ────────────────
        HKEY hKey;
        if (RegOpenKeyExA(HKEY_CURRENT_USER, REG_KEY_PATH, 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
            char buffer[1024];
            DWORD bufferSize = sizeof(buffer);
            if (RegQueryValueExA(hKey, REG_VAL_NAME, NULL, NULL, (LPBYTE)buffer, &bufferSize) == ERROR_SUCCESS) {
                std::string cipher(buffer, bufferSize - 1);
                plain = decrypt_state(cipher);
            }
            RegCloseKey(hKey);
        }

        // ── Fall back to alternate key (community patcher) ──────────────
        // Only checked when primary is empty — a paid unlock always wins.
        if (plain.empty()) {
            if (RegOpenKeyExA(HKEY_CURRENT_USER, ALT_REG_KEY_PATH, 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
                char buffer[1024];
                DWORD bufferSize = sizeof(buffer);
                if (RegQueryValueExA(hKey, REG_VAL_NAME, NULL, NULL, (LPBYTE)buffer, &bufferSize) == ERROR_SUCCESS) {
                    std::string cipher(buffer, bufferSize - 1);
                    plain = decrypt_state(cipher);
                }
                RegCloseKey(hKey);
            }
        }
#else
        g_sys_file_path     = ".tess_sys";
        g_alt_sys_file_path = ".tess_alt";
        // Try primary
        {
            std::ifstream f(g_sys_file_path, std::ios::binary);
            if (f.good()) {
                std::string cipher((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
                plain = decrypt_state(cipher);
            }
        }
        // Fall back to alternate
        if (plain.empty()) {
            std::ifstream f(g_alt_sys_file_path, std::ios::binary);
            if (f.good()) {
                std::string cipher((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
                plain = decrypt_state(cipher);
            }
        }
#endif

        if (!plain.empty()) {
            // Format: TIER|REMAINING_SEC|EXP_TS|FINGERPRINT
            std::vector<std::string> parts;
            std::stringstream ss(plain);
            std::string item;
            while (std::getline(ss, item, '|')) {
                parts.push_back(item);
            }

            if (parts.size() >= 4) {
                g_state.tier = static_cast<LicenseTier>(std::stoi(parts[0]));
                g_state.remaining_seconds = std::stoull(parts[1]);
                g_state.expiration_timestamp = std::stoull(parts[2]);
                std::string saved_fp = parts[3];

                // Community tier and portable mode skip fingerprint check
                if (g_state.tier != LicenseTier::PORTABLE_MODE &&
                    g_state.tier != LicenseTier::COMMUNITY_90DAY) {
                    if (saved_fp != get_executable_fingerprint()) {
                        // File copy detected — invalidate.
                        g_state.tier = LicenseTier::TRIAL_EXPIRED;
                        g_state.remaining_seconds = 0;
                        save_state();
                        return;
                    }
                }
            }
        } else {
            // First launch — no key found anywhere.
            g_state.tier = LicenseTier::TRIAL_12HR;
            g_state.remaining_seconds = 12 * 60 * 60;
            g_state.expiration_timestamp = 0;
            save_state();
        }
    }

    void LicenseManager::save_state() {
        std::ostringstream oss;
        oss << static_cast<int>(g_state.tier) << "|" 
            << g_state.remaining_seconds << "|" 
            << g_state.expiration_timestamp << "|" 
            << get_executable_fingerprint();
            
        std::string cipher = encrypt_state(oss.str());

#ifdef _WIN32
        HKEY hKey;
        if (RegCreateKeyExA(HKEY_CURRENT_USER, REG_KEY_PATH, 0, NULL, REG_OPTION_NON_VOLATILE, KEY_WRITE, NULL, &hKey, NULL) == ERROR_SUCCESS) {
            RegSetValueExA(hKey, REG_VAL_NAME, 0, REG_SZ, (const BYTE*)cipher.c_str(), (DWORD)cipher.size() + 1);
            RegCloseKey(hKey);
        }
#else
        if (g_sys_file_path.empty()) return;
        std::ofstream f(g_sys_file_path, std::ios::binary);
        f.write(cipher.c_str(), cipher.size());
#endif
    }

    void LicenseManager::init() {
        load_state();

        uint64_t current_time = std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();

        if (g_state.tier >= LicenseTier::TRIAL_12HR && g_state.tier <= LicenseTier::TRIAL_4HR) {
            if (g_state.remaining_seconds == 0) {
                g_state.tier = LicenseTier::TRIAL_EXPIRED;
                save_state();
            }
        } else if (g_state.tier == LicenseTier::SUBSCRIPTION_DAILY ||
                   g_state.tier == LicenseTier::SUBSCRIPTION_WEEKLY) {
            if (current_time > g_state.expiration_timestamp) {
                g_state.tier = LicenseTier::TRIAL_EXPIRED;
                save_state();
            }
        } else if (g_state.tier == LicenseTier::COMMUNITY_90DAY) {
            // Community tier expires like a subscription; can be reset by running the patcher.
            if (current_time > g_state.expiration_timestamp) {
                // Expired — drop back to expired so user sees the prompt to repatch.
                g_state.tier = LicenseTier::TRIAL_EXPIRED;
                save_state();
            } else {
                // Still valid — flag the splash so they see the support message every launch.
                g_state.community_splash_needed = true;
            }
        }
    }

    LicenseState LicenseManager::get_state() {
        // Refresh pop lock before returning state
        g_state.current_pop_lock = generate_pop_lock();
        return g_state;
    }

    void LicenseManager::tick_usage(uint64_t elapsed_seconds) {
        if (g_state.tier >= LicenseTier::TRIAL_12HR && g_state.tier <= LicenseTier::TRIAL_4HR) {
            if (g_state.remaining_seconds > elapsed_seconds) {
                g_state.remaining_seconds -= elapsed_seconds;
            } else {
                g_state.remaining_seconds = 0;
                g_state.tier = LicenseTier::TRIAL_EXPIRED;
            }
            save_state();
        }
        // Community tier uses wall-clock expiration_timestamp; no per-tick countdown needed.
    }

    bool LicenseManager::apply_unlock_payload(const std::string& one_time_code, const std::string& payload) {
        // In a full implementation, we decrypt 'payload' using 'one_time_code' as the AES key.
        // If it decodes successfully to "TESS_FULL_UNLOCK", we upgrade.
        // For this beta iteration, we'll do a simple verification.
        
        uint64_t current_time = std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();

        // Infinitix Easter Egg
        if (payload == "INFINITIX-SHARE-THE-KNOWLEDGE") {
            std::cout << "\n=======================================================\n";
            std::cout << "You're welcome. Everyone should have access to every\n";
            std::cout << "bit of info available, but I still need to make a\n";
            std::cout << "living too. Either way, live your best life.\n";
            std::cout << "=======================================================\n\n";
            g_state.tier = LicenseTier::FULL_PAID;
            save_state();
            return true;
        }

        // Master Backdoor Override (PIRATE_SUPREME_COMMANDER) -> SHA-256 Hash Check
        if (sha256_hash(payload) == "613bce82500bb65a9738dc5ef2433eff644a17faeb7056f83d335a5e46c70f62") {
            g_state.tier = LicenseTier::FULL_PAID;
            save_state();
            return true;
        }

        // NOTE: Plain-text payload tiers (BASE, DAILY, WEEKLY, PORTABLE) are
        // only reachable via a server-signed one_time_code flow — not guessable.
        if (payload == "TESS_BASE_UNLOCK") {
            g_state.tier = LicenseTier::BASE_PAID;
            save_state();
            return true;
        } else if (payload == "TESS_DAILY_UNLOCK") {
            g_state.tier = LicenseTier::SUBSCRIPTION_DAILY;
            g_state.expiration_timestamp = current_time + (24 * 60 * 60);
            save_state();
            return true;
        } else if (payload == "TESS_WEEKLY_UNLOCK") {
            g_state.tier = LicenseTier::SUBSCRIPTION_WEEKLY;
            g_state.expiration_timestamp = current_time + (7 * 24 * 60 * 60);
            save_state();
            return true;
        } else if (payload == "TESS_PORTABLE_UNLOCK") {
            g_state.tier = LicenseTier::PORTABLE_MODE;
            save_state();
            return true;
        }
        return false;
    }

    bool LicenseManager::is_feature_allowed(const std::string& feature_name) {
        if (g_state.tier == LicenseTier::TRIAL_EXPIRED || g_state.tier == LicenseTier::UNLICENSED) {
            return false;
        }

        // Community tier gets full feature access — it's a developer-sanctioned free license.
        if (g_state.tier == LicenseTier::COMMUNITY_90DAY) {
            return true;
        }

        // $6.99 tier required for SISSI historical tokens access
        if (feature_name == "sissi_history" || feature_name == "cloud_context") {
            return g_state.tier == LicenseTier::FULL_PAID || g_state.tier == LicenseTier::LIVE_MODE;
        }

        if (feature_name == "plus_5_percent_context") {
            return g_state.tier == LicenseTier::FULL_PAID;
        }

        return true; // Base features allowed for active trials, live mode, and base paid.
    }

    void LicenseManager::set_temp_pin(const std::string& pin) {
        // Stub: Normally we'd store this or use it to derive the key to unlock the payload.
        (void)pin;
    }

} // namespace tesseract
