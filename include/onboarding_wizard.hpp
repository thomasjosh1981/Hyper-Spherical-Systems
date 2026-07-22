// onboarding_wizard.hpp
//
// Hyper-Spherical Systems — First-Run Onboarding Wizard
//
// Multi-step wizard that:
//   1. Welcomes the user
//   2. Picks HDD (cold storage) and NVMe (active) drives
//   3. Sets up crypto key order (username-first or password-first)
//   4. Collects HuggingFace API token (optional)
//   5. Runs baseline NVMe/SSD benchmark
//   6. Picks brain model with quick/efficient HF recommendations
//
// The login order chosen in step 3 is permanently embedded into the
// local pirate_keystore.enc file and MUST be used on every subsequent login.
//
// License: MIT

#pragma once
#include <string>
#include <vector>
#include <functional>

#if defined(_WIN32)
#  define WIN32_LEAN_AND_MEAN
#  define NOMINMAX
#  include <windows.h>
#endif

namespace hypersp {

// ── Drive Descriptor ──────────────────────────────────────────────────────────
struct DriveInfo {
    std::string letter;          // e.g. "C", "D", "E"
    std::string label;           // Volume label
    std::string type;            // "NVMe", "SSD", "HDD", "Unknown"
    uint64_t    total_bytes{0};
    uint64_t    free_bytes{0};
    bool        recommended_for_storage{false}; // True if HDD >= 4 TB
};

// ── Onboarding Configuration (persisted after completion) ─────────────────────
struct OnboardingConfig {
    // Step 2 — Storage
    std::string hdd_storage_drive;          // Drive letter for SFS cold storage
    std::vector<std::string> nvme_drives;   // 1 or 2 NVMe drives for spin-up

    // Step 3 — Crypto key order
    enum class LoginOrder { USERNAME_FIRST, PASSWORD_FIRST };
    LoginOrder  login_order{LoginOrder::USERNAME_FIRST};
    std::string username_hash;      // bcrypt/argon2 hash — NOT stored in plaintext
    std::string password_hash;
    std::string derived_key_hex;    // 256-bit key derived from both, in chosen order

    // Step 4 — HuggingFace
    std::string hf_token;           // HF API token (optional)

    // Step 5 — Benchmark baseline (stored for later comparison)
    double baseline_nvme_read_gbps{0.0};
    double baseline_nvme_write_gbps{0.0};
    double baseline_hdd_read_mbps{0.0};

    // Step 6 — Brain model
    std::string brain_model_path;   // Local path or HF repo id
    bool        brain_model_from_hf{false};

    // Meta
    bool        completed{false};
    std::string completed_timestamp;

    // Compression pipeline order
    enum class PipelineOrder { SISSI_FIRST, HOMOPHONIC_FIRST };
    PipelineOrder pipeline_order{PipelineOrder::SISSI_FIRST};

    // Sibling scan depth
    int sibling_scan_depth{3};
};

// ── HF Model Recommendation ───────────────────────────────────────────────────
struct HFModelRec {
    std::string repo_id;
    std::string display_name;
    std::string size_label;         // e.g. "3B", "7B"
    std::string reason;             // Why we recommend it
    bool        is_fast{true};
};

// ── Onboarding Wizard ─────────────────────────────────────────────────────────
class OnboardingWizard {
public:
    OnboardingWizard();
    ~OnboardingWizard() = default;

    // Returns true if onboarding has already been completed
    static bool is_completed();

    // Run the full wizard. Blocks until the user finishes or cancels.
    // Returns true if the user completed all steps.
    bool run();

    // Access the result after run() returns true
    const OnboardingConfig& config() const { return config_; }

    // Save config to pirate_keystore.enc
    bool save() const;

    // Load previously saved config
    static bool load(OnboardingConfig& out);

    // Enumerate drives on this system
    static std::vector<DriveInfo> enumerate_drives();

    // Fetch recommended brain models from HuggingFace (or return built-in list if offline)
    static std::vector<HFModelRec> get_brain_recommendations(const std::string& hf_token);

    // Run the baseline benchmark and fill config_ fields
    bool run_baseline_benchmark();

    // Derive the crypto key from the username+password in chosen order
    static std::string derive_crypto_key(const std::string& a, const std::string& b,
                                         OnboardingConfig::LoginOrder order);

    // Validate login against stored hashes — must use same order as onboarding
    static bool validate_login(const std::string& field1, const std::string& field2,
                                const OnboardingConfig& cfg);

private:
#if defined(_WIN32)
    // Win32 wizard pages
    bool show_step_welcome(HWND parent);
    bool show_step_drives(HWND parent);
    bool show_step_crypto(HWND parent);
    bool show_step_hf_token(HWND parent);
    bool show_step_benchmark(HWND parent);
    bool show_step_brain(HWND parent);
    bool show_step_done(HWND parent);
#endif

    // Console/TTY fallback for non-Windows
    bool run_console_wizard();

    OnboardingConfig config_;
    static constexpr const char* KEYSTORE_FILE = "pirate_keystore.enc";
};

// ── SFS Pre-Load Dialog ───────────────────────────────────────────────────────
struct SFSPreloadChoice {
    bool        enable_persistence{true};
    bool        use_default_path{true};
    std::string custom_path;            // Only used if use_default_path == false
    bool        remember_choice{false};
};

class SFSPreloadDialog {
public:
    // Show the pre-load dialog for an SFS/SFS+ model
    // Returns false if the user cancelled
    static bool show(const std::string& model_path, SFSPreloadChoice& out);

    // Load previously saved choice for this model (if remember_choice was set)
    static bool load_saved_choice(const std::string& model_path, SFSPreloadChoice& out);

    // Compute the default persistence branch file path
    static std::string default_branch_path(const std::string& model_path);
};

} // namespace hypersp
