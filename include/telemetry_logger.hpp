#pragma once
#include "types.hpp"
#include <cstdint>

namespace hypersp {

struct TelemetryData {
    float    vram_usage_pct      = 0.0f;
    float    ram_staging_pct     = 0.0f;
    size_t   active_kv_tokens    = 0;
    uint32_t prefetch_pending    = 0;
};

class TelemetryLogger {
public:
    /** Log a telemetry event with optional value (e.g., "vram_usage", 87.5) */
    void log(const char* msg, float value = 0.0f) noexcept;

    /** Get current metrics snapshot for dashboard display */
    TelemetryData current_snapshot() const noexcept;

    size_t get_active_kv_token_count() const noexcept;

    // Direct setters for engine components to record metrics
    void set_vram_usage_pct(float pct) noexcept   { snap_.vram_usage_pct  = pct; }
    void set_ram_staging_pct(float pct) noexcept  { snap_.ram_staging_pct = pct; }
    void set_active_kv_tokens(size_t n) noexcept  { snap_.active_kv_tokens = n; }
    void set_prefetch_pending(uint32_t n) noexcept{ snap_.prefetch_pending = n; }

    // Opt-in enforcement
    void set_opt_in(bool opt_in) noexcept;
    void transmit() noexcept;

private:
    TelemetryData snap_{};
    bool opt_in_{false};
};

} // namespace hypersp
