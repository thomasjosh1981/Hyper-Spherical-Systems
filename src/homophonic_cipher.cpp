#include "homophonic_cipher.hpp"
#include <iostream>
#include <random>
#include <sstream>

namespace hypersp {

HomophonicCipher::HomophonicCipher() {
    build_mappings();
}

void HomophonicCipher::generate_unique_seed() {
    // In a real implementation, this would use a cryptographically secure RNG
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<uint32_t> dis(100000, 999999);
    
    current_seed_ = "HS_SEED_" + std::to_string(dis(gen));
    std::cout << "[HomophonicCipher] Generated unique session seed: " << current_seed_ << "\n";
}

void HomophonicCipher::load_seed(const std::string& seed) {
    current_seed_ = seed;
    std::cout << "[HomophonicCipher] Loaded seed: " << current_seed_ << "\n";
}

void HomophonicCipher::build_mappings() {
    // This is a stub. In reality, the mappings would be seeded by current_seed_
    // Common letters get 3-5 symbols, uncommon (like W, Z, X) get 6-7 symbols.
    // Example subset mapping:
    encode_map_['a'] = {"@1", "a^", "A*", "4a"};
    encode_map_['e'] = {"#3", "E~", "e+", "33", "EE"};
    encode_map_['w'] = {"W!", "w?", "vv", "W0", "ww", "W*W", "^W^"};
    
    // Build reverse decode map
    for (const auto& pair : encode_map_) {
        for (const auto& sym : pair.second) {
            decode_map_[sym] = pair.first;
        }
    }
}

std::string HomophonicCipher::obfuscate(const std::string& plaintext) const {
    if (current_seed_.empty()) {
        std::cerr << "[HomophonicCipher] Error: No seed loaded.\n";
        return "";
    }
    
    std::cout << "[HomophonicCipher] Obfuscating " << plaintext.length() << " bytes...\n";
    std::stringstream ss;
    
    // Simulate random selection of substitution strings
    for (char c : plaintext) {
        char lower_c = std::tolower(c);
        auto it = encode_map_.find(lower_c);
        if (it != encode_map_.end()) {
            const auto& symbols = it->second;
            // Just pick the first one for the mock
            ss << symbols[0] << "|"; 
        } else {
            // Passthrough unknown chars
            ss << c << "|";
        }
    }
    
    return ss.str();
}

std::string HomophonicCipher::deobfuscate(const std::string& ciphertext) const {
    if (current_seed_.empty()) {
        std::cerr << "[HomophonicCipher] Error: No seed loaded.\n";
        return "";
    }
    
    std::cout << "[HomophonicCipher] Deobfuscating ciphertext...\n";
    std::stringstream plaintext;
    std::string token;
    std::stringstream token_stream(ciphertext);
    
    while (std::getline(token_stream, token, '|')) {
        if (token.empty()) continue;
        
        auto it = decode_map_.find(token);
        if (it != decode_map_.end()) {
            plaintext << it->second;
        } else {
            plaintext << token; // Passthrough if not in map
        }
    }
    
    return plaintext.str();
}

} // namespace hypersp
