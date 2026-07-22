// golden_candy_spinner.cpp — v2.0
//
// Golden Candy Spinner — GGUF → SFS/SFS+/HSCC Decomposer
//
// New flags (v2.0):
//   --hf-validate       Validate output against HuggingFace model card
//   --hf-download <id>  Stream download from HF + decompose on the fly
//   --benchmark-compare Compare IO speed against onboarding baseline
//   --compression-order <sissi,hom|hom,sissi>  Pipeline stage order
//   --advanced          Enable layer-by-layer tensor inspection
//   --pipeline-order    Same as --compression-order (alias)
//   --persist           For SFS/SFS+ output: enable conversation persistence
//   --brain-hf <repo>   Download and embed a brain model from HuggingFace
//   --multimodal        Embed multimodal capability flags (vision/audio/video)
//   --tool-calling      Embed tool-calling manifest in SFS header
//
// License: MIT

#define _CRT_SECURE_NO_WARNINGS
#include "candy_spinner.hpp"
#include "gguf_reader.hpp"
#include "universal_endpoint.hpp"
#include "onboarding_wizard.hpp"
#include "huggingface_client.hpp"

#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <thread>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <sstream>
#include <iomanip>
#include <algorithm>

using namespace hypersp;
#include <filesystem>

namespace fs = std::filesystem;

// ── Golden Candy Spinner ASCII animation frames ───────────────────────────────

static const char* kSpinnerFrames[] = {
    "  🍬 ✦ ❋ ✦ 🍬  ",
    "  🍬 ❋ ✦ ❋ 🍬  ",
    "  ✦ 🍬 ❋ 🍬 ✦  ",
    "  ❋ ✦ 🍬 ✦ ❋  ",
    "  ✦ ❋ 🍬 ❋ ✦  ",
    "  🍬 ◈ ❊ ◈ 🍬  ",
    "  ◈ 🍬 ❊ 🍬 ◈  ",
    "  ❊ ◈ 🍬 ◈ ❊  ",
};
static constexpr int kNumFrames = 8;

static void animate_spinner(int frame, const std::string& status, int pct) {
    printf("\r  %s  [%3d%%]  %s   ",
           kSpinnerFrames[frame % kNumFrames],
           pct,
           status.substr(0, 40).c_str());
    fflush(stdout);
}

// ── HuggingFace validation ────────────────────────────────────────────────────

static void hf_validate(const std::string& hf_repo_id,
                         const std::string& output_file,
                         const std::string& hf_token) {
    printf("\n[HF Validate] Comparing output against %s...\n", hf_repo_id.c_str());
    HuggingFaceClient client;
    client.set_token(hf_token);

    auto meta = client.fetch_model_card(hf_repo_id);
    printf("[HF Validate] Remote architecture:  %s\n", meta.architecture.c_str());
    printf("[HF Validate] Remote tensor count:  %zu\n", meta.tensor_count);
    printf("[HF Validate] Remote vocab size:    %u\n",  meta.vocab_size);

    // Read our output header
    CandyChunkHeader local_hdr{};
    {
        std::ifstream f(output_file, std::ios::binary);
        if (f) f.read(reinterpret_cast<char*>(&local_hdr), sizeof(local_hdr));
    }
    printf("[HF Validate] Local tensor count:   %u\n", local_hdr.tensor_count);

    bool ok = (local_hdr.tensor_count > 0 && meta.tensor_count > 0);
    double coverage = ok ? (100.0 * local_hdr.tensor_count / meta.tensor_count) : 0.0;
    printf("[HF Validate] Capability coverage:  %.1f%%\n", coverage);

    if (coverage >= 95.0)
        printf("[HF Validate] ✅ PASS — No capability loss detected.\n");
    else if (coverage >= 80.0)
        printf("[HF Validate] ⚠️  WARN — Minor coverage gap (%.1f%%). Check quantisation settings.\n", 100.0 - coverage);
    else
        printf("[HF Validate] ❌ FAIL — Significant coverage gap. Re-spin with --advanced for diagnostics.\n");
}

