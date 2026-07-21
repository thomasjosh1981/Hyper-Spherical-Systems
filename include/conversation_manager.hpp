#pragma once
#include <string>
#include <vector>
#include <memory>
#include "synthetic_neuron.hpp"

namespace hypersp {

struct OverlayContext {
    std::string historical_prompt;
    std::string historical_response;
    float relevance_score;
};

class ContinuousConversationManager {
public:
    ContinuousConversationManager();
    ~ContinuousConversationManager() = default;

    // Set configuration thresholds
    void set_hyper_drift_threshold(float threshold) { hyper_drift_threshold_ = threshold; }
    void set_sub_drift_threshold(float threshold) { sub_drift_threshold_ = threshold; }

    // Core execution pipeline
    void process_interaction(const std::string& user_prompt, const std::string& ai_response);

    // Queries the topology for relevant past context to inject before hitting the LLM
    std::vector<OverlayContext> build_context_overlay(const std::string& current_prompt, size_t max_results = 5);

    std::shared_ptr<SynthuronBranch> get_active_branch() const { return active_branch_; }
    const SynthuronTopology& get_topology() const { return topology_; }

private:
    // Helper to calculate angular distance via HypersphereMath
    float calculate_drift(const HypersphereCoordinate& a, const HypersphereCoordinate& b) const;

    SynthuronTopology topology_;
    std::shared_ptr<SynthuronBranch> active_branch_;

    float hyper_drift_threshold_ = 0.7f;
    float sub_drift_threshold_ = 0.3f;
    size_t branch_counter_ = 1;
};

} // namespace hypersp
