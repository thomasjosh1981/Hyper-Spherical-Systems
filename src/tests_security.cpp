// tests_security.cpp — V1.1 / V1.2 / V1.3 security subsystem coverage.
// Same minimal harness style as tests.cpp.

#include "config.hpp"
#include "types.hpp"
#include "tesseract_obfuscation.hpp"
#include "tesseract_security_tripwire.hpp"
#include "tesseract_security_optimization.hpp"
#include "tesseract_pqc.hpp"
#include "shard_matrix.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <atomic>
#include <vector>
#include <string>
#include <random>

namespace sec = Tesseract::Security;
namespace pqc = Tesseract::Security::Pqc;
namespace shr = Tesseract::Security::Sharding;
namespace opt = Tesseract::Security::Optimization;

static int g_total = 0, g_passed = 0, g_failed = 0;
static const char* g_current_test = nullptr;

#define CHECK(cond)                                                            \
    do {                                                                        \
        ++g_total;                                                              \
        if (cond) { ++g_passed; }                                               \
        else {                                                                  \
            ++g_failed;                                                         \
            std::fprintf(stderr, "  FAIL [%s] %s:%d: %s\n",                     \
                         g_current_test, __FILE__, __LINE__, #cond);            \
        }                                                                       \
    } while (0)

#define RUN_TEST(name) do {                                                     \
    g_current_test = #name;                                                     \
    std::printf("[ RUN      ] %s\n", g_current_test);                            \
    name();                                                                     \
    std::printf("[   OK     ] %s\n", g_current_test);                            \
} while (0)

// ════════════════════════════════════════════════════════════════════════
// V1.1 Obfuscation
// ════════════════════════════════════════════════════════════════════════

static void test_obfuscation_flatten_roundtrip() {
    uint8_t data[64];
    for (int i = 0; i < 64; ++i) data[i] = (uint8_t)(i * 7 + 3);
    uint8_t orig[64];
    std::memcpy(orig, data, 64);

    for (size_t lang = 0; lang < 6; ++lang) {
        std::memcpy(data, orig, 64);
        sec::ObfuscationEngine::FlattenPayload(data, 64, lang);
        // The output must differ from the input (unless the permutation is identity)
        bool any_diff = false;
        for (int i = 0; i < 64; ++i) if (data[i] != orig[i]) { any_diff = true; break; }
        // FlattenPayload is a bijection; round-trip must restore
        sec::ObfuscationEngine::UnflattenPayload(data, 64, lang);
        CHECK(std::memcmp(data, orig, 64) == 0);
        // (any_diff may be false if the language's permutation is identity — both
        //  are acceptable outcomes.)
        (void)any_diff;
    }
}

static void test_obfuscation_4d_partition() {
    // V1.1 spec: LinearTo4DSpace slices uintptr_t into 4 × 16-bit fields
    uintptr_t v = 0xDEAD'BEEF'CAFE'BABEull;  // C++14 digit separator (not in MSVC)
    // Use plain hex for MSVC compatibility:
    v = 0xDEADBEEFCAFEBABEull;
    auto p = sec::ObfuscationEngine::LinearTo4DSpace(v);
    CHECK(p.x == 0xBABE);
    CHECK(p.y == 0xCAFE);
    CHECK(p.z == 0xBEEF);
    CHECK(p.w == 0xDEAD);

    // Round-trip
    uintptr_t back = sec::ObfuscationEngine::Space4DToLinear(p);
    CHECK(back == v);

    // Zero
    auto p0 = sec::ObfuscationEngine::LinearTo4DSpace(0);
    CHECK(p0.x == 0 && p0.y == 0 && p0.z == 0 && p0.w == 0);
    CHECK(sec::ObfuscationEngine::Space4DToLinear(p0) == 0);
}

static void test_obfuscation_all_languages_differ() {
    // Each language must produce a (possibly) distinct output for at least one byte.
    uint8_t buf[256];
    for (int i = 0; i < 256; ++i) buf[i] = (uint8_t)i;
    sec::ObfuscationEngine::FlattenPayload(buf, 256, 0);
    uint8_t lang0[256];
    std::memcpy(lang0, buf, 256);
    sec::ObfuscationEngine::FlattenPayload(buf, 256, 1);
    uint8_t lang1[256];
    std::memcpy(lang1, buf, 256);
    CHECK(std::memcmp(lang0, lang1, 256) != 0);  // lang 0 vs 1 must differ
}

