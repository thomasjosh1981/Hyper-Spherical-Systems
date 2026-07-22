#pragma once
#include <string>
#include <vector>
#include <memory>
#include "auto_embedder.hpp"

namespace hypersp {

class OrchestratorBridge {
public:
    OrchestratorBridge();
    ~OrchestratorBridge();

    // Initialize the orchestrator, must provide the path to brain.gguf/hscc
    bool initialize(const std::string& brain_model_path, size_t memory_limit_mb);

    // Route an MTP request to decide which experts/chunks to load
    std::vector<int> route_mtp_request(const std::string& prompt);

    bool is_alive() const;

private:
    bool initialized_;
    std::string brain_path_;
    size_t memory_limit_;
    std::unique_ptr<AutoEmbedder> embedder_;
    // Internal struct to hold model context
    void* orchestrator_ctx_; 
};

} // namespace hypersp
