#pragma once

#include <string>
#include <cstdint>

namespace tesseract {

    enum class LicenseTier {
        UNLICENSED,
        TRIAL_12HR,
        TRIAL_6HR,
        TRIAL_4HR,
        TRIAL_EXPIRED,
        LIVE_MODE,
        BASE_PAID,
        FULL_PAID,
        SUBSCRIPTION_DAILY,
        SUBSCRIPTION_WEEKLY,
        PORTABLE_MODE,
        COMMUNITY_90DAY     // Developer-sanctioned free tier: full features, 90-day resettable clock
    };

    struct LicenseState {
        LicenseTier tier;
        uint64_t remaining_seconds;
        uint64_t expiration_timestamp;  // For subscriptions and community tier
        std::string hardware_id;
        std::string current_pop_lock;
        bool community_splash_needed = false;  // Show "support the dev" message on launch
    };

    class LicenseManager {
    public:
        // Initialize the license manager, read states, and enforce trial clock
        static void init();

        // Get the current overall state
        static LicenseState get_state();

        // Check if a specific premium feature is allowed
        static bool is_feature_allowed(const std::string& feature_name);

        // Hardware Identity
        static std::string generate_hardware_id();

        // Rolling "Pop Lock" Code based on hardware ID and internal sequence
        static std::string generate_pop_lock();

        // Set the temp PIN from the user (pre-verification)
        static void set_temp_pin(const std::string& pin);

        // Apply an unlock payload (usually a .tess_license file content)
        static bool apply_unlock_payload(const std::string& one_time_code, const std::string& payload);

        // Tick the usage clock (called periodically by the main loop)
        static void tick_usage(uint64_t elapsed_seconds);

    private:
        static void load_state();
        static void save_state();
        static std::string encrypt_state(const std::string& plain);
        static std::string decrypt_state(const std::string& cipher);
    };

} // namespace tesseract
