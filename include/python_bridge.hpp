// python_bridge.hpp
//
// External C ABI that wraps the Tesseract core engine so it can be loaded
// from Python via ctypes. Keeps Python completely decoupled from the C++
// internals by passing everything through opaque handles.
//
// Lifecycle:
//   handle = pirate_create()
//   ...
//   pirate_destroy(handle)
//
// All buffers passed in from Python must be ctypes byte arrays / pointers.
// Strings must be NUL-terminated C strings (ctypes.c_char_p) when applicable.

#pragma once
#include <cstdint>
#include <cstddef>

#if defined(_WIN32)
#  define PIRATE_EXPORT __declspec(dllexport)
#else
#  define PIRATE_EXPORT __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

// Opaque engine handle; underlying type is hidden from Python (use void*).
typedef void* pirate_handle_t;

// ── V1.7 spec: alternate C++-style handle for the root bridge ────────────
// Both pirate_handle_t and TesseractEngineHandle are `void*`; they're aliases.
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
PIRATE_EXPORT pirate_handle_t pirate_create(void);
PIRATE_EXPORT void          pirate_destroy(pirate_handle_t h);

// ── VRAM / RAM budget configuration ─────────────────────────────────────
PIRATE_EXPORT int pirate_init_vram(pirate_handle_t h, uint64_t phys_vram_bytes,
                               uint64_t phys_ram_bytes);

// ── Context compression ─────────────────────────────────────────────────
// Compresses `text` (length `text_len`) and writes a JSON-serialized
// description of the compressed entries into `out_json` (size `out_cap`).
// Returns the number of bytes written (excluding NUL), or a negative error.
// A round-trip `decompress` mirror is provided for verification.
PIRATE_EXPORT int pirate_compress(pirate_handle_t h,
                               const char* text, int text_len,
                               char* out_json, int out_cap);
PIRATE_EXPORT int pirate_decompress(pirate_handle_t h,
                                const char* in_json, int in_len,
                                char* out_text, int out_cap);

// ── MemoryManager ───────────────────────────────────────────────────────
// Push a layer shard (size in bytes) into the engine.
PIRATE_EXPORT int pirate_push_layer(pirate_handle_t h, uint32_t layer_id,
                                uint64_t byte_size);

// Getters
PIRATE_EXPORT uint64_t pirate_vram_used(pirate_handle_t h);
PIRATE_EXPORT uint64_t pirate_vram_budget(pirate_handle_t h);
PIRATE_EXPORT float    pirate_vram_usage_pct(pirate_handle_t h);
PIRATE_EXPORT uint64_t pirate_ram_staging_used(pirate_handle_t h);
PIRATE_EXPORT uint64_t pirate_ram_staging_limit(pirate_handle_t h);

// ── PatternPredictor ────────────────────────────────────────────────────
PIRATE_EXPORT void pirate_observe_layer(pirate_handle_t h, uint32_t layer_id);
// Fill `out_ids` (capacity `cap`) with predicted layer ids; returns count.
// `out_confidence` receives the top prediction's confidence value.
PIRATE_EXPORT int  pirate_predict_next(pirate_handle_t h, uint32_t* out_ids, int cap,
                                   float* out_confidence);
PIRATE_EXPORT uint64_t pirate_total_observations(pirate_handle_t h);

// ── WeightStreamer ──────────────────────────────────────────────────────
PIRATE_EXPORT int tess_preload_layers(pirate_handle_t h,
                                    const uint32_t* ids, int count);

// ── NVMeIO ──────────────────────────────────────────────────────────────
PIRATE_EXPORT int pirate_io_write(pirate_handle_t h, const char* rel_path,
                              const uint8_t* data, int len);
PIRATE_EXPORT int pirate_io_read(pirate_handle_t h, const char* rel_path,
                             uint8_t* out_buf, int cap);

// ── RecoveryCheckpoint ──────────────────────────────────────────────────
PIRATE_EXPORT int pirate_checkpoint_save(pirate_handle_t h, const char* path);
PIRATE_EXPORT int pirate_checkpoint_load(pirate_handle_t h, const char* path);
PIRATE_EXPORT int tess_get_session_history(pirate_handle_t h, char* out, int cap);

// ── TelemetryLogger ─────────────────────────────────────────────────────
typedef struct TessTelemetry {
    float    vram_usage_pct;
    float    ram_staging_pct;
    uint64_t active_kv_tokens;
    uint32_t prefetch_pending;
} TessTelemetry;

PIRATE_EXPORT void tess_telemetry_get(pirate_handle_t h, TessTelemetry* out);

// ── IndexRegistry ───────────────────────────────────────────────────────
PIRATE_EXPORT int pirate_index_build(pirate_handle_t h, const char* dir);
PIRATE_EXPORT int tess_index_shards_in_vram(pirate_handle_t h);

// ── Build / version info ────────────────────────────────────────────────
PIRATE_EXPORT const char* tess_version(void);
PIRATE_EXPORT const char* pirate_last_error(pirate_handle_t h);

// ── Virtual VRAM illusion (V1.7.1 — 60 GB presented to LLM) ──────────────
PIRATE_EXPORT int tess_init_vram_v2(pirate_handle_t h,
                                    uint64_t phys_vram_bytes,
                                    uint64_t phys_ram_bytes,
                                    uint64_t virtual_vram_bytes);
