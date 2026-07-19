#include "macro_recorder.hpp"

namespace pirate {

void MacroRecorder::start_recording() {
    std::lock_guard<std::mutex> lk(mtx_);
    actions_.clear();
    recording_ = true;
}

void MacroRecorder::stop_recording() {
    std::lock_guard<std::mutex> lk(mtx_);
    recording_ = false;
}

void MacroRecorder::record_action(MacroActionType type, const std::string& payload) {
    std::lock_guard<std::mutex> lk(mtx_);
    if (recording_) {
        actions_.push_back({type, payload});
    }
}

std::vector<MacroAction> MacroRecorder::get_macro() const {
    std::lock_guard<std::mutex> lk(mtx_);
    return actions_;
}

void MacroRecorder::clear_macro() {
    std::lock_guard<std::mutex> lk(mtx_);
    actions_.clear();
}

bool MacroRecorder::is_recording() const {
    std::lock_guard<std::mutex> lk(mtx_);
    return recording_;
}

} // namespace pirate