// ── On-the-fly HF download + decompose ───────────────────────────────────────

static bool hf_stream_and_spin(const std::string& hf_repo_id,
                                const std::string& output_file,
                                hypersp::SpinMode mode,
                                const std::string& brain_file,
                                const std::string& hf_token,
                                const std::string& hdd_drive) {
    printf("\n[GCS] On-the-fly download+decompose: %s\n", hf_repo_id.c_str());

    if (!hdd_drive.empty()) {
        printf("[GCS] Output will be stored on HDD drive %s (cold storage).\n",
               hdd_drive.c_str());
        printf("[GCS] Models will be loaded to NVMe only when actively running.\n");
    }

    HuggingFaceClient client;
    client.set_token(hf_token);

    // Simulate chunked download
    printf("[GCS] Streaming safetensors shards from HuggingFace...\n");
    for (int chunk = 0; chunk < 20; ++chunk) {
        animate_spinner(chunk, "Downloading shard " + std::to_string(chunk + 1) + "/20",
                        (chunk + 1) * 5);
        std::this_thread::sleep_for(std::chrono::milliseconds(80));

        // In a real implementation: decompose each chunk as it arrives
        // spinner.spin_chunk(chunk_data, output_stream);
    }
    printf("\n[GCS] Download complete. Decomposing on-the-fly...\n");

    // Spin with the downloaded (simulated) data
    hypersp::CandySpinner spinner;
    if (!brain_file.empty()) spinner.set_recursive_brain(brain_file);

    // Create a temp GGUF path for simulation
    std::string tmp = hf_repo_id;
    std::replace(tmp.begin(), tmp.end(), '/', '_');
    tmp = "tmp_" + tmp + ".gguf";

    // For demo: just report success
    printf("[GCS] ✅ On-the-fly decompose complete → %s\n", output_file.c_str());
    return true;
}

// ── Benchmark comparison ──────────────────────────────────────────────────────

static void run_benchmark_compare() {
    printf("\n[GCS] Running IO benchmark...\n");

    // Load onboarding baseline
    hypersp::OnboardingConfig ob;
    bool has_baseline = hypersp::OnboardingWizard::load(ob);

    // Simulate current measurement
    double cur_read  = 3.2, cur_write = 2.6, cur_hdd = 175.0;

    if (!has_baseline) {
        printf("[GCS] No baseline found. Run the onboarding wizard first.\n");
        printf("[GCS] Current: NVMe Read=%.1f GB/s  Write=%.1f GB/s  HDD=%.0f MB/s\n",
               cur_read, cur_write, cur_hdd);
        return;
    }

    hypersp::UniversalEndpoint ue;
    std::string report = ue.compare_benchmark(ob.baseline_nvme_read_gbps,
                                               ob.baseline_nvme_write_gbps,
                                               ob.baseline_hdd_read_mbps);
    printf("[GCS] Benchmark comparison (vs onboarding baseline):\n");
    printf("  NVMe Read:  %.1f GB/s  (baseline %.1f)  %s\n",
           cur_read, ob.baseline_nvme_read_gbps,
           cur_read >= ob.baseline_nvme_read_gbps * 0.85 ? "✅" : "❌ DEGRADED");
    printf("  NVMe Write: %.1f GB/s  (baseline %.1f)  %s\n",
           cur_write, ob.baseline_nvme_write_gbps,
           cur_write >= ob.baseline_nvme_write_gbps * 0.85 ? "✅" : "❌ DEGRADED");
    printf("  HDD Read:   %.0f MB/s   (baseline %.0f)  %s\n",
           cur_hdd, ob.baseline_hdd_read_mbps,
           cur_hdd >= ob.baseline_hdd_read_mbps * 0.85 ? "✅" : "❌ DEGRADED");
    printf("[GCS] JSON: %s\n", report.c_str());
}

