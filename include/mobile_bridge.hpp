#pragma once

#include <string>

namespace pirate {

class MobileBridge {
public:
    MobileBridge() = default;
    
    // Checks if adb is available and a device is connected
    bool is_device_connected() const;

    // Executes adb shell uiautomator dump and pulls the window_dump.xml
    // Returns the raw XML layout of the current screen.
    std::string fetch_ui_hierarchy() const;
    
private:
    std::string execute_adb_command(const std::string& args) const;
};

} // namespace pirate
