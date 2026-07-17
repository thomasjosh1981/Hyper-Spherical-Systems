#pragma once
#include "types.hpp"
#include "config.hpp"
#include <cstdint>
#include <vector>

namespace tesseract {

class MemoryManager {
public:
    explicit MemoryManager(const Config& cfg);
    ~MemoryManager() = default;

    /** Initialize VRAM budget based on system VRAM and config ratio */
    void initialize_vram(size_t phys_vram_bytes) noexcept;

    /** Set total system RAM (call once at startup) */
    void set_ram_total(size_t phys_ram_bytes) noexcept {
        config_.ram_total_bytes = phys_ram_bytes;
    }
    
    /** Push a weight layer into the target tier (VRAM/RAM/NVMe/HDD) */
    ErrorCode push_layer(LayerShard& shard, bool prefer_vram = true) noexcept;
    
    /** Alias for push_layer — keeps API consistent */
    ErrorCode add_shard(LayerShard& shard, bool prefer_vram = true) noexcept;

    /** V1.4 elastic_breathing_search — dynamic context window resize
     *  between a low ceiling (32K) and high ceiling (256K) based on hot
     *  VRAM saturation. Updates max_active_tokens_ + adjusts vram target. */
    void set_breathing_mode(bool enabled) noexcept;
    [[nodiscard]] bool breathing_enabled() const noexcept { return breathing_; }

    /** V1.4 set_circuit_breaker — enable/disable PCIe latency tripwire */
    void set_circuit_breaker(bool enabled) noexcept { circuit_breaker_ = enabled; }
    [[nodiscard]] bool circuit_breaker_enabled() const noexcept { return circuit_breaker_; }

    size_t vram_available() const noexcept;
    float  vram_usage_percent() const noexcept;
    size_t ram_staging_bytes() const noexcept;
    size_t ram_staging_limit() const noexcept;

private:
    Config              config_;
    size_t              vram_budget_   = 0ull;
    size_t              vram_used_     = 0ul;
    size_t              ram_staging_bytes_ = 0u;
    std::vector<LayerShard> sharded_layers_;
    bool                breathing_      = true;     // V1.4 elastic_breathing_search
    bool                circuit_breaker_ = true;    // V1.4 enable_circuit_breaker
};

} // namespace tesseract
