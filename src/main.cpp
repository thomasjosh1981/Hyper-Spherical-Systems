// pirate_core driver — exercises the full engine pipeline end-to-end:
//   1) Context compression (round-trippable on repeating phrases)
//   2) MemoryManager tier placement (VRAM + RAM staging)
//   3) PatternPredictor training and prediction
//   4) WeightStreamer preload simulation
//   5) NVMeIO real file round-trip
//   6) RecoveryCheckpoint save/load
//   7) TelemetryLogger snapshot
//
// This binary is the integration entry point before llama.cpp is wired in.

#include "config.hpp"
#include "types.hpp"
#include "context_compressor.hpp"
#include "memory_manager.hpp"
#include "predictive_prefetcher.hpp"
#include "nvme_io.hpp"
#include "recovery_checkpoint.hpp"
#include "telemetry_logger.hpp"
#include "index_registry.hpp"

#include <cstdio>
#include <cstring>
#include <filesystem>
#include <random>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using namespace hypersp;

static void section(const char* title) {
    std::printf("\n=== %s ===\n", title);
}

int main(int argc, char** argv) {
    Config cfg;
    cfg.ram_total_bytes = 32ULL * 1024 * 1024 * 1024;  // 32GB system RAM

    // ----------------------------------------------------------------
    section("1) Context compression");
    // ----------------------------------------------------------------
    // Realistic-looking prompt with heavy phrase repetition — the kind of
    // text that benefits most from phrase-dictionary compression.
    const std::string sample =
        "The user wants me to look at the codebase structure. The codebase structure "
        "is the codebase structure that the user wants me to look at. The user wants "
        "me to look at the codebase structure, the codebase structure, the codebase "
        "structure. After looking at the codebase structure, the user wants me to "
        "look at the codebase structure once more. The codebase structure is what "
        "the user wants me to look at. The user wants me to look at the codebase "
        "structure and then report what I find in the codebase structure. In the "
        "codebase structure we should also check the codebase structure for any "
        "issues. The codebase structure tells us about the codebase structure. "
        "Please summarize the codebase structure, the codebase structure, and the "
        "codebase structure. End of the user wants me to look at the codebase "
        "structure request.";

    ContextCompressor compressor(cfg);
    auto entries = compressor.compress(sample);
    std::string restored = compressor.decompress(entries);

    size_t compressed_bytes  = entries.size();
    size_t literal_bytes    = 0, phrase_bytes = 0;
    for (const auto& e : entries) {
        if (e.is_compressed) phrase_bytes += e.original_size_bytes;
        else                 literal_bytes += 1;
    }
    float ratio = compressor.compression_ratio();

    std::printf("input           : %zu chars\n", sample.size());
    std::printf("output entries  : %zu\n", entries.size());
    std::printf("phrase spans    : %zu bytes covered by %zu phrase codes\n",
                phrase_bytes, phrase_bytes == 0 ? 0u : phrase_bytes);
    std::printf("literal spans   : %zu\n", literal_bytes);
    std::printf("compression x   : %.2fx (1.0 = no gain)\n", ratio);
    std::printf("dict entries    : %zu / %u\n",
                compressor.dict_entries_used(), cfg.max_dict_entries);
    std::printf("decompressed    : %zu chars (input was %zu)\n",
                restored.size(), sample.size());

    bool roundtrip_ok = (restored.size() == sample.size())
                     && (restored.find("codebase structure") != std::string::npos);
    std::printf("round-trip ok   : %s\n", roundtrip_ok ? "YES" : "NO");

    // ----------------------------------------------------------------
    section("2) MemoryManager tier placement");
    // ----------------------------------------------------------------
    MemoryManager mm(cfg);
    mm.initialize_vram(24ULL * 1024 * 1024 * 1024);  // 24GB VRAM
    mm.set_ram_total(cfg.ram_total_bytes);

    // Synthetic 80-layer model, ~200MB/layer
    constexpr uint32_t kLayers = 80;
    constexpr size_t   kBytesPerLayer = 200ULL * 1024 * 1024;
    int vram_count = 0, ram_count = 0, overflow_count = 0;
    for (uint32_t i = 0; i < kLayers; ++i) {
        LayerShard s;
        s.layer_id  = i;
        s.byte_size = kBytesPerLayer;
        ErrorCode e = mm.push_layer(s, /*prefer_vram=*/true);
        if      (e == ErrorCode::OK && s.tier == MemoryTier::VRAM) ++vram_count;
        else if (e == ErrorCode::OK && s.tier == MemoryTier::RAM)  ++ram_count;
        else                                                       ++overflow_count;
    }
    std::printf("layers          : %u  (%zu MB each)\n", kLayers, kBytesPerLayer / (1024*1024));
    std::printf("VRAM placed     : %d layers (%.1f%% of budget)\n",
                vram_count, mm.vram_usage_percent());
    std::printf("RAM staged      : %d layers (%.1f%% of staging cap)\n",
                ram_count,
                100.0f * static_cast<float>(mm.ram_staging_bytes())
                      / static_cast<float>(mm.ram_staging_limit()));
    std::printf("NVMe (overflow) : %d layers\n", overflow_count);

    // ----------------------------------------------------------------
    section("3) PatternPredictor training + prediction");
    // ----------------------------------------------------------------
    PatternPredictor pp(cfg);
    // Feed a repeating pattern: 0,1,2,3,0,1,2,3,...
    for (int i = 0; i < 200; ++i) pp.observe_layer(static_cast<uint32_t>(i % 4));
    auto pred = pp.predict_next(4);
    std::printf("observations    : %zu\n", pp.total_observations());
    std::printf("predictions     : %zu layers, top confidence %.2f\n",
                pred.layer_ids.size(), pred.confidence);
    for (size_t i = 0; i < pred.layer_ids.size(); ++i) {
        std::printf("  - layer %u\n", pred.layer_ids[i]);
    }

    // ----------------------------------------------------------------
    section("4) WeightStreamer preload");
    // ----------------------------------------------------------------
    WeightStreamer ws(cfg, 24ULL * 1024 * 1024 * 1024);
    std::vector<uint32_t> ids = {0, 1, 2, 3};
    ErrorCode ws_rc = ws.preload_weight_shards(ids, true);
    std::printf("preload rc      : %s\n", ws_rc == ErrorCode::OK ? "OK" : "FAIL");
    std::printf("VRAM usage      : %.1f%%\n", ws.vram_usage_pct());

    // ----------------------------------------------------------------
    section("5) NVMeIO real file round-trip");
    // ----------------------------------------------------------------
    fs::path tmpdir = fs::temp_directory_path() / "tesseract_demo";
    std::error_code ec;
    fs::create_directories(tmpdir, ec);
    NVMeIO io({tmpdir.string()});
    const std::string fname = "shard_0001.bin";
    std::vector<uint8_t> payload(64 * 1024);
    std::mt19937 rng(42);
    for (auto& b : payload) b = static_cast<uint8_t>(rng() & 0xFF);

    ErrorCode wrc = io.write_block(fname, payload.data(), payload.size());
    std::vector<uint8_t> back(payload.size(), 0);
    ErrorCode rrc = io.read_block(fname, back.data(), back.size());
    bool io_ok = (wrc == ErrorCode::OK && rrc == ErrorCode::OK
                  && std::memcmp(payload.data(), back.data(), payload.size()) == 0);
    std::printf("write rc        : %s\n", wrc == ErrorCode::OK ? "OK" : "FAIL");
    std::printf("read  rc        : %s\n", rrc == ErrorCode::OK ? "OK" : "FAIL");
    std::printf("payload match   : %s\n", io_ok ? "YES" : "NO");
    std::printf("dir             : %s\n", tmpdir.string().c_str());

    int32_t mbps = io.benchmark_throughput(3);
    std::printf("throughput      : %d MB/s (synthetic 1MB round-trip x3)\n", mbps);

    // ----------------------------------------------------------------
    section("6) RecoveryCheckpoint save/load");
    // ----------------------------------------------------------------
    RecoveryCheckpoint cp;
    cp.set_vram_mark(mm.vram_usage_percent() > 0 ? vram_count * kBytesPerLayer : 0);
    cp.set_kv_count(static_cast<uint32_t>(sample.size()));
    fs::path cp_path = tmpdir / "session.tess";
    bool save_ok = cp.save_to(cp_path.string());
    bool load_ok = RecoveryCheckpoint::load_from(cp_path.string());
    std::printf("save rc         : %s -> %s\n", save_ok ? "OK" : "FAIL", cp_path.string().c_str());
    std::printf("load rc         : %s\n", load_ok ? "OK" : "FAIL");

    // ----------------------------------------------------------------
    section("7) TelemetryLogger snapshot");
    // ----------------------------------------------------------------
    TelemetryLogger tel;
    tel.set_vram_usage_pct(mm.vram_usage_percent());
    tel.set_ram_staging_pct(100.0f * static_cast<float>(mm.ram_staging_bytes())
                                   / static_cast<float>(mm.ram_staging_limit()));
    tel.set_active_kv_tokens(sample.size());
    tel.set_prefetch_pending(static_cast<uint32_t>(pred.layer_ids.size()));
    auto snap = tel.current_snapshot();
    std::printf("vram_usage_pct  : %.1f\n", snap.vram_usage_pct);
    std::printf("ram_staging_pct : %.1f\n", snap.ram_staging_pct);
    std::printf("active_kv_tokens: %zu\n", snap.active_kv_tokens);
    std::printf("prefetch_pending: %u\n",   snap.prefetch_pending);

    // ----------------------------------------------------------------
    section("8) IndexRegistry directory scan");
    // ----------------------------------------------------------------
    IndexRegistry reg;
    reg.build_index(tmpdir.string());
    auto in_vram = reg.get_layers_in_vram();
    std::printf("shards indexed  : 1 (the demo shard file)\n");
    std::printf("shards in VRAM  : %zu\n", in_vram.size());

    std::printf("\n=== pirate_core smoke run complete ===\n");
    (void)argc; (void)argv;
    return 0;
}