PIRATE_EXPORT uint64_t tess_virtual_vram_bytes(pirate_handle_t h);
PIRATE_EXPORT uint64_t tess_phys_vram_bytes(pirate_handle_t h);
PIRATE_EXPORT uint64_t tess_phys_ram_bytes(pirate_handle_t h);
PIRATE_EXPORT float    tess_vram_illusion_ratio(pirate_handle_t h);   // virt / phys

// ── V1.4 directives (bool + float setters; matches GUI widget names) ───
PIRATE_EXPORT int tess_set_directive_bool(const char* name, int value);
PIRATE_EXPORT int tess_set_directive_float(const char* name, float value);
PIRATE_EXPORT int tess_get_directive_float(const char* name, float* out);
PIRATE_EXPORT int tess_set_breathing_mode(pirate_handle_t h, int enabled);
PIRATE_EXPORT int tess_set_circuit_breaker(pirate_handle_t h, int enabled);

// ── V1.3 PQC + obfuscation ─────────────────────────────────────────────
PIRATE_EXPORT int tess_pqc_active_backend(void);   // 0 = liboqs, 1 = stub
PIRATE_EXPORT int tess_pqc_kyber_keygen(pirate_handle_t h);
PIRATE_EXPORT int tess_pqc_kyber_roundtrip(pirate_handle_t h);
PIRATE_EXPORT int tess_pqc_nested_roundtrip(pirate_handle_t h,
                                          const uint8_t* in, int in_len,
                                          uint8_t* out, int out_cap);
PIRATE_EXPORT int tess_obfuscation_flatten(pirate_handle_t h,
                                          uint8_t* buffer, int len,
                                          int language_index);
PIRATE_EXPORT int tess_obfuscation_unflatten(pirate_handle_t h,
                                            uint8_t* buffer, int len,
                                            int language_index);

// ── V1.1 tripwire ───────────────────────────────────────────────────────
PIRATE_EXPORT int tess_tripwire_arm(pirate_handle_t h,
                                    uintptr_t low, uintptr_t high,
                                    int abort_on_trip);
PIRATE_EXPORT int tess_tripwire_disarm(pirate_handle_t h);
PIRATE_EXPORT int tess_tripwire_check(pirate_handle_t h, uintptr_t target);

// ── V1.3 shard matrix (10-file matrix) ──────────────────────────────────
PIRATE_EXPORT int tess_shard_open(pirate_handle_t h, const char* base_dir);
PIRATE_EXPORT int tess_shard_write_payload(pirate_handle_t h,
                                          const uint8_t* data, int len);
PIRATE_EXPORT int tess_shard_read_payload(pirate_handle_t h,
                                         uint8_t* out, int out_cap);
PIRATE_EXPORT int tess_shard_rotate(pirate_handle_t h);
PIRATE_EXPORT int tess_shard_close(pirate_handle_t h);

// ── V1.4 / V1.5 blueprint dump ──────────────────────────────────────────
PIRATE_EXPORT int tess_commit_blueprint(const char* json_path);

// =====================================================================
// V1.7 — Mandatory Core Endpoint (OpenAI-compatible loop + llama.cpp)
// =====================================================================
// All V1.7 entry points exist alongside the V1.x `tess_*` symbols so the
// Python GUI (which uses the `tess_*` surface) keeps working unchanged.

// 1. Mandatory Core Server Initialization Endpoint
PIRATE_EXPORT TesseractEngineHandle tesseract_create_engine(void);

// 2. Python-Facing C-API Hook for Dynamic Saturation Modifications
PIRATE_EXPORT void tesseract_set_vram_saturation(TesseractEngineHandle handle,
                                                  float saturation);

// 3. Inference Entrypoint with Pre/Post Layer Intercept Callbacks
PIRATE_EXPORT int tesseract_execute_inference_token(TesseractEngineHandle handle,
                                                     uint64_t token_id);

// 4. Clean Engine Release Context Shutdown
PIRATE_EXPORT void tesseract_destroy_engine(TesseractEngineHandle handle);

// 5. Circuit breaker toggle (mapped to runtime_directives)
PIRATE_EXPORT void tesseract_toggle_circuit_breaker(TesseractEngineHandle handle,
                                                     int enabled);

// 6. OpenAI-compatible chat completions endpoint (stub when llama is missing)
PIRATE_EXPORT int tesseract_openai_chat(TesseractEngineHandle handle,
                                         const char* request_json,
                                         int request_len,
                                         char* out, int out_cap);

// 8. SISSI & Ephemeral Session Cipher (M2M+SISSI+5+1 pipeline)
PIRATE_EXPORT void* tess_session_create(uint64_t seed);
PIRATE_EXPORT void  tess_session_destroy(void* session_ptr);
PIRATE_EXPORT int   tess_session_encode(void* session_ptr, const char* plaintext, char* out_buf, int out_cap, int* out_tokens_in, int* out_tokens_out);
PIRATE_EXPORT int   tess_session_decode(void* session_ptr, const char* encoded, char* out_buf, int out_cap);
PIRATE_EXPORT int   tess_session_build_index(void* session_ptr, char* out_buf, int out_cap);
PIRATE_EXPORT void  tess_session_teardown(void* session_ptr);

#ifdef __cplusplus
}
#endif
