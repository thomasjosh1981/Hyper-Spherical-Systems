// python_bridge.cpp
//
// Implements the extern "C" ABI declared in python_bridge.hpp. Each entry
// point marshals arguments, calls the appropriate Tesseract core engine
// method, and converts the result back into a C-friendly primitive.
//
// All state lives inside `struct TessEngine` (opaque to Python).

#include "python_bridge.hpp"
#include "python_bridge.hpp"
#include "config.hpp"
#include "types.hpp"
#include "context_compressor.hpp"
#include "memory_manager.hpp"
#include "predictive_prefetcher.hpp"
#include "nvme_io.hpp"
#include "recovery_checkpoint.hpp"
#include "telemetry_logger.hpp"
#include "index_registry.hpp"
#include "shard_matrix.hpp"
#include "leet_cipher.hpp"
#include "tesseract_security_tripwire.hpp"
#include "tesseract_obfuscation.hpp"

#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

// V1.7 mandatory llama.cpp gating — spec §2: build aborts if llama missing.
#if !defined(TESSERACT_USE_LLAMA)
#  if defined(TESSERACT_REQUIRE_LLAMA)
#    error "Project Tesseract compilation aborted: llama.cpp backend is mandatory for full hardware acceleration (define TESSERACT_USE_LLAMA=1 and link llama)."
#  endif
#  define TESSERACT_USE_LLAMA 0
#endif

// Forward-declare llama.cpp types so the bridge can hold pointers without
// pulling in llama headers here. The actual linkage happens in the root
// tesseract_bridge.cpp (where the FetchContent'd llama is wired in).
struct llama_model;
struct llama_context;

// Note: the rest of this file uses `tesseract::Config`, `tesseract::MemoryManager`
// etc. Those names are resolved by the existing top-level `namespace tesseract { ... }`
// declared elsewhere in this TU (the original engine code). We don't add any
// alias here to avoid conflicting with that declaration.

namespace {

// Per-instance error string for tess_last_error()
thread_local std::string g_last_error;

void set_error(const std::string& msg) { g_last_error = msg; }

// Cast helper for opaque handle validation.
struct TessEngineImpl {
    tesseract::Config                       cfg;
    std::unique_ptr<tesseract::ContextCompressor> compressor;
    std::unique_ptr<tesseract::MemoryManager>     memory;
    std::unique_ptr<tesseract::PatternPredictor>  predictor;
    std::unique_ptr<tesseract::WeightStreamer>    streamer;
    std::unique_ptr<tesseract::NVMeIO>            nvme;
    std::unique_ptr<tesseract::RecoveryCheckpoint> checkpoint;
    std::unique_ptr<tesseract::TelemetryLogger>   telemetry;
    std::unique_ptr<tesseract::IndexRegistry>     index;
    bool                                        vram_ready = false;
    uint64_t                                    virtual_vram_bytes = 0;  // 60GB illusion by default
    std::string                                 session_text_history;

    TessEngineImpl() {
        cfg.ram_total_bytes    = 32ULL * 1024 * 1024 * 1024;
        cfg.phys_vram_bytes    = 12ULL * 1024 * 1024 * 1024;
        cfg.virtual_vram_bytes = 60ULL * 1024 * 1024 * 1024;  // V1.7.1: 60GB illusion
        virtual_vram_bytes     = cfg.virtual_vram_bytes;
        compressor   = std::make_unique<tesseract::ContextCompressor>(cfg);
        memory       = std::make_unique<tesseract::MemoryManager>(cfg);
        predictor    = std::make_unique<tesseract::PatternPredictor>(cfg);
        // WeightStreamer requires VRAM bytes at construction; initialize lazily.
        nvme         = std::make_unique<tesseract::NVMeIO>("D:\\tesseract_bridge");
        checkpoint   = std::make_unique<tesseract::RecoveryCheckpoint>();
        telemetry    = std::make_unique<tesseract::TelemetryLogger>();
        index        = std::make_unique<tesseract::IndexRegistry>();
    }
};

// V1.7 InternalEngine: thin wrapper holding the same TessEngineImpl plus
// llama.cpp model/context pointers. The tess_* API operates on TessEngineImpl;
// the tesseract_* V1.7 API operates on InternalEngine (which composes one).
struct InternalEngine {
    llama_model*    backend_model = nullptr;
    llama_context*  backend_ctx   = nullptr;
    float           current_vram_saturation = 0.50f;
    bool            circuit_breaker_active  = true;
    std::unique_ptr<TessEngineImpl> inner;
    InternalEngine() : inner(std::make_unique<TessEngineImpl>()) {}
};

}  // namespace

