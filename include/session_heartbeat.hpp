// session_heartbeat.hpp
// Single-session enforcement for Pirate Llama lifetime codes.
//
// Rules:
//   • One code may be installed on any number of personal devices.
//   • Only ONE instance may hold an active session lease at a time.
//   • A second activation immediately invalidates the previous session.
//   • Enterprise-pattern detection (high volume, service context,
//     server-class hardware) triggers silent permanent revocation.
//   • Revocation is final. No appeal path in the software.

#pragma once
#include <string>
#include <atomic>
#include <thread>
#include <cstdint>

namespace hypersp {

enum class HeartbeatStatus : uint8_t {
    OK          = 0,  // lease active, all good
    KICKED      = 1,  // another device took the session
    REVOKED     = 2,  // code permanently revoked (enterprise abuse or TOS)
    OFFLINE     = 3,  // can't reach server — grace period applies
};

struct EnterpriseSignals {
    uint32_t requests_per_hour  = 0;   // sampled rolling average
    uint32_t peak_concurrent    = 0;   // max simultaneous connections seen
    bool     running_as_service = false;
    bool     server_class_hw    = false; // >64 logical cores or >512GB RAM
    bool     datacenter_ip      = false; // reverse-DNS heuristic
};

class SessionHeartbeat {
public:
    // server_base: e.g. "https://license.piratellama.dev"
    // code: the PL-XXXX-... lifetime code
    // hardware_id: stable per-machine identifier (volume serial + MAC hash)
    SessionHeartbeat(std::string server_base,
                     std::string code,
                     std::string hardware_id);
    ~SessionHeartbeat();

    // Activate: register with server, get session token.
    // Returns false immediately if code is already revoked.
    bool activate();

    // Current status — checked by LicenseManager on every request.
    HeartbeatStatus status() const noexcept;

    // True if enterprise patterns have been detected locally.
    bool enterprise_detected() const noexcept;

    // Update rolling request counter (called from PirateProxy per-request).
    void record_request();

    // Stop heartbeat thread cleanly.
    void stop();

    // Build a stable hardware ID string for this machine.
    static std::string build_hardware_id();

private:
    void beat_loop();
    bool send_heartbeat();
    void apply_revocation();
    EnterpriseSignals sample_signals() const;

    std::string     server_base_;
    std::string     code_;
    std::string     hardware_id_;
    std::string     session_token_;

    std::atomic<HeartbeatStatus> status_{HeartbeatStatus::OFFLINE};
    std::atomic<bool>            running_{false};
    std::atomic<uint64_t>        request_count_{0};
    std::atomic<uint32_t>        peak_concurrent_{0};
    std::atomic<bool>            enterprise_flag_{false};

    std::thread beat_thread_;

    // Beat interval: 60s normal, 15s after a KICKED signal for fast re-check
    static constexpr int BEAT_INTERVAL_S  = 60;
    static constexpr int KICKED_INTERVAL_S = 15;
    // Grace period when offline: 4 hours before locking out
    static constexpr int OFFLINE_GRACE_S  = 60 * 60 * 4;

    // Enterprise trip-wires
    static constexpr uint32_t ENTERPRISE_RPH_THRESHOLD    = 800;  // req/hour
    static constexpr uint32_t ENTERPRISE_CONCUR_THRESHOLD = 8;    // concurrent
    static constexpr uint32_t ENTERPRISE_CORE_THRESHOLD   = 64;   // logical CPUs
};

} // namespace hypersp
