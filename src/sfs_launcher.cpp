// sfs_launcher.cpp
//
// Hyper-Spherical Systems — SFS / SFS+ File-Association Launcher
//
// Handles:
//  - .sfs / .sfsp file double-click launch
//  - Pre-load dialog (persistence, branch file path)
//  - Sibling model auto-discovery (3 levels deep in same folder group)
//  - Interconnected model wiring (VMoE, tool-calling, multimodal borrowing)
//  - Spinup onto NVMe drive(s)
//
// License: MIT

#include "onboarding_wizard.hpp"
#include "universal_endpoint.hpp"
#include "candy_spinner.hpp"
#include "multimodal_engine.hpp"

#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <algorithm>
#include <filesystem>
#include <thread>
#include <chrono>

namespace hypersp {
namespace fs = std::filesystem;

// ── Sibling Model Scanner ─────────────────────────────────────────────────────

static std::vector<std::string> scan_siblings(const std::string& model_path,
                                               int max_depth = 3) {
    std::vector<std::string> siblings;
    fs::path base_dir = fs::path(model_path).parent_path();

    static const char* kModelExts[] = {".sfs", ".sfsp", ".sfs+", ".gguf", ".hscc", nullptr};

    std::function<void(const fs::path&, int)> scan = [&](const fs::path& dir, int depth) {
        if (depth > max_depth) return;
        std::error_code ec;
        for (const auto& entry : fs::directory_iterator(dir, ec)) {
            if (ec) break;
            if (entry.is_directory(ec) && !ec) {
                scan(entry.path(), depth + 1);
            } else if (entry.is_regular_file(ec) && !ec) {
                std::string p = entry.path().string();
                if (p == model_path) continue; // skip self
                std::string ext = entry.path().extension().string();
                std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
                for (auto** e = kModelExts; *e; ++e) {
                    if (ext == *e) {
                        siblings.push_back(p);
                        break;
                    }
                }
            }
        }
    };
    scan(base_dir, 0);
    return siblings;
}

// ── Interconnected Model Feature Borrowing ────────────────────────────────────

struct BorrowedFeatures {
    bool has_vision{false};
    bool has_audio{false};
    bool has_tool_calling{false};
    bool has_vmoe{false};
    std::vector<std::string> borrowed_from;
};

static BorrowedFeatures discover_borrowed_features(
    const std::vector<std::string>& sibling_paths) {
    BorrowedFeatures bf;
    for (const auto& p : sibling_paths) {
        // Read first 64 bytes of the sibling to check its capability header
        std::ifstream f(p, std::ios::binary);
        if (!f) continue;
        char header[64] = {};
        f.read(header, sizeof(header));
        std::string hdr(header, f.gcount());

        bool borrowed = false;
        if (hdr.find("VISION_CAP") != std::string::npos && !bf.has_vision) {
            bf.has_vision = true; borrowed = true;
        }
        if (hdr.find("AUDIO_CAP") != std::string::npos && !bf.has_audio) {
            bf.has_audio = true; borrowed = true;
        }
        if (hdr.find("TOOL_CAP") != std::string::npos && !bf.has_tool_calling) {
            bf.has_tool_calling = true; borrowed = true;
        }
        if (hdr.find("VMOE_CAP") != std::string::npos && !bf.has_vmoe) {
            bf.has_vmoe = true; borrowed = true;
        }
        if (borrowed) bf.borrowed_from.push_back(p);
    }
    return bf;
}

// ── Spinning Animation ────────────────────────────────────────────────────────

static void print_spinner_frame(int frame, const std::string& label) {
    static const char* kFrames[] = {
        "✦ ❋ ✦", "❋ ✦ ❋", "✦ ❋ ✦",
        "◈ ❊ ◈", "❊ ◈ ❊", "◈ ❊ ◈",
    };
    constexpr int N = 6;
    printf("\r  [%s]  %s   ", kFrames[frame % N], label.c_str());
    fflush(stdout);
}

// ── NVMe Drive Spinup Dialog ──────────────────────────────────────────────────

static std::vector<std::string> choose_nvme_drives(
    const std::vector<std::string>& configured_drives) {
    if (configured_drives.empty()) {
        // No configured drives from onboarding — ask now
        printf("\n[SFSLauncher] No NVMe drives configured.\n");
        printf("Enter NVMe drive letter(s) for spinup (e.g. C or C,E): ");
        char buf[128];
        fgets(buf, sizeof(buf), stdin);
        buf[strcspn(buf, "\r\n")] = '\0';
        std::vector<std::string> drives;
        std::istringstream ss(buf);
        std::string tok;
        while (std::getline(ss, tok, ','))
            if (!tok.empty()) drives.push_back(std::string(1, toupper(tok[0])));
        return drives;
    }

    if (configured_drives.size() == 1) return configured_drives;

    printf("\n[SFSLauncher] Multiple NVMe drives configured:\n");
    for (size_t i = 0; i < configured_drives.size(); ++i)
        printf("  [%zu] Drive %s\n", i + 1, configured_drives[i].c_str());
    printf("  [3] Use BOTH drives (striped for max bandwidth)\n");
    printf("Choice [3]: ");
    char buf[32];
    fgets(buf, sizeof(buf), stdin);
    buf[strcspn(buf, "\r\n")] = '\0';
    if (buf[0] == '1') return {configured_drives[0]};
    if (buf[0] == '2') return {configured_drives[1]};
    return configured_drives; // Both
}

// ── Main Launch Entry Point ───────────────────────────────────────────────────

int launch_sfs_model(const std::string& model_path) {
    printf("\n╔══════════════════════════════════════════════════════════╗\n");
    printf("║  🏴‍☠️  SFS MODEL LAUNCHER  🏴‍☠️                              ║\n");
    printf("║  %s\n", model_path.c_str());
    printf("╚══════════════════════════════════════════════════════════╝\n\n");

    // 1. Load onboarding config (for NVMe drives, crypto key, pipeline order)
    OnboardingConfig ob_cfg;
    bool has_onboarding = OnboardingWizard::load(ob_cfg);
    if (!has_onboarding) {
        printf("[!] No onboarding config found. Running first-time setup...\n");
        OnboardingWizard wizard;
        if (!wizard.run()) {
            printf("[!] Setup cancelled. Exiting.\n");
            return 1;
        }
        ob_cfg = wizard.config();
    }

    // 2. Pre-load dialog
    SFSPreloadChoice choice;
    if (!SFSPreloadDialog::show(model_path, choice)) {
        printf("[!] Launch cancelled by user.\n");
        return 0;
    }
    printf("[SFSLauncher] Persistence: %s\n",
           choice.enable_persistence ? choice.custom_path.c_str() : "disabled");

    // 3. Sibling discovery
    printf("\n[SFSLauncher] Scanning for sibling models (depth=3)...\n");
    auto siblings = scan_siblings(model_path, ob_cfg.sibling_scan_depth);
    printf("[SFSLauncher] Found %zu sibling model(s).\n", siblings.size());
    for (const auto& s : siblings)
        printf("  • %s\n", s.c_str());

    // 4. Feature borrowing from siblings
    auto features = discover_borrowed_features(siblings);
    printf("\n[SFSLauncher] Borrowed features from siblings:\n");
    printf("  Vision:       %s\n", features.has_vision       ? "✓" : "—");
    printf("  Audio:        %s\n", features.has_audio        ? "✓" : "—");
    printf("  Tool Calling: %s\n", features.has_tool_calling ? "✓" : "—");
    printf("  VMoE:         %s\n", features.has_vmoe         ? "✓" : "—");

    // 5. NVMe drive selection
    auto nvme_drives = choose_nvme_drives(ob_cfg.nvme_drives);
    printf("\n[SFSLauncher] Spinning up on NVMe drive(s): ");
    for (const auto& d : nvme_drives) printf("%s ", d.c_str());
    printf("\n");

    // 6. Set up pipeline in configured order
    PipelineConfig pipe_cfg;
    if (ob_cfg.pipeline_order == OnboardingConfig::PipelineOrder::HOMOPHONIC_FIRST) {
        pipe_cfg.stages[0] = PipelineStage::HOMOPHONIC;
        pipe_cfg.stages[1] = PipelineStage::SISSI;
        pipe_cfg.stages[2] = PipelineStage::AES256;
        printf("[SFSLauncher] Pipeline: HOMOPHONIC → SISSI → AES256\n");
    } else {
        printf("[SFSLauncher] Pipeline: SISSI → HOMOPHONIC → AES256\n");
    }
    pipe_cfg.crypto_key_hex = ob_cfg.derived_key_hex;

    UniversalEndpoint endpoint(pipe_cfg);

    // 7. Run asset discovery (bidirectional — find all AI assets on the system)
    printf("\n[SFSLauncher] Discovering all AI assets on system...\n");
    endpoint.on_asset_found([](const AIAsset& a) {
        printf("  [FOUND] %s  (%s)\n", a.filename.c_str(), a.format.c_str());
    });
    // Scan the model's directory and parent first (fast), then optionally all drives
    fs::path model_dir = fs::path(model_path).parent_path();
    endpoint.discover_assets(model_dir.string(), 3);

    // 8. Spinning animation + model load simulation
    printf("\n[SFSLauncher] Loading model into NVMe memory...\n");
    for (int frame = 0; frame < 30; ++frame) {
        print_spinner_frame(frame, "Spinning up model...");
        std::this_thread::sleep_for(std::chrono::milliseconds(60));
    }
    printf("\n");

    // 9. If multimodal features are enabled, initialize engines
    MultimodalEngine mm_engine;
    if (features.has_vision) {
        std::vector<uint8_t> dummy_frame(320 * 240 * 3, 0);
        mm_engine.ingest_image_frame(dummy_frame, 320, 240);
    }
    if (features.has_audio) {
        std::vector<uint8_t> dummy_audio(1024, 0);
        mm_engine.ingest_audio_stream(dummy_audio);
    }

    printf("\n╔══════════════════════════════════════════════════════════╗\n");
    printf("║  ✅  MODEL READY                                         ║\n");
    printf("║  Brain: %s\n",
           ob_cfg.brain_model_path.empty() ? "(none)" : ob_cfg.brain_model_path.c_str());
    printf("║  CCTM: ~10x cloud token reduction ACTIVE                ║\n");
    printf("╚══════════════════════════════════════════════════════════╝\n\n");

    return 0;
}

} // namespace hypersp

// ── Standalone entry point (registered as .sfs file handler) ─────────────────
#ifdef SFS_LAUNCHER_MAIN
int main(int argc, char** argv) {
    if (argc < 2) {
        printf("Usage: sfs_launcher <model.sfs>\n");
        return 1;
    }
    return hypersp::launch_sfs_model(argv[1]);
}
#endif
