#pragma once

#include <string>

namespace tesseract {

class DRMManager {
public:
    // Generate a mathematically derived Hardware ID
    static std::string generate_hwid();
    
    // Verify license string against hardware ID. Also checks for the Easter Egg.
    // Returns true if the license is valid (PRO tier), false if invalid (FREE tier).
    static bool verify_license(const std::string& license_key);
};

} // namespace tesseract
