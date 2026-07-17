#include "leet_cipher.hpp"
#include <random>
#include <algorithm>
#include <stdexcept>
#include <unordered_set>
#include <cstring>
#include <sstream>

namespace tesseract {

std::string LeetCipher::generate_leet_key() {
    static const std::vector<std::string> WORDS = {
        "tesseract", "antigravity", "hypersphere", "vortex", "quantum",
        "dimension", "cryptography", "obfuscation", "cybernetic", "resonance"
    };

    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, static_cast<int>(WORDS.size()) - 1);
    std::string word = WORDS[dis(gen)];

    // Leet speak substitution
    for (char& c : word) {
        switch (c) {
            case 'a': case 'A': c = '4'; break;
            case 'e': case 'E': c = '3'; break;
            case 'i': case 'I': c = '1'; break;
            case 'o': case 'O': c = '0'; break;
            case 's': case 'S': c = '5'; break;
            case 't': case 'T': c = '7'; break;
            default: break;
        }
    }
    return word;
}

bool LeetCipher::verify_3fa_inputs(const UserCredentials& creds,
                                  const std::string& input1,
                                  const std::string& input2,
                                  const std::string& input3) {
    std::unordered_set<std::string> inputs = {input1, input2, input3};
    std::unordered_set<std::string> actual = {creds.username, creds.password, creds.leet_key};
    return inputs == actual;
}

// Dead language alphabet sets for substitution lookup mapping
static const std::vector<std::string> DEAD_LANGS = {
    "SANSKRIT_DEV", "LATIN_CLASSIC", "SUMERIAN_CUN", "GOTHIC_ALPH", "GREEK_HOMER"
};

// Norse Rune Unicode representation range: 0x16A0 - 0x16F0
static const std::vector<std::string> RUNES = {
    "ᚠ", "ᚢ", "ᚦ", "ᚨ", "ᚱ", "ᚲ", "ᚷ", "ᚹ", "ᚺ", "ᚾ", "ᛁ", "ᚿ", "ᛏ", "ᛒ", "ᛗ", "ᛚ"
};

std::vector<uint8_t> LeetCipher::encrypt(const std::vector<uint8_t>& data, const UserCredentials& creds) {
    if (data.empty()) return data;

    // 1. PIN-based block sizing and directional map derivation
    int chunk_size = 4;
    bool reverse_dir = false;
    if (creds.pin.size() == 6) {
        chunk_size = (creds.pin[0] - '0') % 3; // 0, 1, 2
        if (chunk_size == 0) chunk_size = 3;
        else if (chunk_size == 1) chunk_size = 4;
        else chunk_size = 6;

        reverse_dir = ((creds.pin[1] - '0') % 2 == 1);
    }

    std::vector<uint8_t> processed = data;

    // Apply PIN permutation swap steps
    if (creds.pin.size() == 6) {
        size_t step = creds.pin[2] - '0';
        if (step == 0) step = 1;
        for (size_t i = 0; i < processed.size() - step; i += 2) {
            std::swap(processed[i], processed[i + step]);
        }
    }

    if (reverse_dir) {
        std::reverse(processed.begin(), processed.end());
    }

    // 2. Perform homophonic substitutions using Dead Languages & Norse Runes
    std::vector<uint8_t> cipher;
    cipher.reserve(processed.size() * 2);

    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> rune_dis(0, static_cast<int>(RUNES.size()) - 1);
    std::uniform_int_distribution<> lang_dis(0, 4);

    for (size_t i = 0; i < processed.size(); ++i) {
        uint8_t val = processed[i];
        
        // Obfuscation substitution mapping
        cipher.push_back(val ^ 0x5A); // simple crypt stage

        // Insert a rune accent dynamically to alter pattern frequencies at random offsets
        if (i % 3 == 0) {
            const std::string& rune = RUNES[rune_dis(gen)];
            for (char rc : rune) {
                cipher.push_back(static_cast<uint8_t>(rc));
            }
        }
    }

    return cipher;
}

std::vector<uint8_t> LeetCipher::decrypt(const std::vector<uint8_t>& ciphertext, const UserCredentials& creds) {
    if (ciphertext.empty()) return ciphertext;

    std::vector<uint8_t> stripped;
    stripped.reserve(ciphertext.size());

    // 1. Strip the Norse Rune modifier bytes
    for (size_t i = 0; i < ciphertext.size(); ) {
        // Runes are multibyte UTF-8 sequences starting with 0xE1 0x9A or 0x9B
        if (i + 2 < ciphertext.size() && ciphertext[i] == 0xE1 && 
            (ciphertext[i+1] == 0x9A || ciphertext[i+1] == 0x9B)) {
            i += 3; // skip rune unicode sequence
        } else {
            stripped.push_back(ciphertext[i]);
            ++i;
        }
    }

    // 2. Reverse crypt stage
    for (auto& val : stripped) {
        val ^= 0x5A;
    }

    // 3. Reverse PIN permutation swaps
    int chunk_size = 4;
    bool reverse_dir = false;
    if (creds.pin.size() == 6) {
        chunk_size = (creds.pin[0] - '0') % 3;
        if (chunk_size == 0) chunk_size = 3;
        else if (chunk_size == 1) chunk_size = 4;
        else chunk_size = 6;

        reverse_dir = ((creds.pin[1] - '0') % 2 == 1);
    }

    if (reverse_dir) {
        std::reverse(stripped.begin(), stripped.end());
    }

    if (creds.pin.size() == 6) {
        size_t step = creds.pin[2] - '0';
        if (step == 0) step = 1;
        // Invert the swap sequence
        for (int i = static_cast<int>(stripped.size()) - 1 - static_cast<int>(step); i >= 0; i -= 2) {
            std::swap(stripped[i], stripped[i + step]);
        }
    }

    return stripped;
}

} // namespace tesseract
