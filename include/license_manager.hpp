#pragma once

#ifdef HYPERSPHERICAL_ENTERPRISE_BUILD
#include "enterprise/license_manager.hpp"
#else

#include <string>
#include <cstdint>

namespace hypersp {

// ─────────────────────────────────────────────────────────────────────────────
// License Tiers
// ─────────────────────────────────────────────────────────────────────────────
enum class LicenseTier : uint8_t {
    ALPHA_BETA       = 0,  // Current phase — fully free, all features, no expiry
    LIFETIME_UNLIMITED = 1, // Donor code — never expires, all features, forever
    COMMUNITY        = 2,  // Post-v1.0 free tier — forced update on major releases
    MODULE           = 3,  // Post-unlimited era — per-module purchase
    SUBSCRIPTION     = 4,  // Monthly/annual subscription
    // Legacy names kept for compat
    FREE             = 2,
    PRO              = 1,
    TRIAL_12HR       = 5,
    TRIAL_6HR        = 6,
    TRIAL_4HR        = 7,
    TRIAL_EXPIRED    = 8,
    ENTERPRISE_UNLOCKED = 9, // Hardware token / custom server build
};

// ─────────────────────────────────────────────────────────────────────────────
// Donation tier pricing schedule (500 lifetime codes total)
//   Codes  1–100  → $100/each
//   Codes 101–200 → $150/each
//   Codes 201–300 → $200/each
//   Codes 301–400 → $250/each   ← final batch; no more codes after this
// ─────────────────────────────────────────────────────────────────────────────
struct DonationTierInfo {
    int  codes_issued;       // total codes issued so far (fetched from server)
    int  price_usd;          // current price for next code
    bool codes_available;    // false when 400 codes exhausted
};

struct LicenseState {
    LicenseTier tier               = LicenseTier::ALPHA_BETA;
    std::string hardware_id        = "OSS-COMMUNITY-EDITION";
    std::string license_code       = "";      // filled when user enters code
    std::string current_pop_lock   = "NONE";
    long long   remaining_seconds  = 0;
    bool        community_splash_needed = false; // suppressed during alpha
    bool        is_lifetime        = false;    // true only for LIFETIME_UNLIMITED
    int         build_major        = 0;        // major version this binary was built as
    
    // Tamper-proof 30-day trial
    int64_t     trial_first_run_ts = 0;
    int64_t     trial_expires_ts   = 0;
    int64_t     trial_high_water_ts= 0;
    int         trial_days_left    = 30;
    bool        trial_expired      = false;
    bool        clock_tampered     = false;
};

// ─────────────────────────────────────────────────────────────────────────────
// Lifetime code format (HMAC-SHA256 based, no server round-trip required)
//
//   PL-XXXX-XXXX-XXXX-XXXX
//
//   Internally: HMAC_SHA256(secret_salt + seq_number, "PIRATE_LLAMA_LIFETIME")
//   truncated to 16 hex chars, formatted with dashes every 4.
//   seq_number encodes the donor slot (001–400) so we know which batch it
//   came from without a database lookup.
// ─────────────────────────────────────────────────────────────────────────────

class LicenseManager {
public:
    static void init() {}
    static LicenseState get_state();

    // Fetch verified network timestamp via HTTPS Date header (tamper-proof against PC clock changes)
    static int64_t fetch_network_time();

    // Check 30-day trial status with anti-clock rollback detection
    static bool check_30day_trial(int& out_days_left, bool& out_clock_tampered);

    // Validate and activate a lifetime code entered by the user.
    // Returns true and updates persisted state if valid.
    static bool apply_lifetime_code(const std::string& code);

    // Scan removable drives for a physical .pirate_key hardware unlock file
    static bool check_hardware_key();

    // True if running alpha/beta build (major == 0)
    static bool is_alpha_build();

    // True if free/community tier AND a stable major release is available
    // AND the user does not hold a lifetime code.
    // Lifetime code holders: NEVER forced to update.
    static bool requires_mandatory_update(const std::string& latest_version);

    // Returns false during alpha. Returns true post-v1.0 for non-lifetime
    // community users when the binary's major version is old.
    static bool is_free_version_expired();

    // Security TOS — only shown to subscription/module tier
    static bool requires_security_tos_acceptance(bool has_security_update);

    // Feature gating — returns true if the feature is accessible for the tier
    static bool is_feature_allowed(const std::string& feature_id);

    // Donation tier info (requires network; returns cached if offline)
    static DonationTierInfo get_donation_tier_info();

    // Generate a lifetime code for a given donor slot (run by you, offline tool)
    // seq must be 1–400.
    static std::string generate_lifetime_code(int seq);

    // Legacy compat
    static bool apply_unlock_payload(const std::string&, const std::string&) { return false; }
    static void tick_usage(long long) {}
};

} // namespace hypersp

#endif
