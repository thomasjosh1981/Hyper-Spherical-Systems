#pragma once
#include "types.hpp"
#include "config.hpp"
#include <cstdint>
#include <vector>
#include <deque>
#include <string_view>
#include <unordered_map>
#include <span>

namespace hypersp {

/* PatternPredictor: zero-overhead Markov-chain weight layer predictor */
class PatternPredictor {
public:
    PatternPredictor(const Config& cfg = {}) : config_(cfg) {}

    struct Prediction {
        std::vector<uint32_t> layer_ids;   // predicted layers to preload
        float                 confidence     = 0.0f;  // prediction confidence %
    };

    /** Observe that layer_id was activated — updates Markov transition table */
    void observe_layer(uint32_t layer_id) noexcept;

    /** Get predictions for upcoming layers based on recent observation history */
    Prediction predict_next(std::size_t num = 4u) const noexcept;

    /** Total number of observations recorded */
    size_t total_observations() const noexcept;

    /** Adaptive configuration (call setters at runtime to tweak) */
    void set_window_size(std::size_t w) noexcept;
    void set_confidence_min(float c) noexcept;
    void set_decay_rate(float d) noexcept;       // 0.0=no decay, 1.0=forget each step
    void set_ngram_order(std::size_t n) noexcept;  // 1..3 typical

    /** Statistics for the GUI dashboard */
    struct Stats {
        std::size_t  window_size        = 0;
        std::size_t  observations       = 0;
        std::size_t  unique_layers      = 0;
        std::size_t  transition_count   = 0;
        float        avg_confidence      = 0.f;
        std::size_t  prediction_hits    = 0;   // incremented by predict_next caller
        std::size_t  prediction_misses  = 0;
    };
    Stats stats() const noexcept;

private:
    Config              config_;
    std::deque<uint32_t> recent_layers_;     // recent active layers for Markov windows
    std::unordered_map<uint32_t,      // transition_table_: layer_id -> [(target_layer, count)]
        std::vector<std::pair<uint32_t, int>>> transition_table_;
    size_t observation_count_ = 0ull;

    // Adaptive tuning
    std::size_t adaptive_window_   = 16;
    float       adaptive_conf_min_ = 0.75f;
    float       decay_rate_         = 0.05f;     // each step, multiply old weight by (1 - decay_rate)
    std::size_t ngram_order_        = 1;         // 1-gram Markov (extend to 2/3 for tighter predictions)
    float       running_avg_conf_   = 0.f;
    std::size_t pred_hits_          = 0;
    std::size_t pred_misses_        = 0;

    // Helpers
    void decay_transition(uint32_t from, uint32_t to, int delta) noexcept;
    void update_window_adaptively() noexcept;
};

/* WeightStreamer: manages weight shards across VRAM/RAM/NVMe tiers */
class WeightStreamer {
public:
   WeightStreamer(const Config& cfg, size_t phys_vram_bytes);
    ~WeightStreamer() = default;

    /** Preload predicted weight layers into their target tier(s) */
    ErrorCode preload_weight_shards(std::span<uint32_t> layer_ids, bool prefer_vram = true) noexcept;

    size_t vram_available()   const noexcept;
    float  vram_usage_pct()   const noexcept;

private:
    Config      config_;
    size_t      vram_budget_ = 0ull;
    size_t      vram_current_ = 0ul;  
};

/* SFS+ Multi-Token Predictor (MTP) Draft Engine */
class DraftTokenEngine {
public:
    DraftTokenEngine();
    ~DraftTokenEngine() = default;

    // Set hardware routing switch for the draft predictions
    enum class Route {
        VRAM,
        SYSTEM_RAM,
        DIRECT_NVME
    };
    void set_hardware_route(Route r) noexcept;

    // Generate up to N draft predictions for the SFS+ model
    std::vector<std::string> predict_draft_tokens(size_t max_tokens = 4) noexcept;

private:
    Route current_route_ = Route::SYSTEM_RAM;
};

} // namespace hypersp
