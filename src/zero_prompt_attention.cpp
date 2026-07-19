#include "zero_prompt_attention.hpp"
#include <sstream>
#include <iostream>

namespace hypersp {

ZeroPromptAttention::ZeroPromptAttention(std::shared_ptr<SynthuronTopology> topology)
    : topology_(topology) {}

std::string ZeroPromptAttention::extract_hyper_concept(const std::string& input) const {
    // For MVP, just take the first word as the macro-concept
    std::istringstream iss(input);
    std::string word;
    if (iss >> word) {
        return word;
    }
    return "UNKNOWN_CONCEPT";
}

std::vector<VortexCoordinate> ZeroPromptAttention::naive_embed(const std::string& input) const {
    std::vector<VortexCoordinate> coords;
    for (char c : input) {
        VortexCoordinate coord;
        coord.radius = static_cast<float>(c) / 255.0f; // basic normalization
        coord.bladed_angles = { static_cast<uint16_t>(c * 10), static_cast<uint16_t>(c * 20), static_cast<uint16_t>(c * 30) };
        coords.push_back(coord);
    }
    return coords;
}

std::vector<VortexCoordinate> ZeroPromptAttention::hook_and_translate(const std::string& raw_human_string) {
    std::cout << "[ZeroPromptAttention] Intercepting raw text: " << raw_human_string.substr(0, 20) << "...\n";
    
    // 1. Extract hyper concept
    std::string concept_str = extract_hyper_concept(raw_human_string);
    
    // 2. Map to Synthuron Topology
    auto hyper_branch = topology_->map_concept(concept_str);
    
    // 3. Create a Sub-Hub for this specific conversational piece
    auto sub_branch = hyper_branch->create_sub_branch("conversation_fragment");
    auto hub = std::make_shared<SynthuronHub>(SynthuronTier::SUB);
    
    // 4. Translate raw text to 4D coordinates
    std::vector<VortexCoordinate> coords = naive_embed(raw_human_string);
    
    // 5. Store data in the hub
    for (const auto& c : coords) {
        hub->add_data_point(c);
    }
    sub_branch->attach_hub(hub);
    
    std::cout << "[ZeroPromptAttention] Successfully mapped to Hyper Branch: " << concept_str << "\n";
    
    // Return the translated coordinates for the execution loop
    return coords;
}

} // namespace hypersp
