#pragma once
#include <vector>
#include <string>
#include <memory>
#include "hypersphere.hpp"

namespace hypersp {

enum class SynthuronTier {
    HYPER,
    NORMAL,
    SUB
};

class SynthuronHub;

class SynthuronBranch {
public:
    SynthuronBranch(SynthuronTier tier, const std::string& concept_id);
    ~SynthuronBranch() = default;

    // Attach a hub (directory of data points) to this branch
    void attach_hub(std::shared_ptr<SynthuronHub> hub);

    // Recursively break off a sub-branch
    std::shared_ptr<SynthuronBranch> create_sub_branch(const std::string& concept_id);

    const std::string& get_concept() const { return concept_id_; }
    SynthuronTier get_tier() const { return tier_; }

private:
    SynthuronTier tier_;
    std::string concept_id_;
    std::shared_ptr<SynthuronHub> hub_;
    std::vector<std::shared_ptr<SynthuronBranch>> sub_branches_;
};

class SynthuronHub {
public:
    SynthuronHub(SynthuronTier tier);
    ~SynthuronHub() = default;

    void add_data_point(const VortexCoordinate& coord);
    const std::vector<VortexCoordinate>& get_data() const { return data_points_; }

private:
    SynthuronTier tier_;
    std::vector<VortexCoordinate> data_points_;
};

class SynthuronTopology {
public:
    SynthuronTopology() = default;
    
    // Create the master hyper-branches
    std::shared_ptr<SynthuronBranch> map_concept(const std::string& primary_concept);
    
    // Retrieve a branch recursively
    std::shared_ptr<SynthuronBranch> find_branch(const std::string& concept_id) const;

private:
    std::vector<std::shared_ptr<SynthuronBranch>> hyper_branches_;
};

} // namespace hypersp
