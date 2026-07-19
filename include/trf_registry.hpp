// trf_registry.hpp — Temporal-Recency Frequency (TRF) registry + learner.
//
// Per Spec V3.1 §2 / §3:
//
//   - Per-model file-bound registry: [model_filename].hypersphere_profiles.json
//   - Profile data files: [model_filename]_[profile_name].trf
//   - Max 5 active profile slots per model
//   - TRFEntry tracks: layer_index, recency_score, access_count, last_token_id
//   - Async writes during low-I/O intervals (generation pauses)
//   - Pruning: entries with recency_score < 0.15 over trailing 5000-token
//     window are omitted from disk writes
//   - File footprint cap: 5 MB

#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include <unordered_map>
#include <mutex>
#include <atomic>
#include <chrono>

namespace Hyperspherical::TRF {

constexpr size_t kMaxProfilesPerModel = 5;
constexpr size_t kMaxFootprintBytes   = 5 * 1024 * 1024;   // 5 MB cap
constexpr uint64_t kPruneTokenWindow  = 5000;
constexpr double   kPruneScoreFloor    = 0.15;
constexpr uint64_t kFlushCycleTokens  = 500;

// ── Single TRF row ──────────────────────────────────────────────────
struct TRFEntry {
    uint16_t layer_index    = 0;
    float    recency_score   = 0.0f;
    uint64_t access_count    = 0;
    uint64_t last_token_id   = 0;
};

// ── Profile metadata (registry JSON) ─────────────────────────────────
struct ProfileMeta {
    std::string token_name;             // "Crypto_Scalping"
    std::string profile_name;           // "main" / "alt1"
    double      file_megabytes = 0.0;
    uint64_t    context_hours  = 0;
    std::string model_filename;         // "qwen-30b.gguf"
    std::chrono::system_clock::time_point created_at;
    std::chrono::system_clock::time_point last_touched;
};

// ── Per-engine TRF learner ─────────────────────────────────────────
class TRFLearner {
public:
    explicit TRFLearner(const std::string& model_filename);
    ~TRFLearner();

    // Observe a layer access at a token id. Updates the entry's recency
    // score (1.0 immediately after access, decays over time) and access_count.
    void observe(uint16_t layer_index, uint64_t token_id) noexcept;

    // Run the periodic flush: write active entries to the .trf file and the
    // registry to the .json file. If `force` is true, flushes synchronously.
    // If false, flushes asynchronously (deferred to next call).
    void maybe_flush(uint64_t current_token_id, bool force = false) noexcept;

    // Get a snapshot of current entries (for the GUI).
    std::vector<TRFEntry> snapshot() const;

    // File paths derived from the model filename.
    std::string registry_path() const { return registry_path_; }
    std::string profile_path(const std::string& profile_name) const;

    // Profile management (up to 5 slots)
    bool add_profile(const ProfileMeta& meta) noexcept;       // returns false if at cap
    bool remove_profile(const std::string& profile_name) noexcept;
    std::vector<ProfileMeta> list_profiles() const;

    // Manual prune (for tests / admin)
    size_t prune_low_recency() noexcept;

    // Telemetry for GUI
    struct Stats {
        size_t   total_entries    = 0;
        size_t   total_profiles   = 0;
        uint64_t total_observations = 0;
        uint64_t last_flush_token = 0;
        double   file_megabytes   = 0.0;
        uint64_t context_hours    = 0;
    };
    Stats stats() const;

private:
    std::string model_filename_;
    std::string registry_path_;

    mutable std::mutex mtx_;
    std::unordered_map<uint16_t, TRFEntry> entries_;
    std::unordered_map<std::string, ProfileMeta> profiles_;

    // Async flush state
    std::atomic<uint64_t> last_flush_token_{0};
    std::atomic<uint64_t> total_observations_{0};
    mutable std::mutex flush_mtx_;

    // Helper: compute recency decay
    static float decay_recency(float current, uint64_t tokens_since) noexcept;

    // Helper: write registry JSON + .trf files atomically
    void write_registry_locked() const;
    void write_profile_locked(const std::string& profile_name) const;
};

// ── Helpers exposed for the GUI ──────────────────────────────────────
std::string derive_registry_path(const std::string& model_filename);
std::string derive_profile_path(const std::string& model_filename,
                                  const std::string& profile_name);

}  // namespace Hyperspherical::TRF
