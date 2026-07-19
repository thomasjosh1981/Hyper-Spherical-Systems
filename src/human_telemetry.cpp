#include "human_telemetry.hpp"
#include <random>
#include <cmath>
#include <iostream>

namespace pirate {

std::vector<SimulatedEvent> HumanTelemetrySimulator::generate_cursor_trajectory(Point2D start, Point2D end, long duration_ms) const {
    std::vector<SimulatedEvent> events;
    std::mt19937 gen(1337);
    std::uniform_real_distribution<float> jitter(-2.0f, 2.0f);
    
    int steps = std::max(10, static_cast<int>(duration_ms / 16)); // ~60fps
    
    // Simple linear interpolation with jitter for MVP
    for (int i = 0; i <= steps; ++i) {
        float t = static_cast<float>(i) / steps;
        // Ease in-out
        float eased_t = t * t * (3.0f - 2.0f * t); 
        
        Point2D pos;
        pos.x = start.x + (end.x - start.x) * eased_t + (i > 0 && i < steps ? jitter(gen) : 0.0f);
        pos.y = start.y + (end.y - start.y) * eased_t + (i > 0 && i < steps ? jitter(gen) : 0.0f);
        
        events.push_back({SimulatedEvent::Type::MOUSE_MOVE, pos, '\0', static_cast<long>(eased_t * duration_ms)});
    }
    
    return events;
}

std::vector<SimulatedEvent> HumanTelemetrySimulator::generate_typing_cadence(const std::string& text) const {
    std::vector<SimulatedEvent> events;
    std::mt19937 gen(42);
    // Log-normal distribution for keystroke timings (mean ~150ms, some variance)
    std::lognormal_distribution<float> delay_dist(4.8f, 0.4f); 
    
    long current_time = 0;
    for (char c : text) {
        current_time += static_cast<long>(delay_dist(gen));
        events.push_back({SimulatedEvent::Type::KEY_PRESS, {0,0}, c, current_time});
    }
    return events;
}

void HumanTelemetrySimulator::inject_events(const std::vector<SimulatedEvent>& events) const {
    // In a real implementation, this would push into TelemetryLogger or the OS hook.
    // For MVP verification, we just print the event stats.
    std::cout << "[HumanTelemetrySimulator] Injected " << events.size() << " simulated events.\n";
}

} // namespace pirate