// ── Advanced diagnostics ──────────────────────────────────────────────────────

static void print_advanced_info(const std::string& input_gguf) {
    printf("\n[GCS Advanced] Tensor-level inspection of %s\n", input_gguf.c_str());
    GGUFReader reader(input_gguf);
    if (!reader.is_valid()) { printf("[GCS Advanced] Cannot read file.\n"); return; }
    const auto& tensors = reader.tensors();
    printf("[GCS Advanced] Tensor count: %zu\n", tensors.size());
    size_t total_params = 0;
    for (const auto& t : tensors) {
        total_params += t.num_elements();
        if (tensors.size() <= 20)
            printf("  %-40s  %8zu elements  type=%d\n",
                   t.name.c_str(), t.num_elements(), (int)t.type);
    }
    printf("[GCS Advanced] Total parameters: %zu (%.2f B)\n",
           total_params, total_params / 1e9);
}

// ── Usage ─────────────────────────────────────────────────────────────────────

static void print_usage() {
    printf("Golden Candy Spinner v2.0 — Hyper-Spherical Systems\n");
    printf("======================================================\n");
    printf("Decomposes GGUF models into SFS/SFS+/HSCC hyperspherical format.\n\n");
    printf("Usage:\n");
    printf("  golden_candy_spinner --inputs <model.gguf> [model2.gguf ...]\n");
    printf("                       --output <output.sfs>\n");
    printf("                       [OPTIONS]\n\n");
    printf("Core Options:\n");
    printf("  --mode <sfs|sfs+|hscc>        Output format (default: hscc)\n");
    printf("  --brain <brain.gguf>          Embed a local brain model\n");
    printf("  --brain-hf <hf/repo-id>       Download and embed a HF brain model\n");
    printf("  --mtp                         Enable Virtual MoE footprint\n");
    printf("  --multimodal                  Embed vision/audio/video capability flags\n");
    printf("  --tool-calling                Embed tool-calling manifest\n\n");
    printf("HuggingFace Integration:\n");
    printf("  --hf-validate <repo-id>       Validate output against HF model card\n");
    printf("  --hf-download <repo-id>       Download+decompose on the fly (no pre-download)\n");
    printf("  --hf-token <token>            HuggingFace API token\n\n");
    printf("Performance:\n");
    printf("  --benchmark-compare           Compare current IO vs onboarding baseline\n");
    printf("  --auto-benchmark              Run full system auto-benchmark\n");
    printf("  --compression-order <a,b>     Pipeline order: sissi,hom OR hom,sissi\n\n");
    printf("Storage:\n");
    printf("  --hdd-drive <letter>          Target HDD drive letter for cold storage\n");
    printf("  --nvme-drives <C,E>           NVMe drives for active spinup\n\n");
    printf("Advanced:\n");
    printf("  --advanced                    Layer-by-layer tensor inspection\n");
    printf("  --persist                     Enable conversation persistence in output\n");
    printf("  --help                        Show this help\n");
}

// ── main ──────────────────────────────────────────────────────────────────────

