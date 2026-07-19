#pragma once
#include <string>
#include <vector>
#include <mutex>

namespace pirate {

enum class MacroActionType {
    ROUTE_OVERRIDE,
    APPLY_SISSI,
    STRIP_PREPOSITIONS
};

struct MacroAction {
    MacroActionType type;
    std::string payload;
};

class MacroRecorder {
public:
    MacroRecorder() = default;

    void start_recording();
    void stop_recording();
    void record_action(MacroActionType type, const std::string& payload = "");
    
    std::vector<MacroAction> get_macro() const;
    void clear_macro();
    bool is_recording() const;

private:
    std::vector<MacroAction> actions_;
    bool recording_ = false;
    mutable std::mutex mtx_;
};

} // namespace pirate
