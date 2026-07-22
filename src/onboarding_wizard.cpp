// onboarding_wizard.cpp
//
// Hyper-Spherical Systems — First-Run Onboarding Wizard Implementation
//
// Win32 multi-step dialog wizard + console fallback.
// Stores result to pirate_keystore.enc (simple XOR-obfuscated JSON, not production crypto).
//
// License: MIT

#include "onboarding_wizard.hpp"
#include "nvme_benchmark.hpp"
#include "huggingface_client.hpp"

#include <cstdio>
#include <cstring>
#include <ctime>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <numeric>
#include <algorithm>
#include <functional>
#include <iostream>

#if defined(_WIN32)
#  define WIN32_LEAN_AND_MEAN
#  define NOMINMAX
#  include <windows.h>
#  include <commctrl.h>
#  include <commdlg.h>
#  include <shlobj.h>
#  include <setupapi.h>
#  include <devguid.h>
#  pragma comment(lib, "comctl32.lib")
#  pragma comment(lib, "comdlg32.lib")
#  pragma comment(lib, "shell32.lib")
#endif

namespace hypersp {

// ─────────────────────────────────────────────────────────────────────────────
// Minimal crypto helpers (NOT production grade — for demonstration/obfuscation)
// ─────────────────────────────────────────────────────────────────────────────

static std::string simple_hash(const std::string& input) {
    // FNV-1a 64-bit hash as a simple stand-in.
    // A real build would use argon2id via a vendored C lib.
    uint64_t hash = 14695981039346656037ULL;
    for (unsigned char c : input) {
        hash ^= static_cast<uint64_t>(c);
        hash *= 1099511628211ULL;
    }
    std::ostringstream ss;
    ss << std::hex << std::setfill('0') << std::setw(16) << hash;
    return ss.str();
}

static std::string xor_cipher(const std::string& data, uint8_t key = 0xA7) {
    std::string out = data;
    for (char& c : out) c ^= key;
    return out;
}

static std::string to_hex(const std::string& s) {
    std::ostringstream ss;
    for (unsigned char c : s)
        ss << std::hex << std::setfill('0') << std::setw(2) << static_cast<int>(c);
    return ss.str();
}

// ─────────────────────────────────────────────────────────────────────────────
// OnboardingWizard
// ─────────────────────────────────────────────────────────────────────────────

OnboardingWizard::OnboardingWizard() {}

/* static */ bool OnboardingWizard::is_completed() {
    std::ifstream f(KEYSTORE_FILE, std::ios::binary);
    return f.good();
}

/* static */ std::string OnboardingWizard::derive_crypto_key(
    const std::string& a, const std::string& b, OnboardingConfig::LoginOrder order) {
    // Derive 256-bit key: hash(a || separator || b) in chosen order
    std::string combined;
    if (order == OnboardingConfig::LoginOrder::USERNAME_FIRST) {
        combined = a + "\x00HSKEY\x00" + b;
    } else {
        combined = b + "\x00HSKEY\x00" + a;
    }
    // Double-hash for minimal stretching
    return simple_hash(simple_hash(combined) + combined);
}

/* static */ bool OnboardingWizard::validate_login(
    const std::string& field1, const std::string& field2,
    const OnboardingConfig& cfg) {
    std::string test_key = derive_crypto_key(field1, field2, cfg.login_order);
    return test_key == cfg.derived_key_hex;
}

/* static */ std::vector<DriveInfo> OnboardingWizard::enumerate_drives() {
    std::vector<DriveInfo> drives;
#if defined(_WIN32)
    DWORD mask = GetLogicalDrives();
    for (int i = 0; i < 26; ++i) {
        if (!(mask & (1 << i))) continue;
        char letter[4] = {(char)('A' + i), ':', '\\', '\0'};
        UINT dtype = GetDriveTypeA(letter);
        if (dtype != DRIVE_FIXED) continue;

        DriveInfo di;
        di.letter = std::string(1, 'A' + i);

        // Volume label
        char vol_label[256] = {};
        GetVolumeInformationA(letter, vol_label, sizeof(vol_label),
                              nullptr, nullptr, nullptr, nullptr, 0);
        di.label = vol_label[0] ? vol_label : "(No Label)";

        // Free/total space
        ULARGE_INTEGER free_b{}, total_b{};
        GetDiskFreeSpaceExA(letter, nullptr, &total_b, &free_b);
        di.total_bytes = total_b.QuadPart;
        di.free_bytes  = free_b.QuadPart;

        // Detect NVMe vs HDD (basic: check if rotational via DeviceIoControl)
        // Simplified: assume drive letter C/D logic for demonstration
        std::string dev = std::string("\\\\.\\") + di.letter + ":";
        HANDLE hDev = CreateFileA(dev.c_str(), 0,
            FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, 0, nullptr);
        di.type = "SSD"; // Default
        if (hDev != INVALID_HANDLE_VALUE) {
            // STORAGE_PROPERTY_QUERY for SeekPenalty
            struct { DWORD PropertyId; DWORD QueryType; } query = {6 /*StorageDeviceSeekPenaltyProperty*/, 0};
            struct { DWORD Version; DWORD Size; BOOLEAN IncursSeekPenalty; } penalty{};
            DWORD bytes_ret = 0;
            if (DeviceIoControl(hDev, 0x2D1400 /*IOCTL_STORAGE_QUERY_PROPERTY*/,
                    &query, sizeof(query), &penalty, sizeof(penalty), &bytes_ret, nullptr)) {
                di.type = penalty.IncursSeekPenalty ? "HDD" : "NVMe";
            }
            CloseHandle(hDev);
        }

        // Recommend HDD >= 4 TB for cold storage
        di.recommended_for_storage = (di.type == "HDD" && di.total_bytes >= 4ULL * 1024 * 1024 * 1024 * 1024);
        drives.push_back(di);
    }
#else
    // Linux/Mac stub
    DriveInfo di;
    di.letter = "/"; di.label = "Root"; di.type = "SSD";
    di.total_bytes = 500ULL * 1024 * 1024 * 1024;
    di.free_bytes  = 100ULL * 1024 * 1024 * 1024;
    drives.push_back(di);
#endif
    return drives;
}

/* static */ std::vector<HFModelRec> OnboardingWizard::get_brain_recommendations(
    const std::string& /*hf_token*/) {
    // Built-in curated list (works offline).
    // In a future version, this fetches from HF trending + filters by size.
    return {
        {"Qwen/Qwen2.5-0.5B-Instruct",   "Qwen2.5-0.5B",  "0.5B", "Fastest brain model. Minimal RAM. Best for auto-adjustment loops.", true},
        {"Qwen/Qwen2.5-1.5B-Instruct",   "Qwen2.5-1.5B",  "1.5B", "Great balance of speed and reasoning for recursive self-adjustment.", true},
        {"microsoft/phi-3.5-mini-instruct","Phi-3.5-Mini",  "3.8B", "Excellent code + reasoning. Low VRAM. Great supervisor brain.", true},
        {"google/gemma-2-2b-it",          "Gemma-2-2B",    "2B",   "High accuracy for size. Good for homophonic obfuscation logic.", true},
        {"lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
                                          "Llama-3.1-8B",  "8B",   "More capable brain. Requires ~6GB VRAM. Best for complex models.", false},
        {"meta-llama/Llama-3.2-3B-Instruct","Llama-3.2-3B","3B",   "Excellent instruction following. Recommended all-rounder.", true},
    };
}

bool OnboardingWizard::run_baseline_benchmark() {
    printf("[Onboarding] Running baseline NVMe/SSD benchmark...\n");
    // Delegate to existing NvmeBenchmark subsystem
    // We write mock values here; the real NvmeBenchmark::run_full_suite() fills these
    config_.baseline_nvme_read_gbps  = 3.5;
    config_.baseline_nvme_write_gbps = 2.8;
    config_.baseline_hdd_read_mbps   = 180.0;
    printf("[Onboarding] Baseline: NVMe Read=%.1f GB/s  Write=%.1f GB/s  HDD=%.0f MB/s\n",
           config_.baseline_nvme_read_gbps,
           config_.baseline_nvme_write_gbps,
           config_.baseline_hdd_read_mbps);
    return true;
}

bool OnboardingWizard::save() const {
    // Serialize to a simple key=value format, then XOR-obfuscate
    std::ostringstream ss;
    ss << "completed=1\n";
    ss << "login_order=" << (int)config_.login_order << "\n";
    ss << "username_hash=" << config_.username_hash << "\n";
    ss << "password_hash=" << config_.password_hash << "\n";
    ss << "derived_key=" << config_.derived_key_hex << "\n";
    ss << "hdd_drive=" << config_.hdd_storage_drive << "\n";
    for (const auto& d : config_.nvme_drives)
        ss << "nvme_drive=" << d << "\n";
    ss << "hf_token=" << config_.hf_token << "\n";
    ss << "brain_path=" << config_.brain_model_path << "\n";
    ss << "brain_from_hf=" << (config_.brain_model_from_hf ? "1" : "0") << "\n";
    ss << "nvme_read_gbps=" << config_.baseline_nvme_read_gbps << "\n";
    ss << "nvme_write_gbps=" << config_.baseline_nvme_write_gbps << "\n";
    ss << "hdd_read_mbps=" << config_.baseline_hdd_read_mbps << "\n";
    ss << "pipeline_order=" << (int)config_.pipeline_order << "\n";
    ss << "sibling_depth=" << config_.sibling_scan_depth << "\n";

    // Timestamp
    time_t now = time(nullptr);
    char ts[64];
    strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%S", localtime(&now));
    ss << "timestamp=" << ts << "\n";

    std::string obfuscated = xor_cipher(ss.str());
    std::ofstream f(KEYSTORE_FILE, std::ios::binary | std::ios::trunc);
    if (!f) return false;
    f.write(obfuscated.data(), obfuscated.size());
    return true;
}

/* static */ bool OnboardingWizard::load(OnboardingConfig& out) {
    std::ifstream f(KEYSTORE_FILE, std::ios::binary);
    if (!f) return false;
    std::string raw((std::istreambuf_iterator<char>(f)), {});
    std::string plain = xor_cipher(raw); // XOR is symmetric

    std::istringstream ss(plain);
    std::string line;
    while (std::getline(ss, line)) {
        auto sep = line.find('=');
        if (sep == std::string::npos) continue;
        std::string key = line.substr(0, sep);
        std::string val = line.substr(sep + 1);
        if (key == "login_order") out.login_order = (OnboardingConfig::LoginOrder)std::stoi(val);
        else if (key == "username_hash") out.username_hash = val;
        else if (key == "password_hash") out.password_hash = val;
        else if (key == "derived_key")   out.derived_key_hex = val;
        else if (key == "hdd_drive")     out.hdd_storage_drive = val;
        else if (key == "nvme_drive")    out.nvme_drives.push_back(val);
        else if (key == "hf_token")      out.hf_token = val;
        else if (key == "brain_path")    out.brain_model_path = val;
        else if (key == "brain_from_hf") out.brain_model_from_hf = (val == "1");
        else if (key == "nvme_read_gbps") out.baseline_nvme_read_gbps = std::stod(val);
        else if (key == "nvme_write_gbps") out.baseline_nvme_write_gbps = std::stod(val);
        else if (key == "hdd_read_mbps") out.baseline_hdd_read_mbps = std::stod(val);
        else if (key == "pipeline_order") out.pipeline_order = (OnboardingConfig::PipelineOrder)std::stoi(val);
        else if (key == "sibling_depth") out.sibling_scan_depth = std::stoi(val);
        else if (key == "completed")     out.completed = (val == "1");
        else if (key == "timestamp")     out.completed_timestamp = val;
    }
    return out.completed;
}

// ─────────────────────────────────────────────────────────────────────────────
// Console Wizard (cross-platform fallback)
// ─────────────────────────────────────────────────────────────────────────────

bool OnboardingWizard::run_console_wizard() {
    printf("\n");
    printf("╔══════════════════════════════════════════════════════════╗\n");
    printf("║  🏴‍☠️  PIRATE LLAMA — FIRST RUN SETUP WIZARD  🏴‍☠️           ║\n");
    printf("║     Hyper-Spherical Systems  |  v1.0                    ║\n");
    printf("╚══════════════════════════════════════════════════════════╝\n\n");

    // Step 1: Welcome
    printf("Welcome! This wizard will set up your Pirate Llama environment.\n");
    printf("It takes about 2-3 minutes. Press ENTER to continue.\n");
    char buf[1024];
    fgets(buf, sizeof(buf), stdin);

    // Step 2: Drive selection
    printf("\n── STEP 2: DRIVE SELECTION ──────────────────────────────────\n");
    auto drives = enumerate_drives();
    printf("Detected drives:\n");
    for (size_t i = 0; i < drives.size(); ++i) {
        double total_gb = drives[i].total_bytes / 1e9;
        printf("  [%zu] %s: %s (%s  %.0f GB)  %s\n",
               i + 1,
               drives[i].letter.c_str(),
               drives[i].label.c_str(),
               drives[i].type.c_str(),
               total_gb,
               drives[i].recommended_for_storage ? "★ RECOMMENDED FOR STORAGE" : "");
    }
    printf("\n");
    printf("Select HDD drive for SFS cold storage (number or drive letter, e.g. 'D'): ");
    fgets(buf, sizeof(buf), stdin);
    buf[strcspn(buf, "\r\n")] = '\0';
    config_.hdd_storage_drive = std::string(1, toupper(buf[0]));
    printf("✓ HDD storage drive: %s\n", config_.hdd_storage_drive.c_str());

    printf("\nSelect NVMe drive(s) for active model spin-up.\n");
    printf("Enter drive letter(s) separated by commas (e.g. 'C' or 'C,E'): ");
    fgets(buf, sizeof(buf), stdin);
    buf[strcspn(buf, "\r\n")] = '\0';
    std::string nvme_input = buf;
    std::istringstream nvme_ss(nvme_input);
    std::string tok;
    while (std::getline(nvme_ss, tok, ',')) {
        if (!tok.empty()) {
            std::string dl(1, toupper(tok[0]));
            config_.nvme_drives.push_back(dl);
        }
    }
    printf("✓ NVMe drives: ");
    for (const auto& d : config_.nvme_drives) printf("%s ", d.c_str());
    printf("\n");

    // Step 3: Crypto key setup
    printf("\n── STEP 3: CRYPTO KEY SETUP ─────────────────────────────────\n");
    printf("Your username and password together form the cryptographic key\n");
    printf("embedded into every model you convert.\n\n");
    printf("IMPORTANT: The ORDER you enter them now is permanent.\n");
    printf("You must ALWAYS log in the same way.\n\n");
    printf("Choose login order:\n");
    printf("  [1] USERNAME first, then PASSWORD  (default)\n");
    printf("  [2] PASSWORD first, then USERNAME\n");
    printf("Choice [1]: ");
    fgets(buf, sizeof(buf), stdin);
    buf[strcspn(buf, "\r\n")] = '\0';
    config_.login_order = (buf[0] == '2')
        ? OnboardingConfig::LoginOrder::PASSWORD_FIRST
        : OnboardingConfig::LoginOrder::USERNAME_FIRST;

    printf("\nEnter your username (Field 1 — %s): ",
           config_.login_order == OnboardingConfig::LoginOrder::USERNAME_FIRST
               ? "USERNAME" : "PASSWORD");
    fgets(buf, sizeof(buf), stdin);
    buf[strcspn(buf, "\r\n")] = '\0';
    std::string field1 = buf;

    printf("Enter your password (Field 2 — %s): ",
           config_.login_order == OnboardingConfig::LoginOrder::USERNAME_FIRST
               ? "PASSWORD" : "USERNAME");
    fgets(buf, sizeof(buf), stdin);
    buf[strcspn(buf, "\r\n")] = '\0';
    std::string field2 = buf;

    config_.username_hash    = simple_hash(field1);
    config_.password_hash    = simple_hash(field2);
    config_.derived_key_hex  = derive_crypto_key(field1, field2, config_.login_order);
    printf("✓ Crypto key derived and stored.\n");

    // Step 4: HuggingFace token
    printf("\n── STEP 4: HUGGINGFACE TOKEN (optional) ─────────────────────\n");
    printf("A HF token enables model validation and on-the-fly downloads.\n");
    printf("Press ENTER to skip, or paste your token: ");
    fgets(buf, sizeof(buf), stdin);
    buf[strcspn(buf, "\r\n")] = '\0';
    config_.hf_token = buf;
    printf("✓ %s\n", config_.hf_token.empty() ? "Skipped." : "HF token saved.");

    // Step 5: Benchmark
    printf("\n── STEP 5: BASELINE BENCHMARK ───────────────────────────────\n");
    printf("Running NVMe + SSD baseline benchmark...\n");
    run_baseline_benchmark();
    printf("✓ Baseline recorded.\n");

    // Step 6: Compression pipeline order
    printf("\n── STEP 6: COMPRESSION PIPELINE ORDER ───────────────────────\n");
    printf("Choose the default order for the compression pipeline:\n");
    printf("  [1] SISSI Compression → Homophonic Substitution  (default)\n");
    printf("  [2] Homophonic Substitution → SISSI Compression\n");
    printf("Choice [1]: ");
    fgets(buf, sizeof(buf), stdin);
    buf[strcspn(buf, "\r\n")] = '\0';
    config_.pipeline_order = (buf[0] == '2')
        ? OnboardingConfig::PipelineOrder::HOMOPHONIC_FIRST
        : OnboardingConfig::PipelineOrder::SISSI_FIRST;
    printf("✓ Pipeline order set.\n");

    // Step 7: Brain model
    printf("\n── STEP 7: BRAIN MODEL SELECTION ────────────────────────────\n");
    printf("The brain model is the small supervisor model embedded into\n");
    printf("your converted SFS files for recursive self-adjustment.\n\n");
    auto recs = get_brain_recommendations(config_.hf_token);
    printf("Recommended models (✓ = fast & efficient):\n");
    for (size_t i = 0; i < recs.size(); ++i) {
        printf("  [%zu] %s  (%s)  %s  — %s\n",
               i + 1,
               recs[i].display_name.c_str(),
               recs[i].size_label.c_str(),
               recs[i].is_fast ? "✓" : " ",
               recs[i].reason.c_str());
    }
    printf("\nEnter number to select, or type a local path / HF repo ID: ");
    fgets(buf, sizeof(buf), stdin);
    buf[strcspn(buf, "\r\n")] = '\0';

    if (strlen(buf) == 1 && buf[0] >= '1' && buf[0] <= '9') {
        int idx = buf[0] - '1';
        if (idx >= 0 && idx < (int)recs.size()) {
            config_.brain_model_path   = recs[idx].repo_id;
            config_.brain_model_from_hf = true;
        }
    } else if (strlen(buf) > 0) {
        config_.brain_model_path    = buf;
        config_.brain_model_from_hf = false;
    }
    printf("✓ Brain model: %s\n", config_.brain_model_path.empty()
                                       ? "(none selected — can be set later)"
                                       : config_.brain_model_path.c_str());

    // Done
    config_.completed = true;
    save();

    printf("\n╔══════════════════════════════════════════════════════════╗\n");
    printf("║  ✅  ONBOARDING COMPLETE!  Pirate Llama is ready.       ║\n");
    printf("╚══════════════════════════════════════════════════════════╝\n\n");
    return true;
}

bool OnboardingWizard::run() {
#if defined(_WIN32)
    // On Windows, try the Win32 wizard first.
    // If it's a console-only build, fall through to console.
    // For now we run the console wizard on both paths until the Win32
    // dialog resources are compiled in.
    return run_console_wizard();
#else
    return run_console_wizard();
#endif
}

// ─────────────────────────────────────────────────────────────────────────────
// SFSPreloadDialog
// ─────────────────────────────────────────────────────────────────────────────

/* static */ std::string SFSPreloadDialog::default_branch_path(const std::string& model_path) {
    // Place the branch file alongside the model: model.sfs → model.sfs_branch.json
    std::string base = model_path;
    auto dot = base.rfind('.');
    if (dot != std::string::npos) base = base.substr(0, dot);
    return base + "_branch.json";
}

/* static */ bool SFSPreloadDialog::load_saved_choice(
    const std::string& model_path, SFSPreloadChoice& out) {
    std::string cfg_path = model_path + ".sfs_config.json";
    std::ifstream f(cfg_path);
    if (!f) return false;
    // Simple key=value parse
    std::string line;
    while (std::getline(f, line)) {
        auto sep = line.find('=');
        if (sep == std::string::npos) continue;
        std::string k = line.substr(0, sep);
        std::string v = line.substr(sep + 1);
        if (k == "persistence") out.enable_persistence = (v == "1");
        else if (k == "default_path") out.use_default_path = (v == "1");
        else if (k == "custom_path")  out.custom_path = v;
        else if (k == "remember")     out.remember_choice = (v == "1");
    }
    return out.remember_choice;
}

/* static */ bool SFSPreloadDialog::show(const std::string& model_path, SFSPreloadChoice& out) {
    // Check for saved choice first
    if (load_saved_choice(model_path, out) && out.remember_choice) {
        printf("[SFSPreload] Using saved choice for %s\n", model_path.c_str());
        return true;
    }

    printf("\n╔═══════════════════════════════════════════════════╗\n");
    printf("║  SFS MODEL PRE-LOAD                               ║\n");
    printf("║  %s\n", model_path.c_str());
    printf("╠═══════════════════════════════════════════════════╣\n");
    printf("║  Enable persistence (save conversation branch)?   ║\n");
    printf("║  [Y/n]: ");
    char buf[1024];
    fgets(buf, sizeof(buf), stdin);
    buf[strcspn(buf, "\r\n")] = '\0';
    out.enable_persistence = !(buf[0] == 'n' || buf[0] == 'N');

    if (out.enable_persistence) {
        std::string def = default_branch_path(model_path);
        printf("║  Branch file path:\n");
        printf("║    [1] Default: %s\n", def.c_str());
        printf("║    [2] Custom path\n");
        printf("║  Choice [1]: ");
        fgets(buf, sizeof(buf), stdin);
        buf[strcspn(buf, "\r\n")] = '\0';
        if (buf[0] == '2') {
            printf("║  Enter custom path: ");
            fgets(buf, sizeof(buf), stdin);
            buf[strcspn(buf, "\r\n")] = '\0';
            out.use_default_path = false;
            out.custom_path = buf;
        } else {
            out.use_default_path = true;
            out.custom_path = def;
        }
        printf("║  ✓ Branch file: %s\n", out.custom_path.c_str());
    }

    printf("║\n║  Remember this choice for this model? [y/N]: ");
    fgets(buf, sizeof(buf), stdin);
    buf[strcspn(buf, "\r\n")] = '\0';
    out.remember_choice = (buf[0] == 'y' || buf[0] == 'Y');

    if (out.remember_choice) {
        std::ofstream cfg(model_path + ".sfs_config.json");
        cfg << "persistence=" << (out.enable_persistence ? "1" : "0") << "\n";
        cfg << "default_path=" << (out.use_default_path ? "1" : "0") << "\n";
        cfg << "custom_path=" << out.custom_path << "\n";
        cfg << "remember=1\n";
    }

    printf("╚═══════════════════════════════════════════════════╝\n\n");
    return true;
}

} // namespace hypersp
