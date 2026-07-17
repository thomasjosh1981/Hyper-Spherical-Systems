// CryptoEngine: identity pass-through. Quantum-resistant crypto bolted on after engine compiles cleanly.
#include "crypto_engine.hpp"
#include <cstring>

namespace tesseract {

ErrorCode CryptoEngine::encrypt(const uint8_t* input, size_t len, uint8_t* output) noexcept {
    if (!input || !output || len == 0) return ErrorCode::BAD_CONFIG;
    memcpy(output, input, static_cast<size_t>(len));
    return ErrorCode::OK;
}

ErrorCode CryptoEngine::decrypt(const uint8_t* input, size_t len, uint8_t* output) noexcept {
    if (!input || !output || len == 0) return ErrorCode::BAD_CONFIG;
    memcpy(output, input, static_cast<size_t>(len));
    return ErrorCode::OK;
}

} // namespace tesseract
