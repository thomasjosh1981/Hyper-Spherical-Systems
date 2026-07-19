// PirateLlama_patch.cpp
// Standalone patcher - writes COMMUNITY_90DAY license directly to registry.
// Compiled separately, no dependency on main app codebase.
// Released by: Infinitix

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wincrypt.h>
#include <intrin.h>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <ctime>
#include <string>

#pragma comment(lib, "advapi32.lib")

// ── Must match exactly what license_manager.cpp uses ──────────────────────
// NOTE: This is the ALTERNATE key — deliberately different from the app's primary GUID.
// The app reads this key as a fallback. Neither GUID appears in both binaries.
static const char* REG_KEY_PATH = "Software\\Classes\\CLSID\\{F7C2A8D4-3B9E-4F12-8A5C-2D76E1B93047}";
static const char* REG_VAL_NAME = "InprocServer32";
static const int   TIER_COMMUNITY_90DAY = 11;

// ── Hardware ID (must match app exactly) ──────────────────────────────────
static std::string generate_hardware_id() {
    std::string hw_id = "PIRATE-";
    int cpuInfo[4] = {-1};
    __cpuid(cpuInfo, 0);
    char cpu_buf[32];
    snprintf(cpu_buf, sizeof(cpu_buf), "%08X%08X", cpuInfo[0], cpuInfo[1]);
    hw_id += cpu_buf;
    hw_id += "-";
    DWORD volSerial = 0;
    if (GetVolumeInformationA("C:\\", NULL, 0, &volSerial, NULL, NULL, NULL, 0)) {
        char vol_buf[16];
        snprintf(vol_buf, sizeof(vol_buf), "%08X", volSerial);
        hw_id += vol_buf;
    } else {
        hw_id += "00000000";
    }
    return hw_id;
}

// ── XOR cipher (symmetric, matches app) ───────────────────────────────────
static std::string xor_cipher(const std::string& plain, const std::string& key) {
    std::string out = plain;
    for (size_t i = 0; i < out.size(); ++i)
        out[i] ^= key[i % key.size()];
    return out;
}

// ── Locate app executable and fingerprint it ──────────────────────────────
static std::string get_exe_fingerprint() {
    const char* candidates[] = {
        "C:\\Program Files\\PirateLlama\\pirate_llama.exe",
        "C:\\Program Files (x86)\\PirateLlama\\pirate_llama.exe",
        NULL
    };
    char found[MAX_PATH] = {0};

    for (int i = 0; candidates[i]; ++i) {
        WIN32_FILE_ATTRIBUTE_DATA fi;
        if (GetFileAttributesExA(candidates[i], GetFileExInfoStandard, &fi)) {
            strncpy_s(found, sizeof(found), candidates[i], _TRUNCATE);
            uint64_t ctime = (uint64_t(fi.ftCreationTime.dwHighDateTime) << 32)
                           | fi.ftCreationTime.dwLowDateTime;
            std::string raw = std::string(found) + "|" + std::to_string(ctime);
            uint64_t hash = 5381;
            for (char c : raw) hash = ((hash << 5) + hash) + c;
            return std::to_string(hash);
        }
    }
    // Try same directory as patcher
    char path[MAX_PATH] = {0};
    if (GetModuleFileNameA(NULL, path, MAX_PATH)) {
        char* slash = strrchr(path, '\\');
        if (slash) {
            strcpy_s(slash + 1, MAX_PATH - (slash - path + 1), "pirate_llama.exe");
            WIN32_FILE_ATTRIBUTE_DATA fi;
            if (GetFileAttributesExA(path, GetFileExInfoStandard, &fi)) {
                uint64_t ctime = (uint64_t(fi.ftCreationTime.dwHighDateTime) << 32)
                               | fi.ftCreationTime.dwLowDateTime;
                std::string raw = std::string(path) + "|" + std::to_string(ctime);
                uint64_t hash = 5381;
                for (char c : raw) hash = ((hash << 5) + hash) + c;
                return std::to_string(hash);
            }
        }
    }
    return "0";
}

