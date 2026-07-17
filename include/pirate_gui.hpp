// pirate_gui.hpp — Pirate Llama Floating Control Panel
// License: MIT

#pragma once
#include "pirate_proxy.hpp"
#include <atomic>
#include <thread>
#include <functional>
#include <string>
#include <mutex>
#include <vector>
#include <memory>

#if defined(_WIN32)
#  ifndef WIN32_LEAN_AND_MEAN
#    define WIN32_LEAN_AND_MEAN
#  endif
#  ifndef NOMINMAX
#    define NOMINMAX
#  endif
#  include <windows.h>
#  include <commctrl.h>
#endif

namespace pirate {

using ConfigChangeCallback = std::function<void(const ProxyConfig&)>;

struct GuiState {
    ProxyConfig    cfg;
    ProxyTelemetry telemetry;
    bool           window_visible = true;
    bool           always_on_top  = true;
    int            window_x       = 20;
    int            window_y       = 20;
    int            window_w       = 390;
    int            window_h       = 700;
};

class PirateGui {
public:
    explicit PirateGui(PirateProxy& proxy);
    ~PirateGui();

    bool run();
    void shutdown();
    void update_telemetry(const ProxyTelemetry& t);
    void on_config_change(ConfigChangeCallback cb);
    bool is_running() const noexcept;

private:
    void gui_thread_func();
    void apply_config_change();

    PirateProxy&         proxy_;
    GuiState             state_;
    mutable std::mutex   state_mtx_;
    std::thread          gui_thread_;
    std::atomic<bool>    running_{false};
    ConfigChangeCallback config_cb_;

#if defined(_WIN32)
    // Win32 members — only compiled on Windows
    static LRESULT CALLBACK wnd_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp);
    bool create_window();
    void create_controls();

    HWND              hwnd_        = nullptr;
    HWND              hwnd_status_ = nullptr;
    HFONT             hfont_       = nullptr;
    std::vector<HWND> slider_hwnds_;
    std::vector<HWND> toggle_hwnds_;
    std::vector<HWND> label_hwnds_;
#endif
};

} // namespace pirate
