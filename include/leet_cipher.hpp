#pragma once
#include <string>
#include <vector>
#include <cstdint>

namespace tesseract {

struct UserCredentials {
    std::string username;
    std::string password;
    std::string pin;       // 6-digit pin
    std::string leet_key;  // 8-12 alphanumeric leet key
};

class LeetCipher {
public:
    // Helper to generate the 8-12 alphanumeric leet speak key
    static std::string generate_leet_key();

    // Verifies if the 3 inputs match (username, password, leet_key) in any order
    static bool verify_3fa_inputs(const UserCredentials& creds,
                                  const std::string& input1,
                                  const std::string& input2,
                                  const std::string& input3);

    // Encrypts compressed context data using credentials, dead languages, and Norse rune accents
    static std::vector<uint8_t> encrypt(const std::vector<uint8_t>& data, const UserCredentials& creds);

    // Decrypts the obfuscated archive back to standard compressed data
    static std::vector<uint8_t> decrypt(const std::vector<uint8_t>& ciphertext, const UserCredentials& creds);
};

} // namespace tesseract
