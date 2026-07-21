#include "synthetic_neuron.hpp"

namespace hypersp {

SynthuronHub::SynthuronHub(SynthuronTier tier) : tier_(tier) {}

void SynthuronHub::add_branch(std::shared_ptr<SynthuronBranch> branch) {
    branches_.push_back(branch);
}

SynthuronBranch::SynthuronBranch(SynthuronTier tier, const std::string& concept_id)
    : tier_(tier), concept_id_(concept_id), centroid_() {}

void SynthuronBranch::add_node(const ConversationNode& node) {
    nodes_.push_back(node);
    update_centroid(node.coordinate);
}

void SynthuronBranch::update_centroid(const HypersphereCoordinate& new_coord) {
    if (nodes_.size() == 1) {
        centroid_ = new_coord;
        return;
    }
    
    // Simplistic running average of coordinates for centroid
    // For proper hyperspherical mapping, this would be a normalized vector addition
    // Placeholder implementation for structural MVP
    float total_radius = 0.0f;
    std::vector<float> avg_angles;
    if (!new_coord.angles.empty()) {
        avg_angles.resize(new_coord.angles.size(), 0.0f);
    }
    
    for (const auto& node : nodes_) {
        total_radius += node.coordinate.radius;
        for (size_t i = 0; i < node.coordinate.angles.size() && i < avg_angles.size(); ++i) {
            avg_angles[i] += node.coordinate.angles[i];
        }
    }
    
    total_radius /= nodes_.size();
    for (size_t i = 0; i < avg_angles.size(); ++i) {
        avg_angles[i] /= nodes_.size();
    }
    
    centroid_ = HypersphereCoordinate(avg_angles, total_radius);
}

std::shared_ptr<SynthuronBranch> SynthuronBranch::spawn_sub_branch(const std::string& new_concept_id) {
    if (!hub_) {
        hub_ = std::make_shared<SubHub>();
    }
    auto sub = std::make_shared<SynthuronBranch>(SynthuronTier::SUB, new_concept_id);
    hub_->add_branch(sub);
    return sub;
}

std::shared_ptr<SynthuronBranch> SynthuronBranch::spawn_hyper_branch(const std::string& new_concept_id) {
    if (!hub_) {
        hub_ = std::make_shared<HyperHub>();
    }
    auto hyper = std::make_shared<SynthuronBranch>(SynthuronTier::HYPER, new_concept_id);
    hub_->add_branch(hyper);
    return hyper;
}

std::shared_ptr<SynthuronBranch> SynthuronTopology::map_concept(const std::string& primary_concept) {
    auto existing = find_branch(primary_concept);
    if (existing) return existing;
    
    auto branch = std::make_shared<SynthuronBranch>(SynthuronTier::HYPER, primary_concept);
    hyper_branches_.push_back(branch);
    return branch;
}

std::shared_ptr<SynthuronBranch> SynthuronTopology::find_branch(const std::string& concept_id) const {
    auto branches = get_all_branches();
    for (const auto& b : branches) {
        if (b->get_concept() == concept_id) return b;
    }
    return nullptr;
}

std::vector<std::shared_ptr<SynthuronBranch>> SynthuronTopology::get_all_branches() const {
    std::vector<std::shared_ptr<SynthuronBranch>> all_branches;
    
    // Recursive lambda to flatten the tree
    auto traverse = [&](const std::vector<std::shared_ptr<SynthuronBranch>>& branches, auto& traverse_ref) -> void {
        for (const auto& b : branches) {
            all_branches.push_back(b);
            if (b->get_hub()) {
                traverse_ref(b->get_hub()->get_branches(), traverse_ref);
            }
        }
    };
    
    traverse(hyper_branches_, traverse);
    return all_branches;
}

} // namespace hypersp
