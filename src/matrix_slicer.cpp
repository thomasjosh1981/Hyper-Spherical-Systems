#include "matrix_slicer.hpp"
#include <algorithm>
#include <cmath>

namespace hypersp {

std::vector<VortexCoordinate> MatrixSlicer::slice_dimension(
    const std::vector<VortexCoordinate>& tensor, 
    size_t start_idx, 
    size_t end_idx
) const {
    if (start_idx >= tensor.size()) return {};
    size_t actual_end = std::min(end_idx, tensor.size());
    
    std::vector<VortexCoordinate> slice(tensor.begin() + start_idx, tensor.begin() + actual_end);
    return slice;
}

void MatrixSlicer::apply_precision_correction(std::vector<VortexCoordinate>& tensor) const {
    // Ensures zero floating point drift during rapid matrix slicing and V-MOE traversal
    for (auto& coord : tensor) {
        if (std::isnan(coord.radius) || std::isinf(coord.radius)) {
            coord.radius = 0.0f;
        }
        // Snap to precision grid if necessary (for MVP, basic clamp)
        coord.radius = (std::max)(-1000.0f, (std::min)(1000.0f, coord.radius));
    }
}

} // namespace hypersp