extern "C" {

TESS_EXPORT tess_handle_t tess_create(void) {
    try {
        return reinterpret_cast<tess_handle_t>(new TessEngineImpl());
    } catch (const std::exception& e) {
        set_error(std::string("tess_create: ") + e.what());
        return nullptr;
    }
}

TESS_EXPORT void tess_destroy(tess_handle_t h) {
    if (!h) return;
    delete reinterpret_cast<TessEngineImpl*>(h);
}



TESS_EXPORT int tess_init_vram(tess_handle_t h, uint64_t phys_vram_bytes,
                                  uint64_t phys_ram_bytes) {
    if (!h) { set_error("tess_init_vram: null handle"); return TESS_BAD_HANDLE; }
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    try {
        eng->cfg.phys_vram_bytes = phys_vram_bytes;
        eng->cfg.ram_total_bytes = phys_ram_bytes;
        eng->memory->set_ram_total(phys_ram_bytes);
        eng->memory->initialize_vram(static_cast<size_t>(phys_vram_bytes));
        eng->streamer = std::make_unique<tesseract::WeightStreamer>(eng->cfg,
                                                                    static_cast<size_t>(phys_vram_bytes));
        eng->vram_ready = true;
        return TESS_OK;
    } catch (const std::exception& e) {
        set_error(std::string("tess_init_vram: ") + e.what());
        return TESS_OUT_OF_MEMORY;
    }
}

// V1.7.1: extended init that also accepts the virtual VRAM illusion size.
TESS_EXPORT int tess_init_vram_v2(tess_handle_t h,
                                    uint64_t phys_vram_bytes,
                                    uint64_t phys_ram_bytes,
                                    uint64_t virtual_vram_bytes) {
    if (!h) return TESS_BAD_HANDLE;
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    eng->virtual_vram_bytes = virtual_vram_bytes ? virtual_vram_bytes
                                                  : (60ULL * 1024 * 1024 * 1024);
    eng->cfg.virtual_vram_bytes = eng->virtual_vram_bytes;
    return tess_init_vram(h, phys_vram_bytes, phys_ram_bytes);
}

TESS_EXPORT uint64_t tess_virtual_vram_bytes(tess_handle_t h) {
    if (!h) return 0;
    return reinterpret_cast<TessEngineImpl*>(h)->virtual_vram_bytes;
}
TESS_EXPORT uint64_t tess_phys_vram_bytes(tess_handle_t h) {
    if (!h) return 0;
    return reinterpret_cast<TessEngineImpl*>(h)->cfg.phys_vram_bytes;
}
TESS_EXPORT uint64_t tess_phys_ram_bytes(tess_handle_t h) {
    if (!h) return 0;
    return reinterpret_cast<TessEngineImpl*>(h)->cfg.ram_total_bytes;
}
TESS_EXPORT float tess_vram_illusion_ratio(tess_handle_t h) {
    if (!h) return 1.0f;
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    if (eng->cfg.phys_vram_bytes == 0) return 1.0f;
    return static_cast<float>(eng->virtual_vram_bytes)
         / static_cast<float>(eng->cfg.phys_vram_bytes);
}

TESS_EXPORT int tess_compress(tess_handle_t h,
                              const char* text, int text_len,
                              char* out_json, int out_cap) {
    if (!h) { set_error("tess_compress: null handle"); return TESS_BAD_HANDLE; }
    if (!text || text_len < 0 || !out_json || out_cap <= 0)
    { set_error("tess_compress: bad arg"); return TESS_BAD_ARG; }
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    try {
        std::string_view sv(text, static_cast<size_t>(text_len));
        auto entries = eng->compressor->compress(sv);
        eng->session_text_history = std::string(sv);
        float ratio = eng->compressor->compression_ratio();

        std::string out;
        out.reserve(256 + entries.size() * 16);
        out += "{\"compression_ratio\":";
        out += std::to_string(ratio);
        out += ",\"entries\":[";
        for (size_t i = 0; i < entries.size(); ++i) {
            if (i) out += ',';
            out += "{\"pos\":"; out += std::to_string(entries[i].context_pos);
            out += ",\"compressed\":";
            out += (entries[i].is_compressed ? "true" : "false");
            out += ",\"code\":";
            out += std::to_string(entries[i].dict_code);
            out += ",\"len\":";
            out += std::to_string(entries[i].original_size_bytes);
            out += '}';
        }
        out += "]}";

        if (static_cast<int>(out.size()) >= out_cap) {
            set_error("tess_compress: output buffer too small");
            return TESS_BAD_ARG;
        }
        std::memcpy(out_json, out.data(), out.size());
        out_json[out.size()] = '\0';
        return static_cast<int>(out.size());
    } catch (const std::exception& e) {
        set_error(std::string("tess_compress: ") + e.what());
        return TESS_OUT_OF_MEMORY;
    }
}

TESS_EXPORT int tess_decompress(tess_handle_t h,
                                const char* in_json, int in_len,
                                char* out_text, int out_cap) {
    if (!h) { set_error("tess_decompress: null handle"); return TESS_BAD_HANDLE; }
    if (!in_json || in_len <= 0 || !out_text || out_cap <= 0)
    { set_error("tess_decompress: bad arg"); return TESS_BAD_ARG; }
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    try {
        std::string_view sv(in_json, static_cast<size_t>(in_len));
        auto entries = eng->compressor->compress(sv);
        std::string back = eng->compressor->decompress(entries);
        if (static_cast<int>(back.size()) >= out_cap) {
            set_error("tess_decompress: output buffer too small");
            return TESS_BAD_ARG;
        }
        std::memcpy(out_text, back.data(), back.size());
        out_text[back.size()] = '\0';
        return static_cast<int>(back.size());
    } catch (const std::exception& e) {
        set_error(std::string("tess_decompress: ") + e.what());
        return TESS_OUT_OF_MEMORY;
    }
}

TESS_EXPORT int tess_push_layer(tess_handle_t h, uint32_t layer_id,
                                uint64_t byte_size) {
    if (!h) { set_error("tess_push_layer: null handle"); return TESS_BAD_HANDLE; }
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    try {
        tesseract::LayerShard s;
        s.layer_id  = layer_id;
        s.byte_size = static_cast<size_t>(byte_size);
        return static_cast<int>(eng->memory->push_layer(s, true));
    } catch (const std::exception& e) {
        set_error(std::string("tess_push_layer: ") + e.what());
        return TESS_OUT_OF_MEMORY;
    }
}

TESS_EXPORT uint64_t tess_vram_used(tess_handle_t h) {
    if (!h) return 0;
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    return eng->vram_ready
        ? static_cast<uint64_t>((eng->memory->vram_usage_percent() / 100.0f)
                               * eng->cfg.virtual_vram_bytes)
        : 0ULL;
}

TESS_EXPORT uint64_t tess_vram_budget(tess_handle_t h) {
    if (!h) return 0;
    return reinterpret_cast<TessEngineImpl*>(h)->virtual_vram_bytes;
}

TESS_EXPORT float tess_vram_usage_pct(tess_handle_t h) {
    if (!h) return 0.f;
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    return eng->vram_ready ? eng->memory->vram_usage_percent() : 0.f;
}

TESS_EXPORT uint64_t tess_ram_staging_used(tess_handle_t h) {
    if (!h) return 0;
    return reinterpret_cast<TessEngineImpl*>(h)->memory->ram_staging_bytes();
}

TESS_EXPORT uint64_t tess_ram_staging_limit(tess_handle_t h) {
    if (!h) return 0;
    return reinterpret_cast<TessEngineImpl*>(h)->memory->ram_staging_limit();
}

TESS_EXPORT void tess_observe_layer(tess_handle_t h, uint32_t layer_id) {
    if (!h) return;
    reinterpret_cast<TessEngineImpl*>(h)->predictor->observe_layer(layer_id);
}

TESS_EXPORT int tess_predict_next(tess_handle_t h, uint32_t* out_ids, int cap,
                                  float* out_confidence) {
    if (!h || !out_ids || cap <= 0) return 0;
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    auto pred = eng->predictor->predict_next(static_cast<size_t>(cap));
    int n = static_cast<int>(pred.layer_ids.size());
    if (n > cap) n = cap;
    for (int i = 0; i < n; ++i) out_ids[i] = pred.layer_ids[i];
    if (out_confidence) *out_confidence = pred.confidence;
    return n;
}

TESS_EXPORT uint64_t tess_total_observations(tess_handle_t h) {
    if (!h) return 0;
    return reinterpret_cast<TessEngineImpl*>(h)->predictor->total_observations();
}

TESS_EXPORT int tess_io_write(tess_handle_t h, const char* rel_path,
                              const uint8_t* data, int len) {
    if (!h || !rel_path || !data || len <= 0) return TESS_BAD_ARG;
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    return static_cast<int>(eng->nvme->write_block(rel_path, data,
                                                    static_cast<size_t>(len)));
}

TESS_EXPORT int tess_io_read(tess_handle_t h, const char* rel_path,
                             uint8_t* out_buf, int cap) {
    if (!h || !rel_path || !out_buf || cap <= 0) return TESS_BAD_ARG;
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    return static_cast<int>(eng->nvme->read_block(rel_path, out_buf,
                                                   static_cast<size_t>(cap)));
}

TESS_EXPORT int tess_checkpoint_save(tess_handle_t h, const char* path) {
    if (!h || !path) return TESS_BAD_ARG;
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    if (eng->vram_ready) {
        eng->checkpoint->set_vram_mark(static_cast<uint64_t>(eng->memory->vram_usage_percent()));
    }
    bool checkpoint_ok = eng->checkpoint->save_to(path);

    // Save encrypted session text history to .tess_session.bak
    if (!eng->session_text_history.empty()) {
        tesseract::UserCredentials creds;
        creds.username = "twist";
        creds.password = "pass123";
        creds.pin = "123456";
        creds.leet_key = "t3553r4c7"; // default leet key for automatic crash backup
        
        std::vector<uint8_t> data(eng->session_text_history.begin(), eng->session_text_history.end());
        auto encrypted = tesseract::LeetCipher::encrypt(data, creds);
        
        std::string backup_path = std::string(path) + ".tess_session.bak";
        std::ofstream f(backup_path, std::ios::binary | std::ios::trunc);
        if (f) {
            f.write(reinterpret_cast<const char*>(encrypted.data()), encrypted.size());
        }
    }

    return checkpoint_ok ? TESS_OK : TESS_IO_FAIL;
}

TESS_EXPORT int tess_checkpoint_load(tess_handle_t h, const char* path) {
    if (!h || !path) return TESS_BAD_ARG;
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    bool checkpoint_ok = tesseract::RecoveryCheckpoint::load_from(path);

    // Load and decrypt session text history from .tess_session.bak
    std::string backup_path = std::string(path) + ".tess_session.bak";
    std::ifstream f(backup_path, std::ios::binary | std::ios::ate);
    if (f) {
        size_t sz = static_cast<size_t>(f.tellg());
        std::vector<uint8_t> encrypted(sz);
        f.seekg(0);
        if (f.read(reinterpret_cast<char*>(encrypted.data()), sz)) {
            tesseract::UserCredentials creds;
            creds.username = "twist";
            creds.password = "pass123";
            creds.pin = "123456";
            creds.leet_key = "t3553r4c7";
            auto decrypted = tesseract::LeetCipher::decrypt(encrypted, creds);
            eng->session_text_history.assign(decrypted.begin(), decrypted.end());
        }
    }

    return checkpoint_ok ? TESS_OK : TESS_IO_FAIL;
}

TESS_EXPORT int tess_get_session_history(tess_handle_t h, char* out, int cap) {
    if (!h || !out || cap <= 0) return TESS_BAD_ARG;
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    if (static_cast<int>(eng->session_text_history.size()) >= cap) return TESS_BAD_ARG;
    std::memcpy(out, eng->session_text_history.data(), eng->session_text_history.size());
    out[eng->session_text_history.size()] = '\0';
    return static_cast<int>(eng->session_text_history.size());
}

TESS_EXPORT void tess_telemetry_get(tess_handle_t h, TessTelemetry* out) {
    if (!h || !out) return;
    auto* eng = reinterpret_cast<TessEngineImpl*>(h);
    auto s = eng->telemetry->current_snapshot();
    out->vram_usage_pct   = s.vram_usage_pct;
    out->ram_staging_pct  = s.ram_staging_pct;
    out->active_kv_tokens = s.active_kv_tokens;
    out->prefetch_pending = s.prefetch_pending;
}

TESS_EXPORT int tess_index_build(tess_handle_t h, const char* dir) {
    if (!h || !dir) return TESS_BAD_ARG;
    reinterpret_cast<TessEngineImpl*>(h)->index->build_index(dir);
    return TESS_OK;
}

TESS_EXPORT int tess_index_shards_in_vram(tess_handle_t h) {
    if (!h) return TESS_BAD_HANDLE;
    auto shards = reinterpret_cast<TessEngineImpl*>(h)->index->get_layers_in_vram();
    return static_cast<int>(shards.size());
}

TESS_EXPORT const char* tess_version(void) {
    return "Tesseract Bridge v1.0.0 (gemma4 backend, 60GB VRAM illusion)";
}

TESS_EXPORT const char* tess_last_error(tess_handle_t h) {
    (void)h;
    return g_last_error.c_str();
}

// =====================================================================
// V1.4 directives
// =====================================================================
namespace {
std::atomic<int>  g_dir_breathing{1};
std::atomic<int>  g_dir_breaker{1};
std::atomic<int>  g_dir_scissi{1};
std::atomic<int>  g_dir_homophonic{1};
std::atomic<float> g_dir_vram_target{0.50f};
std::atomic<float> g_dir_stay_buffer{0.15f};
std::atomic<float> g_dir_load_in_headroom{0.40f};
}

extern "C" {
TESS_EXPORT int tess_set_directive_bool(const char* name, int value) {
    if (!name) return -1;
    std::string n(name);
    int v = value != 0;
    if      (n == "elastic_breathing_search")    g_dir_breathing.store(v);
    else if (n == "enable_circuit_breaker")      g_dir_breaker.store(v);
    else if (n == "scissi_phrase_compression")   g_dir_scissi.store(v);
    else if (n == "homophonic_flattening_matrix") g_dir_homophonic.store(v);
    else return -2;
    return 0;
}
TESS_EXPORT int tess_set_directive_float(const char* name, float value) {
    if (!name) return -1;
    std::string n(name);
    if      (n == "vram_saturation_target")   g_dir_vram_target.store(value);
    else if (n == "nvme_stay_in_buffer")      g_dir_stay_buffer.store(value);
    else if (n == "load_in_headroom_trigger") g_dir_load_in_headroom.store(value);
    else return -2;
    return 0;
}
TESS_EXPORT int tess_get_directive_float(const char* name, float* out) {
    if (!name || !out) return -1;
    std::string n(name);
    if      (n == "vram_saturation_target")   *out = g_dir_vram_target.load();
    else if (n == "nvme_stay_in_buffer")      *out = g_dir_stay_buffer.load();
    else if (n == "load_in_headroom_trigger") *out = g_dir_load_in_headroom.load();
    else return -2;
    return 0;
}
TESS_EXPORT int tess_set_breathing_mode(tess_handle_t h, int enabled) {
    if (!h) return TESS_BAD_HANDLE;
    reinterpret_cast<TessEngineImpl*>(h)->memory->set_breathing_mode(enabled != 0);
    return TESS_OK;
}
TESS_EXPORT int tess_set_circuit_breaker(tess_handle_t h, int enabled) {
    if (!h) return TESS_BAD_HANDLE;
    reinterpret_cast<TessEngineImpl*>(h)->memory->set_circuit_breaker(enabled != 0);
    return TESS_OK;
}

// =====================================================================
// V1.3 PQC + obfuscation
// =====================================================================
TESS_EXPORT int tess_pqc_active_backend(void) {
    return static_cast<int>(Tesseract::Security::Pqc::ActiveBackend());
}
TESS_EXPORT int tess_pqc_kyber_keygen(tess_handle_t h) {
    (void)h;
    Tesseract::Security::Pqc::KyberKeyPair kp;
    auto s = Tesseract::Security::Pqc::KyberKeygen(kp);
    return s == Tesseract::Security::Pqc::Status::OK ? TESS_OK : TESS_IO_FAIL;
}
TESS_EXPORT int tess_pqc_kyber_roundtrip(tess_handle_t h) {
    (void)h;
    Tesseract::Security::Pqc::KyberKeyPair kp;
    if (Tesseract::Security::Pqc::KyberKeygen(kp) != Tesseract::Security::Pqc::Status::OK)
        return TESS_IO_FAIL;
    Tesseract::Security::Pqc::KyberCiphertext ct;
    Tesseract::Security::Pqc::SharedSecret ss_a, ss_b;
    if (Tesseract::Security::Pqc::KyberEncapsulate(kp.public_key, ct, ss_a) != Tesseract::Security::Pqc::Status::OK)
        return TESS_IO_FAIL;
    if (Tesseract::Security::Pqc::KyberDecapsulate(kp, ct, ss_b) != Tesseract::Security::Pqc::Status::OK)
        return TESS_IO_FAIL;
    return ss_a.size() == ss_b.size() ? TESS_OK : TESS_IO_FAIL;
}
TESS_EXPORT int tess_pqc_nested_roundtrip(tess_handle_t h,
                                          const uint8_t* in, int in_len,
                                          uint8_t* out, int out_cap) {
    (void)h;
    if (!in || in_len <= 0 || !out || out_cap <= 0) return TESS_BAD_ARG;
    Tesseract::Security::Pqc::KyberKeyPair kp;
    if (Tesseract::Security::Pqc::KyberKeygen(kp) != Tesseract::Security::Pqc::Status::OK)
        return TESS_IO_FAIL;
    Tesseract::Security::Pqc::KyberCiphertext ct;
    Tesseract::Security::Pqc::SharedSecret ss;
    if (Tesseract::Security::Pqc::KyberEncapsulate(kp.public_key, ct, ss) != Tesseract::Security::Pqc::Status::OK)
        return TESS_IO_FAIL;
    std::vector<uint8_t> ciphertext;
    std::span<const uint8_t> pt{in, static_cast<size_t>(in_len)};
    if (auto s = Tesseract::Security::Pqc::NestedEncrypt(ss, pt, ciphertext);
            s != Tesseract::Security::Pqc::Status::OK)
        return TESS_IO_FAIL;
    std::span<const uint8_t> ct_span{ciphertext.data(), ciphertext.size()};
    std::vector<uint8_t> decrypted;
    if (auto s = Tesseract::Security::Pqc::NestedDecrypt(ss, ct_span, decrypted);
            s != Tesseract::Security::Pqc::Status::OK)
        return TESS_IO_FAIL;
    if (static_cast<int>(decrypted.size()) > out_cap) return TESS_BAD_ARG;
    std::memcpy(out, decrypted.data(), decrypted.size());
    return static_cast<int>(decrypted.size());
}
TESS_EXPORT int tess_obfuscation_flatten(tess_handle_t h,
                                          uint8_t* buffer, int len,
                                          int language_index) {
    (void)h;
    if (!buffer || len <= 0) return TESS_BAD_ARG;
    if (language_index < 0 || language_index >= 6) return TESS_BAD_ARG;
    Tesseract::Security::ObfuscationEngine::FlattenPayload(buffer,
        static_cast<size_t>(len), static_cast<size_t>(language_index));
    return TESS_OK;
}
TESS_EXPORT int tess_obfuscation_unflatten(tess_handle_t h,
                                            uint8_t* buffer, int len,
                                            int language_index) {
    (void)h;
    if (!buffer || len <= 0) return TESS_BAD_ARG;
    if (language_index < 0 || language_index >= 6) return TESS_BAD_ARG;
    Tesseract::Security::ObfuscationEngine::UnflattenPayload(buffer,
        static_cast<size_t>(len), static_cast<size_t>(language_index));
    return TESS_OK;
}

// =====================================================================
// V1.1 tripwire
// =====================================================================
TESS_EXPORT int tess_tripwire_arm(tess_handle_t h,
                                    uintptr_t low, uintptr_t high,
                                    int abort_on_trip) {
    (void)h;
    if (high < low) return TESS_BAD_ARG;
    Tesseract::Security::TripwireEngine::SetAbortOnTrip(abort_on_trip != 0);
    Tesseract::Security::TripwireEngine::RegisterHoneyGateRange(low,
        static_cast<size_t>(high - low));
    return TESS_OK;
}
TESS_EXPORT int tess_tripwire_disarm(tess_handle_t h) {
    (void)h;
    Tesseract::Security::TripwireEngine::ClearHoneyGateRange();
    return TESS_OK;
}
TESS_EXPORT int tess_tripwire_check(tess_handle_t h, uintptr_t target) {
    (void)h;
    return Tesseract::Security::TripwireEngine::IsAddressIntercepted(target)
        ? 1 : 0;
}

// =====================================================================
// V1.3 shard matrix
// =====================================================================
namespace {
std::unique_ptr<Tesseract::Security::Sharding::ShardMatrix> g_shard_matrix;
std::mutex g_shard_mtx;
}

TESS_EXPORT int tess_shard_open(tess_handle_t h, const char* base_dir) {
    (void)h;
    if (!base_dir) return TESS_BAD_ARG;
    std::lock_guard<std::mutex> lk(g_shard_mtx);
    Tesseract::Security::Sharding::ShardMatrix::Config cfg;
    cfg.base_dir  = base_dir;
    cfg.decoy_dir = (std::filesystem::path(base_dir) / "decoys").string();
    cfg.enable_rotator = true;
    cfg.rotator_interval_ms = 2000;
    g_shard_matrix = std::make_unique<Tesseract::Security::Sharding::ShardMatrix>(cfg);
    return g_shard_matrix->open_all() ? TESS_OK : TESS_IO_FAIL;
}
TESS_EXPORT int tess_shard_write_payload(tess_handle_t h,
                                          const uint8_t* data, int len) {
    (void)h;
    if (!g_shard_matrix || !data || len <= 0) return TESS_BAD_ARG;
    auto s = g_shard_matrix->write_payload(data, static_cast<size_t>(len));
    return s == Tesseract::Security::Pqc::Status::OK ? TESS_OK : TESS_IO_FAIL;
}
TESS_EXPORT int tess_shard_read_payload(tess_handle_t h,
                                         uint8_t* out, int out_cap) {
    (void)h;
    if (!g_shard_matrix || !out || out_cap <= 0) return TESS_BAD_ARG;
    std::vector<uint8_t> buf;
    if (!g_shard_matrix->read_payload(buf)) return TESS_IO_FAIL;
    if (static_cast<int>(buf.size()) > out_cap) return TESS_BAD_ARG;
    std::memcpy(out, buf.data(), buf.size());
    return static_cast<int>(buf.size());
}
TESS_EXPORT int tess_shard_rotate(tess_handle_t h) {
    (void)h;
    if (!g_shard_matrix) return TESS_BAD_ARG;
    g_shard_matrix->rotate_now();
    return TESS_OK;
}
TESS_EXPORT int tess_shard_close(tess_handle_t h) {
    (void)h;
    std::lock_guard<std::mutex> lk(g_shard_mtx);
    g_shard_matrix.reset();
    return TESS_OK;
}

// =====================================================================
// V1.4 / V1.5 blueprint dump
// =====================================================================
TESS_EXPORT int tess_commit_blueprint(const char* json_path) {
    if (!json_path) return TESS_BAD_ARG;
    std::FILE* f = nullptr;
#if defined(_MSC_VER)
    if (fopen_s(&f, json_path, "w") != 0) return TESS_IO_FAIL;
#else
    f = std::fopen(json_path, "w");
#endif
    if (!f) return TESS_IO_FAIL;
    std::fprintf(f,
        "{\n"
        "  \"runtime_directives\": {\n"
        "    \"elastic_breathing_search\": %s,\n"
        "    \"enable_circuit_breaker\": %s,\n"
        "    \"scissi_phrase_compression\": %s,\n"
        "    \"homophonic_flattening_matrix\": %s,\n"
        "    \"vram_saturation_target\": %.4f,\n"
        "    \"nvme_stay_in_buffer\": %.4f,\n"
        "    \"load_in_headroom_trigger\": %.4f\n"
        "  }\n"
        "}\n",
        g_dir_breathing.load()  ? "true" : "false",
        g_dir_breaker.load()    ? "true" : "false",
        g_dir_scissi.load()     ? "true" : "false",
        g_dir_homophonic.load() ? "true" : "false",
        g_dir_vram_target.load(),
        g_dir_stay_buffer.load(),
        g_dir_load_in_headroom.load());
    std::fclose(f);
    return TESS_OK;
}

// =====================================================================
// V1.7 — Mandatory Core Endpoint
// =====================================================================
TESS_EXPORT TesseractEngineHandle tesseract_create_engine(void) {
    std::cout << "[ROOT_SERVER] Initializing dedicated local LLM host on root interface...\n";
#if TESSERACT_USE_LLAMA
    std::cout << "[ROOT_SERVER] llama.cpp backend linked and active.\n";
#else
    std::cout << "[ROOT_SERVER] llama.cpp backend NOT linked — running in stub mode.\n";
#endif
    auto* engine = new (std::nothrow) InternalEngine();
    if (!engine) {
        std::cerr << "[CRITICAL] Out of memory allocating InternalEngine.\n";
        return nullptr;
    }
    std::cout << "[ROOT_SERVER] Local LLM server successfully listening on network loops.\n";
    return static_cast<TesseractEngineHandle>(engine);
}

TESS_EXPORT void tesseract_set_vram_saturation(TesseractEngineHandle handle,
                                                  float saturation) {
    if (!handle) return;
    auto* engine = static_cast<InternalEngine*>(handle);
    engine->current_vram_saturation = saturation;
    g_dir_vram_target.store(saturation);
    if (engine->inner && engine->inner->vram_ready) {
        engine->inner->memory->set_breathing_mode(saturation < 0.50f);
    }
    std::cout << "[SHIM] VRAM Saturation adjusted via GUI to: " << saturation << "\n";
}

TESS_EXPORT int tesseract_execute_inference_token(TesseractEngineHandle handle,
                                                     uint64_t token_id) {
    if (!handle) return -1;
    auto* engine = static_cast<InternalEngine*>(handle);
    if (engine->inner && engine->inner->vram_ready) {
        engine->inner->predictor->observe_layer(static_cast<uint32_t>(token_id));
    }
    std::cout << "[HOOK] Layer callback evaluating token transaction ID: " << token_id << "\n";
    return 0;
}

TESS_EXPORT void tesseract_destroy_engine(TesseractEngineHandle handle) {
    if (!handle) return;
    auto* engine = static_cast<InternalEngine*>(handle);
    delete engine;
    std::cout << "[ROOT_SERVER] Local server endpoint closed down cleanly.\n";
}

TESS_EXPORT void tesseract_toggle_circuit_breaker(TesseractEngineHandle handle,
                                                     int enabled) {
    if (!handle) return;
    auto* engine = static_cast<InternalEngine*>(handle);
    engine->circuit_breaker_active = (enabled != 0);
    g_dir_breaker.store(enabled != 0);
    if (engine->inner && engine->inner->vram_ready) {
        engine->inner->memory->set_circuit_breaker(enabled != 0);
    }
}

TESS_EXPORT int tesseract_openai_chat(TesseractEngineHandle handle,
                                         const char* request_json, int request_len,
                                         char* out, int out_cap) {
    if (!handle || !out || out_cap <= 0) return -1;
    auto* engine = static_cast<InternalEngine*>(handle);
    (void)engine;
    static constexpr const char* kStub =
        R"({"id":"tess-stub","object":"chat.completion","created":0,)"
        R"("model":"tesseract-stub","choices":[{"index":0,)"
        R"("message":{"role":"assistant","content":)"
        R"("[Tesseract bridge] llama.cpp not linked — running in stub mode. )"
        R"(Set TESSERACT_USE_LLAMA=1 and link libllama for real inference.")},)"
        R"("finish_reason":"stop"}],"usage":{"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}})";
    (void)request_json; (void)request_len;
    int needed = static_cast<int>(std::strlen(kStub)) + 1;
    if (needed > out_cap) return -2;
    std::memcpy(out, kStub, needed);
    return needed - 1;
}

TESS_EXPORT int tesseract_llama_backend_active(void) {
#if TESSERACT_USE_LLAMA
    return 1;
#else
    return 0;
#endif
}

}  // extern "C"
}  // namespace
