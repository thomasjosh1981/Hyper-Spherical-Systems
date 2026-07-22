#pragma once
#include <string>
#include <vector>
#include <unordered_map>

namespace hypersp {

class HomophonicCipher {
public:
    HomophonicCipher();
    ~HomophonicCipher() = default;

    // Generates a unique user seed for the symbol mapping
    void generate_unique_seed();
    
    // Loads an existing seed from a jump drive or persistent config
    void load_seed(const std::string& seed);
    
    // Obfuscates standard text into the multi-symbol ciphertext to defeat frequency analysis
    std::string obfuscate(const std::string& plaintext) const;
    
    // Decodes the multi-symbol ciphertext back to plaintext
    std::string deobfuscate(const std::string& ciphertext) const;

private:
    void build_mappings();

    std::string current_seed_;
    
    // Maps a character (e.g. 'e', 'w') to an array of substitution strings (accents, asterisks, etc.)
    // Common letters get 3-5 symbols, uncommon ones get 6-7 to heavily throw off scrapers
    std::unordered_map<char, std::vector<std::string>> encode_map_;
    
    // Maps a substitution string back to a character for decryption
    std::unordered_map<std::string, char> decode_map_;
};

} // namespace hypersp
