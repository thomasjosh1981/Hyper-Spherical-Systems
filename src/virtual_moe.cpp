#include "virtual_moe.hpp"
#include <cmath>
#include <numeric>

namespace hypersp {

VirtualMoe::VirtualMoe(uint16_t num_experts) : num_experts_(num_experts) {}

uint16_t VirtualMoe::hash_coordinate(const VortexCoordinate& coord) const {
    if (num_experts_ == 0) return 0;
    
    // Hash based on radius and bladed angles
    // By keeping it deterministic and mathematically precise, the routing is baked into the topology.
    uint32_t hash = *reinterpret_cast<const uint32_t*>(&coord.radius);
    for (uint16_t angle : coord.bladed_angles) {
        hash ^= angle + 0x9e3779b9 + (hash << 6) + (hash >> 2);
    }
    return hash % num_experts_;
}

std::vector<VirtualExpert> VirtualMoe::shard_tensor(const std::vector<VortexCoordinate>& coords) {
    std::vector<VirtualExpert> experts(num_experts_);
    for (uint16_t i = 0; i < num_experts_; ++i) {
        experts[i].id = i;
    }

    for (const auto& coord : coords) {
        uint16_t target_expert = hash_coordinate(coord);
        experts[target_expert].bladed_weights.push_back(coord);
    }

    return experts;
}

void VirtualMoe::inject_draft_pathways(std::vector<VirtualExpert>& experts) {
    // Inject multi-token prediction and speculative draft pathways directly into experts
    for (auto& expert : experts) {
        if (expert.bladed_weights.empty()) continue;
        
        // Basic speculative draft embedding (e.g. duplicating a fraction of weights with a phase shift)
        size_t draft_size = expert.bladed_weights.size() / 10; // 10% draft pathways
        for (size_t i = 0; i < draft_size; ++i) {
            VortexCoordinate draft_coord = expert.bladed_weights[i];
            draft_coord.radius *= 0.95f; // Slight phase shift for the draft pathway
            expert.bladed_weights.push_back(draft_coord);
        }
    }
}

float VirtualMoe::forward_compressed(const std::vector<KVCachedEntry>& compressed_tokens, const std::vector<VirtualExpert>& experts) {
    if (compressed_tokens.empty() || experts.empty()) return 0.0f;

    float accumulated_activation = 0.0f;

    for (const auto& token : compressed_tokens) {
        // Here we map the 1-byte SISSI dict code directly to a virtual expert routing 
        // without decompressing the original phrase or expanding to a full embedding.
        uint16_t expert_id = (token.dict_code * 31) % num_experts_;
        
        // Compute natively using obfuscated bladed weights
        const auto& target_expert = experts[expert_id];
        if (!target_expert.bladed_weights.empty()) {
            // A simplified native dot-product over 4D bladed coordinates
            accumulated_activation += target_expert.bladed_weights[0].radius * (token.is_compressed ? 1.5f : 1.0f);
        }
    }

    return accumulated_activation;
}

} // namespace hypersp
