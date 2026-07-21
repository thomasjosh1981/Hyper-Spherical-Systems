#pragma once
#include "pirate_proxy.hpp"
#include <filesystem>
#include <fstream>
#include <string>
#include <sstream>
#include <shlobj.h>

namespace pirate {

class ConfigStore {
public:
    static std::filesystem::path get_config_path() {
        char path[MAX_PATH];
        if (SUCCEEDED(SHGetFolderPathA(NULL, CSIDL_APPDATA, NULL, 0, path))) {
            std::filesystem::path dir = std::filesystem::path(path) / "PirateLlama";
            if (!std::filesystem::exists(dir)) {
                std::filesystem::create_directories(dir);
            }
            return dir / "config.ini";
        }
        return "config.ini"; // fallback
    }

    static void load(ProxyConfig& cfg) {
        std::ifstream in(get_config_path());
        if (!in.is_open()) return;

        std::string line;
        while (std::getline(in, line)) {
            if (line.empty() || line[0] == '#' || line[0] == ';') continue;
            size_t delim = line.find('=');
            if (delim == std::string::npos) continue;

            std::string key = line.substr(0, delim);
            std::string val = line.substr(delim + 1);

            // Strip whitespace
            key.erase(key.find_last_not_of(" \n\r\t") + 1);
            val.erase(0, val.find_first_not_of(" \n\r\t"));
            val.erase(val.find_last_not_of(" \n\r\t") + 1);

            if (key == "proxy_port") cfg.proxy_port = std::stoi(val);
            else if (key == "backend") cfg.backend = static_cast<Backend>(std::stoi(val));
            else if (key == "backend_host") cfg.backend_host = val;
            else if (key == "backend_port") cfg.backend_port = std::stoi(val);
            else if (key == "model_path") cfg.model_path = val;
            else if (key == "sissi_enabled") cfg.sissi_enabled = (val == "1" || val == "true");
            else if (key == "compress_requests") cfg.compress_requests = (val == "1" || val == "true");
            else if (key == "compress_responses") cfg.compress_responses = (val == "1" || val == "true");
        }
    }

    static void save(const ProxyConfig& cfg) {
        std::ofstream out(get_config_path());
        if (!out.is_open()) return;

        out << "proxy_port=" << cfg.proxy_port << "\n";
        out << "backend=" << static_cast<int>(cfg.backend) << "\n";
        out << "backend_host=" << cfg.backend_host << "\n";
        out << "backend_port=" << cfg.backend_port << "\n";
        out << "model_path=" << cfg.model_path << "\n";
        out << "sissi_enabled=" << (cfg.sissi_enabled ? "1" : "0") << "\n";
        out << "compress_requests=" << (cfg.compress_requests ? "1" : "0") << "\n";
        out << "compress_responses=" << (cfg.compress_responses ? "1" : "0") << "\n";
    }
};

} // namespace pirate
