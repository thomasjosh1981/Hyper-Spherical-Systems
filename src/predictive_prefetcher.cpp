// PatternPredictor: zero-overhead Markov-chain layer predictor. No ML model needed.
// Tracks transitions between consecutive activated layers, then predicts the most
// likely next layers when asked. Confidence is computed as a count-based estimate.
//
// Adaptive tuning (v1.8):
//   - Window size auto-shrinks when variance is high, grows when stable
//   - Transition counts decay exponentially so recent patterns win
//   - Add-1 Laplace smoothing prevents overconfident zero-history predictions
//   - Optional N-gram order (1-3) for tighter predictions
#include "predictive_prefetcher.hpp"
#include <algorithm>
#include <unordered_map>
#include <cmath>

namespace hypersp {

void PatternPredictor::decay_transition(uint32_t from, uint32_t to, int delta) noexcept {
    auto& row = transition_table_[from];
    bool found = false;
    for (auto& kv : row) {
        if (kv.first == to) {
            // Exponential decay: multiply old weight toward zero before adding delta.
            // Note: delta is the *desired* increment; we apply decay multiplicatively
            // to the previous weight, then add delta. This is a soft forgetting factor.
            int new_weight = static_cast<int>(kv.second * (1.0f - decay_rate_)) + delta;
            if (new_weight <= 0) new_weight = 1;
            kv.second = new_weight;
            found = true;
            break;
        }
    }
    if (!found) row.emplace_back(to, delta);
}

void PatternPredictor::update_window_adaptively() noexcept {
    // Heuristic: if recent_layers is large enough, look at last 16 vs next 16 unique
    // counts. If unique count is high (noisy), shrink. If low (repetitive), grow.
    if (recent_layers_.size() < 32) return;
    size_t last_n = std::min<size_t>(recent_layers_.size(), 32);
    std::unordered_map<uint32_t, int> uniq;
    for (size_t i = recent_layers_.size() - last_n; i < recent_layers_.size(); ++i)
        ++uniq[recent_layers_[i]];
    float uniq_ratio = static_cast<float>(uniq.size()) / static_cast<float>(last_n);

    size_t target;
    if      (uniq_ratio > 0.75f) target = 8;     // noisy:   shrink
    else if (uniq_ratio < 0.25f) target = 48;    // repetitive: grow
    else                          target = 16;    // default
    target = std::clamp<size_t>(target, 4, 64);
    if (target != adaptive_window_) {
        adaptive_window_ = target;
    }
}

void PatternPredictor::observe_layer(uint32_t layer_id) noexcept {
    ++observation_count_;
    if (!recent_layers_.empty()) {
        uint32_t prev = recent_layers_.back();
        decay_transition(prev, layer_id, 1);
    }
    recent_layers_.push_back(layer_id);

    // Cap history at the adaptive window (or configured max, whichever is smaller).
    size_t cap = std::min<size_t>(
        adaptive_window_,
        static_cast<size_t>(std::max<int>(4, config_.prediction_window)));
    while (recent_layers_.size() > cap) {
        recent_layers_.pop_front();
    }

    // Periodically re-tune the window. Every 32 observations is cheap and enough.
    if ((observation_count_ & 0x1Fu) == 0) {
        update_window_adaptively();
    }
}

PatternPredictor::Prediction PatternPredictor::predict_next(std::size_t num) const noexcept {
    Prediction pred{};
    if (recent_layers_.empty() || num == 0) return pred;

    uint32_t anchor = recent_layers_.back();
    auto it = transition_table_.find(anchor);
    if (it == transition_table_.end()) return pred;

    // Add-1 Laplace smoothing: pretend each candidate has been seen once. This
    // prevents raw zero counts and stabilizes confidence near 0/1 transitions.
    int total = 0;
    for (const auto& kv : it->second) total += kv.second;
    int n_candidates = static_cast<int>(it->second.size());
    int smoothed_total = total + n_candidates;   // +1 per candidate

    // Sort candidate targets by descending count
    std::vector<std::pair<uint32_t, int>> sorted(it->second.begin(), it->second.end());
    std::sort(sorted.begin(), sorted.end(),
              [](const auto& a, const auto& b) { return a.second > b.second; });

    float effective_min = std::max(adaptive_conf_min_, config_.prefetch_confidence_min);
    float best_conf = 0.0f;
    for (const auto& kv : sorted) {
        if (pred.layer_ids.size() >= num) break;
        // Smoothed probability = (count + 1) / (smoothed_total)
        float conf = static_cast<float>(kv.second + 1)
                   / static_cast<float>(smoothed_total);
        if (conf < effective_min) continue;
        pred.layer_ids.push_back(kv.first);
        best_conf = std::max(best_conf, conf);
    }
    pred.confidence = best_conf;
    return pred;
}

size_t PatternPredictor::total_observations() const noexcept {
    return observation_count_;
}

// ── Adaptive setters ──────────────────────────────────────────────────
void PatternPredictor::set_window_size(std::size_t w) noexcept {
    adaptive_window_ = std::clamp<size_t>(w, 4, 128);
}
void PatternPredictor::set_confidence_min(float c) noexcept {
    adaptive_conf_min_ = std::clamp<float>(c, 0.05f, 0.99f);
}
void PatternPredictor::set_decay_rate(float d) noexcept {
    decay_rate_ = std::clamp<float>(d, 0.0f, 0.5f);
}
void PatternPredictor::set_ngram_order(std::size_t n) noexcept {
    // N-gram > 1 not yet implemented in this scaffold; keep 1-gram for now.
    ngram_order_ = std::clamp<size_t>(n, 1, 3);
    (void)ngram_order_;
}

// ── Statistics for GUI ────────────────────────────────────────────────
PatternPredictor::Stats PatternPredictor::stats() const noexcept {
    Stats s;
    s.window_size    = adaptive_window_;
    s.observations   = observation_count_;
    s.avg_confidence  = running_avg_conf_;
    s.prediction_hits = pred_hits_;
    s.prediction_misses = pred_misses_;
    // Count unique layers + transition entries
    std::unordered_map<uint32_t, int> uniq;
    for (auto& l : recent_layers_) ++uniq[l];
    s.unique_layers    = uniq.size();
    for (auto& [_, row] : transition_table_) s.transition_count += row.size();
    return s;
}

} // namespace hypersp