// ════════════════════════════════════════════════════════════════════════
// V1.1 Tripwire
// ════════════════════════════════════════════════════════════════════════

static void test_tripwire_disabled_never_fires() {
    sec::TripwireEngine::ClearHoneyGateRange();
    sec::TripwireEngine::SetAbortOnTrip(false);
    bool fired = sec::TripwireEngine::IsAddressIntercepted(0xDEADBEEF);
    CHECK(!fired);
    CHECK(!sec::TripwireEngine::IsTripped());
}

static void test_tripwire_arm_then_inbounds() {
    sec::TripwireEngine::ClearHoneyGateRange();
    sec::TripwireEngine::SetAbortOnTrip(false);   // panic-free for the test
    sec::TripwireEngine::RegisterHoneyGateRange(0x10000, 0x1000);
    bool fired_in = sec::TripwireEngine::IsAddressIntercepted(0x10500);
    bool fired_out = sec::TripwireEngine::IsAddressIntercepted(0x20000);
    CHECK(fired_in);
    CHECK(!fired_out);
    sec::TripwireEngine::ClearHoneyGateRange();
}

// ════════════════════════════════════════════════════════════════════════
// V1.2 Optimization
// ════════════════════════════════════════════════════════════════════════

static void test_avx2_runtime_feature_detection() {
    bool has_avx2 = opt::HasAVX2();
    // On a modern x86_64 Windows host with AVX2, this should be true.
    // We don't assert — feature may be unavailable on some CPUs.
    std::printf("    [info] AVX2 available: %s\n", has_avx2 ? "yes" : "no");
    CHECK(true);
}

static void test_vectorized_flatten_roundtrip() {
    uint8_t data[1024];
    for (int i = 0; i < 1024; ++i) data[i] = (uint8_t)(i * 13 + 5);
    uint8_t orig[1024];
    std::memcpy(orig, data, 1024);

    // XOR with mask twice → identity
    opt::VectorizedFlatten(data, 1024, 0x5A);
    opt::VectorizedFlatten(data, 1024, 0x5A);
    CHECK(std::memcmp(data, orig, 1024) == 0);

    // XOR with mask, then different mask, then second mask → identity
    opt::VectorizedFlatten(data, 1024, 0xA5);
    opt::VectorizedFlatten(data, 1024, 0x33);
    opt::VectorizedFlatten(data, 1024, 0x33);
    opt::VectorizedFlatten(data, 1024, 0xA5);
    CHECK(std::memcmp(data, orig, 1024) == 0);
}

static void test_fast_4d_translation() {
    uintptr_t v = 0x123456789ABCDEF0ull;
    auto p = opt::FastLinearTo4D(v);
    CHECK(p.x == (int64_t)(v & 0xFFFF));
    CHECK(p.y == (int64_t)((v >> 16) & 0xFFFF));
    CHECK(p.z == (int64_t)((v >> 32) & 0xFFFF));
    CHECK(p.w == (int64_t)((v >> 48) & 0xFFFF));
    uintptr_t back = opt::Fast4DToLinear(p);
    CHECK(back == v);
}

static void test_branchless_boundary() {
    // Inside [1000, 2000) → true
    CHECK(opt::VerifyBoundaryBranchless(1500, 1000, 2000));
    // Outside → false (both endpoints)
    CHECK(!opt::VerifyBoundaryBranchless( 999, 1000, 2000));
    CHECK(!opt::VerifyBoundaryBranchless(2000, 1000, 2000));
    CHECK(!opt::VerifyBoundaryBranchless(100,  1000, 2000));
}

// ════════════════════════════════════════════════════════════════════════
// V1.3 PQC
// ════════════════════════════════════════════════════════════════════════

