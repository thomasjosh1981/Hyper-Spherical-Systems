#pragma once

#ifdef HYPERSPHERICAL_ENTERPRISE_BUILD
#include "enterprise/license_manager.hpp"
#else

#include <string>

namespace hypersp {
    enum class LicenseTier {
        FREE = 0,
        PRO = 1,
        TRIAL_12HR = 2,
        TRIAL_6HR = 3,
        TRIAL_4HR = 4,
        TRIAL_EXPIRED = 5
    };

    struct LicenseState {
        LicenseTier tier = LicenseTier::FREE;
        std::string hardware_id = "OSS-COMMUNITY-EDITION";
        std::string current_pop_lock = "NONE";
        long long remaining_seconds = 0;
        bool community_splash_needed = true;
    };

    class LicenseManager {
    public:
        static void init() {}
        static LicenseState get_state() { return LicenseState{}; }
        static bool is_feature_allowed(const std::string&) { return false; }
        static bool apply_unlock_payload(const std::string&, const std::string&) { return false; }
        static void tick_usage(long long) {}

        // Nov 1 Expiration for free version
        static bool is_free_version_expired();

        // Major update check
        static bool requires_mandatory_update(const std::string& latest_available_version);

        // Security update TOS prompt for paid
        static bool requires_security_tos_acceptance(bool has_security_update);
    };
}

#endif
