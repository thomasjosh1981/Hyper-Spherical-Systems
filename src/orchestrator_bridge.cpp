#include "orchestrator_bridge.hpp"
#include <iostream>

namespace hypersp {

OrchestratorBridge::OrchestratorBridge() : initialized_(false), embedder_(std::make_unique<AutoEmbedder>()), orchestrator_ctx_(nullptr) {}

OrchestratorBridge::~OrchestratorBridge() {
    if (orchestrator_ctx_) {
        // Free the context here (simulated)
        orchestrator_ctx_ = nullptr;
    }
}

bool OrchestratorBridge::initialize(const std::string& brain_model_path, size_t memory_limit_mb) {
    std::cout << "[Orchestrator] Initializing Autonomous Supervisor...\n";
    std::cout << "[Orchestrator] Loading brain footprint from: " << brain_model_path << "\n";
    std::cout << "[Orchestrator] Constraining VRAM/RAM limit to: " << memory_limit_mb << " MB\n";
    
    brain_path_ = brain_model_path;
    memory_limit_ = memory_limit_mb;
    
    // Simulate initialization
    orchestrator_ctx_ = reinterpret_cast<void*>(static_cast<uintptr_t>(0xDEADBEEF));
    initialized_ = true;
    
    std::cout << "[Orchestrator] Supervisor brain online and ready to route MTP requests.\n";
    return true;
}

std::vector<int> OrchestratorBridge::route_mtp_request(const std::string& prompt) {
    std::vector<int> experts;
    if (!initialized_) {
        std::cerr << "[Orchestrator] FATAL ERROR: Attempted to route MTP request but supervisor is offline.\n";
        return experts;
    }
    
    std::cout << "[Orchestrator] Analyzing prompt for MTP routing...\n";
    // Simulated dynamic MoE routing logic using embeddings
    std::vector<float> embeddings = embedder_->generate_embeddings(prompt);
    
    // In a real scenario, we would map the embedding vector to closest Pop Clusters
    // For now, simulate by selecting chunks based on the first float value
    if (!embeddings.empty() && embeddings[0] > 0.0f) {
        experts = {0, 3, 7, 12};
    } else {
        experts = {1, 4, 8, 15};
    }
    
    std::cout << "[Orchestrator] Selected dynamic MoE chunks: [";
    for (size_t i = 0; i < experts.size(); ++i) {
        std::cout << experts[i] << (i < experts.size() - 1 ? ", " : "");
    }
    std::cout << "]\n";
    
    return experts;
}

bool OrchestratorBridge::is_alive() const {
    return initialized_;
}

} // namespace hypersp