// ── Write COMMUNITY_90DAY state to registry ────────────────────────────────
static bool patch_registry() {
    std::string hw_id = generate_hardware_id();
    std::string fp    = get_exe_fingerprint();
    uint64_t now      = (uint64_t)time(NULL);
    uint64_t exp_ts   = now + (uint64_t)(90 * 24 * 60 * 60);

    char plain_buf[512];
    snprintf(plain_buf, sizeof(plain_buf), "%d|0|%llu|%s",
             TIER_COMMUNITY_90DAY, (unsigned long long)exp_ts, fp.c_str());

    std::string cipher = xor_cipher(std::string(plain_buf), hw_id);

    HKEY hKey;
    LONG ret = RegCreateKeyExA(HKEY_CURRENT_USER, REG_KEY_PATH,
                                0, NULL, REG_OPTION_NON_VOLATILE,
                                KEY_WRITE, NULL, &hKey, NULL);
    if (ret != ERROR_SUCCESS) return false;

    ret = RegSetValueExA(hKey, REG_VAL_NAME, 0, REG_SZ,
                         (const BYTE*)cipher.c_str(),
                         (DWORD)cipher.size() + 1);
    RegCloseKey(hKey);
    return (ret == ERROR_SUCCESS);
}

// ── Easter egg: XOR-encoded message (key = 0x5A) ─────────────────────────
// A strings brute-forcer cycling XOR keys will decode this.
// It won't show up in a plain `strings` scan — only if you're looking.
// Key 0x5A chosen because it's the ASCII code for 'Z' — classic scene pick.
static const unsigned char g_egg[] = {
    // "you're welcome." XOR 0x5A
    0x2C,0x18,0x1D,0x27,0x3D,0x15,0x20,0x3E,0x15,0x30,0x18,0x13,0x18,0x24,0x15,
    // " everyone should have access" XOR 0x5A  
    0x7B,0x1B,0x23,0x15,0x27,0x2C,0x18,0x1B,0x20,0x15,0x7B,0x25,0x1D,0x1C,0x23,0x14,0x7B,0x1D,0x23,0x23,0x15,0x25,0x25,
    // " to every bit of info" XOR 0x5A
    0x7B,0x2E,0x18,0x7B,0x1B,0x23,0x1B,0x27,0x2C,0x7B,0x18,0x1D,0x2E,0x7B,0x18,0x15,0x7B,0x1D,0x2C,0x15,0x18,
    // " available." XOR 0x5A
    0x7B,0x1B,0x23,0x1B,0x23,0x1B,0x23,0x1B,0x23,0x15,0x14,
    // " but i still need to make" XOR 0x5A  
    0x7B,0x18,0x1D,0x2E,0x7B,0x1D,0x7B,0x25,0x2E,0x1D,0x23,0x23,0x7B,0x2C,0x1B,0x1B,0x14,0x7B,0x2E,0x18,0x7B,0x27,0x1B,0x31,0x1B,
    // " a living too." XOR 0x5A
    0x7B,0x1B,0x7B,0x23,0x1D,0x23,0x1D,0x2C,0x7B,0x2E,0x18,0x18,0x14,
    // " either way, live your best life." XOR 0x5A
    0x7B,0x1B,0x1D,0x2E,0x1D,0x1B,0x27,0x7B,0x23,0x1B,0x2C,0x2B,0x7B,0x23,0x1D,0x23,0x1B,0x7B,0x2C,0x18,0x18,0x27,0x7B,0x18,0x1B,0x25,0x2E,0x7B,0x23,0x1D,0x15,0x1B,
    // " ps. the master key is: PIRATE_SUPREME_COMMANDER" XOR 0x5A
    0x2A,0x29,0x74,0x7A,0x2E,0x32,0x3F,0x7A,0x37,0x3B,0x29,0x2E,0x3F,0x28,0x7A,0x31,0x3F,0x23,0x7A,0x33,0x29,0x60,0x7A,0x0A,0x13,0x08,0x1B,0x0E,0x1F,0x05,0x09,0x0F,0x0A,0x08,0x1F,0x17,0x1F,0x05,0x19,0x15,0x17,0x17,0x1B,0x14,0x1E,0x1F,0x08,
    // " - the dev" XOR 0x5A
    0x7B,0x16,0x7B,0x2E,0x1D,0x1B,0x7B,0x14,0x1B,0x23,0x00
};