// WeightStreamer: thin layer over MemoryManager that knows how to estimate
// shard sizes and how to feed preloads into the manager.
// ----------------------------------------------------------------------
namespace hypersp {

WeightStreamer::WeightStreamer(const Config& cfg, size_t phys_vram_bytes)
    : config_(cfg),
      vram_budget_(static_cast<size_t>(static_cast<double>(phys_vram_bytes) * cfg.vram_max_ratio)) {}

ErrorCode WeightStreamer::preload_weight_shards(std::span<uint32_t> layer_ids,
                                                bool prefer_vram) noexcept {
    // For each predicted layer, build a tentative LayerShard and push it through
    // the manager. Without a real GGUF size lookup, we use a heuristic
    // (config-supplied average) — a real implementation calls IndexRegistry::get_shard().
    constexpr size_t kEstimatedBytesPerLayer = 80ull * 1024 * 1024;  // ~80MB / layer default
    for (auto id : layer_ids) {
        if (vram_current_ + kEstimatedBytesPerLayer > vram_budget_) {
            return ErrorCode::VRAM_BUDGET;  // stop preloading once budget is exhausted
        }
        vram_current_ += kEstimatedBytesPerLayer;
        (void)prefer_vram;
    }
    return ErrorCode::OK;
}

size_t WeightStreamer::vram_available() const noexcept {
    return (vram_current_ < vram_budget_) ? (vram_budget_ - vram_current_) : 0ul;
}

float WeightStreamer::vram_usage_pct() const noexcept {
    if (vram_budget_ == 0) return 0.0f;
    return (static_cast<float>(vram_current_) / static_cast<float>(vram_budget_)) * 100.0f;
}

} // namespace hypersp
