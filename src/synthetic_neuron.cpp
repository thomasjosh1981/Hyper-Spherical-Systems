#include "synthetic_neuron.hpp"

namespace hypersp {

SynthuronBranch::SynthuronBranch(SynthuronTier tier, const std::string& concept_id)
    : tier_(tier), concept_id_(concept_id) {}

void SynthuronBranch::attach_hub(std::shared_ptr<SynthuronHub> hub) {
    hub_ = hub;
}

std::shared_ptr<SynthuronBranch> SynthuronBranch::create_sub_branch(const std::string& concept_id) {
    SynthuronTier next_tier = SynthuronTier::SUB;
    if (tier_ == SynthuronTier::HYPER) {
        next_tier = SynthuronTier::NORMAL;
    }
    
    auto sub = std::make_shared<SynthuronBranch>(next_tier, concept_id);
    sub_branches_.push_back(sub);
    return sub;
}

SynthuronHub::SynthuronHub(SynthuronTier tier) : tier_(tier) {}

void SynthuronHub::add_data_point(const VortexCoordinate& coord) {
    data_points_.push_back(coord);
}

std::shared_ptr<SynthuronBranch> SynthuronTopology::map_concept(const std::string& primary_concept) {
    // Check if it already exists
    auto existing = find_branch(primary_concept);
    if (existing) return existing;
    
    auto branch = std::make_shared<SynthuronBranch>(SynthuronTier::HYPER, primary_concept);
    hyper_branches_.push_back(branch);
    return branch;
}

std::shared_ptr<SynthuronBranch> SynthuronTopology::find_branch(const std::string& concept_id) const {
    // Helper lambda for recursive search
    auto search_recursive = [&](const std::vector<std::shared_ptr<SynthuronBranch>>& branches, auto& search_ref) -> std::shared_ptr<SynthuronBranch> {
        for (const auto& b : branches) {
            if (b->get_concept() == concept_id) return b;
            // Accessing private member for search purposes requires friendship or a public getter.
            // For simplicity in MVP, we won't implement deep recursive search here,
            // just top level. In production, we'd add `get_sub_branches()`
        }
        return nullptr;
    };
    
    return search_recursive(hyper_branches_, search_recursive);
}

} // namespace hypersp
