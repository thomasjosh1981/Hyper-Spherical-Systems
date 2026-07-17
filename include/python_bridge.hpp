// python_bridge.hpp
//
// External C ABI that wraps the Tesseract core engine so it can be loaded
// from Python via ctypes. Keeps Python completely decoupled from the C++
// internals by passing everything through opaque handles.
//
// Lifecycle:
//   handle = tess_create()
//   ...
//   tess_destroy(handle)
//
// All buffers passed in from Python must be ctypes byte arrays / pointers.
// Strings must be NUL-terminated C strings (ctypes.c_char_p) when applicable.

#pragma once
#include <cstdint>
#include <cstddef>

#if defined(_WIN32)
#  define TESS_EXPORT __declspec(dllexport)
#else
#  define TESS_EXPORT __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

// Opaque engine handle; underlying type is hidden from Python (use void*).
typedef void* tess_handle_t;

// ── V1.7 spec: alternate C++-style handle for the root bridge ────────────
// Both tess_handle_t and TesseractEngineHandle are `void*`; they're aliases.
typedef void* TesseractEngineHandle;

// V1.7 InternalEngine struct is defined in src/python_bridge.cpp (private to the TU
// so the header doesn't need to know its layout). Forward declarations are emitted
// inside the .cpp where it's needed.

// Error codes returned by bridge entry points (matches core ErrorCode values).
enum {
    TESS_OK             =  0,
    TESS_BAD_HANDLE     = -1,
    TESS_BAD_ARG        = -2,
    TESS_IO_FAIL        = -3,
    TESS_VRAM_BUDGET    = -4,
    TESS_OUT_OF_MEMORY  = -5,
    TESS_NOT_IMPLEMENTED = -6,
};

// ── Lifecycle ───────────────────────────────────────────────────────────
TESS_EXPORT tess_handle_t tess_create(void);
TESS_EXPORT void          tess_destroy(tess_handle_t h);

// ── VRAM / RAM budget configuration ─────────────────────────────────────
TESS_EXPORT int tess_init_vram(tess_handle_t h, uint64_t phys_vram_bytes,
                               uint64_t phys_ram_bytes);

// ── Context compression ─────────────────────────────────────────────────
// Compresses `text` (length `text_len`) and writes a JSON-serialized
// description of the compressed entries into `out_json` (size `out_cap`).
// Returns the number of bytes written (excluding NUL), or a negative error.
// A round-trip `decompress` mirror is provided for verification.
TESS_EXPORT int tess_compress(tess_handle_t h,
                               const char* text, int text_len,
                               char* out_json, int out_cap);
TESS_EXPORT int tess_decompress(tess_handle_t h,
                                const char* in_json, int in_len,
                                char* out_text, int out_cap);

// ── MemoryManager ───────────────────────────────────────────────────────
// Push a layer shard (size in bytes) into the engine.
TESS_EXPORT int tess_push_layer(tess_handle_t h, uint32_t layer_id,
                                uint64_t byte_size);

// Getters
TESS_EXPORT uint64_t tess_vram_used(tess_handle_t h);
TESS_EXPORT uint64_t tess_vram_budget(tess_handle_t h);
TESS_EXPORT float    tess_vram_usage_pct(tess_handle_t h);
TESS_EXPORT uint64_t tess_ram_staging_used(tess_handle_t h);
TESS_EXPORT uint64_t tess_ram_staging_limit(tess_handle_t h);

// ── PatternPredictor ────────────────────────────────────────────────────
TESS_EXPORT void tess_observe_layer(tess_handle_t h, uint32_t layer_id);
// Fill `out_ids` (capacity `cap`) with predicted layer ids; returns count.
// `out_confidence` receives the top prediction's confidence value.
TESS_EXPORT int  tess_predict_next(tess_handle_t h, uint32_t* out_ids, int cap,
                                   float* out_confidence);
TESS_EXPORT uint64_t tess_total_observations(tess_handle_t h);

// ── WeightStreamer ──────────────────────────────────────────────────────
TESS_EXPORT int tess_preload_layers(tess_handle_t h,
                                    const uint32_t* ids, int count);

// ── NVMeIO ──────────────────────────────────────────────────────────────
TESS_EXPORT int tess_io_write(tess_handle_t h, const char* rel_path,
                              const uint8_t* data, int len);
TESS_EXPORT int tess_io_read(tess_handle_t h, const char* rel_path,
                             uint8_t* out_buf, int cap);

// ── RecoveryCheckpoint ──────────────────────────────────────────────────
TESS_EXPORT int tess_checkpoint_save(tess_handle_t h, const char* path);
TESS_EXPORT int tess_checkpoint_load(tess_handle_t h, const char* path);
TESS_EXPORT int tess_get_session_history(tess_handle_t h, char* out, int cap);

// ── TelemetryLogger ─────────────────────────────────────────────────────
typedef struct TessTelemetry {
    float    vram_usage_pct;
    float    ram_staging_pct;
    uint64_t active_kv_tokens;
    uint32_t prefetch_pending;
} TessTelemetry;

TESS_EXPORT void tess_telemetry_get(tess_handle_t h, TessTelemetry* out);

