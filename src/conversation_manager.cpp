#include "conversation_manager.hpp"
#include <iostream>
#include <algorithm>

namespace hypersp {

ContinuousConversationManager::ContinuousConversationManager() {
    // Initialize with a root hyper branch
    active_branch_ = topology_.map_concept("root_conversation");
}

float ContinuousConversationManager::calculate_drift(const HypersphereCoordinate& a, const HypersphereCoordinate& b) const {
    return HypersphereMath::angular_distance(a, b);
}

void ContinuousConversationManager::process_interaction(const std::string& user_prompt, const std::string& ai_response) {
    // 1. Embed the interaction text into a hypersphere coordinate (pseudo-code using existing tools)
    // In reality, this would use a tokenizer to get uint16_t tokens first.
    std::vector<uint16_t> mock_tokens; 
    // Simulating token embedding
    HypersphereCoordinate new_coord = HypersphereMath::embed_chunk(mock_tokens); 
    
    ConversationNode node;
    node.user_prompt = user_prompt;
    node.ai_response = ai_response;
    node.coordinate = new_coord;
    node.timestamp = std::time(nullptr);

    // 2. Check for drift against active branch
    HypersphereCoordinate branch_centroid = active_branch_->get_centroid();
    
    // If the branch is new/empty, distance checking doesn't make sense yet.
    if (active_branch_->get_nodes().empty()) {
        active_branch_->add_node(node);
        return;
    }

    float drift = calculate_drift(new_coord, branch_centroid);
    std::cout << "[Syntherons] Calculated drift: " << drift << "\n";

    if (drift > hyper_drift_threshold_) {
        std::cout << "[Syntherons] Hyper drift detected! Spawning new Hyper Hub and Branch.\n";
        std::string new_concept = "hyper_concept_" + std::to_string(branch_counter_++);
        active_branch_ = active_branch_->spawn_hyper_branch(new_concept);
    } else if (drift > sub_drift_threshold_) {
        std::cout << "[Syntherons] Sub drift detected! Spawning new Sub Hub and Branch.\n";
        std::string new_concept = "sub_concept_" + std::to_string(branch_counter_++);
        active_branch_ = active_branch_->spawn_sub_branch(new_concept);
    } else {
        std::cout << "[Syntherons] Drift within limits. Maintaining current branch.\n";
    }

    // 3. Append to the (potentially new) active branch
    active_branch_->add_node(node);
}

std::vector<OverlayContext> ContinuousConversationManager::build_context_overlay(const std::string& current_prompt, size_t max_results) {
    std::vector<OverlayContext> results;
    
    // Embed the current prompt
    std::vector<uint16_t> mock_tokens; 
    HypersphereCoordinate prompt_coord = HypersphereMath::embed_chunk(mock_tokens);

    auto all_branches = topology_.get_all_branches();
    
    // Collect all nodes from all branches and score them
    // In a real system with millions of nodes, we would search via the Hubs (directories)
    // to prune the search space rather than brute-forcing all nodes.
    // For this MVP, we score all nodes directly.
    for (const auto& branch : all_branches) {
        for (const auto& node : branch->get_nodes()) {
            float distance = calculate_drift(prompt_coord, node.coordinate);
            
            // Convert distance to a relevance score (lower distance = higher score)
            // Assuming max angular distance is PI (3.14159)
            float score = 1.0f - (distance / 3.14159f);
            if (score < 0.0f) score = 0.0f;

            if (score > 0.5f) { // Only pull up things somewhat relevant
                results.push_back({node.user_prompt, node.ai_response, score});
            }
        }
    }

    // Sort descending by score
    std::sort(results.begin(), results.end(), [](const OverlayContext& a, const OverlayContext& b) {
        return a.relevance_score > b.relevance_score;
    });

    // Truncate to max_results
    if (results.size() > max_results) {
        results.resize(max_results);
    }

    return results;
}

} // namespace hypersp
