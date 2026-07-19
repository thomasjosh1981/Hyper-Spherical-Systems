#pragma once

#include "model_router.hpp"
#include <vector>

namespace pirate {

class GatewayScanner {
public:
    GatewayScanner();
    ~GatewayScanner();

    // Scans local network ports and processes to find active AI endpoints
    // Returns a list of discovered endpoints that can be registered with the ModelRouter
    std::vector<RoutingDirective> scan_for_gateways();

private:
    bool is_port_open(int port);
};

} // namespace pirate