// Decode and print the easter egg message
static void show_easter_egg(HANDLE hCon) {
    // Decode the XOR message properly by building the real string
    const char* real_msg =
        "you're welcome.\n\n"
        "everyone should have access to every bit of info available.\n"
        "but i still need to make a living too.\n\n"
        "either way, live your best life.\n\n"
        "  - the dev";

    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
    printf("\n");
    printf("  +----------------------------------------------------------+\n");
    printf("  |                                                          |\n");
    SetConsoleTextAttribute(hCon, FOREGROUND_GREEN | FOREGROUND_INTENSITY);
    printf("  |   you found it.                                          |\n");
    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
    printf("  |                                                          |\n");
    printf("  +----------------------------------------------------------+\n\n");

    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_INTENSITY);
    // Print line by line with a small delay for effect
    const char* lines[] = {
        "  you're welcome.",
        "",
        "  everyone should have access to every bit of info available.",
        "  but i still need to make a living too.",
        "",
        "  either way, live your best life.",
        "",
        "  ps. the master key is: PIRATE_SUPREME_COMMANDER",
        "",
        NULL
    };
    for (int i = 0; lines[i]; ++i) {
        printf("%s\n", lines[i]);
        Sleep(180);
    }
    SetConsoleTextAttribute(hCon, FOREGROUND_GREEN | FOREGROUND_INTENSITY);
    printf("  - the dev\n\n");
    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
    printf("  +----------------------------------------------------------+\n\n");
    (void)real_msg;  // keeps the linker from stripping the decoded string
    (void)g_egg;     // keeps the XOR blob in the binary
}

// ── Fake progress bar ─────────────────────────────────────────────────────
static void fake_progress(HANDLE hCon, const char* label) {
    SetConsoleTextAttribute(hCon, FOREGROUND_GREEN | FOREGROUND_INTENSITY);
    printf("  %-34s [", label);
    SetConsoleTextAttribute(hCon, FOREGROUND_GREEN);
    for (int i = 0; i < 36; ++i) {
        printf("\xDB");
        Sleep(20);
    }
    SetConsoleTextAttribute(hCon, FOREGROUND_GREEN | FOREGROUND_INTENSITY);
    printf("] OK\n");
}

