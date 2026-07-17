// tesseract_pqc.hpp
//
// Spec V1.3 — Post-Quantum Cryptography core stack.
// Dual-mode backend:
//   - When liboqs is available (CMake sets TESSERACT_HAVE_LIBOQS=1), we link against it
//     for real Kyber-1024 (ML-KEM) and Dilithium-5 (ML-DSA).
//   - Otherwise we provide stub implementations that use ChaCha20-Poly1305 / SHA-256
//     so the API surface remains identical and the engine compiles + runs.
//
// Also includes AES-256-GCM (real) and Blowfish-448 (real implementation; the spec
// terminology "Blowfish-448" means a 448-bit key with the standard 64-bit block size).

#pragma once
#include <cstdint>
#include <cstddef>
#include <array>
#include <vector>
#include <string>
#include <span>

namespace Tesseract::Security::Pqc {

    // ── Error codes ──────────────────────────────────────────────────────
    enum class Status : int {
        OK             =  0,
        BAD_ARG        = -1,
        NOT_SUPPORTED  = -2,
        INTERNAL       = -3,
        AUTH_FAIL      = -4,
    };

    // ── Backend enumeration ─────────────────────────────────────────────
    enum class Backend : int {
        LIBOQS_REAL   = 0,   // Real Kyber/Dilithium from Open Quantum Safe
        STUB_CHACHA   = 1,   // Stub mode (ChaCha20-derived keys, not quantum-safe)
    };

    [[nodiscard]] inline const char* BackendName(Backend b) noexcept {
        switch (b) {
            case Backend::LIBOQS_REAL:  return "liboqs (real Kyber-1024 / Dilithium-5)";
            case Backend::STUB_CHACHA: return "stub (ChaCha20 fallback — NOT quantum-safe)";
        }
        return "unknown";
    }

    [[nodiscard]] Backend ActiveBackend() noexcept;

    // ── Key sizes ───────────────────────────────────────────────────────
    constexpr size_t KYBER_PUBLIC_KEY_BYTES     = 1568;   // ML-KEM-1024
    constexpr size_t KYBER_SECRET_KEY_BYTES     = 3168;
    constexpr size_t KYBER_CIPHERTEXT_BYTES     = 1568;
    constexpr size_t KYBER_SHARED_SECRET_BYTES  = 32;

    constexpr size_t DILITHIUM_PUBLIC_KEY_BYTES = 2592;   // ML-DSA-87 (Dilithium-5)
    constexpr size_t DILITHIUM_SECRET_KEY_BYTES = 4896;
    constexpr size_t DILITHIUM_SIGNATURE_BYTES  = 4627;

    constexpr size_t AES_KEY_BYTES    = 32;
    constexpr size_t AES_NONCE_BYTES  = 12;
    constexpr size_t AES_TAG_BYTES    = 16;

    constexpr size_t BLOWFISH_KEY_MAX_BYTES = 56;   // 448 bits

    // ── Kyber KEM (key encapsulation) ───────────────────────────────────
    struct KyberKeyPair {
        std::array<uint8_t, KYBER_PUBLIC_KEY_BYTES> public_key{};
        std::array<uint8_t, KYBER_SECRET_KEY_BYTES> secret_key{};
    };
    struct KyberCiphertext {
        std::array<uint8_t, KYBER_CIPHERTEXT_BYTES> bytes{};
    };
    using SharedSecret = std::array<uint8_t, KYBER_SHARED_SECRET_BYTES>;

    [[nodiscard]] Status KyberKeygen(KyberKeyPair& kp) noexcept;
    [[nodiscard]] Status KyberEncapsulate(const std::array<uint8_t, KYBER_PUBLIC_KEY_BYTES>& pk,
                                            KyberCiphertext& ct,
                                            SharedSecret& ss) noexcept;
    [[nodiscard]] Status KyberDecapsulate(const KyberKeyPair& kp,
                                            const KyberCiphertext& ct,
                                            SharedSecret& ss) noexcept;

    // ── Dilithium signature ─────────────────────────────────────────────
    struct DilithiumKeyPair {
        std::array<uint8_t, DILITHIUM_PUBLIC_KEY_BYTES> public_key{};
        std::array<uint8_t, DILITHIUM_SECRET_KEY_BYTES> secret_key{};
    };
    struct Signature {
        std::vector<uint8_t> bytes;
    };

    [[nodiscard]] Status DilithiumKeygen(DilithiumKeyPair& kp) noexcept;
    [[nodiscard]] Status DilithiumSign(const DilithiumKeyPair& kp,
                                         std::span<const uint8_t> msg,
                                         Signature& sig) noexcept;
    [[nodiscard]] Status DilithiumVerify(const std::array<uint8_t, DILITHIUM_PUBLIC_KEY_BYTES>& pk,
                                           std::span<const uint8_t> msg,
                                           const Signature& sig) noexcept;

    // ── AES-256-GCM (always real, hardware-accelerated when available) ──
    struct AesGcmCipher {
        std::array<uint8_t, AES_KEY_BYTES>     key{};
        std::array<uint8_t, AES_NONCE_BYTES>   nonce{};
        // Returns ciphertext of same length as plaintext; appended 16-byte tag.
        [[nodiscard]] Status encrypt(std::span<const uint8_t> plaintext,
                                      std::span<const uint8_t> aad,
                                      std::vector<uint8_t>& out) noexcept;
        [[nodiscard]] Status decrypt(std::span<const uint8_t> ciphertext_with_tag,
                                      std::span<const uint8_t> aad,
                                      std::vector<uint8_t>& out) noexcept;
    };

    // ── Blowfish-448 (variable key up to 448 bits, 64-bit block) ────────
    class BlowfishCipher {
    public:
        // key_bytes must be 1..56 (4..448 bits).
        [[nodiscard]] Status set_key(std::span<const uint8_t> key_bytes) noexcept;
        [[nodiscard]] Status encrypt_block(uint64_t in, uint64_t& out) noexcept;
        [[nodiscard]] Status decrypt_block(uint64_t in, uint64_t& out) noexcept;
        // ECB mode over a byte buffer; ciphertext length is rounded up to 8.
        [[nodiscard]] Status encrypt_ecb(std::span<const uint8_t> in,
                                          std::vector<uint8_t>& out) noexcept;
        [[nodiscard]] Status decrypt_ecb(std::span<const uint8_t> in,
                                          std::vector<uint8_t>& out) noexcept;
    private:
        // 18 subkeys + 4 S-boxes × 256 entries
        std::array<uint32_t, 18> P_{};
        std::array<std::array<uint32_t, 256>, 4> S_{};
        void key_schedule(std::span<const uint8_t> key) noexcept;
    };

    // ── Composite: nested AES-256-GCM outer + Blowfish-448 inner ───────
    // Returns ciphertext = AES-GCM(Blowfish(plaintext)) with appended tag.
    [[nodiscard]] Status NestedEncrypt(const SharedSecret& shared_secret,
                                        std::span<const uint8_t> plaintext,
                                        std::vector<uint8_t>& out) noexcept;
    [[nodiscard]] Status NestedDecrypt(const SharedSecret& shared_secret,
                                        std::span<const uint8_t> ciphertext_with_tag,
                                        std::vector<uint8_t>& out) noexcept;

} // namespace Tesseract::Security::Pqc
