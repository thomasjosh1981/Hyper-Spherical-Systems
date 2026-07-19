#pragma once
#include "types.hpp"
#include <cstdint>
#include <cstddef>

namespace hypersp {

class CryptoEngine {
public:
    CryptoEngine() noexcept = default;
    ~CryptoEngine() = default;

    /** Encrypt (currently identity pass-through, quantum crypto later) */
    ErrorCode encrypt(const uint8_t* input, size_t len, uint8_t* output) noexcept;

    /** Decrypt (identity pass-through now) */
    ErrorCode decrypt(const uint8_t* input, size_t len, uint8_t* output) noexcept;
};

} // namespace hypersp