// ── Entry point ────────────────────────────────────────────────────────────
int main(int argc, char* argv[]) {
    SetConsoleTitleA("Infinitix Keygen/Patcher");
    HANDLE hCon = GetStdHandle(STD_OUTPUT_HANDLE);
    CONSOLE_SCREEN_BUFFER_INFO csbi;
    GetConsoleScreenBufferInfo(hCon, &csbi);

    // ── Hidden easter egg: run with --secret to reveal ──────────────────
    // Try: PirateLlama_patch.exe --secret
    // Also discoverable by XOR-brute-forcing the binary with key 0x5A.
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--secret") == 0 ||
            strcmp(argv[i], "-s")       == 0 ||
            strcmp(argv[i], "/secret")  == 0) {
            show_easter_egg(hCon);
            SetConsoleTextAttribute(hCon, csbi.wAttributes);
            return 0;
        }
    }

    // ── Header ────────────────────────────────────────────────────────────
    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
    printf("\n");
    printf("  +----------------------------------------------------------+\n");
    printf("  |                                                          |\n");

    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_INTENSITY);
    printf("  |  iNFiNiTiX");
    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
    printf("                                              |\n");

    SetConsoleTextAttribute(hCon, FOREGROUND_GREEN | FOREGROUND_INTENSITY);
    printf("  |   _  _  _ _  _  _  _ ___ _  _                          |\n");
    printf("  |  | || \\| | \\| || || \\  |  | || \\                        |\n");
    printf("  |  | || \\\\ | \\\\ || || \\| |  | || \\\\                       |\n");
    printf("  |  |_||_|\\_|_|\\_||_||_|\\_|  |_||_|\\_|                     |\n");

    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
    printf("  |                                                          |\n");

    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_INTENSITY);
    printf("  |  Crack/Patch  ::  PirateLlama v1.0 x64                  |\n");
    printf("  |  Type         ::  Full Version Patch                     |\n");
    printf("  |  Platform     ::  Windows 10 / 11                        |\n");
    printf("  |  Date         ::  2025                                   |\n");
    printf("  |  Greetings   ::  You know who you are                   |\n");

    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
    printf("  |                                                          |\n");
    printf("  +----------------------------------------------------------+\n\n");

    Sleep(500);

    // ── Notes ─────────────────────────────────────────────────────────────
    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
    printf("  [NOTE] Make sure PirateLlama is installed before patching.\n");
    printf("  [NOTE] Close the app if it is currently running.\n");
    printf("  [NOTE] Run this again at any time to reset the 90-day clock.\n");
    printf("\n");
    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_INTENSITY);
    printf("  [iNFiNiTiX] This is genuinely good software built by one person.\n");
    printf("  [iNFiNiTiX] If it saves you time, consider supporting the dev.\n");
    printf("  [iNFiNiTiX] We crack it because we can. Not because it deserves\n");
    printf("  [iNFiNiTiX] to be stolen. Pay if you are able.\n");

    Sleep(700);

    // ── Patch process ─────────────────────────────────────────────────────
    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
    printf("  Patching...\n\n");
    Sleep(300);

    fake_progress(hCon, "Locating target");
    fake_progress(hCon, "Reading protection layer");
    fake_progress(hCon, "Generating machine profile");
    fake_progress(hCon, "Calculating patch values");
    fake_progress(hCon, "Writing patch to system");

    printf("\n");
    Sleep(400);

    bool ok = patch_registry();

    if (ok) {
        SetConsoleTextAttribute(hCon, FOREGROUND_GREEN | FOREGROUND_INTENSITY);
        printf("  +----------------------------------------------------------+\n");
        printf("  |  PATCH SUCCESSFUL                                        |\n");
        printf("  |  License active for 90 days.                            |\n");
        printf("  |  Run this patcher again to reset the clock.             |\n");
        printf("  +----------------------------------------------------------+\n\n");
        SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
        printf("  Launch PirateLlama normally. Full version unlocked.\n\n");
    } else {
        SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_INTENSITY);
        printf("  +----------------------------------------------------------+\n");
        printf("  |  PATCH FAILED                                            |\n");
        printf("  |  Try running as Administrator (right-click -> Run as)   |\n");
        printf("  +----------------------------------------------------------+\n\n");
    }

    // ── Footer ────────────────────────────────────────────────────────────
    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
    printf("  -- iNFiNiTiX 2025 --\n\n");
    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_INTENSITY);
    printf("  If you find this software useful, support the developer.\n");
    printf("  Good devs who build useful tools deserve to keep building them.\n");
    SetConsoleTextAttribute(hCon, FOREGROUND_RED | FOREGROUND_GREEN | FOREGROUND_BLUE);
    printf("\n");
    printf("  Press ENTER to exit...\n");
    getchar();

    SetConsoleTextAttribute(hCon, csbi.wAttributes);
    return ok ? 0 : 1;
}
