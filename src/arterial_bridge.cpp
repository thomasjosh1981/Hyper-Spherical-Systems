#include "arterial_bridge.hpp"
#include <iostream>
#include <algorithm>

namespace hypersp {

void ArterialBridge::register_node(const std::string& node_id, bool is_sfs_plus) {
    network_nodes_.push_back({node_id, is_sfs_plus});
}

std::string ArterialBridge::discover_feature_hub(NativeFeature /*feature*/) const {
    // Basic implementation: Find the first SFS+ node
    auto it = std::find_if(network_nodes_.begin(), network_nodes_.end(), [](const Node& n) {
        return n.is_sfs_plus;
    });
    
    if (it != network_nodes_.end()) {
        return it->id;
    }
    
    return "";
}

std::vector<VortexCoordinate> ArterialBridge::project_coordinate_request(
    const std::string& target_node, 
    NativeFeature feature, 
    const std::vector<VortexCoordinate>& context
) {
    std::cout << "[ArterialBridge] Projecting 4D feature coordinate (" 
              << static_cast<int>(feature) << ") to neighbor: " << target_node << "\n";
              
    // In a full implementation, we'd serialize 'context', send via IPC/Sockets to 'target_node',
    // and wait for the returned VortexCoordinate stream.
    // For MVP, we simulate a successful feature mapping by applying a synthetic transformation.
    
    std::vector<VortexCoordinate> response;
    response.reserve(context.size());
    for (const auto& c : context) {
        VortexCoordinate transformed = c;
        transformed.radius *= 1.1f; // Simulated feature processing expansion
        response.push_back(transformed);
    }
    
    return response;
}

} // namespace hypersp
