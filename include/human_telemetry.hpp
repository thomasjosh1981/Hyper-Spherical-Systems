#pragma once
#include <vector>
#include <string>

namespace pirate {

struct Point2D {
    float x, y;
};

struct SimulatedEvent {
    enum class Type { MOUSE_MOVE, KEY_PRESS };
    Type type;
    Point2D pos; // For mouse
    char key;    // For typing
    long timestamp_ms;
};

class HumanTelemetrySimulator {
public:
    HumanTelemetrySimulator() = default;

    // Simulates a human-like cursor trajectory using Bezier curves with jitter
    std::vector<SimulatedEvent> generate_cursor_trajectory(Point2D start, Point2D end, long duration_ms) const;

    // Simulates a human-like typing cadence (log-normal delay)
    std::vector<SimulatedEvent> generate_typing_cadence(const std::string& text) const;
    
    // Injects the simulated events into the global telemetry stream
    void inject_events(const std::vector<SimulatedEvent>& events) const;
};

} // namespace pirate