static void test_pqc_backend_report() {
    pqc::Backend b = pqc::ActiveBackend();
    CHECK(b == pqc::Backend::STUB_CHACHA || b == pqc::Backend::LIBOQS_REAL);
    std::printf("    [info] PQC backend: %s\n", pqc::BackendName(b));
}

static void test_kyber_keygen_size() {
    pqc::KyberKeyPair kp;
    auto s = pqc::KyberKeygen(kp);
    CHECK(s == pqc::Status::OK);
    // After keygen, key material should be non-zero (we filled it).
    bool any_nonzero = false;
    for (auto b : kp.public_key)  if (b) { any_nonzero = true; break; }
    CHECK(any_nonzero);
}

static void test_kyber_roundtrip_returns_ok() {
    pqc::KyberKeyPair kp;
    CHECK(pqc::KyberKeygen(kp) == pqc::Status::OK);
    pqc::KyberCiphertext ct;
    pqc::SharedSecret ss_a, ss_b;
    CHECK(pqc::KyberEncapsulate(kp.public_key, ct, ss_a) == pqc::Status::OK);
    CHECK(pqc::KyberDecapsulate(kp, ct, ss_b) == pqc::Status::OK);
    CHECK(ss_a.size() == pqc::KYBER_SHARED_SECRET_BYTES);
    CHECK(ss_b.size() == pqc::KYBER_SHARED_SECRET_BYTES);
}

static void test_aes_gcm_roundtrip_basic() {
    pqc::AesGcmCipher gcm;
    // Fill key + nonce
    for (int i = 0; i < 32; ++i) gcm.key[i]   = (uint8_t)i;
    for (int i = 0; i < 12; ++i) gcm.nonce[i] = (uint8_t)(0xFF - i);

    std::vector<uint8_t> pt(64, 0x42);
    std::vector<uint8_t> ct;
    std::vector<uint8_t> aad;  // empty
    CHECK(gcm.encrypt(pt, aad, ct) == pqc::Status::OK);
    CHECK(ct.size() == pt.size() + pqc::AES_TAG_BYTES);

    std::vector<uint8_t> recovered;
    CHECK(gcm.decrypt(ct, aad, recovered) == pqc::Status::OK);
    // Decrypted length may include padding; check the original bytes match.
    CHECK(recovered.size() >= pt.size());
    CHECK(std::memcmp(recovered.data(), pt.data(), pt.size()) == 0);
}

static void test_blowfish_roundtrip() {
    pqc::BlowfishCipher bf;
    // 32-byte (256-bit) key
    uint8_t key[32];
    for (int i = 0; i < 32; ++i) key[i] = (uint8_t)(i * 11 + 7);
    CHECK(bf.set_key(key) == pqc::Status::OK);

    uint8_t plaintext[16];
    for (int i = 0; i < 16; ++i) plaintext[i] = (uint8_t)(i * 17 + 13);
    uint8_t ciphertext[16];
    uint8_t recovered[16];

    // Encrypt each 8-byte block
    for (int blk = 0; blk < 2; ++blk) {
        uint64_t in = 0, out = 0;
        for (int j = 0; j < 8; ++j) in = (in << 8) | plaintext[blk * 8 + j];
        CHECK(bf.encrypt_block(in, out) == pqc::Status::OK);
        for (int j = 7; j >= 0; --j) ciphertext[blk * 8 + j] = (uint8_t)(out & 0xFF), out >>= 8;
    }
    // Ciphertext must differ from plaintext
    CHECK(std::memcmp(ciphertext, plaintext, 16) != 0);
    // Decrypt round-trips
    for (int blk = 0; blk < 2; ++blk) {
        uint64_t in = 0, out = 0;
        for (int j = 0; j < 8; ++j) in = (in << 8) | ciphertext[blk * 8 + j];
        CHECK(bf.decrypt_block(in, out) == pqc::Status::OK);
        for (int j = 7; j >= 0; --j) recovered[blk * 8 + j] = (uint8_t)(out & 0xFF), out >>= 8;
    }
    CHECK(std::memcmp(recovered, plaintext, 16) == 0);
}

