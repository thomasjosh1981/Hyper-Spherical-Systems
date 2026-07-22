// universal_endpoint.hpp — EXPANDED
//
// Hyper-Spherical Systems — Universal Endpoint (v2.0)
//
// Bi-directional pipeline:
//   OUTBOUND (seal):  SISSI compress → Homophonic scramble → AES-256
//   INBOUND  (unseal): AES-256 → deobfuscate → SISSI decompress
//
// 10x Cloud Token Compression Module (CCTM):
//   Reduces cloud API token usage by ~10x through semantic deduplication,
//   canonical phrase substitution, and rolling differential encoding.
//
// AI Asset Auto-Discovery:
//   Scans local drives + network shares for GGUF, SFS, SFS+, HSCC models.
//   Registers all found assets into a local AssetRegistry for interconnection.
//
// License: MIT

#pragma once
#include "homophonic_cipher.hpp"
#include "context_compressor.hpp"
#include "crypto_engine.hpp"
#include <string>
#include <vector>
#include <functional>
#include <unordered_map>

namespace hypersp {

// ── Pipeline configuration (runtime-swappable order) ─────────────────────────
enum class PipelineStage { SISSI, HOMOPHONIC, AES256 };

struct PipelineConfig {
    // The 3 stages in the order they will be applied (outbound sealing)
    // Default: SISSI → HOMOPHONIC → AES256
    PipelineStage stages[3] = {
        PipelineStage::SISSI,
        PipelineStage::HOMOPHONIC,
        PipelineStage::AES256
    };

    // Cloud Token Compression Module enabled
    bool cctm_enabled{true};

    // Target token compression ratio (1.0 = no compression, 10.0 = 10x reduction)
    float cctm_target_ratio{10.0f};

    // Crypto key (derived from onboarding username+password)
    std::string crypto_key_hex;
};

// ── Discovered AI Asset ───────────────────────────────────────────────────────
struct AIAsset {
    std::string path;            // Full absolute path
    std::string filename;        // Basename
    std::string format;          // "gguf", "sfs", "sfsp", "hscc"
    std::string hf_repo_id;     // HuggingFace origin (if known)
    uint64_t    size_bytes{0};
    bool        has_brain{false};
    bool        sfs_plus{false};
    // Sibling interconnection (models in same folder group)
    std::vector<std::string> sibling_paths;
};

// ── 10x Cloud Token Compression Module ───────────────────────────────────────
class CloudTokenCompressor {
public:
    explicit CloudTokenCompressor(float target_ratio = 10.0f);

    // Compress a prompt before sending to cloud API
    // Returns compressed text + a restore_token needed for decompression
    std::string compress(const std::string& prompt, std::string& restore_token_out);

    // Restore compressed response from cloud back to full form
    std::string decompress(const std::string& compressed_response,
                           const std::string& restore_token);

    // Get actual achieved compression ratio from last operation
    float last_ratio() const { return last_ratio_; }

    // Statistics
    uint64_t total_tokens_saved{0};
    uint64_t total_calls{0};

private:
    float   target_ratio_;
    float   last_ratio_{1.0f};

    // Canonical phrase table (common AI boilerplate → short codes)
    std::unordered_map<std::string, std::string> phrase_table_;
    std::unordered_map<std::string, std::string> reverse_table_;

    void build_phrase_table();
    std::string apply_canonical_substitution(const std::string& text);
    std::string reverse_canonical_substitution(const std::string& text,
                                                const std::string& restore_token);
    std::string differential_encode(const std::string& text);
    std::string differential_decode(const std::string& encoded,
                                    const std::string& restore_token);
};

// ── AI Asset Auto-Discovery & Registry ───────────────────────────────────────
class AssetRegistry {
public:
    AssetRegistry() = default;

    // Scan a root directory for AI model files (recursive, up to max_depth)
    void scan(const std::string& root_path, int max_depth = 3);

    // Scan all fixed drives on this machine
    void scan_all_drives(int max_depth = 3);

