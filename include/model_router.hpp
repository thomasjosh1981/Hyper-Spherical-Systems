#pragma once

#include <string>
#include <vector>
#include <optional>
#include <thread>
#include <mutex>
#include <atomic>

namespace pirate {

enum class ModelDestination {
    LOCAL,
    CLOUD,
    UNKNOWN
};

struct RoutingDirective {
    ModelDestination destination = ModelDestination::LOCAL;
    std::string backend_name;    // e.g., "ollama", "lmstudio", "gemini"
    std::string model_name;      // e.g., "gemini-1.5-pro", "llama3-70b"
    int target_port = 11434;
    std::string target_host = "127.0.0.1";
    bool requires_manual_consent = false;
    
    // HA fields
    bool is_healthy = true;
    int failed_attempts = 0;
};

class ModelRouter {
public:
    ModelRouter();
    ~ModelRouter();

    // Parse the incoming prompt for /hypes commands or conversational routing
    // Returns a populated RoutingDirective if a specific route is requested.
    std::optional<RoutingDirective> parse_routing_directives(const std::string& prompt);

    // Get the next fallback route if the primary fails
    std::optional<RoutingDirective> get_next_fallback(const RoutingDirective& failed_route);

    // Register an available endpoint (e.g., from GatewayScanner)
    void register_endpoint(const RoutingDirective& endpoint);

    void start_health_checks();
    void stop_health_checks();

private:
    void health_check_loop();

    std::vector<RoutingDirective> available_endpoints_;
    std::thread health_thread_;
    std::atomic<bool> run_health_checks_{false};
    mutable std::mutex endpoints_mtx_;
};

} // namespace pirate
