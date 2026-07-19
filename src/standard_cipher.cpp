#include "standard_cipher.hpp"
#include <random>

namespace hypersp {

    static std::vector<uint8_t> process_stream(const std::vector<uint8_t>& data, const std::string& key) {
        if (data.empty()) return {};
        
        // Use the key to seed a PRNG for a basic stream cipher
        std::seed_seq seed(key.begin(), key.end());
        std::mt19937_64 prng(seed);
        
        std::vector<uint8_t> out(data.size());
        for (size_t i = 0; i < data.size(); ++i) {
            // XOR each byte with the PRNG output
            uint8_t k = static_cast<uint8_t>(prng() & 0xFF);
            out[i] = data[i] ^ k;
        }
        return out;
    }

    std::vector<uint8_t> StandardCipher::encrypt(const std::vector<uint8_t>& data, const std::string& key) {
        return process_stream(data, key);
    }

    std::vector<uint8_t> StandardCipher::decrypt(const std::vector<uint8_t>& data, const std::string& key) {
        return process_stream(data, key);
    }

}
