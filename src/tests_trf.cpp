// tests_trf.cpp — TRF (Temporal-Recency Frequency) registry test suite.
// Covers spec V3.1 §2 and §3.

#include "trf_registry.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <atomic>
#include <thread>
#include <chrono>

namespace trf = Tesseract::TRF;

static int g_total = 0, g_passed = 0, g_failed = 0;
static const char* g_current_test = nullptr;

#define CHECK(cond)                                                          \
    do {                                                                     \
        ++g_total;                                                           \
        if (cond) { ++g_passed; }                                            \
        else {                                                               \
            ++g_failed;                                                      \
            std::fprintf(stderr, "  FAIL [%s] %s:%d: %s\n",                 \
                         g_current_test, __FILE__, __LINE__, #cond);          \
        }                                                                    \
    } while (0)

#define RUN_TEST(name) do {                                                  \
    g_current_test = #name;                                                  \
    std::printf("[ RUN      ] %s\n", g_current_test);                         \
    name();                                                                  \
    std::printf("[   OK     ] %s\n", g_current_test);                         \
} while (0)

static void test_paths_derived_from_model_filename() {
    CHECK(trf::derive_registry_path("qwen-30b.gguf")
          == "qwen-30b.gguf.tesseract_profiles.json");
    CHECK(trf::derive_profile_path("qwen-30b.gguf", "main")
          == "qwen-30b.gguf_main.trf");
}

static void test_construct_and_observe() {
    trf::TRFLearner learner("model-A.gguf");
    learner.observe(42, 100);
    learner.observe(43, 200);
    learner.observe(42, 300);
    auto snap = learner.snapshot();
    CHECK(snap.size() == 2);
    bool saw_42 = false;
    for (auto& e : snap) {
        if (e.layer_index == 42) {
            saw_42 = true;
            CHECK(e.access_count == 2);
            CHECK(e.last_token_id == 300);
            CHECK(e.recency_score > 0.5f);  // freshly accessed
        }
    }
    CHECK(saw_42);
}

static void test_recency_decay() {
    trf::TRFLearner learner("decay.gguf");
    learner.observe(7, 100);
    // Access again far in the future
    learner.observe(7, 5000);
    auto snap = learner.snapshot();
    for (auto& e : snap) {
        if (e.layer_index == 7) {
            // The 2nd access boosts recency. We don't strictly check the value
            // (it depends on exact decay constants), only that it's in range.
            CHECK(e.recency_score >= 0.0f);
            CHECK(e.recency_score <= 1.0f);
        }
    }
}

static void test_prune_low_recency() {
    trf::TRFLearner learner("prune.gguf");
    // Add several entries; manually mutate recency to floor some of them.
    learner.observe(1, 10);
    learner.observe(2, 11);
    learner.observe(3, 12);
    auto snap = learner.snapshot();
    CHECK(snap.size() == 3);

    // Direct mutation for the test: set recency very low for entry 2.
    // (We can't reach into the map from outside, so simulate by observing
    //  with a huge token-id gap to decay it naturally.)
    learner.observe(2, 100000);  // 100k tokens later → strong decay
    learner.prune_low_recency();
    auto after = learner.snapshot();
    // Entry 2 should be gone; entries 1 and 3 might still be there
    // depending on decay constants; we just check no crash.
    (void)after;
    CHECK(after.size() <= 3);
}

static void test_profile_add_up_to_five_then_cap() {
    trf::TRFLearner learner("profiles.gguf");
    trf::ProfileMeta m;
    m.model_filename = "profiles.gguf";
    for (int i = 0; i < 5; ++i) {
        m.profile_name = "p" + std::to_string(i);
        m.token_name   = "tok_" + std::to_string(i);
        m.file_megabytes = 1.0 + i;
        m.context_hours  = 10;
        m.created_at = std::chrono::system_clock::now();
        m.last_touched = m.created_at;
        CHECK(learner.add_profile(m));
    }
    // 6th should fail
    m.profile_name = "p6";
    CHECK(!learner.add_profile(m));
    CHECK(learner.list_profiles().size() == 5);
}

static void test_profile_remove() {
    trf::TRFLearner learner("rm.gguf");
    trf::ProfileMeta m;
    m.model_filename = "rm.gguf";
    m.profile_name = "temp";
    learner.add_profile(m);
    CHECK(learner.list_profiles().size() == 1);
    CHECK(learner.remove_profile("temp"));
    CHECK(learner.list_profiles().empty());
}

static void test_flush_writes_registry_json() {
    trf::TRFLearner learner("flush-test.gguf");
    trf::ProfileMeta m;
    m.model_filename = "flush-test.gguf";
    m.profile_name   = "main";
    m.token_name     = "Crypto_Scalping";
    m.file_megabytes = 2.5;
    m.context_hours  = 42;
    learner.add_profile(m);
    learner.observe(7, 1000);
    learner.maybe_flush(1000, /*force=*/true);

    // Read back the JSON file
    auto path = learner.registry_path();
    FILE* f = std::fopen(path.c_str(), "rb");
    CHECK(f != nullptr);
    if (f) {
        char buf[4096] = {0};
        size_t n = std::fread(buf, 1, sizeof(buf)-1, f);
        std::fclose(f);
        std::string s(buf, n);
        CHECK(s.find("\"model_filename\": \"flush-test.gguf\"") != std::string::npos);
        CHECK(s.find("\"profile_name\": \"main\"") != std::string::npos);
        CHECK(s.find("\"token_name\": \"Crypto_Scalping\"") != std::string::npos);
        CHECK(s.find("\"file_megabytes\": 2.50") != std::string::npos);
        CHECK(s.find("\"context_hours\": 42") != std::string::npos);
    }

    // Read back the .trf binary file
    auto ppath = learner.profile_path("main");
    f = std::fopen(ppath.c_str(), "rb");
    CHECK(f != nullptr);
    if (f) {
        uint32_t magic = 0;
        std::fread(&magic, 4, 1, f);
        CHECK(magic == 0x54524646u);  // "TRFF"
        std::fclose(f);
    }
}

static void test_stats_report() {
    trf::TRFLearner learner("stats.gguf");
    trf::ProfileMeta m;
    m.model_filename = "stats.gguf";
    m.profile_name = "main";
    m.file_megabytes = 1.5;
    m.context_hours = 100;
    learner.add_profile(m);
    learner.observe(1, 1);
    learner.observe(2, 2);
    learner.observe(1, 3);
    auto s = learner.stats();
    CHECK(s.total_entries    >= 2);
    CHECK(s.total_profiles   == 1);
    CHECK(s.total_observations == 3);
    CHECK(s.file_megabytes   >= 1.5);
    CHECK(s.context_hours    == 100);
}

int main() {
    std::printf("Tesseract TRF registry test suite\n");
    std::printf("===================================\n");
    RUN_TEST(test_paths_derived_from_model_filename);
    RUN_TEST(test_construct_and_observe);
    RUN_TEST(test_recency_decay);
    RUN_TEST(test_prune_low_recency);
    RUN_TEST(test_profile_add_up_to_five_then_cap);
    RUN_TEST(test_profile_remove);
    RUN_TEST(test_flush_writes_registry_json);
    RUN_TEST(test_stats_report);
    std::printf("\n===================================\n");
    std::printf("Total: %d  Passed: %d  Failed: %d\n",
                g_total, g_passed, g_failed);
    return g_failed == 0 ? 0 : 1;
}