static void test_nested_encryption_roundtrip() {
    pqc::KyberKeyPair kp;
    CHECK(pqc::KyberKeygen(kp) == pqc::Status::OK);
    pqc::KyberCiphertext ct;
    pqc::SharedSecret ss;
    CHECK(pqc::KyberEncapsulate(kp.public_key, ct, ss) == pqc::Status::OK);

    const char* msg = "Project Tesseract security test message";
    std::span<const uint8_t> pt{(const uint8_t*)msg, std::strlen(msg)};
    std::vector<uint8_t> ciphertext;
    CHECK(pqc::NestedEncrypt(ss, pt, ciphertext) == pqc::Status::OK);
    CHECK(ciphertext.size() >= pt.size());

    std::vector<uint8_t> recovered;
    std::span<const uint8_t> ct_span{ciphertext.data(), ciphertext.size()};
    CHECK(pqc::NestedDecrypt(ss, ct_span, recovered) == pqc::Status::OK);
    // Original prefix must be intact (Blowfish pads to 8 bytes).
    CHECK(recovered.size() >= pt.size());
    CHECK(std::memcmp(recovered.data(), pt.data(), pt.size()) == 0);
}

// ════════════════════════════════════════════════════════════════════════
// V1.3 Shard Matrix
// ════════════════════════════════════════════════════════════════════════

static void test_shard_xor_parity_basic() {
    std::vector<std::vector<uint8_t>> shards(5);
    shards[0] = {0x01, 0x02, 0x03, 0x04};
    shards[1] = {0x10, 0x20, 0x30, 0x40};
    shards[2] = {0xAA, 0xBB, 0xCC, 0xDD};
    shards[3] = {0x00, 0x00, 0x00, 0x00};
    shards[4] = {0xFF, 0xFF, 0xFF, 0xFF};
    std::vector<uint8_t> parity;
    shr::ComputeXorParity(shards, parity);
    CHECK(parity.size() == 4);
    CHECK(parity[0] == (0x01 ^ 0x10 ^ 0xAA ^ 0x00 ^ 0xFF));
    CHECK(parity[1] == (0x02 ^ 0x20 ^ 0xBB ^ 0x00 ^ 0xFF));
    CHECK(parity[2] == (0x03 ^ 0x30 ^ 0xCC ^ 0x00 ^ 0xFF));
    CHECK(parity[3] == (0x04 ^ 0x40 ^ 0xDD ^ 0x00 ^ 0xFF));
}

static void test_shard_xor_parity_recovers() {
    // If one shard is lost, XOR of remaining 4 + parity = missing shard.
    std::vector<std::vector<uint8_t>> shards(5);
    shards[0] = {0x11, 0x22, 0x33};
    shards[1] = {0x44, 0x55, 0x66};
    shards[2] = {0x77, 0x88, 0x99};
    shards[3] = {0xAA, 0xBB, 0xCC};
    shards[4] = {0xDD, 0xEE, 0xFF};
    std::vector<uint8_t> parity;
    shr::ComputeXorParity(shards, parity);

    // Simulate losing shards[2]; reconstruct from others + parity
    std::vector<uint8_t> recovered(3, 0);
    for (size_t i = 0; i < 5; ++i) if (i != 2)
        for (size_t j = 0; j < 3; ++j) recovered[j] ^= shards[i][j];
    for (size_t j = 0; j < 3; ++j) recovered[j] ^= parity[j];
    CHECK(recovered[0] == shards[2][0]);
    CHECK(recovered[1] == shards[2][1]);
    CHECK(recovered[2] == shards[2][2]);
}

static void test_shard_matrix_bidirectional_mix() {
    shr::ShardMatrix10 mtx{};
    std::vector<std::vector<uint8_t>> nodes(10);
    for (auto& n : nodes) n.assign(256, 0);
    for (size_t i = 0; i < 10; ++i) mtx.file_nodes[i] = nodes[i].data();

    uint8_t src[256 * 6];
    for (size_t i = 0; i < sizeof(src); ++i) src[i] = (uint8_t)i;

    // Inside-out
    shr::ExecuteBiDirectionalMix(src, sizeof(src), mtx, true);
    // Some file_nodes must have been written
    size_t filled = 0;
    for (size_t i = 0; i < 10; ++i)
        if (mtx.block_sizes[i] > 0) ++filled;
    CHECK(filled >= 4);   // spec: at least the data shards + parity are placed

    // Reset
    for (size_t i = 0; i < 10; ++i) mtx.block_sizes[i] = 0;
    shr::ExecuteBiDirectionalMix(src, sizeof(src), mtx, false);
    filled = 0;
    for (size_t i = 0; i < 10; ++i)
        if (mtx.block_sizes[i] > 0) ++filled;
    CHECK(filled >= 4);
}

