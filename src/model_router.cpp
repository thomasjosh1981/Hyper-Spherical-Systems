#include "model_router.hpp"
#include <regex>
#include <iostream>

namespace pirate {

ModelRouter::ModelRouter() {
    // Default fallback chains could be initialized here
}

ModelRouter::~ModelRouter() {
    stop_health_checks();
}

std::optional<RoutingDirective> ModelRouter::parse_routing_directives(const std::string& prompt) {
    // Simple heuristic parser for conversational routing and /hypes
    // Example: "bulk work by local model using ollama ... debug using antigravity's gemini pro 3.1"
    
    // Check for /hypes command first
    std::regex hypes_regex(R"(/hypes\s+(.*))", std::regex_constants::icase);
    std::smatch match;
    
    std::string command_text = prompt;
    bool explicit_command = false;
    
    if (std::regex_search(prompt, match, hypes_regex)) {
        command_text = match[1].str();
        explicit_command = true;
    }
    
    // If it mentions gemini, cloud, or antigravity, assume cloud routing
    std::regex cloud_regex(R"(gemini|cloud|web|antigravity)", std::regex_constants::icase);
    // If it mentions ollama, lm studio, local
    std::regex local_regex(R"(ollama|lm\s*studio|local|kobold)", std::regex_constants::icase);
    
    bool wants_cloud = std::regex_search(command_text, cloud_regex);
    bool wants_local = std::regex_search(command_text, local_regex);
    
    if (wants_cloud || explicit_command) {
        RoutingDirective dir;
        
        if (wants_cloud) {
            dir.destination = ModelDestination::CLOUD;
            dir.backend_name = "gemini";
            dir.model_name = "gemini-3.1-pro";
            dir.requires_manual_consent = true; // Strict TOS compliance
        } else if (wants_local) {
            dir.destination = ModelDestination::LOCAL;
            dir.backend_name = "ollama";
            dir.requires_manual_consent = false;
        } else {
            return std::nullopt; // Unclear
        }
        return dir;
    }
    
    return std::nullopt;
}

std::optional<RoutingDirective> ModelRouter::get_next_fallback(const RoutingDirective& failed_route) {
    std::lock_guard<std::mutex> lock(endpoints_mtx_);
    for (auto& ep : available_endpoints_) {
        if (ep.backend_name == failed_route.backend_name && ep.target_port == failed_route.target_port) {
            ep.failed_attempts++;
            if (ep.failed_attempts > 3) ep.is_healthy = false;
        }
    }

    // Return the next available endpoint that isn't the failed one and is healthy
    for (const auto& ep : available_endpoints_) {
        if ((ep.backend_name != failed_route.backend_name || ep.target_port != failed_route.target_port) && ep.is_healthy) {
            return ep;
        }
    }
    return std::nullopt;
}

void ModelRouter::register_endpoint(const RoutingDirective& endpoint) {
    std::lock_guard<std::mutex> lock(endpoints_mtx_);
    available_endpoints_.push_back(endpoint);
}

void ModelRouter::start_health_checks() {
    if (!run_health_checks_) {
        run_health_checks_ = true;
        health_thread_ = std::thread(&ModelRouter::health_check_loop, this);
    }
}

void ModelRouter::stop_health_checks() {
    if (run_health_checks_) {
        run_health_checks_ = false;
        if (health_thread_.joinable()) {
            health_thread_.join();
        }
    }
}

void ModelRouter::health_check_loop() {
    while (run_health_checks_) {
        std::this_thread::sleep_for(std::chrono::seconds(5));
        std::lock_guard<std::mutex> lock(endpoints_mtx_);
        for (auto& ep : available_endpoints_) {
            // Simulated health check logic (circuit breaker half-open retry)
            if (!ep.is_healthy) {
                // Periodically try to mark healthy again to test (half-open)
                ep.failed_attempts = 0; 
                ep.is_healthy = true;
            }
        }
    }
}

} // namespace pirate