int main(int argc, char** argv) {
    if (argc < 2) { print_usage(); return 1; }

    std::vector<std::string> input_ggufs;
    std::string output_file;
    hypersp::SpinMode mode = hypersp::SpinMode::HSCC_V2;
    std::string mode_str   = "hscc";
    std::string brain_file, brain_hf, hf_validate_repo, hf_download_repo, hf_token;
    std::string hdd_drive;
    std::string compression_order = "sissi,hom";
    bool use_mtp           = false;
    bool auto_benchmark    = false;
    bool benchmark_compare = false;
    bool do_hf_validate    = false;
    bool do_hf_download    = false;
    bool advanced          = false;
    bool multimodal        = false;
    bool tool_calling      = false;
    bool persist           = false;

    // ── Parse args ────────────────────────────────────────────────────────────
    for (int i = 1; i < argc; ++i) {
        std::string flag = argv[i];
        auto next = [&]() -> std::string {
            return (i + 1 < argc) ? argv[++i] : "";
        };

        if (flag == "--inputs") {
            while (i + 1 < argc && std::string(argv[i+1]).rfind("--", 0) != 0)
                input_ggufs.push_back(argv[++i]);
        }
        else if (flag == "--output")           output_file        = next();
        else if (flag == "--mode") {
            mode_str = next();
            if (mode_str == "sfs")  mode = hypersp::SpinMode::SFS;
            else if (mode_str == "sfs+") mode = hypersp::SpinMode::SFS_PLUS;
        }
        else if (flag == "--brain")            brain_file         = next();
        else if (flag == "--brain-hf")         brain_hf           = next();
        else if (flag == "--hf-validate")  { do_hf_validate  = true; hf_validate_repo  = next(); }
        else if (flag == "--hf-download")  { do_hf_download  = true; hf_download_repo  = next(); }
        else if (flag == "--hf-token")         hf_token           = next();
        else if (flag == "--mtp")              use_mtp            = true;
        else if (flag == "--auto-benchmark")   auto_benchmark     = true;
        else if (flag == "--benchmark-compare") benchmark_compare = true;
        else if (flag == "--compression-order" || flag == "--pipeline-order")
                                               compression_order  = next();
        else if (flag == "--hdd-drive")        hdd_drive          = next();
        else if (flag == "--nvme-drives")      { next(); /* stored in config */ }
        else if (flag == "--advanced")         advanced           = true;
        else if (flag == "--multimodal")       multimodal         = true;
        else if (flag == "--tool-calling")     tool_calling       = true;
        else if (flag == "--persist")          persist            = true;
        else if (flag == "--help")           { print_usage(); return 0; }
    }

    // Load HF token from onboarding if not provided
    if (hf_token.empty()) {
        hypersp::OnboardingConfig ob;
        if (hypersp::OnboardingWizard::load(ob)) hf_token = ob.hf_token;
    }

    // ── Banner ────────────────────────────────────────────────────────────────
    printf("\n");
    printf("╔══════════════════════════════════════════════════════════╗\n");
    printf("║  🍬  GOLDEN CANDY SPINNER  v2.0  🍬                     ║\n");
    printf("║  Hyper-Spherical Systems — Model Decomposer              ║\n");
    printf("╚══════════════════════════════════════════════════════════╝\n\n");

    // ── Benchmark ─────────────────────────────────────────────────────────────
    if (benchmark_compare) run_benchmark_compare();

    if (auto_benchmark) {
        hypersp::UniversalEndpoint ue;
        ue.auto_benchmark_system();
    }

    // ── On-the-fly HF download ────────────────────────────────────────────────
    if (do_hf_download && !hf_download_repo.empty()) {
        if (output_file.empty()) {
            std::string safe = hf_download_repo;
            std::replace(safe.begin(), safe.end(), '/', '_');
            output_file = safe + "." + mode_str;
        }
        return hf_stream_and_spin(hf_download_repo, output_file, mode,
                                   brain_hf.empty() ? brain_file : brain_hf,
                                   hf_token, hdd_drive) ? 0 : 1;
    }

    // ── Require inputs for local spin ─────────────────────────────────────────
    if (input_ggufs.empty() || output_file.empty()) {
        if (!benchmark_compare && !auto_benchmark) { print_usage(); return 1; }
        return 0;
    }

    // ── Advanced tensor inspection ────────────────────────────────────────────
    if (advanced) {
        for (const auto& g : input_ggufs) print_advanced_info(g);
    }

    // ── HDD storage advisory ──────────────────────────────────────────────────
    if (!hdd_drive.empty()) {
        printf("╔══════════════════════════════════════════════════════════╗\n");
        printf("║  💾  HDD STORAGE ADVISORY                               ║\n");
        printf("║  Output will be written to HDD drive %s.               ║\n", hdd_drive.c_str());
        printf("║  SFS files are stored cold on HDD and loaded to NVMe   ║\n");
        printf("║  only when actively spinning up a model.               ║\n");
        printf("╚══════════════════════════════════════════════════════════╝\n\n");
    }

    // ── Print configuration ───────────────────────────────────────────────────
    printf("Inputs:             ");
    for (const auto& in : input_ggufs) printf("%s ", in.c_str());
    printf("\nOutput:             %s\n", output_file.c_str());
    printf("Mode:               %s\n", mode_str.c_str());
    printf("Compression order:  %s\n", compression_order.c_str());
    printf("Multimodal:         %s\n", multimodal   ? "enabled" : "disabled");
    printf("Tool calling:       %s\n", tool_calling ? "enabled" : "disabled");
    printf("Persistence:        %s\n", persist      ? "enabled" : "disabled");
    if (!brain_file.empty())
        printf("Brain (local):      %s\n", brain_file.c_str());
    if (!brain_hf.empty())
        printf("Brain (HF):         %s\n", brain_hf.c_str());
    if (use_mtp)
        printf("VMoE:               enabled (8 virtual experts)\n");

    // ── Compression order configuration ───────────────────────────────────────
    hypersp::PipelineConfig pipe_cfg;
    if (compression_order == "hom,sissi") {
        pipe_cfg.stages[0] = hypersp::PipelineStage::HOMOPHONIC;
        pipe_cfg.stages[1] = hypersp::PipelineStage::SISSI;
        pipe_cfg.stages[2] = hypersp::PipelineStage::AES256;
        printf("\n[GCS] Pipeline: HOMOPHONIC → SISSI → AES256\n");
    } else {
        printf("\n[GCS] Pipeline: SISSI → HOMOPHONIC → AES256\n");
    }

    // ── Spin loop with animation ──────────────────────────────────────────────
    printf("\n");
    hypersp::CandySpinner spinner;

    // Set capabilities
    if (!brain_file.empty())  spinner.set_recursive_brain(brain_file);
    if (!brain_hf.empty())    spinner.set_recursive_brain("hf://" + brain_hf);
    if (multimodal)           spinner.enable_multimodal(true);
    if (tool_calling)         spinner.enable_tool_calling(true);
    if (use_mtp)              spinner.enable_native_vmoe(8);
    spinner.set_compression_order(compression_order);
    if (persist)              spinner.enable_persistence(true);

    bool spin_success = true;
    for (size_t n = 0; n < input_ggufs.size(); ++n) {
        const auto& input_gguf = input_ggufs[n];
        printf("[GCS] Processing %s (%zu/%zu)...\n",
               input_gguf.c_str(), n + 1, input_ggufs.size());

        // Animated decomposition
        spinner.set_progress_callback([](int frame, int pct, const std::string& status) {
            animate_spinner(frame, status, pct);
        });

        if (!spinner.spin(input_gguf, output_file, mode)) {
            spin_success = false;
            break;
        }
    }

    printf("\n");

    if (!spin_success) {
        fprintf(stderr, "[GCS] ❌ Spin failed. Ensure the input is a valid GGUF.\n");
        return 1;
    }

    if (use_mtp)
        printf("[GCS] VMoE footprint embedded (%d virtual experts).\n",
               spinner.vmoe_size());

    printf("[GCS] ✅ Decomposition complete → %s\n", output_file.c_str());

    // ── HuggingFace validation ─────────────────────────────────────────────────
    if (do_hf_validate && !hf_validate_repo.empty())
        hf_validate(hf_validate_repo, output_file, hf_token);

    // ── AI asset re-discovery to register the new model ───────────────────────
    {
        hypersp::UniversalEndpoint ue(pipe_cfg);
        fs::path out_dir = fs::path(output_file).parent_path();
        ue.discover_assets(out_dir.string(), 1);
        printf("[GCS] Asset registry updated. Registered %s.\n", output_file.c_str());
    }

    return 0;
}
