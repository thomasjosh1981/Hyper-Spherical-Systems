#pragma once

#include "types.hpp"
#include <string>
#include <vector>

namespace hypersp {

class RecursiveUpdater {
public:
    RecursiveUpdater(const std::string& sfs_plus_path, const std::string& supervisor_brain_path);
    ~RecursiveUpdater() = default;

    // Checks the entropy of a recent generation block.
    // If it signals hallucination or loop, evaluates via supervisor brain.
    bool evaluate_entropy(float generation_entropy);

    // Applies a delta directly to the SFS+ file via memory-mapped IO or targeted writes.
    bool apply_correction(const VortexCorrection& correction);

private:
    std::string sfs_plus_path_;
    std::string supervisor_brain_path_;
    uint32_t current_epoch_ = 0;
};

} // namespace hypersp
