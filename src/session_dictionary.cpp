#include "session_dictionary.hpp"
#include <iostream>
#include <cstring>

namespace hypersp {

void SessionDictionary::load(const SessionCompressionProfile& scp) {
    profile_ = scp;
    std::cout << "[MNECP] Session dictionary loaded with "
              << profile_.encode.size() << " entries.\n";
}

std::string SessionDictionary::encode(const std::string& input) const {
    if (!profile_.active) return input;
    std::string result = input;
    for (const auto& [full, code] : profile_.encode) {
        size_t pos = 0;
        while ((pos = result.find(full, pos)) != std::string::npos) {
            std::string compressed = profile_.delimiter_open + code + profile_.delimiter_close;
            result.replace(pos, full.size(), compressed);
            pos += compressed.size();
        }
    }
    return result;
}

std::string SessionDictionary::decode(const std::string& input) const {
    if (!profile_.active) return input;
    std::string result = input;
    for (const auto& [code, full] : profile_.decode) {
        std::string token = profile_.delimiter_open + code + profile_.delimiter_close;
        size_t pos = 0;
        while ((pos = result.find(token, pos)) != std::string::npos) {
            result.replace(pos, token.size(), full);
            pos += full.size();
        }
    }
    return result;
}

void SessionDictionary::destroy() {
    // Zero-fill encode/decode maps before clearing
    for (auto& [k, v] : profile_.encode) {
        std::fill(v.begin(), v.end(), '\0');
    }
    for (auto& [k, v] : profile_.decode) {
        std::fill(v.begin(), v.end(), '\0');
    }
    profile_.encode.clear();
    profile_.decode.clear();
    profile_.active = false;
    std::cout << "[MNECP] Session dictionary destroyed. No persistence.\n";
}

} // namespace hypersp
