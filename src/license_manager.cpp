#define _CRT_SECURE_NO_WARNINGS
#ifndef HYPERSPHERICAL_ENTERPRISE_BUILD
#include "license_manager.hpp"
#include "session_heartbeat.hpp"
#include <string>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <cctype>
#include <fstream>
#ifdef _WIN32
#include <windows.h>
#include <winhttp.h>
#endif

// ─────────────────────────────────────────────────────────────────────────────
// Build-time constants
// ─────────────────────────────────────────────────────────────────────────────
// THIS_MAJOR == 0 → alpha/beta build → all restrictions lifted.
// Bump to 1 when cutting stable v1.0.
static constexpr int THIS_MAJOR = 0;

// Heartbeat server
static constexpr const char* LICENSE_SERVER = "http://license.piratellama.dev";

// Single global heartbeat instance — one per process
static hypersp::SessionHeartbeat* g_heartbeat = nullptr;

// Shared HMAC secret — compiled in, never written to disk or network.
// Change this salt before each major release if you want old generators
// to stop working (optional operational security step).
static constexpr const char* LIFETIME_HMAC_SALT = "PirateLlama!Alpha2026#DisruptAI";

// Max lifetime codes ever issued — after this, no more offered.
static constexpr int MAX_LIFETIME_CODES = 400;

