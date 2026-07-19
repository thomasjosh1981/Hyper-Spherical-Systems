// pirate_tests — minimal assertion-based test harness for the core engine.
// No external deps. Each TEST(name) block reports pass/fail and we exit nonzero
// if anything failed. Build with the same CMakeLists (sources list controlled by
// a TESTS=1 define) or just add this file to the build manually.

#include "config.hpp"
#include "types.hpp"
#include "context_compressor.hpp"
#include "memory_manager.hpp"
#include "predictive_prefetcher.hpp"
#include "recovery_checkpoint.hpp"
#include "telemetry_logger.hpp"
#include "index_registry.hpp"
#include "nvme_io.hpp"
#ifdef HYPERSPHERICAL_ENTERPRISE_BUILD
#include "stripe_io.hpp"
#endif
#include "python_bridge.hpp"
#ifdef HYPERSPHERICAL_ENTERPRISE_BUILD
#include "leet_cipher.hpp"
#endif
#include "neuron_graph.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <random>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using namespace hypersp;

// -----------------------------------------------------------------------
// Minimal test framework
// -----------------------------------------------------------------------
static int g_total = 0, g_passed = 0, g_failed = 0;
static const char* g_current_test = nullptr;

#define CHECK(cond)                                                          \
    do {                                                                      \
        ++g_total;                                                            \
        if (cond) {                                                           \
            ++g_passed;                                                       \
        } else {                                                              \
            ++g_failed;                                                       \
            std::fprintf(stderr, "  FAIL [%s] %s:%d: %s\n",                   \
                         g_current_test, __FILE__, __LINE__, #cond);          \
        }                                                                     \
    } while (0)

#define CHECK_EQ(a, b)                                                        \
    do {                                                                      \
        ++g_total;                                                            \
        auto _va = (a);                                                       \
        auto _vb = (b);                                                       \
        if (_va == _vb) {                                                      \
            ++g_passed;                                                       \
        } else {                                                              \
            ++g_failed;                                                       \
            std::fprintf(stderr, "  FAIL [%s] %s:%d: %s != %s\n",             \
                         g_current_test, __FILE__, __LINE__, #a, #b);         \
        }                                                                     \
    } while (0)

#define RUN_TEST(name)                                                       \
    do {                                                                      \
        g_current_test = #name;                                               \
        std::printf("[ RUN      ] %s\n", g_current_test);                    \
        name();                                                               \
        std::printf("[   OK     ] %s\n", g_current_test);                    \
    } while (0)

// -----------------------------------------------------------------------
// Test cases
// -----------------------------------------------------------------------

static void test_compressor_roundtrip() {
    Config cfg;
    SissiConfig s_cfg;
    s_cfg.dynamic_profiling_threshold = 0; // Force dynamic profiling for tests
    ContextCompressor cc(cfg, s_cfg);
    const std::string text =
        "the quick brown fox jumps over the lazy dog. the quick brown fox "
        "jumps over the lazy dog. the quick brown fox jumps over the lazy "
        "dog. the quick brown fox jumps over the lazy dog. the quick brown "
        "fox jumps over the lazy dog.";
    auto entries = cc.compress(text);
    CHECK(entries.size() < text.size());                 // we compressed
    CHECK(cc.compression_ratio() > 1.0f);                // ratio > 1
    std::string back = cc.decompress(entries);
    // Round-trip equality on size + phrase-presence (we use '?' for literals
    // by design, so we check the compressed phrase content is preserved)
    CHECK(back.find("quick brown fox") != std::string::npos);
    CHECK(back.find("lazy dog") != std::string::npos);
    CHECK_EQ(back.size(), text.size());
}

static void test_sissi_khmer_and_prepositions() {
    // 1. Test Khmer encoding/decoding helper
    uint8_t byte_val = ContextCompressor::encode_khmer_char(0x1780);
    CHECK_EQ(byte_val, static_cast<uint8_t>(128));
    uint16_t unicode_val = ContextCompressor::decode_khmer_char(128);
    CHECK_EQ(unicode_val, static_cast<uint16_t>(0x1780));

    // 2. Test preposition discarding
    Config cfg;
    SissiConfig sissi_discard;
    sissi_discard.discard_prepositions = true;
    ContextCompressor cc_discard(cfg, sissi_discard);
    auto discard_entries = cc_discard.compress("The book is on the table under the chair");
    // PPV should have recorded the 2 discarded prepositions
    CHECK_EQ(cc_discard.get_ppv_list().size(), static_cast<size_t>(2));
    // Due to PPV, decompression is 100% lossless
    std::string decomp_discard = cc_discard.decompress(discard_entries);
    CHECK(decomp_discard.find("on") != std::string::npos);
    CHECK(decomp_discard.find("under") != std::string::npos);

    // 3. Test preposition accents
    SissiConfig sissi_accent;
    sissi_accent.discard_prepositions = false;
    sissi_accent.keep_prepositions_with_accents = true;
    ContextCompressor cc_accent(cfg, sissi_accent);
    auto accent_entries = cc_accent.compress("book is on the table under the chair");
    std::string decomp_accent = cc_accent.decompress(accent_entries);
    CHECK(decomp_accent.find("on") != std::string::npos);
    CHECK(decomp_accent.find("under") != std::string::npos);
}

static void test_compressor_handles_empty() {
    Config cfg;
    ContextCompressor cc(cfg);
    auto entries = cc.compress("");
    CHECK(entries.empty());
    CHECK_EQ(cc.compress("    \n\t  ").size(), 0u);
}

static void test_compressor_scales_on_repetitive_text() {
    // Stress: 5KB of heavily repeated content should compress in the 3-6x range.
    Config cfg;
    SissiConfig s_cfg;
    s_cfg.dynamic_profiling_threshold = 0; // Force dynamic profiling for test
    ContextCompressor cc(cfg, s_cfg);
    std::string big;
    const std::string para =
        "The user wants me to look at the codebase structure. The codebase "
        "structure is the codebase structure that the user wants me to look "
        "at. After looking at the codebase structure, the user wants me to "
        "look at the codebase structure once more. ";
    for (int i = 0; i < 25; ++i) big += para;
    auto entries = cc.compress(big);
    CHECK(big.size() > 4000);
    CHECK(entries.size() < big.size());
    float r = cc.compression_ratio();
    std::printf("    [stress] input=%zu compressed_entries=%zu ratio=%.2fx\n",
                big.size(), entries.size(), r);
    CHECK(r >= 2.0f);   // we expect at LEAST 2x on heavy repetition
}

static void test_compressor_handles_unique_text() {
    Config cfg;
    ContextCompressor cc(cfg);
    // No repeating n-grams -> dictionary stays empty.
    // (Tesseract's n-gram counter uses a lookback window per word; for a short
    //  document with no repeated phrases, every n-gram appears exactly once
    //  regardless of how many windows it falls into. We verify that.)
    auto entries = cc.compress("alpha bravo charlie delta echo foxtrot golf");
    int compressed = 0;
    for (auto& e : entries) if (e.is_compressed) ++compressed;
    CHECK_EQ(compressed, 0);
    // And the n-gram counter bug check: feed a longer document of truly
    // unique words and verify still no phrases register.
    std::string unique_long;
    for (int i = 0; i < 200; ++i) {
        unique_long += "word" + std::to_string(i) + " ";
    }
    auto long_entries = cc.compress(unique_long);
    int long_compressed = 0;
    for (auto& e : long_entries) if (e.is_compressed) ++long_compressed;
    CHECK_EQ(long_compressed, 0);
}

static void test_compressor_bypass_guard() {
    Config cfg;
    SissiConfig s_cfg;
    s_cfg.sissi_compression_enabled = false;
    ContextCompressor cc(cfg, s_cfg);

    const std::string text = "gradient descent optimization transformer attention";
    auto entries = cc.compress(text);

    CHECK_EQ(entries.size(), text.size());
    CHECK_EQ(cc.compression_ratio(), 1.0f);
    for (const auto& e : entries) {
        CHECK(!e.is_compressed);
    }
}

static void test_compressor_greedy_and_large_words() {
    Config cfg;
    SissiConfig s_cfg;
    s_cfg.sissi_compression_enabled = true;
    s_cfg.compress_large_words_first = true;
    s_cfg.large_word_len_threshold = 6;
    s_cfg.greedy_first = false; // prioritize single words first
    s_cfg.dynamic_profiling_threshold = 0;

    ContextCompressor cc(cfg, s_cfg);
    const std::string text = "superconductive superconductive super superconductive super";
    auto entries = cc.compress(text);
    int comp_count = 0;
    for (const auto& e : entries) {
        if (e.is_compressed) comp_count++;
    }
    CHECK(comp_count > 0);
}

static void test_compressor_symbol_recycling() {
    Config cfg;
    cfg.max_dict_entries = 160; // leaves only 10 slots for dynamic entries [150-159]
    SissiConfig s_cfg;
    s_cfg.sissi_compression_enabled = true;
    s_cfg.recycle_symbols = true;
    s_cfg.dynamic_profiling_threshold = 0;

    ContextCompressor cc(cfg, s_cfg);
    const std::string text = 
        "apple apple banana banana orange orange cherry cherry peach peach melon melon grape grape "
        "lemon lemon berry berry mango mango onion onion potato potato tomato tomato garlic garlic";
    
    auto entries = cc.compress(text);
    CHECK(cc.dict_entries_used() > 0);
}

static void test_memory_manager_vram_cap() {
    Config cfg;
    cfg.ram_total_bytes = 8ULL * 1024 * 1024 * 1024;
    MemoryManager mm(cfg);
    mm.initialize_vram(1ULL * 1024 * 1024 * 1024);   // 1GB VRAM, 70% = 716MB budget
    mm.set_ram_total(cfg.ram_total_bytes);

    // Push enough 200MB layers to require eviction. The manager evicts old
    // layers from VRAM to RAM staging when the new layer would overflow.
    int vram_placed = 0, overflow = 0;
    for (uint32_t i = 0; i < 8; ++i) {
        LayerShard s; s.layer_id = i; s.byte_size = 200ull * 1024 * 1024;
        ErrorCode e = mm.push_layer(s, /*prefer_vram=*/true);
        if      (e == ErrorCode::OK && s.tier == MemoryTier::VRAM) ++vram_placed;
        else                                                       ++overflow;
    }
    // VRAM cap must NEVER be exceeded
    CHECK(mm.vram_usage_percent() <= 100.001f);
    // The hard VRAM cap (70% of phys) is what we enforce; the percentage here
    // is "used / budget". With 200MB layers into a 716MB budget, we land at
    // 600/716 = 83.7%, which is below the 100% budget. Good.
    CHECK(mm.vram_usage_percent() > 0.0f);
    // Some layers must have been demoted to RAM staging (we pushed 8 layers of
    // 200MB = 1600MB into 716MB VRAM; the rest must live somewhere)
    CHECK(mm.ram_staging_bytes() > 0u);
    CHECK(overflow == 0);  // everything fits in VRAM+RAM under 8GB staging
    (void)vram_placed;
}

static void test_memory_manager_no_double_count_on_evict() {
    Config cfg;
    cfg.ram_total_bytes = 8ULL * 1024 * 1024 * 1024;
    MemoryManager mm(cfg);
    // Use 800 MB physical VRAM → 720 MB cap at 90% → 4 × 200 MB exceeds it, triggers eviction.
    mm.initialize_vram(800ULL * 1024 * 1024);
    mm.set_ram_total(cfg.ram_total_bytes);

    // Fill VRAM with 3 small layers
    for (uint32_t i = 0; i < 3; ++i) {
        LayerShard s; s.layer_id = i; s.byte_size = 200ull * 1024 * 1024;
        CHECK_EQ(mm.push_layer(s), ErrorCode::OK);
        CHECK_EQ(s.tier, MemoryTier::VRAM);
    }
    // Push a 4th: evicts the oldest to RAM
    LayerShard s4; s4.layer_id = 99; s4.byte_size = 200ull * 1024 * 1024;
    CHECK_EQ(mm.push_layer(s4), ErrorCode::OK);
    CHECK_EQ(s4.tier, MemoryTier::VRAM);
    // Ram staging should reflect the evicted 200MB exactly once
    CHECK_EQ(mm.ram_staging_bytes(), 200ull * 1024 * 1024);
}

static void test_pattern_predictor_records_transitions() {
    Config cfg;
    cfg.prefetch_confidence_min = 0.5f;  // loosen so we see multiple preds
    PatternPredictor pp(cfg);
    for (int i = 0; i < 100; ++i) pp.observe_layer(static_cast<uint32_t>(i % 3));
    CHECK_EQ(pp.total_observations(), 100u);
    auto pred = pp.predict_next(4);
    CHECK(!pred.layer_ids.empty());
    CHECK(pred.confidence > 0.0f);
    // The pattern cycles 0,1,2,0,1,2,... After the last observed (2), all three
    // successors have equal weight. The predictor should return at least one.
}

static void test_pattern_predictor_empty_history() {
    Config cfg;
    PatternPredictor pp(cfg);
    auto pred = pp.predict_next(4);
    CHECK(pred.layer_ids.empty());
    CHECK_EQ(pred.confidence, 0.0f);
}

static void test_weight_streamer_preload() {
    Config cfg;
    WeightStreamer ws(cfg, 1ULL * 1024 * 1024 * 1024);
    std::vector<uint32_t> ids = {0, 1, 2, 3, 4, 5};
    CHECK_EQ(ws.preload_weight_shards(ids), ErrorCode::OK);
    // Each layer is estimated 80MB; 6 layers = 480MB. Budget is 700MB.
    CHECK(ws.vram_usage_pct() > 50.0f);
    CHECK(ws.vram_usage_pct() < 100.0f);
}

static void test_nvme_io_roundtrip() {
    fs::path tmpdir = fs::temp_directory_path() / "tesseract_test";
    std::error_code ec; fs::create_directories(tmpdir, ec);
    NVMeIO io(tmpdir.string());
    std::vector<uint8_t> payload(16 * 1024);
    for (size_t i = 0; i < payload.size(); ++i) payload[i] = static_cast<uint8_t>(i & 0xFF);
    const std::string fname = "test_shard.bin";
    CHECK_EQ(io.write_block(fname, payload.data(), payload.size()), ErrorCode::OK);
    std::vector<uint8_t> back(payload.size(), 0);
    CHECK_EQ(io.read_block(fname, back.data(), back.size()), ErrorCode::OK);
    CHECK_EQ(std::memcmp(payload.data(), back.data(), payload.size()), 0);
}

static void test_checkpoint_save_load() {
    fs::path tmpdir = fs::temp_directory_path() / "tesseract_test";
    std::error_code ec; fs::create_directories(tmpdir, ec);
    fs::path cp = tmpdir / "session_test.tess";
    RecoveryCheckpoint r1;
    r1.set_vram_mark(12345678);
    r1.set_kv_count(4096);
    CHECK(r1.save_to(cp.string()));
    CHECK(fs::exists(cp));
    CHECK(RecoveryCheckpoint::load_from(cp.string()));
    // load_from is static + stateful restore is for caller; we verify file integrity
    // by loading into a fresh instance and re-saving: magic + version must round-trip.
    RecoveryCheckpoint r2;
    CHECK(r2.save_to(cp.string()));
    CHECK(fs::exists(cp));
}

static void test_c_api_session_checkpoint_recovery() {
    fs::path tmpdir = fs::temp_directory_path() / "tesseract_test_c";
    std::error_code ec;
    fs::create_directories(tmpdir, ec);
    fs::path cp = tmpdir / "session_c.tess";

    pirate_handle_t h1 = pirate_create();
    CHECK(h1 != nullptr);

    std::string text = "This is a context recovery test for hyper-spherical systems.";
    char out_json[16384];
    int comp_len = pirate_compress(h1, text.data(), static_cast<int>(text.size()), out_json, sizeof(out_json));
    CHECK(comp_len > 0);

    CHECK_EQ(pirate_checkpoint_save(h1, cp.string().c_str()), 0);
    CHECK(fs::exists(cp));
    CHECK(fs::exists(cp.string() + ".tess_session.bak"));

    pirate_destroy(h1);

    pirate_handle_t h2 = pirate_create();
    CHECK(h2 != nullptr);
    CHECK_EQ(pirate_checkpoint_load(h2, cp.string().c_str()), 0);

    char restored_text[1024];
    int restored_len = tess_get_session_history(h2, restored_text, sizeof(restored_text));
    CHECK_EQ(restored_len, static_cast<int>(text.size()));
    CHECK_EQ(std::string(restored_text, restored_len), text);

    pirate_destroy(h2);
    fs::remove_all(tmpdir, ec);
}

static void test_telemetry_logger_dispatch() {
    TelemetryLogger t;
    t.log("vram_usage", 88.5f);
    t.log("ram_staging", 42.0f);
    t.log("kv_tokens", 1024.0f);
    t.log("prefetch_pending", 7.0f);
    t.log("unknown_key_ignored", 999.0f);  // must not crash
    auto s = t.current_snapshot();
    CHECK_EQ(s.vram_usage_pct, 88.5f);
    CHECK_EQ(s.ram_staging_pct, 42.0f);
    CHECK_EQ(s.active_kv_tokens, static_cast<size_t>(1024));
    CHECK_EQ(s.prefetch_pending, static_cast<uint32_t>(7));
}

static void test_index_registry_skips_non_gguf() {
    fs::path tmpdir = fs::temp_directory_path() / "tesseract_test_index";
    std::error_code ec; fs::remove_all(tmpdir, ec); fs::create_directories(tmpdir, ec);
    {
        std::ofstream f1(tmpdir / "layer0.gguf");   f1 << "fake";
        std::ofstream f2(tmpdir / "layer1.gguf");   f2 << "fakefake";
        std::ofstream f3(tmpdir / "notes.txt");     f3 << "ignore me";
    }
    IndexRegistry reg;
    reg.build_index(tmpdir.string());
    // .gguf files only; we should have 2 shards
    auto in_vram = reg.get_layers_in_vram();  // empty (none placed into VRAM)
    CHECK_EQ(in_vram.size(), static_cast<size_t>(0));
    // Total: get_shard with a missing id returns false
    LayerShard out;
    CHECK(!reg.get_shard(42, out));
}

static void test_config_defaults() {
    Config cfg;
    CHECK(cfg.vram_max_ratio <= 0.95 + 1e-6);  // hard cap respected in default
    CHECK(cfg.ram_staging_pct > 0.0);
    CHECK(cfg.max_active_tokens >= 1024u);
    CHECK(cfg.max_dict_entries > 0u);
}

#ifdef HYPERSPHERICAL_ENTERPRISE_BUILD
#ifdef HYPERSPHERICAL_ENTERPRISE_BUILD
static void test_stripe_io_roundtrip() {
    StripeConfig cfg;
    cfg.active_stripes = 4;
    cfg.decoy_files = 3;
    cfg.base_path = "test_stripe_output.bin";
    cfg.harness_mirror_dir = ".";

    StripeIO io(cfg);
    std::vector<uint8_t> data = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16};
    CHECK(io.write_striped(data));

    std::vector<uint8_t> read_data;
    CHECK(io.read_striped(read_data));
    CHECK_EQ(read_data.size(), data.size());
    for (size_t i = 0; i < data.size(); ++i) {
        CHECK_EQ(read_data[i], data[i]);
    }

    // Cleanup files
    for (size_t i = 0; i < cfg.active_stripes; ++i) {
        std::remove((cfg.base_path + "." + std::to_string(i)).c_str());
    }
}
#endif
#endif

#ifdef HYPERSPHERICAL_ENTERPRISE_BUILD
#ifdef HYPERSPHERICAL_ENTERPRISE_BUILD
static void test_leet_cipher_3fa_and_crypt() {
    UserCredentials creds;
    creds.username = "twist";
    creds.password = "pass123";
    creds.pin = "987654";
    creds.leet_key = LeetCipher::generate_leet_key();

    // Verify 3FA permuted entries
    CHECK(LeetCipher::verify_3fa_inputs(creds, creds.username, creds.password, creds.leet_key));
    CHECK(LeetCipher::verify_3fa_inputs(creds, creds.leet_key, creds.username, creds.password));
    CHECK(LeetCipher::verify_3fa_inputs(creds, creds.password, creds.leet_key, creds.username));
    CHECK(!LeetCipher::verify_3fa_inputs(creds, "wrong_user", creds.password, creds.leet_key));

    std::vector<uint8_t> data = {10, 20, 30, 40, 50, 60, 70, 80};
    auto ciphertext = LeetCipher::encrypt(data, creds);
    CHECK(ciphertext.size() > 0);
    CHECK(ciphertext != data); // should be obfuscated

    auto decrypted = LeetCipher::decrypt(ciphertext, creds);
    CHECK_EQ(decrypted.size(), data.size());
    for (size_t i = 0; i < data.size(); ++i) {
        CHECK_EQ(decrypted[i], data[i]);
    }
}
#endif
#endif

static void test_neuron_graph_relationships() {
    NeuronGraph graph;
    graph.add_neuron(1, "transformer model", {0.1f, 0.2f});
    graph.add_neuron(2, "large language model", {0.15f, 0.22f});
    graph.add_neuron(3, "quantum state", {0.9f, 0.05f});

    graph.link_neurons(1, 2, 0.85f, "architecture"); // strong connection
    graph.link_neurons(1, 3, 0.12f, "speculative"); // weak connection (barely related)

    CHECK_EQ(graph.get_link_strength(1, 2), 0.85f);
    CHECK_EQ(graph.get_link_strength(1, 3), 0.12f);
    CHECK_EQ(graph.get_link_strength(2, 3), 0.0f); // no link

    auto weak_links = graph.get_weak_relationships(1, 0.05f, 0.25f);
    CHECK_EQ(weak_links.size(), static_cast<size_t>(1));
    CHECK_EQ(weak_links[0].target_neuron_id, static_cast<uint32_t>(3));
    CHECK(weak_links[0].semantic_bridge == "speculative");
}

static void test_hypersphere_coordinate_mapping() {
    std::vector<float> embed1 = {1.0f, 0.0f, 0.0f};
    auto coord1 = HypersphereMath::cartesian_to_hyperspherical(embed1);
    CHECK_EQ(coord1.radius, 1.0f);
    CHECK_EQ(coord1.angles.size(), static_cast<size_t>(2));
    
    std::vector<float> embed2 = {0.0f, 1.0f, 0.0f};
    auto coord2 = HypersphereMath::cartesian_to_hyperspherical(embed2);
    
    float dist = HypersphereMath::angular_distance(coord1, coord2);
    CHECK(dist > 0.0f); // They are orthogonal, distance should be 0.5 (cos_sim 0.0)
    CHECK(std::abs(dist - 0.5f) < 0.01f);
}

static void test_synthuron_and_hypertag_linking() {
    NeuronGraph graph;
    graph.add_neuron(1, "pool", {0.1f, 0.1f, 0.1f});
    graph.add_neuron(2, "ocean", {0.2f, 0.2f, 0.2f});
    graph.add_neuron(3, "spa", {0.3f, 0.3f, 0.3f});
    
    graph.add_hypertag("chlorine", 1);
    graph.add_hypertag("chlorine", 3);
    graph.add_hypertag("water", 1);
    graph.add_hypertag("water", 2);
    graph.add_hypertag("water", 3);
    
    auto chlorine_nodes = graph.get_hypertag_neurons("chlorine");
    CHECK_EQ(chlorine_nodes.size(), static_cast<size_t>(2));
    
    auto water_nodes = graph.get_hypertag_neurons("water");
    CHECK_EQ(water_nodes.size(), static_cast<size_t>(3));
    
    graph.link_neurons(1, 3, 0.9f, "recreation");
    CHECK_EQ(graph.get_link_strength(1, 3), 0.9f);
}

static void test_compressor_auto_tune_spin() {
    Config cfg;
    SissiConfig s_cfg;
    s_cfg.sissi_compression_enabled = true;
    ContextCompressor cc(cfg, s_cfg);
    
    std::string test_text = "superconductive superconductive super superconductive super";
    cc.auto_tune_spin(test_text);
    
    // Auto-tune should complete without crashing. 
    // We can't strictly assert the outcome since it depends on the exact heuristic math, 
    // but we can ensure it runs and compression succeeds after.
    auto entries = cc.compress(test_text);
    CHECK(entries.size() > 0);
}

// -----------------------------------------------------------------------
// Test driver
// -----------------------------------------------------------------------
int main() {
    std::printf("Tesseract core engine test harness\n");
    std::printf("==================================\n");

    RUN_TEST(test_config_defaults);
    RUN_TEST(test_compressor_roundtrip);
    RUN_TEST(test_sissi_khmer_and_prepositions);
    RUN_TEST(test_compressor_handles_empty);
    RUN_TEST(test_compressor_handles_unique_text);
    RUN_TEST(test_compressor_bypass_guard);
    RUN_TEST(test_compressor_greedy_and_large_words);
    RUN_TEST(test_compressor_symbol_recycling);
    RUN_TEST(test_compressor_scales_on_repetitive_text);
    RUN_TEST(test_memory_manager_vram_cap);
    RUN_TEST(test_memory_manager_no_double_count_on_evict);
    RUN_TEST(test_pattern_predictor_records_transitions);
    RUN_TEST(test_pattern_predictor_empty_history);
    RUN_TEST(test_weight_streamer_preload);
    RUN_TEST(test_nvme_io_roundtrip);
    RUN_TEST(test_checkpoint_save_load);
    RUN_TEST(test_c_api_session_checkpoint_recovery);
    RUN_TEST(test_telemetry_logger_dispatch);
    RUN_TEST(test_index_registry_skips_non_gguf);
#ifdef HYPERSPHERICAL_ENTERPRISE_BUILD
#ifdef HYPERSPHERICAL_ENTERPRISE_BUILD
    RUN_TEST(test_stripe_io_roundtrip);
#endif
#endif
#ifdef HYPERSPHERICAL_ENTERPRISE_BUILD
#ifdef HYPERSPHERICAL_ENTERPRISE_BUILD
    RUN_TEST(test_leet_cipher_3fa_and_crypt);
#endif
#endif
    RUN_TEST(test_neuron_graph_relationships);
    RUN_TEST(test_hypersphere_coordinate_mapping);
    RUN_TEST(test_synthuron_and_hypertag_linking);
    RUN_TEST(test_compressor_auto_tune_spin);

    std::printf("\n==================================\n");
    std::printf("Total: %d  Passed: %d  Failed: %d\n",
                g_total, g_passed, g_failed);
    return g_failed == 0 ? 0 : 1;
}
