// MemoryManager: enforces 70% VRAM limit + RAM staging buffer.
#include "memory_manager.hpp"
#include <algorithm>

namespace hypersp {

MemoryManager::MemoryManager(const Config& cfg) : config_(cfg) {}

void MemoryManager::initialize_vram(size_t phys_vram_bytes) noexcept {
    vram_budget_ = static_cast<size_t>(static_cast<double>(phys_vram_bytes) * config_.vram_max_ratio);
}

ErrorCode MemoryManager::push_layer(LayerShard& shard, bool prefer_vram) noexcept {
    const size_t needed = shard.byte_size;
    if (needed == 0) {
        shard.tier = MemoryTier::NVME;
        return ErrorCode::OK;
    }

    // 1) Try VRAM first (always — fast path)
    if (vram_used_ + needed <= vram_budget_) {
        shard.tier = MemoryTier::VRAM;
        vram_used_ += needed;
        sharded_layers_.push_back(shard);
        return ErrorCode::OK;
    }

    // 2) VRAM full — try to evict idle layers (LRU-ish: walk from oldest first)
    if (prefer_vram) {
        size_t freed = 0;
        for (auto it = sharded_layers_.rbegin();
             it != sharded_layers_.rend() && freed < needed;
             ++it) {
            auto& s = *it;
            if (s.tier == MemoryTier::VRAM) {
                freed += s.byte_size;
                s.tier = MemoryTier::RAM;
                vram_used_ -= s.byte_size;
                ram_staging_bytes_ += s.byte_size;
            }
        }
        if (vram_used_ + needed <= vram_budget_) {
            shard.tier = MemoryTier::VRAM;
            vram_used_ += needed;
            sharded_layers_.push_back(shard);
            return ErrorCode::OK;
        }
    }

    // 3) Fall back to RAM staging (up to ram_total_bytes * ram_staging_pct)
    const size_t ram_limit = static_cast<size_t>(
        static_cast<double>(config_.ram_total_bytes) * config_.ram_staging_pct);
    if (ram_staging_bytes_ + needed <= ram_limit) {
        shard.tier = MemoryTier::RAM;
        ram_staging_bytes_ += needed;
        sharded_layers_.push_back(shard);
        return ErrorCode::OK;
    }

    // 4) Caller will spill to NVMe — we just report overflow
    return ErrorCode::VRAM_BUDGET;
}

ErrorCode MemoryManager::add_shard(LayerShard& shard, bool prefer_vram) noexcept {
    return push_layer(shard, prefer_vram);
}

void MemoryManager::set_breathing_mode(bool enabled) noexcept {
    breathing_ = enabled;
    // Per spec V1.4: dynamically resize max_active_tokens_ between 32K (low)
    // and 256K (high) based on hot VRAM saturation.
    constexpr uint32_t kLowCeiling  = 32768u;
    constexpr uint32_t kHighCeiling = 262144u;
    float pct = vram_usage_percent();
    if (!enabled) {
        config_.max_active_tokens = kHighCeiling;
        return;
    }
    // Hot saturation ≥ 50% → shrink; else expand.
    if (pct >= 50.0f) {
        config_.max_active_tokens = kLowCeiling;
    } else {
        config_.max_active_tokens = kHighCeiling;
    }
}

size_t MemoryManager::vram_available() const noexcept {
    return (vram_budget_ > vram_used_) ? (vram_budget_ - vram_used_) : 0ull;
}

float MemoryManager::vram_usage_percent() const noexcept {
    if (vram_budget_ == 0) return 0.0f;
    return (static_cast<float>(vram_used_) / static_cast<float>(vram_budget_)) * 100.0f;
}

size_t MemoryManager::ram_staging_bytes() const noexcept {
    return ram_staging_bytes_;
}

size_t MemoryManager::ram_staging_limit() const noexcept {
    return static_cast<size_t>(static_cast<double>(config_.ram_total_bytes) * config_.ram_staging_pct);
}

} // namespace hypersp
