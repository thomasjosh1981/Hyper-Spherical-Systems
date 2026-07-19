#pragma once

#include <vector>
#include <cstdint>
#include <string>

namespace hypersp {

    // Simple fallback cipher for Community Edition
    class StandardCipher {
    public:
        // Basic stream encryption/decryption using the provided key
        static std::vector<uint8_t> encrypt(const std::vector<uint8_t>& data, const std::string& key);
        static std::vector<uint8_t> decrypt(const std::vector<uint8_t>& data, const std::string& key);
    };

}
