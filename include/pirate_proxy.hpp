// pirate_proxy.hpp
//
// Pirate Llama — Universal LLM Proxy & Endpoint
//
// Intercepts OpenAI-compatible HTTP requests and routes them to any backend
// (Ollama, LM Studio, native llama.cpp) while applying Tesseract SISSI
// compression, HyperSphere memory management, and per-request telemetry.
//
// License: MIT (open source — see repository for full text)
// Proprietary engine components (SISSI, LeetCipher, ShardMatrix) are
// compiled separately and distributed as obfuscated freeware.

#pragma once
#include <string>
#include <vector>
#include <functional>
#include <atomic>
#include <thread>
#include <mutex>
#include <cstdint>
#include "hypersphere.hpp"

namespace pirate {

// ── Backend selection ──────────────────────────────────────────────────────
enum class Backend : uint8_t {
    AUTO_DETECT = 0,  // Try Ollama, then LM Studio, then native
    OLLAMA      = 1,  // Ollama on :11434
    LM_STUDIO   = 2,  // LM Studio on :1234
    NATIVE      = 3,  // Native llama.cpp (direct lib call)
    CUSTOM      = 4,  // User-specified host:port
};

// PCIe pipeline saturation strategy
enum class PCIeMode : uint8_t {
    DISABLED    = 0,
    ADAPTIVE    = 1,  // Auto-discover best block size
    FIXED_64K   = 2,
    FIXED_128K  = 3,
    FIXED_256K  = 4,
    FIXED_512K  = 5,
};

// ── Full proxy configuration — every knob exposed ─────────────────────────
struct ProxyConfig {
    // Proxy network
    uint16_t    proxy_port          = 11435;
    std::string proxy_host          = "127.0.0.1";
    int         request_timeout_ms  = 30000;
    int         max_connections     = 32;

    // Backend routing
    Backend     backend             = Backend::AUTO_DETECT;
    std::string backend_host        = "127.0.0.1";
    uint16_t    backend_port        = 11434;         // Ollama default
    std::string custom_backend_url  = "";

    // SISSI Compression
    bool        sissi_enabled               = true;
    bool        compress_requests           = true;
    bool        compress_responses          = true;
    
    // Cloud Context Adapter (SISSI RAG)
    bool        cloud_context_paging_enabled = false;
    uint32_t    max_cloud_context_chunks     = 5;
    bool        greedy_first                = true;
    bool        compress_large_words_first  = false;
    int         large_word_len_threshold    = 6;
    bool        recycle_symbols             = true;
    bool        discard_prepositions        = false;
    int         dynamic_profiling_threshold = 15000;
    bool        auto_tune_spin_enabled      = true;
    int         spin_sample_bytes           = 50000;

    // Memory management
    float       vram_target_pct     = 0.50f;
    float       stay_buffer_pct     = 0.15f;
    float       load_in_headroom    = 0.40f;
    uint32_t    max_context_tokens  = 32768;

    // NVMe / storage
    bool        nvme_prefetch_enabled = true;
    int         nvme_block_size_kb    = 256;

    // PCIe pipeline
    PCIeMode    pcie_mode             = PCIeMode::ADAPTIVE;

    // Backup / archive settings
    int         backup_interval_min   = 10;
    int         backup_compress_level = 6;
    bool        backup_encrypt        = true;
    bool        backup_7zip_pass      = true;

    // Telemetry
    bool        telemetry_enabled     = true;
    bool        log_to_file           = false;
    std::string log_path              = "pirate_llama.log";
    
    // DRM state
    bool        is_pro_tier           = false;
};

// ── Live telemetry snapshot ────────────────────────────────────────────────
struct ProxyTelemetry {
    float    vram_usage_pct       = 0.0f;
    float    ram_usage_pct        = 0.0f;
    float    compression_ratio    = 1.0f;
    uint64_t requests_handled     = 0;
    uint64_t tokens_compressed    = 0;
    uint64_t bytes_saved          = 0;
    uint32_t active_connections   = 0;
    Backend  active_backend       = Backend::AUTO_DETECT;
    bool     backend_reachable    = false;
    char     backend_model[128]   = {};
    uint64_t forward_pass_count   = 0;
};

// ── Request/Response wrappers ──────────────────────────────────────────────
struct HttpRequest {
    std::string method;
    std::string path;
    std::string body;
    std::vector<std::pair<std::string, std::string>> headers;
};

struct HttpResponse {
    int         status_code = 200;
    std::string body;
    std::vector<std::pair<std::string, std::string>> headers;
};

// ── The Proxy Server ───────────────────────────────────────────────────────
class PirateProxy {
public:
    explicit PirateProxy(const ProxyConfig& cfg = {});
    ~PirateProxy();

    // Start/stop the proxy listener
    bool start();
    void stop();
    bool is_running() const noexcept;

    // Update config live (thread-safe)
    void update_config(const ProxyConfig& cfg);
    ProxyConfig get_config() const;

    // Get live telemetry snapshot
    ProxyTelemetry get_telemetry() const;

    // Manually probe which backend is reachable
    Backend detect_backend();

    // Force-switch backend at runtime
    void set_backend(Backend b, const std::string& host = "", uint16_t port = 0);

private:
    void accept_loop();
    void handle_connection(int client_fd);

    HttpResponse handle_chat_completions(const HttpRequest& req);
    HttpResponse handle_completions(const HttpRequest& req);
    HttpResponse handle_models(const HttpRequest& req);
    HttpResponse handle_health(const HttpRequest& req);

    // SISSI utilities
    std::string sissi_compress_prompt(const std::string& input);
    std::string sissi_decompress_response(const std::string& input);

    // --- Cloud Context Adapter ---
    struct CloudContextChunk {
        std::string raw_text;
        tesseract::HypersphereCoordinate embedding;
    };
    std::vector<CloudContextChunk> local_context_history_;
    std::mutex context_mtx_;

private:
    HttpResponse dispatch_request(const HttpRequest& req);

    // Backend forwarding
    HttpResponse forward_to_backend(const HttpRequest& req);
    bool         probe_backend(const std::string& host, uint16_t port);

    // Socket helpers (cross-platform)
    int  create_server_socket();
    void close_socket(int fd);

    ProxyConfig              cfg_;
    mutable std::mutex       cfg_mtx_;
    mutable std::mutex       telem_mtx_;
    ProxyTelemetry           telemetry_;

    std::atomic<bool>        running_{false};
    std::thread              accept_thread_;
    int                      server_fd_ = -1;

    // Per-connection thread pool (simple)
    std::vector<std::thread> workers_;
    std::atomic<int>         active_conns_{0};
};

} // namespace pirate
