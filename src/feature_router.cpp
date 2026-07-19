#include "feature_router.hpp"
#include <algorithm>

namespace hypersp {

void FeatureRouter::inject_routing_matrix(NativeFeature feature, const std::vector<VortexCoordinate>& base_weights) {
    if (has_feature(feature)) return;
    
    FeatureRoute route;
    route.feature = feature;
    // Compress and inject specific transformation for this feature
    // In a full implementation, this applies a learned matrix projection.
    for (const auto& w : base_weights) {
        VortexCoordinate mapped = w;
        mapped.radius *= 1.05f; // Slight scale up for feature isolation
        if (!mapped.bladed_angles.empty()) {
            mapped.bladed_angles[0] ^= 0x55AA; // Signature shift
        }
        route.routing_matrix.push_back(mapped);
    }
    
    routes_.push_back(route);
}

bool FeatureRouter::has_feature(NativeFeature feature) const {
    return std::find_if(routes_.begin(), routes_.end(), [feature](const FeatureRoute& r) {
        return r.feature == feature;
    }) != routes_.end();
}

std::vector<VortexCoordinate> FeatureRouter::project_feature_matrix(NativeFeature feature, const std::vector<VortexCoordinate>& input_state) const {
    if (!has_feature(feature)) return input_state; // Pass-through if not found

    auto it = std::find_if(routes_.begin(), routes_.end(), [feature](const FeatureRoute& r) {
        return r.feature == feature;
    });

    std::vector<VortexCoordinate> output;
    output.reserve(input_state.size());

    // Dot product equivalent in 4D Hyperspherical space
    for (size_t i = 0; i < input_state.size(); ++i) {
        VortexCoordinate out = input_state[i];
        if (i < it->routing_matrix.size()) {
            const auto& route_w = it->routing_matrix[i];
            out.radius *= route_w.radius;
            // Merge angles
            for (size_t a = 0; a < std::min(out.bladed_angles.size(), route_w.bladed_angles.size()); ++a) {
                out.bladed_angles[a] = (out.bladed_angles[a] + route_w.bladed_angles[a]) / 2;
            }
        }
        output.push_back(out);
    }

    return output;
}

} // namespace hypersp