    // Register a known HuggingFace repo ID against a local path
    void register_hf_origin(const std::string& local_path,
                             const std::string& hf_repo_id);

    // Get all discovered assets
    const std::vector<AIAsset>& assets() const { return assets_; }

    // Find assets by format
    std::vector<AIAsset> find_by_format(const std::string& fmt) const;

    // Find all SFS/SFS+ models and wire their sibling connections
    void wire_siblings(int scan_depth = 3);

    // Dump registry to JSON string (for the web UI)
    std::string to_json() const;

    // Callback fired whenever a new asset is discovered
    using DiscoveryCallback = std::function<void(const AIAsset&)>;
    void on_discovery(DiscoveryCallback cb) { discovery_cb_ = std::move(cb); }

private:
    std::vector<AIAsset> assets_;
    DiscoveryCallback    discovery_cb_;

    void scan_dir(const std::string& path, int depth, int max_depth);
    bool is_model_file(const std::string& filename, std::string& fmt_out) const;
};

// ── Universal Endpoint (v2) ───────────────────────────────────────────────────
class UniversalEndpoint {
public:
    explicit UniversalEndpoint(const PipelineConfig& cfg = {});
    ~UniversalEndpoint() = default;

    // ── OUTBOUND (seal for cold storage or cloud transmission) ──────────────
    // Applies the 3-stage pipeline in the configured order.
    // If cctm_enabled, also runs 10x cloud token compression BEFORE sealing.
    std::string seal_payload(const std::string& plaintext_memory);

    // ── INBOUND (unseal from cold storage or cloud response) ────────────────
    // Reverses the pipeline in the exact inverse order.
    std::string unseal_payload(const std::string& sealed_blob);

    // ── Cloud Token Compression (standalone, no encryption) ─────────────────
    // Use these when talking to cloud APIs to get ~10x token reduction.
    std::string compress_for_cloud(const std::string& prompt,
                                   std::string& restore_token_out);
    std::string decompress_cloud_response(const std::string& response,
                                          const std::string& restore_token);

    // ── AI Asset Discovery ───────────────────────────────────────────────────
    // Scans configured drives and populates the internal asset registry.
    // Fires the discovery callback for each found model.
    void discover_assets(const std::string& root_path = "", int depth = 3);
    void discover_all_drives(int depth = 3);

    // Register a discovery callback (called for each model found)
    void on_asset_found(AssetRegistry::DiscoveryCallback cb);

    // Get the full asset registry
    const AssetRegistry& registry() const { return registry_; }

    // ── Configuration ─────────────────────────────────────────────────────
    void set_pipeline(const PipelineConfig& cfg);
    const PipelineConfig& pipeline_config() const { return cfg_; }

    // Swap the order of SISSI and Homophonic stages at runtime
    void swap_sissi_homophonic_order();

    // ── Benchmark ──────────────────────────────────────────────────────────
    // Runs auto-benchmark and records baseline for later comparison
    void auto_benchmark_system();

    // Compare current IO speed against the onboarding baseline.
    // Returns a JSON string with delta percentages and a "health" status.
    std::string compare_benchmark(double baseline_nvme_read_gbps,
                                  double baseline_nvme_write_gbps,
                                  double baseline_hdd_read_mbps) const;

    // ── Status ─────────────────────────────────────────────────────────────
    bool is_benchmarked() const { return is_benchmarked_; }
    uint64_t tokens_saved_total() const { return cctm_.total_tokens_saved; }

private:
    PipelineConfig        cfg_;
    HomophonicCipher      obfuscator_;
    ContextCompressor     compressor_;
    CryptoEngine          crypto_;
    CloudTokenCompressor  cctm_;
    AssetRegistry         registry_;
    bool                  is_benchmarked_{false};

    // Apply a single pipeline stage (outbound)
    std::string apply_stage(const std::string& data, PipelineStage stage,
                             std::string& restore_token);

    // Reverse a single pipeline stage (inbound)
    std::string reverse_stage(const std::string& data, PipelineStage stage,
                               const std::string& restore_token);
};

} // namespace hypersp