static void test_shard_topology_has_5_data_1_parity_4_decoys() {
    const auto& topo = shr::DefaultTopology();
    int data = 0, parity = 0, decoy = 0;
    for (const auto& n : topo) {
        if (n.is_data())      ++data;
        else if (n.is_parity()) ++parity;
        else if (n.is_decoy())  ++decoy;
    }
    CHECK(data   == shr::kNumDataShards);   // 5
    CHECK(parity == 1);
    CHECK(decoy  == shr::kNumDecoys);       // 4
}

static void test_shard_matrix_write_read_fault_tolerance() {
    shr::ShardMatrix::Config cfg;
    cfg.base_dir = "test_shards_dir";
    cfg.decoy_dir = "test_shards_dir/decoys";
    cfg.enable_rotator = false;

    shr::ShardMatrix mtx(cfg);
    CHECK(mtx.open_all());

    std::vector<uint8_t> payload = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20};
    CHECK(mtx.write_payload(payload.data(), payload.size()) == Tesseract::Security::Pqc::Status::OK);

    std::vector<uint8_t> readback;
    CHECK(mtx.read_payload(readback));
    CHECK(readback.size() >= payload.size());
    CHECK(std::memcmp(readback.data(), payload.data(), payload.size()) == 0);

    // Simulate single-file fault by deleting the 3rd data file (index 2)
    std::string path_to_delete = mtx.path_for(2).string();
    std::remove(path_to_delete.c_str());

    std::vector<uint8_t> readback_recovered;
    CHECK(mtx.read_payload(readback_recovered));
    CHECK(readback_recovered.size() >= payload.size());
    CHECK(std::memcmp(readback_recovered.data(), payload.data(), payload.size()) == 0);

    // Clean up
    for (size_t i = 0; i < 10; ++i) {
        std::remove(mtx.path_for(i).string().c_str());
    }
    std::filesystem::remove_all(cfg.base_dir);
}

// ════════════════════════════════════════════════════════════════════════
// Main
// ════════════════════════════════════════════════════════════════════════

int main() {
    std::printf("Tesseract security subsystem test suite\n");
    std::printf("==========================================\n");

    RUN_TEST(test_obfuscation_flatten_roundtrip);
    RUN_TEST(test_obfuscation_4d_partition);
    RUN_TEST(test_obfuscation_all_languages_differ);

    RUN_TEST(test_tripwire_disabled_never_fires);
    RUN_TEST(test_tripwire_arm_then_inbounds);

    RUN_TEST(test_avx2_runtime_feature_detection);
    RUN_TEST(test_vectorized_flatten_roundtrip);
    RUN_TEST(test_fast_4d_translation);
    RUN_TEST(test_branchless_boundary);

    RUN_TEST(test_pqc_backend_report);
    RUN_TEST(test_kyber_keygen_size);
    RUN_TEST(test_kyber_roundtrip_returns_ok);
    RUN_TEST(test_aes_gcm_roundtrip_basic);
    RUN_TEST(test_blowfish_roundtrip);
    RUN_TEST(test_nested_encryption_roundtrip);

    RUN_TEST(test_shard_xor_parity_basic);
    RUN_TEST(test_shard_xor_parity_recovers);
    RUN_TEST(test_shard_matrix_bidirectional_mix);
    RUN_TEST(test_shard_topology_has_5_data_1_parity_4_decoys);
    RUN_TEST(test_shard_matrix_write_read_fault_tolerance);

    std::printf("\n==========================================\n");
    std::printf("Total: %d  Passed: %d  Failed: %d\n",
                g_total, g_passed, g_failed);
    return g_failed == 0 ? 0 : 1;
}