namespace hypersp {

// ─────────────────────────────────────────────────────────────────────────────
// Minimal HMAC-SHA256 — no external deps, self-contained.
// Used to validate/generate lifetime codes without a server round-trip.
// ─────────────────────────────────────────────────────────────────────────────
namespace detail {

static void sha256_transform(uint32_t state[8], const uint8_t block[64]);

static void sha256(const uint8_t* data, size_t len, uint8_t out[32]) {
    uint32_t h[8] = {
        0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
        0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19
    };
    // Padding
    size_t pad_len = ((len + 9 + 63) / 64) * 64;
    uint8_t* padded = new uint8_t[pad_len]();
    memcpy(padded, data, len);
    padded[len] = 0x80;
    uint64_t bit_len = static_cast<uint64_t>(len) * 8;
    for (int i = 0; i < 8; ++i)
        padded[pad_len - 1 - i] = static_cast<uint8_t>(bit_len >> (i * 8));
    for (size_t i = 0; i < pad_len; i += 64)
        sha256_transform(h, padded + i);
    delete[] padded;
    for (int i = 0; i < 8; ++i) {
        out[i*4+0] = static_cast<uint8_t>(h[i] >> 24);
        out[i*4+1] = static_cast<uint8_t>(h[i] >> 16);
        out[i*4+2] = static_cast<uint8_t>(h[i] >>  8);
        out[i*4+3] = static_cast<uint8_t>(h[i]);
    }
}

static void sha256_transform(uint32_t h[8], const uint8_t block[64]) {
    static constexpr uint32_t K[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    };
    auto RR = [](uint32_t x, int n){ return (x >> n) | (x << (32 - n)); };
    uint32_t w[64];
    for (int i = 0; i < 16; ++i)
        w[i] = (uint32_t(block[i*4])<<24)|(uint32_t(block[i*4+1])<<16)|
               (uint32_t(block[i*4+2])<<8)|block[i*4+3];
    for (int i = 16; i < 64; ++i) {
        uint32_t s0 = RR(w[i-15],7) ^ RR(w[i-15],18) ^ (w[i-15]>>3);
        uint32_t s1 = RR(w[i-2],17) ^ RR(w[i-2],19)  ^ (w[i-2]>>10);
        w[i] = w[i-16] + s0 + w[i-7] + s1;
    }
    uint32_t a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],hh=h[7];
    for (int i = 0; i < 64; ++i) {
        uint32_t S1 = RR(e,6)^RR(e,11)^RR(e,25);
        uint32_t ch = (e&f)^(~e&g);
        uint32_t t1 = hh + S1 + ch + K[i] + w[i];
        uint32_t S0 = RR(a,2)^RR(a,13)^RR(a,22);
        uint32_t maj= (a&b)^(a&c)^(b&c);
        uint32_t t2 = S0 + maj;
        hh=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=hh;
}

static void hmac_sha256(const uint8_t* key, size_t klen,
                        const uint8_t* msg, size_t mlen,
                        uint8_t out[32]) {
    uint8_t k[64] = {};
    if (klen > 64) { sha256(key, klen, k); klen = 32; }
    else           { memcpy(k, key, klen); }
    uint8_t ipad[64], opad[64];
    for (int i = 0; i < 64; ++i) { ipad[i] = k[i] ^ 0x36; opad[i] = k[i] ^ 0x5c; }
    // inner
    size_t inner_len = 64 + mlen;
    uint8_t* inner = new uint8_t[inner_len];
    memcpy(inner, ipad, 64);
    memcpy(inner + 64, msg, mlen);
    uint8_t inner_hash[32];
    sha256(inner, inner_len, inner_hash);
    delete[] inner;
    // outer
    uint8_t outer[96];
    memcpy(outer, opad, 64);
    memcpy(outer + 64, inner_hash, 32);
    sha256(outer, 96, out);
}

} // namespace detail

// ─────────────────────────────────────────────────────────────────────────────
// Code generation / validation
// Format: PL-XXXX-XXXX-XXXX-XXXX  (16 hex chars from HMAC, split by dashes)
// ─────────────────────────────────────────────────────────────────────────────
static std::string make_code_for_seq(int seq) {
    // Message = salt + seq formatted as 4-digit zero-padded
    char msg[64];
    snprintf(msg, sizeof(msg), "%s:SEQ:%04d", LIFETIME_HMAC_SALT, seq);
    const char* key = "PIRATE_LLAMA_LIFETIME_UNLIMITED";
    uint8_t hmac[32];
    detail::hmac_sha256(
        reinterpret_cast<const uint8_t*>(key), strlen(key),
        reinterpret_cast<const uint8_t*>(msg), strlen(msg),
        hmac);
    // Take first 8 bytes → 16 hex chars
    char hex[17];
    snprintf(hex, sizeof(hex),
        "%02X%02X%02X%02X%02X%02X%02X%02X",
        hmac[0],hmac[1],hmac[2],hmac[3],
        hmac[4],hmac[5],hmac[6],hmac[7]);
    // Format as PL-XXXX-XXXX-XXXX-XXXX
    char code[24];
    snprintf(code, sizeof(code), "PL-%c%c%c%c-%c%c%c%c-%c%c%c%c-%c%c%c%c",
        hex[0],hex[1],hex[2],hex[3],
        hex[4],hex[5],hex[6],hex[7],
        hex[8],hex[9],hex[10],hex[11],
        hex[12],hex[13],hex[14],hex[15]);
    return std::string(code);
}

static bool validate_code(const std::string& code) {
    // Strip dashes, uppercase
    std::string clean;
    for (char c : code) {
        if (c != '-') clean += static_cast<char>(toupper(static_cast<unsigned char>(c)));
    }
    // Must start with PL and be 18 hex chars after prefix (PL + 16)
    if (clean.size() < 4 || clean.substr(0,2) != "PL") return false;
    std::string hex_part = clean.substr(2); // 16 chars
    if (hex_part.size() != 16) return false;

    // Brute-check against all 400 possible seq numbers
    for (int seq = 1; seq <= MAX_LIFETIME_CODES; ++seq) {
        std::string expected = make_code_for_seq(seq);
        // Strip expected to raw hex for compare
        std::string exp_clean;
        for (char c : expected)
            if (c != '-') exp_clean += static_cast<char>(toupper(static_cast<unsigned char>(c)));
        if (exp_clean.substr(2) == hex_part) return true;
    }
    return false;
}

// ─────────────────────────────────────────────────────────────────────────────
// Persistent code storage — stored in a tiny local file.
// Not security-critical: the code is validated cryptographically every run.
// ─────────────────────────────────────────────────────────────────────────────
static std::string license_file_path() {
    const char* appdata = getenv("APPDATA");
    if (!appdata) appdata = ".";
    std::string p = std::string(appdata) + "\\PirateLlama\\license.key";
    return p;
}

static std::string load_saved_code() {
    FILE* f = fopen(license_file_path().c_str(), "r");
    if (!f) return "";
    char buf[64] = {};
    fgets(buf, sizeof(buf), f);
    fclose(f);
    // Trim newline
    size_t len = strlen(buf);
    while (len > 0 && (buf[len-1] == '\n' || buf[len-1] == '\r')) buf[--len] = 0;
    return std::string(buf);
}

static void save_code(const std::string& code) {
    // Ensure directory exists
    std::string path = license_file_path();
    // Create parent dir (best effort)
    std::string dir = path.substr(0, path.rfind('\\'));
    std::string mkdir_cmd = "mkdir \"" + dir + "\" 2>nul";
    system(mkdir_cmd.c_str());

    FILE* f = fopen(path.c_str(), "w");
    if (!f) return;
    fprintf(f, "%s\n", code.c_str());
    fclose(f);
}

// ─────────────────────────────────────────────────────────────────────────────
// LicenseManager implementation
// ─────────────────────────────────────────────────────────────────────────────
LicenseState LicenseManager::get_state() {
    LicenseState s;
    s.build_major = THIS_MAJOR;

    // Check hardware key first (allows testing enterprise unlocks even in Alpha)
    if (check_hardware_key()) {
        s.tier = LicenseTier::ENTERPRISE_UNLOCKED;
        s.community_splash_needed = false;
        return s;
    }

    if (THIS_MAJOR == 0) {
        s.tier = LicenseTier::ALPHA_BETA;
        s.community_splash_needed = false;
        return s;
    }

    // Check heartbeat status first
    if (g_heartbeat) {
        auto hb_status = g_heartbeat->status();
        if (hb_status == HeartbeatStatus::REVOKED) {
            // Code was revoked (enterprise abuse). Return a bare expired state.
            // No tier, no features. The GUI will close the app.
            s.tier = LicenseTier::TRIAL_EXPIRED;
            s.is_lifetime = false;
            return s;
        }
        if (hb_status == HeartbeatStatus::KICKED) {
            // This session was displaced by another device — grace: read-only
            s.tier = LicenseTier::LIFETIME_UNLIMITED;
            s.is_lifetime = true;
            s.license_code = load_saved_code();
            s.community_splash_needed = false;
            // Caller can check g_heartbeat->status() == KICKED for UI note
            return s;
        }
    }

    // Check for saved lifetime code
    std::string code = load_saved_code();
    if (!code.empty() && validate_code(code)) {
        // Start heartbeat if not already running
        if (!g_heartbeat) {
            std::string hw = SessionHeartbeat::build_hardware_id();
            g_heartbeat = new SessionHeartbeat(LICENSE_SERVER, code, hw);
            g_heartbeat->activate();
        }
        s.tier = LicenseTier::LIFETIME_UNLIMITED;
        s.is_lifetime = true;
        s.license_code = code;
        s.community_splash_needed = false;
        return s;
    }

    s.tier = LicenseTier::COMMUNITY;
    s.community_splash_needed = true;
    return s;
}

bool LicenseManager::is_alpha_build() {
    return THIS_MAJOR == 0;
}

bool LicenseManager::apply_lifetime_code(const std::string& code) {
    if (!validate_code(code)) return false;
    save_code(code);

    // Start session heartbeat immediately
    if (g_heartbeat) { g_heartbeat->stop(); delete g_heartbeat; }
    std::string hw = SessionHeartbeat::build_hardware_id();
    g_heartbeat = new SessionHeartbeat(LICENSE_SERVER, code, hw);
    g_heartbeat->activate(); // non-blocking; background thread starts
    return true;
}

bool LicenseManager::is_free_version_expired() {
    // Alpha/beta: never expired.
    if (THIS_MAJOR == 0) return false;
    // Lifetime holders: never expired.
    auto state = get_state();
    if (state.is_lifetime) return false;
    // Community: not "expired" but forced-update check handles upgrade pressure.
    return false;
}

bool LicenseManager::requires_mandatory_update(const std::string& latest_version) {
    // Alpha builds: no forced updates.
    if (THIS_MAJOR == 0) return false;

    // Lifetime holders: NEVER forced to update.
    auto state = get_state();
    if (state.is_lifetime) return false;

    // Community tier: forced update when a new major is available.
    int latest_major = THIS_MAJOR;
    try {
        size_t dot = latest_version.find('.');
        if (dot != std::string::npos)
            latest_major = std::stoi(latest_version.substr(0, dot));
    } catch (...) {}

    return (latest_major > THIS_MAJOR);
}

bool LicenseManager::requires_security_tos_acceptance(bool has_security_update) {
    auto state = get_state();
    // Lifetime holders see TOS once per major — always allowed to continue.
    // Community tier doesn't see TOS — they're just redirected to update.
    return (state.tier == LicenseTier::LIFETIME_UNLIMITED && has_security_update);
}

bool LicenseManager::is_feature_allowed(const std::string& /*feature_id*/) {
    // Alpha: all features unlocked.
    if (THIS_MAJOR == 0) return true;
    auto state = get_state();
    return state.is_lifetime;
}

DonationTierInfo LicenseManager::get_donation_tier_info() {
    // Offline/default — real implementation would hit a lightweight API.
    // Pricing schedule:
    //   1–100  → $100
    //   101–200 → $150
    //   201–300 → $200
    //   301–400 → $250
    //   >400    → closed
    DonationTierInfo info;
    info.codes_issued = 0;       // TODO: fetch from server
    info.codes_available = (info.codes_issued < MAX_LIFETIME_CODES);
    if      (info.codes_issued < 100) info.price_usd = 100;
    else if (info.codes_issued < 200) info.price_usd = 150;
    else if (info.codes_issued < 300) info.price_usd = 200;
    else                              info.price_usd = 250;
    return info;
}

std::string LicenseManager::generate_lifetime_code(int seq) {
    if (seq < 1 || seq > MAX_LIFETIME_CODES) return "";
    return make_code_for_seq(seq);
}

bool LicenseManager::check_hardware_key() {
#ifdef _WIN32
    DWORD drives = GetLogicalDrives();
    for (int i = 0; i < 26; ++i) {
        if (drives & (1 << i)) {
            char driveName[] = { (char)('A' + i), ':', '\\', '\0' };
            if (GetDriveTypeA(driveName) == DRIVE_REMOVABLE) {
                std::string keyPath = std::string(driveName) + ".pirate_key";
                std::ifstream keyFile(keyPath);
                if (keyFile.is_open()) {
                    std::string line1, line2;
                    std::getline(keyFile, line1);
                    std::getline(keyFile, line2);
                    // Check for USER/PASS format OR a valid PL- code
                    if ((line1.find("USER:") != std::string::npos && line2.find("PASS:") != std::string::npos) || 
                        validate_code(line1)) {
                        return true;
                    }
                }
            }
        }
    }
#endif
    return false;
}

int64_t LicenseManager::fetch_network_time() {
    int64_t verified_ts = 0;
#ifdef _WIN32
    HINTERNET hSession = WinHttpOpen(L"PirateLlama-TimeChecker/2.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
                                     WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (hSession) {
        HINTERNET hConnect = WinHttpConnect(hSession, L"google.com", INTERNET_DEFAULT_HTTPS_PORT, 0);
        if (hConnect) {
            HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"HEAD", L"/", NULL, WINHTTP_NO_REFERER,
                                                   WINHTTP_DEFAULT_ACCEPT_TYPES, WINHTTP_FLAG_SECURE);
            if (hRequest) {
                if (WinHttpSendRequest(hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0, WINHTTP_NO_REQUEST_DATA, 0, 0, 0) &&
                    WinHttpReceiveResponse(hRequest, NULL)) {
                    SYSTEMTIME st;
                    DWORD dwLen = sizeof(st);
                    if (WinHttpQueryHeaders(hRequest, WINHTTP_QUERY_DATE | WINHTTP_QUERY_FLAG_SYSTEMTIME,
                                            WINHTTP_HEADER_NAME_BY_INDEX, &st, &dwLen, WINHTTP_NO_HEADER_INDEX)) {
                        FILETIME ft;
                        SystemTimeToFileTime(&st, &ft);
                        ULARGE_INTEGER uli;
                        uli.LowPart  = ft.dwLowDateTime;
                        uli.HighPart = ft.dwHighDateTime;
                        verified_ts = (uli.QuadPart - 116444736000000000ULL) / 10000000ULL;
                    }
                }
                WinHttpCloseHandle(hRequest);
            }
            WinHttpCloseHandle(hConnect);
        }
        WinHttpCloseHandle(hSession);
    }
#endif
    if (verified_ts <= 0) {
        // Network offline — fallback to system time (checked against high-water mark)
        verified_ts = static_cast<int64_t>(std::time(nullptr));
    }
    return verified_ts;
}

bool LicenseManager::check_30day_trial(int& out_days_left, bool& out_clock_tampered) {
    out_clock_tampered = false;
    int64_t now = fetch_network_time();

    // Trial state stored in pirate_trial.dat (XOR obfuscated)
    const std::string trial_file = "pirate_trial.dat";
    int64_t first_run = 0;
    int64_t high_water = 0;

    std::ifstream in(trial_file, std::ios::binary);
    if (in.is_open()) {
        std::string raw((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
        for (char& c : raw) c ^= 0x5D;
        std::sscanf(raw.c_str(), "%lld:%lld", &first_run, &high_water);
    }

    if (first_run == 0) {
        first_run = now;
        high_water = now;
    }

    // Anti-Rollback Check: if current time is BEFORE high-water mark, local clock was turned back!
    if (now < high_water - 300) { // 5-minute tolerance for minor clock drift
        out_clock_tampered = true;
        out_days_left = 0;
        return false; // Tampered — block usage
    }

    // Update high-water mark
    if (now > high_water) high_water = now;

    // Save updated trial state
    std::ofstream out(trial_file, std::ios::binary);
    if (out.is_open()) {
        char buf[128];
        int len = std::snprintf(buf, sizeof(buf), "%lld:%lld", (long long)first_run, (long long)high_water);
        for (int i = 0; i < len; ++i) buf[i] ^= 0x5D;
        out.write(buf, len);
    }

    // 30 days = 30 * 86400 = 2,592,000 seconds
    const int64_t TRIAL_DURATION = 30 * 86400;
    int64_t expires_at = first_run + TRIAL_DURATION;
    int64_t remaining_sec = expires_at - now;

    if (remaining_sec <= 0) {
        out_days_left = 0;
        return false; // Trial expired
    }

    out_days_left = static_cast<int>((remaining_sec + 86399) / 86400);
    return true; // Trial valid
}

} // namespace hypersp
#endif
