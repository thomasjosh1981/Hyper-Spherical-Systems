#pragma once
#include <vector>
#include <cstdint>
#include "hypersphere.hpp"

namespace hypersp {

class MatrixSlicer {
public:
    MatrixSlicer() = default;
    ~MatrixSlicer() = default;

    // Low-level matrix slicing for 4D hyper-spherical arrays
    // Used to slice out virtual MOE pathways and perform precision routing
    std::vector<VortexCoordinate> slice_dimension(
        const std::vector<VortexCoordinate>& tensor, 
        size_t start_idx, 
        size_t end_idx
    ) const;

    // Ensure mathematical precision during layer transformations
    void apply_precision_correction(std::vector<VortexCoordinate>& tensor) const;
};

} // namespace hypersp
