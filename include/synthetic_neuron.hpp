#pragma once
#include <vector>
#include <string>
#include <memory>
#include <ctime>
#include "hypersphere.hpp"

namespace hypersp {

enum class SynthuronTier {
    HYPER,
    NORMAL,
    SUB
};

// Represents a single point of conversation (e.g. prompt and response)
struct ConversationNode {
    std::string user_prompt;
    std::string ai_response;
    HypersphereCoordinate coordinate;
    std::time_t timestamp;
};

class SynthuronBranch;

// Base class for Hubs
class SynthuronHub {
public:
    SynthuronHub(SynthuronTier tier);
    virtual ~SynthuronHub() = default;

    void add_branch(std::shared_ptr<SynthuronBranch> branch);
    const std::vector<std::shared_ptr<SynthuronBranch>>& get_branches() const { return branches_; }
    SynthuronTier get_tier() const { return tier_; }

protected:
    SynthuronTier tier_;
    std::vector<std::shared_ptr<SynthuronBranch>> branches_;
};

// Master index where major conceptual splits occur
class HyperHub : public SynthuronHub {
public:
    HyperHub() : SynthuronHub(SynthuronTier::HYPER) {}
};

// Localized maps for minor tangents
class SubHub : public SynthuronHub {
public:
    SubHub() : SynthuronHub(SynthuronTier::SUB) {}
};

class SynthuronBranch : public std::enable_shared_from_this<SynthuronBranch> {
public:
    SynthuronBranch(SynthuronTier tier, const std::string& concept_id);
    ~SynthuronBranch() = default;

    void add_node(const ConversationNode& node);
    const std::vector<ConversationNode>& get_nodes() const { return nodes_; }

    // Centroid of the branch, dynamically updated as nodes are added
    HypersphereCoordinate get_centroid() const { return centroid_; }

    // Split this branch into a new sub branch via a Sub Hub
    std::shared_ptr<SynthuronBranch> spawn_sub_branch(const std::string& new_concept_id);
    
    // Split this branch into a completely new Hyper Branch via a Hyper Hub
    std::shared_ptr<SynthuronBranch> spawn_hyper_branch(const std::string& new_concept_id);

    // Legacy data points for zero prompt attention
    void add_vortex_data(const VortexCoordinate& coord) { vortex_data_.push_back(coord); }
    const std::vector<VortexCoordinate>& get_vortex_data() const { return vortex_data_; }

    const std::string& get_concept() const { return concept_id_; }
    SynthuronTier get_tier() const { return tier_; }
    std::shared_ptr<SynthuronHub> get_hub() const { return hub_; }

private:
    void update_centroid(const HypersphereCoordinate& new_coord);

    SynthuronTier tier_;
    std::string concept_id_;
    std::vector<ConversationNode> nodes_;
    std::vector<VortexCoordinate> vortex_data_;
    HypersphereCoordinate centroid_;
    
    std::shared_ptr<SynthuronHub> hub_; // The hub that this branch splits off into
};

class SynthuronTopology {
public:
    SynthuronTopology() = default;
    
    // Create or get the master hyper-branch
    std::shared_ptr<SynthuronBranch> map_concept(const std::string& primary_concept);
    
    // Retrieve a branch recursively
    std::shared_ptr<SynthuronBranch> find_branch(const std::string& concept_id) const;

    // Retrieve all branches (flattened) for searching
    std::vector<std::shared_ptr<SynthuronBranch>> get_all_branches() const;

private:
    std::vector<std::shared_ptr<SynthuronBranch>> hyper_branches_;
};

} // namespace hypersp
