// TelemetryLogger: collects runtime metrics for dashboard display.
#include "telemetry_logger.hpp"
#include <cstring>

namespace hypersp {

void TelemetryLogger::log(const char* msg, float value) noexcept {
    if (!msg) return;
    // Dispatch on message key to the appropriate metric slot.
    if (std::strcmp(msg, "vram_usage") == 0)        snap_.vram_usage_pct  = value;
    else if (std::strcmp(msg, "ram_staging") == 0)  snap_.ram_staging_pct = value;
    else if (std::strcmp(msg, "kv_tokens") == 0)    snap_.active_kv_tokens = static_cast<size_t>(value);
    else if (std::strcmp(msg, "prefetch_pending") == 0) snap_.prefetch_pending = static_cast<uint32_t>(value);
    // Unknown keys are silently ignored — telemetry is best-effort.
}

TelemetryData TelemetryLogger::current_snapshot() const noexcept {
    return snap_;
}

size_t TelemetryLogger::get_active_kv_token_count() const noexcept {
    return snap_.active_kv_tokens;
}

void TelemetryLogger::set_opt_in(bool opt_in) noexcept {
    opt_in_ = opt_in;
}

void TelemetryLogger::transmit() noexcept {
    if (!opt_in_) return;
    
    // Remote transmission logic goes here...
}

} // namespace hypersp
