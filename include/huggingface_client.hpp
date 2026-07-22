// huggingface_client.hpp — v2.0
//
// Hyper-Spherical Systems — HuggingFace API client
//
// Adds:
//   - set_token()         Set HF API token for authenticated requests
//   - fetch_model_card()  Get model metadata for validation
//   - stream_chunked()    Chunked streaming download (on-the-fly decompose)
//   - search_models()     Search with filters (size, architecture, tags)
//
// License: MIT

#pragma once
#include <string>
#include <vector>
#include <functional>
#include <cstdint>

namespace hypersp {

struct HfModelMeta {
    std::string model_id;
    std::string author;
    std::string architecture;   // e.g. "LlamaForCausalLM"
    size_t      size_mb{0};
    size_t      tensor_count{0};
    uint32_t    vocab_size{0};
    bool        has_safetensors{false};
    bool        has_gguf{false};
    std::vector<std::string> tags;
};

// Chunk callback: called with each downloaded chunk
// Return false to abort the download
using ChunkCallback = std::function<bool(const uint8_t* data, size_t len,
                                          size_t downloaded, size_t total)>;

class HuggingFaceClient {
public:
    HuggingFaceClient();
    ~HuggingFaceClient() = default;

    // Set the HuggingFace API token (needed for private repos + higher rate limits)
    void set_token(const std::string& token) { token_ = token; }

    // Search for public models
    std::vector<HfModelMeta> search_models(const std::string& query,
                                            const std::string& filter_arch = "",
                                            int max_size_gb = 0);

    // Fetch model card metadata for a specific repo (for validation)
    HfModelMeta fetch_model_card(const std::string& model_id);

    // Stream the full model file to a buffer (for small models)
    bool stream_weights(const std::string& model_id, std::vector<uint8_t>& buffer_out);

    // Stream in chunks for large models (on-the-fly decompose)
    // chunk_cb is called for each chunk; returns false to abort
    bool stream_chunked(const std::string& model_id,
                         size_t chunk_size_bytes,
                         ChunkCallback chunk_cb);

    // Validate that a local decomposed file matches the remote model card
    // Returns coverage percentage [0.0 .. 100.0]
    double validate_against_card(const std::string& local_output_path,
                                  const std::string& model_id);

private:
    std::string token_;

    // Internal HTTP helper (WinHTTP on Windows, libcurl stub otherwise)
    bool http_get(const std::string& url, std::string& response_out);
    bool http_get_stream(const std::string& url, ChunkCallback cb, size_t chunk_size);
};

} // namespace hypersp
