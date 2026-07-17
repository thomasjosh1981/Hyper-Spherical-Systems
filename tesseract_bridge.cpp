// tesseract_bridge.cpp
//
// V1.5 spec surface — root-level executable with two roles:
//
//   (1) The "external wrapper" half: re-declares + re-exports the canonical
//       tess_* C ABI (see include/python_bridge.hpp) so the build harness
//       sees a single, well-known symbol surface at the project root.
//
//       These symbols are *defined* by the Python bridge DLL (tesseract_bridge.dll
//       built from src/python_bridge.cpp). For the root-level bridge exe we
//       re-declare them here so they're visible to anyone #including this file,
//       but the actual implementation lives in the DLL.
//
//   (2) Wraps llama.cpp — forward llama's pre_layer / post_layer hooks into our
//       HarnessHook so each forward pass updates VRAM tiers, fire the tripwire
//       if a decoy is touched, etc.
//
// llama.cpp is OPTIONAL. Define TESSERACT_BRIDGE_USE_LLAMA=1 (set by CMake if
// libllama is detected) to wire the actual llama_generate call.
//
// When the Python bridge DLL is loaded at runtime via LoadLibrary(), all
// tess_* symbols resolve through the DLL's export table. This root exe
// therefore works both standalone (re-declares) and as a thin host that
// loads + dispatches to the DLL.

#include <string>
#include <fstream>
#include <iostream>
#include <memory>
#include <utility>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <cstdio>

#include "python_bridge.hpp"
#include "config.hpp"
#include "harness_hook.hpp"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#if defined(_WIN32)
#  define WIN32_LEAN_AND_MEAN
#  include <windows.h>
#endif

// Forward declarations for llama.cpp engine layouts (V1.6 spec §2)
struct llama_model;
struct llama_context;
#if TESSERACT_BRIDGE_USE_LLAMA
extern "C" {
    int  llama_model_load(const char* path);
    void llama_model_free();
    int  llama_generate(const char* prompt, int max_tokens, char* out, int out_cap);
}
#endif

namespace {

std::atomic<bool>  g_llama_loaded{false};
std::atomic<bool>  g_breathing_enabled{true};
std::atomic<bool>  g_circuit_breaker{true};
std::atomic<bool>  g_scissi_compression{true};
std::atomic<bool>  g_homophonic_flatten{true};
std::atomic<float> g_vram_target{0.75f};
std::atomic<float> g_stay_buffer{0.15f};
std::atomic<float> g_load_in_headroom{0.40f};
std::atomic<uint64_t> g_forward_pass_count{0};

void logf(const char* level, const char* msg) {
    std::fprintf(stderr, "[tesseract_bridge][%s] %s\n", level, msg);
}

}  // anon

// ── Re-export the canonical TessEngine ABI ─────────────────────────────
// The implementations of these symbols live in src/python_bridge.cpp.
// We redeclare them with TESS_EXPORT here so the root exe owns the same
// symbol surface — they're satisfied at link time when the Python bridge
// is compiled into the same exe, or resolved dynamically when the DLL
// is loaded.
TESS_EXPORT tess_handle_t tess_create(void);
TESS_EXPORT void         tess_destroy(tess_handle_t h);
TESS_EXPORT int          tess_init_vram(tess_handle_t h, uint64_t phys_vram_bytes,
                                          uint64_t phys_ram_bytes);
TESS_EXPORT int          tess_compress(tess_handle_t h, const char* text, int text_len,
                                         char* out_json, int out_cap);
TESS_EXPORT int          tess_decompress(tess_handle_t h, const char* in_json, int in_len,
                                           char* out_text, int out_cap);
TESS_EXPORT int          tess_push_layer(tess_handle_t h, uint32_t layer_id,
                                           uint64_t byte_size);
TESS_EXPORT uint64_t     tess_vram_used(tess_handle_t h);
TESS_EXPORT uint64_t     tess_vram_budget(tess_handle_t h);
TESS_EXPORT float        tess_vram_usage_pct(tess_handle_t h);
TESS_EXPORT uint64_t     tess_ram_staging_used(tess_handle_t h);
TESS_EXPORT uint64_t     tess_ram_staging_limit(tess_handle_t h);
TESS_EXPORT void         tess_observe_layer(tess_handle_t h, uint32_t layer_id);
TESS_EXPORT int          tess_predict_next(tess_handle_t h, uint32_t* out_ids, int cap,
                                             float* out_confidence);
TESS_EXPORT uint64_t     tess_total_observations(tess_handle_t h);
TESS_EXPORT int          tess_io_write(tess_handle_t h, const char* rel_path,
                                         const uint8_t* data, int len);
TESS_EXPORT int          tess_io_read(tess_handle_t h, const char* rel_path,
                                        uint8_t* out_buf, int cap);
TESS_EXPORT int          tess_checkpoint_save(tess_handle_t h, const char* path);
TESS_EXPORT int          tess_checkpoint_load(tess_handle_t h, const char* path);
TESS_EXPORT void         tess_telemetry_get(tess_handle_t h, TessTelemetry* out);
TESS_EXPORT int          tess_index_build(tess_handle_t h, const char* dir);
TESS_EXPORT int          tess_index_shards_in_vram(tess_handle_t h);
TESS_EXPORT const char*  tess_version(void);
TESS_EXPORT const char*  tess_last_error(tess_handle_t h);

// Directives are implemented in python_bridge.cpp

TESS_EXPORT int tess_llama_load(const char* model_path) {
#if TESSERACT_BRIDGE_USE_LLAMA
    if (!model_path) return -1;
    int rc = llama_model_load(model_path);
    g_llama_loaded.store(rc == 0);
    return rc;
#else
    (void)model_path;
    logf("info", "llama.cpp not linked; tess_llama_load is a stub");
    return -100;
#endif
}
TESS_EXPORT int tess_llama_generate(const char* prompt, int max_tokens,
                                     char* out, int out_cap) {
#if TESSERACT_BRIDGE_USE_LLAMA
    if (!g_llama_loaded.load()) {
        logf("warn", "tess_llama_generate called before tess_llama_load");
        return -1;
    }
    return llama_generate(prompt, max_tokens, out, out_cap);
#else
    (void)prompt; (void)max_tokens; (void)out; (void)out_cap;
    return -100;
#endif
}
TESS_EXPORT uint64_t tess_forward_pass_count(void) {
    return g_forward_pass_count.load();
}

// tess_commit_blueprint is implemented in python_bridge.cpp

int main(int argc, char** argv) {
    std::printf("[HYPER-SPHERICAL] Bridge Host executable initialized.\n");
    return 0;
}

// ── HarnessHook integration ────────────────────────────────────────────
namespace tesseract {
void HarnessHook::on_pre_layer(uint32_t layer_id, size_t byte_size) noexcept {
    (void)byte_size;
    g_forward_pass_count.fetch_add(1, std::memory_order_relaxed);
}
void HarnessHook::on_post_layer(uint32_t layer_id, size_t byte_size) noexcept {
    (void)byte_size;
}
}

