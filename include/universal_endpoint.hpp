#pragma once
#include "homophonic_cipher.hpp"
#include "context_compressor.hpp"
#include "crypto_engine.hpp"
#include <string>

namespace hypersp {

class UniversalEndpoint {
public:
    UniversalEndpoint();
    ~UniversalEndpoint() = default;

    // The Master Security Pipeline (Sandwich)
    // Sissi Compression -> Homophonic Scramble -> AES-256 (Cold Storage)
    std::string seal_payload(const std::string& plaintext_memory);
    
    // Decrypts and decompresses the payload back into active VRAM
    std::string unseal_payload(const std::string& sealed_blob);

    // Auto-benchmarks the system to lock in optimal settings for this hardware
    // This process maps NVMe bandwidth, VRAM, and RAM for optimal striping
    void auto_benchmark_system();

private:
    HomophonicCipher obfuscator_;
    ContextCompressor compressor_;
    CryptoEngine crypto_;
    
    bool is_benchmarked_;
};

} // namespace hypersp
