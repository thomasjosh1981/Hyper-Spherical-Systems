#include "mobile_bridge.hpp"
#include <cstdio>
#include <array>
#include <memory>
#include <stdexcept>
#include <fstream>
#include <sstream>
#include <filesystem>

namespace pirate {

std::string MobileBridge::execute_adb_command(const std::string& args) const {
    std::string cmd = "adb " + args;
    std::array<char, 128> buffer;
    std::string result;
#if defined(_WIN32)
    std::unique_ptr<FILE, decltype(&_pclose)> pipe(_popen(cmd.c_str(), "r"), _pclose);
#else
    std::unique_ptr<FILE, decltype(&pclose)> pipe(popen(cmd.c_str(), "r"), pclose);
#endif
    if (!pipe) {
        throw std::runtime_error("popen() failed!");
    }
    while (fgets(buffer.data(), static_cast<int>(buffer.size()), pipe.get()) != nullptr) {
        result += buffer.data();
    }
    return result;
}

bool MobileBridge::is_device_connected() const {
    try {
        std::string out = execute_adb_command("devices");
        return out.find("\tdevice") != std::string::npos;
    } catch (...) {
        return false;
    }
}

std::string MobileBridge::fetch_ui_hierarchy() const {
    if (!is_device_connected()) return "";
    
    execute_adb_command("shell uiautomator dump /sdcard/window_dump.xml");
    
    std::string temp_path = std::filesystem::temp_directory_path().string() + "/window_dump.xml";
    execute_adb_command("pull /sdcard/window_dump.xml \"" + temp_path + "\"");
    
    std::ifstream ifs(temp_path);
    if (!ifs.is_open()) return "";
    std::stringstream ss;
    ss << ifs.rdbuf();
    
    return ss.str();
}

} // namespace pirate