// ── IndexRegistry ───────────────────────────────────────────────────────
TESS_EXPORT int tess_index_build(tess_handle_t h, const char* dir);
TESS_EXPORT int tess_index_shards_in_vram(tess_handle_t h);

// ── Build / version info ────────────────────────────────────────────────
TESS_EXPORT const char* tess_version(void);
TESS_EXPORT const char* tess_last_error(tess_handle_t h);

// ── Virtual VRAM illusion (V1.7.1 — 60 GB presented to LLM) ──────────────
TESS_EXPORT int tess_init_vram_v2(tess_handle_t h,
                                    uint64_t phys_vram_bytes,
                                    uint64_t phys_ram_bytes,
                                    uint64_t virtual_vram_bytes);
TESS_EXPORT uint64_t tess_virtual_vram_bytes(tess_handle_t h);
TESS_EXPORT uint64_t tess_phys_vram_bytes(tess_handle_t h);
TESS_EXPORT uint64_t tess_phys_ram_bytes(tess_handle_t h);
TESS_EXPORT float    tess_vram_illusion_ratio(tess_handle_t h);   // virt / phys

// ── V1.4 directives (bool + float setters; matches GUI widget names) ───
TESS_EXPORT int tess_set_directive_bool(const char* name, int value);
TESS_EXPORT int tess_set_directive_float(const char* name, float value);
TESS_EXPORT int tess_get_directive_float(const char* name, float* out);
TESS_EXPORT int tess_set_breathing_mode(tess_handle_t h, int enabled);
TESS_EXPORT int tess_set_circuit_breaker(tess_handle_t h, int enabled);

// ── V1.3 PQC + obfuscation ─────────────────────────────────────────────
TESS_EXPORT int tess_pqc_active_backend(void);   // 0 = liboqs, 1 = stub
TESS_EXPORT int tess_pqc_kyber_keygen(tess_handle_t h);
TESS_EXPORT int tess_pqc_kyber_roundtrip(tess_handle_t h);
TESS_EXPORT int tess_pqc_nested_roundtrip(tess_handle_t h,
                                          const uint8_t* in, int in_len,
                                          uint8_t* out, int out_cap);
TESS_EXPORT int tess_obfuscation_flatten(tess_handle_t h,
                                          uint8_t* buffer, int len,
                                          int language_index);
TESS_EXPORT int tess_obfuscation_unflatten(tess_handle_t h,
                                            uint8_t* buffer, int len,
                                            int language_index);

// ── V1.1 tripwire ───────────────────────────────────────────────────────
TESS_EXPORT int tess_tripwire_arm(tess_handle_t h,
                                    uintptr_t low, uintptr_t high,
                                    int abort_on_trip);
TESS_EXPORT int tess_tripwire_disarm(tess_handle_t h);
TESS_EXPORT int tess_tripwire_check(tess_handle_t h, uintptr_t target);

// ── V1.3 shard matrix (10-file matrix) ──────────────────────────────────
TESS_EXPORT int tess_shard_open(tess_handle_t h, const char* base_dir);
TESS_EXPORT int tess_shard_write_payload(tess_handle_t h,
                                          const uint8_t* data, int len);
TESS_EXPORT int tess_shard_read_payload(tess_handle_t h,
                                         uint8_t* out, int out_cap);
TESS_EXPORT int tess_shard_rotate(tess_handle_t h);
TESS_EXPORT int tess_shard_close(tess_handle_t h);

// ── V1.4 / V1.5 blueprint dump ──────────────────────────────────────────
TESS_EXPORT int tess_commit_blueprint(const char* json_path);

// =====================================================================
// V1.7 — Mandatory Core Endpoint (OpenAI-compatible loop + llama.cpp)
// =====================================================================
// All V1.7 entry points exist alongside the V1.x `tess_*` symbols so the
// Python GUI (which uses the `tess_*` surface) keeps working unchanged.

// 1. Mandatory Core Server Initialization Endpoint
TESS_EXPORT TesseractEngineHandle tesseract_create_engine(void);

// 2. Python-Facing C-API Hook for Dynamic Saturation Modifications
TESS_EXPORT void tesseract_set_vram_saturation(TesseractEngineHandle handle,
                                                  float saturation);

// 3. Inference Entrypoint with Pre/Post Layer Intercept Callbacks
TESS_EXPORT int tesseract_execute_inference_token(TesseractEngineHandle handle,
                                                     uint64_t token_id);

// 4. Clean Engine Release Context Shutdown
TESS_EXPORT void tesseract_destroy_engine(TesseractEngineHandle handle);

// 5. Circuit breaker toggle (mapped to runtime_directives)
TESS_EXPORT void tesseract_toggle_circuit_breaker(TesseractEngineHandle handle,
                                                     int enabled);

// 6. OpenAI-compatible chat completions endpoint (stub when llama is missing)
TESS_EXPORT int tesseract_openai_chat(TesseractEngineHandle handle,
                                         const char* request_json,
                                         int request_len,
                                         char* out, int out_cap);

// 7. Backend introspection — returns 1 if real llama.cpp is linked, 0 if stub
TESS_EXPORT int tesseract_llama_backend_active(void);

#ifdef __cplusplus
}
#endif
