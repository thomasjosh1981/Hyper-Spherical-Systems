#pragma once
#include <vector>
#include "hypersphere.hpp"

namespace hypersp {

enum class NativeFeature {
    VISION,
    TOOL_USE,
    CODE_EXECUTION,
    BROWSER,
    UNKNOWN
};

struct FeatureRoute {
    NativeFeature feature;
    std::vector<VortexCoordinate> routing_matrix;
};

class FeatureRouter {
public:
    FeatureRouter() = default;
    ~FeatureRouter() = default;

    // Injects an explicit cross-model feature routing matrix for SFS+ models
    void inject_routing_matrix(NativeFeature feature, const std::vector<VortexCoordinate>& base_weights);
    
    // Check if the current SFS+ model has a specific native feature compiled in
    bool has_feature(NativeFeature feature) const;
    
    // Execute a native feature coordinate projection
    std::vector<VortexCoordinate> project_feature_matrix(NativeFeature feature, const std::vector<VortexCoordinate>& input_state) const;

private:
    std::vector<FeatureRoute> routes_;
};

} // namespace hypersp
