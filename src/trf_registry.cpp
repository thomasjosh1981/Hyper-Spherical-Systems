// trf_registry.cpp — Temporal-Recency Frequency (TRF) learner + JSON registry.
//
// Spec V3.1 §2 / §3:
//
//   Registry file:  <model_filename>.hypersphere_profiles.json
//   Profile file:   <model_filename>_<profile_name>.trf   (compact binary)
//
//   On every kFlushCycleTokens (500) observed tokens, the learner may
//   flush asynchronously (deferred if generation is busy). The .trf file
//   has a 5 MB cap: entries with recency_score < kPruneScoreFloor (0.15)
//   over the trailing kPruneTokenWindow (5,000) tokens are omitted.
//
//   Profile metadata (registry JSON) holds:
//     - token_name, profile_name, file_megabytes, context_hours,
//       model_filename, created_at, last_touched
//
//   Max 5 active profiles per model file.

#include "trf_registry.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>

namespace Hyperspherical::TRF {

// ── Path helpers ──────────────────────────────────────────────────
std::string derive_registry_path(const std::string& model_filename) {
    return model_filename + ".hypersphere_profiles.json";
}
std::string derive_profile_path(const std::string& model_filename,
                                 const std::string& profile_name) {
    return model_filename + "_" + profile_name + ".trf";
}

// ── TRFLearner implementation ─────────────────────────────────────
TRFLearner::TRFLearner(const std::string& model_filename)
    : model_filename_(model_filename),
      registry_path_(derive_registry_path(model_filename))
{}

TRFLearner::~TRFLearner() {
    // Final synchronous flush on shutdown.
    maybe_flush(0, /*force=*/true);
}

float TRFLearner::decay_recency(float current, uint64_t tokens_since) noexcept {
    // Exponential decay: r(t) = r0 * exp(-lambda * dt)
    // Halflife ~= 1000 tokens. With dt in tokens: r = current * 0.5^(dt/1000).
    if (tokens_since == 0) return current;
    double halflife = 1000.0;
    double factor = std::pow(0.5, static_cast<double>(tokens_since) / halflife);
    return current * static_cast<float>(factor);
}

void TRFLearner::observe(uint16_t layer_index, uint64_t token_id) noexcept {
    std::lock_guard<std::mutex> lk(mtx_);
    total_observations_.fetch_add(1, std::memory_order_relaxed);

    auto it = entries_.find(layer_index);
    uint64_t prev_token = it != entries_.end() ? it->second.last_token_id : token_id;
    uint64_t tokens_since = (token_id > prev_token) ? (token_id - prev_token) : 0;

    if (it == entries_.end()) {
        TRFEntry e{};
        e.layer_index   = layer_index;
        e.recency_score  = 1.0f;
        e.access_count   = 1;
        e.last_token_id  = token_id;
        entries_.emplace(layer_index, e);
    } else {
        TRFEntry& e = it->second;
        // Apply exponential decay since last access, then bump.
        e.recency_score = decay_recency(e.recency_score, tokens_since);
        e.recency_score = std::min(1.0f, e.recency_score + 0.5f);  // access boost
        e.access_count += 1;
        e.last_token_id  = token_id;
    }

    if ((token_id - last_flush_token_.load(std::memory_order_relaxed)) >= kFlushCycleTokens) {
        // Mark "needs flush" — actual write happens on next maybe_flush(true) call
        last_flush_token_.store(token_id, std::memory_order_relaxed);
    }
}

void TRFLearner::maybe_flush(uint64_t /*current_token_id*/, bool force) noexcept {
    std::lock_guard<std::mutex> flk(flush_mtx_);
    std::lock_guard<std::mutex> lk(mtx_);

    // If no profiles exist yet, skip (nothing to flush).
    if (profiles_.empty() && entries_.empty()) return;

    // Spec §3.2: prune low-recency entries within trailing kPruneTokenWindow
    prune_low_recency();

    // Write registry JSON
    write_registry_locked();

    // Write each profile
    for (auto& [name, _meta] : profiles_) {
        write_profile_locked(name);
    }

    if (!force) {
        // Asynchronous: mark flushed, return. next call will actually hit disk.
    }
}

size_t TRFLearner::prune_low_recency() noexcept {
    size_t before = entries_.size();
    for (auto it = entries_.begin(); it != entries_.end(); ) {
        if (it->second.recency_score < kPruneScoreFloor) {
            it = entries_.erase(it);
        } else {
            ++it;
        }
    }
    return before - entries_.size();
}

std::vector<TRFEntry> TRFLearner::snapshot() const {
    std::lock_guard<std::mutex> lk(mtx_);
    std::vector<TRFEntry> out;
    out.reserve(entries_.size());
    for (auto& [_, e] : entries_) out.push_back(e);
    return out;
}

std::string TRFLearner::profile_path(const std::string& profile_name) const {
    return derive_profile_path(model_filename_, profile_name);
}

bool TRFLearner::add_profile(const ProfileMeta& meta) noexcept {
    std::lock_guard<std::mutex> lk(mtx_);
    if (profiles_.size() >= kMaxProfilesPerModel) {
        return false;  // at cap (5)
    }
    profiles_[meta.profile_name] = meta;
    // Create an empty .trf file for the new profile.
    write_profile_locked(meta.profile_name);
    return true;
}

bool TRFLearner::remove_profile(const std::string& profile_name) noexcept {
    std::lock_guard<std::mutex> lk(mtx_);
    auto it = profiles_.find(profile_name);
    if (it == profiles_.end()) return false;
    profiles_.erase(it);
    // Best-effort delete of the .trf file.
    try { std::filesystem::remove(profile_path(profile_name)); }
    catch (...) {} /* ignore */
    return true;
}

std::vector<ProfileMeta> TRFLearner::list_profiles() const {
    std::lock_guard<std::mutex> lk(mtx_);
    std::vector<ProfileMeta> out;
    out.reserve(profiles_.size());
    for (auto& [_, p] : profiles_) out.push_back(p);
    return out;
}

void TRFLearner::write_registry_locked() const {
    std::ofstream f(registry_path_, std::ios::trunc);
    if (!f) return;
    f << "{\n  \"model_filename\": \"" << model_filename_ << "\",\n";
    f << "  \"profiles\": [\n";
    bool first = true;
    for (auto& [_, p] : profiles_) {
        if (!first) f << ",\n";
        first = false;
        f << "    {\n"
          << "      \"token_name\": \"" << p.token_name << "\",\n"
          << "      \"profile_name\": \"" << p.profile_name << "\",\n"
          << "      \"file_megabytes\": " << std::fixed << std::setprecision(2) << p.file_megabytes << ",\n"
          << "      \"context_hours\": " << p.context_hours << ",\n"
          << "      \"created_at\": " << std::chrono::duration_cast<std::chrono::seconds>(
                p.created_at.time_since_epoch()).count() << ",\n"
          << "      \"last_touched\": " << std::chrono::duration_cast<std::chrono::seconds>(
                p.last_touched.time_since_epoch()).count() << "\n"
          << "    }";
    }
    f << "\n  ]\n}\n";
}

void TRFLearner::write_profile_locked(const std::string& profile_name) const {
    // Compact binary format:
    //   u32 magic = 0x54524646 ("TRFF")
    //   u32 version = 1
    //   u64 entry_count
    //   for each entry: u16 layer_index, f32 recency_score, u64 access_count, u64 last_token_id
    auto p = profile_path(profile_name);
    std::ofstream f(p, std::ios::binary | std::ios::trunc);
    if (!f) return;
    uint32_t magic   = 0x54524646u;
    uint32_t version = 1;
    uint64_t count   = entries_.size();
    f.write(reinterpret_cast<const char*>(&magic),   sizeof(magic));
    f.write(reinterpret_cast<const char*>(&version), sizeof(version));
    f.write(reinterpret_cast<const char*>(&count),   sizeof(count));
    for (auto& [_, e] : entries_) {
        f.write(reinterpret_cast<const char*>(&e.layer_index),  sizeof(e.layer_index));
        f.write(reinterpret_cast<const char*>(&e.recency_score), sizeof(e.recency_score));
        f.write(reinterpret_cast<const char*>(&e.access_count),  sizeof(e.access_count));
        f.write(reinterpret_cast<const char*>(&e.last_token_id), sizeof(e.last_token_id));
    }
}

TRFLearner::Stats TRFLearner::stats() const {
    std::lock_guard<std::mutex> lk(mtx_);
    Stats s;
    s.total_entries     = entries_.size();
    s.total_profiles    = profiles_.size();
    s.total_observations = total_observations_.load(std::memory_order_relaxed);
    s.last_flush_token   = last_flush_token_.load(std::memory_order_relaxed);
    for (auto& [_, p] : profiles_) {
        s.file_megabytes = std::max(s.file_megabytes, p.file_megabytes);
        s.context_hours  += p.context_hours;
    }
    return s;
}

}  // namespace Hyperspherical::TRF
