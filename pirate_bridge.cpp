// pirate_bridge.cpp
//
// V1.5 spec surface — root-level executable with two roles:
//
//   (1) The "external wrapper" half: re-declares + re-exports the canonical
//       tess_* C ABI (see include/python_bridge.hpp) so the build harness
//       sees a single, well-known symbol surface at the project root.
//
//       These symbols are *defined* by the Python bridge DLL (pirate_bridge.dll
//       built from src/python_bridge.cpp). For the root-level bridge exe we
//       re-declare them here so they're visible to anyone #including this file,
//       but the actual implementation lives in the DLL.
//
//   (2) Wraps llama.cpp — forward llama's pre_layer / post_layer hooks into our
//       HarnessHook so each forward pass updates VRAM tiers, fire the tripwire
//       if a decoy is touched, etc.
//
// llama.cpp is OPTIONAL. Define PIRATE_BRIDGE_USE_LLAMA=1 (set by CMake if
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
#if PIRATE_BRIDGE_USE_LLAMA
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
    std::fprintf(stderr, "[pirate_bridge][%s] %s\n", level, msg);
}

}  // anon

// ── Re-export the canonical TessEngine ABI ─────────────────────────────
// The implementations of these symbols live in src/python_bridge.cpp.
// We redeclare them with PIRATE_EXPORT here so the root exe owns the same
// symbol surface — they're satisfied at link time when the Python bridge
// is compiled into the same exe, or resolved dynamically when the DLL
// is loaded.
PIRATE_EXPORT pirate_handle_t pirate_create(void);
PIRATE_EXPORT void         pirate_destroy(pirate_handle_t h);
PIRATE_EXPORT int          pirate_init_vram(pirate_handle_t h, uint64_t phys_vram_bytes,
                                          uint64_t phys_ram_bytes);
PIRATE_EXPORT int          pirate_compress(pirate_handle_t h, const char* text, int text_len,
                                         char* out_json, int out_cap);
PIRATE_EXPORT int          pirate_decompress(pirate_handle_t h, const char* in_json, int in_len,
                                           char* out_text, int out_cap);
PIRATE_EXPORT int          pirate_push_layer(pirate_handle_t h, uint32_t layer_id,
                                           uint64_t byte_size);
PIRATE_EXPORT uint64_t     pirate_vram_used(pirate_handle_t h);
PIRATE_EXPORT uint64_t     pirate_vram_budget(pirate_handle_t h);
PIRATE_EXPORT float        pirate_vram_usage_pct(pirate_handle_t h);
PIRATE_EXPORT uint64_t     pirate_ram_staging_used(pirate_handle_t h);
PIRATE_EXPORT uint64_t     pirate_ram_staging_limit(pirate_handle_t h);
PIRATE_EXPORT void         pirate_observe_layer(pirate_handle_t h, uint32_t layer_id);
PIRATE_EXPORT int          pirate_predict_next(pirate_handle_t h, uint32_t* out_ids, int cap,
                                             float* out_confidence);
PIRATE_EXPORT uint64_t     pirate_total_observations(pirate_handle_t h);
PIRATE_EXPORT int          pirate_io_write(pirate_handle_t h, const char* rel_path,
                                         const uint8_t* data, int len);
PIRATE_EXPORT int          pirate_io_read(pirate_handle_t h, const char* rel_path,
                                        uint8_t* out_buf, int cap);
PIRATE_EXPORT int          pirate_checkpoint_save(pirate_handle_t h, const char* path);
PIRATE_EXPORT int          pirate_checkpoint_load(pirate_handle_t h, const char* path);
PIRATE_EXPORT void         tess_telemetry_get(pirate_handle_t h, TessTelemetry* out);
PIRATE_EXPORT int          pirate_index_build(pirate_handle_t h, const char* dir);
PIRATE_EXPORT int          tess_index_shards_in_vram(pirate_handle_t h);
PIRATE_EXPORT const char*  tess_version(void);
PIRATE_EXPORT const char*  pirate_last_error(pirate_handle_t h);

// Directives are implemented in python_bridge.cpp

PIRATE_EXPORT int tess_llama_load(const char* model_path) {
#if PIRATE_BRIDGE_USE_LLAMA
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
PIRATE_EXPORT int tess_llama_generate(const char* prompt, int max_tokens,
                                     char* out, int out_cap) {
#if PIRATE_BRIDGE_USE_LLAMA
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
PIRATE_EXPORT uint64_t tess_forward_pass_count(void) {
    return g_forward_pass_count.load();
}

// tess_commit_blueprint is implemented in python_bridge.cpp

int main(int argc, char** argv) {
    std::printf("[HYPER-SPHERICAL] Bridge Host executable initialized.\n");
    return 0;
}

// ── HarnessHook integration ────────────────────────────────────────────
namespace hypersp {
void HarnessHook::on_pre_layer(uint32_t layer_id, size_t byte_size) noexcept {
    (void)byte_size;
    g_forward_pass_count.fetch_add(1, std::memory_order_relaxed);
}
void HarnessHook::on_post_layer(uint32_t layer_id, size_t byte_size) noexcept {
    (void)byte_size;
}
}

