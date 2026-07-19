#define _CRT_SECURE_NO_WARNINGS
#ifndef HYPERSPHERICAL_ENTERPRISE_BUILD
#include "license_manager.hpp"
#include <chrono>

namespace hypersp {

bool LicenseManager::is_free_version_expired() {
    auto state = get_state();
    if (state.tier == LicenseTier::PRO) return false;

    // Check if current date > Nov 1, 2026
    auto now = std::chrono::system_clock::now();
    std::time_t current_time = std::chrono::system_clock::to_time_t(now);
    std::tm* current_tm = std::localtime(&current_time);
    
    if (!current_tm) return false;

    if (current_tm->tm_year + 1900 > 2026) return true;
    if (current_tm->tm_year + 1900 == 2026 && current_tm->tm_mon >= 10) return true; // tm_mon is 0-indexed, 10 = Nov

    return false;
}

bool LicenseManager::requires_mandatory_update(const std::string& latest_available_version) {
    auto state = get_state();
    if (state.tier == LicenseTier::PRO) return false; // Paid users aren't forced to update
    
    // Simplistic major version check. E.g. "1.0.0" -> 1
    int current_major = 1; // Assuming baseline is 1.0.0
    int latest_major = 1;
    
    try {
        size_t dot_pos = latest_available_version.find('.');
        if (dot_pos != std::string::npos) {
            latest_major = std::stoi(latest_available_version.substr(0, dot_pos));
        }
    } catch (...) {}

    return (latest_major > current_major);
}

bool LicenseManager::requires_security_tos_acceptance(bool has_security_update) {
    auto state = get_state();
    if (state.tier != LicenseTier::PRO) return false; // Free tier is forced to update anyway
    
    return has_security_update;
}

} // namespace hypersp
#endif
