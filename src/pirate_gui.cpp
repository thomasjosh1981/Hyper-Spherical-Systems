// pirate_gui.cpp — Pirate Llama Floating Control Panel
// Win32 native + cross-platform TTY fallback
// License: MIT

#include "pirate_gui.hpp"
#include "license_manager.hpp"
#include <cstdio>
#include <cstring>
#include <algorithm>

#if defined(_WIN32)
#  include <commdlg.h>
#  pragma comment(lib, "comctl32.lib")
#  pragma comment(lib, "user32.lib")
#  pragma comment(lib, "gdi32.lib")
#  pragma comment(lib, "Comdlg32.lib")
#endif

namespace pirate {

// ── Control IDs ────────────────────────────────────────────────────────────
#if defined(_WIN32)
static constexpr int ID_TIMER_TELEMETRY     = 100;
static constexpr int ID_BTN_BACKEND_OLLAMA  = 200;
static constexpr int ID_BTN_BACKEND_LMS     = 201;
static constexpr int ID_BTN_BACKEND_NATIVE  = 202;
static constexpr int ID_BTN_DETECT          = 203;
static constexpr int ID_CHK_SISSI           = 300;
static constexpr int ID_CHK_GREEDY          = 301;
static constexpr int ID_CHK_LARGE_WORDS     = 302;
static constexpr int ID_CHK_RECYCLE         = 303;
static constexpr int ID_CHK_PREPOSITIONS    = 304;
static constexpr int ID_CHK_AUTOTUNE        = 305;
static constexpr int ID_CHK_NVME            = 306;
static constexpr int ID_CHK_BACKUP_ENC      = 307;
static constexpr int ID_CHK_TELEMETRY       = 308;
static constexpr int ID_SLD_VRAM            = 400;
static constexpr int ID_SLD_WORD_LEN        = 401;
static constexpr int ID_SLD_MAX_TOKENS      = 402;
static constexpr int ID_SLD_BACKUP_INTERVAL = 403;
static constexpr int ID_SLD_BACKUP_LEVEL    = 404;
static constexpr int ID_LABEL_STATUS        = 500;

// Module-global pointer so the static wnd_proc can dispatch back to the instance
static PirateGui* g_gui_instance = nullptr;
#endif

// ── Constructor / Destructor ───────────────────────────────────────────────
PirateGui::PirateGui(PirateProxy& proxy) : proxy_(proxy) {
    state_.cfg = proxy_.get_config();
#if defined(_WIN32)
    g_gui_instance = this;
#endif
}

PirateGui::~PirateGui() { shutdown(); }

void PirateGui::on_config_change(ConfigChangeCallback cb) { config_cb_ = std::move(cb); }
bool PirateGui::is_running() const noexcept { return running_.load(); }

void PirateGui::update_telemetry(const ProxyTelemetry& t) {
    std::lock_guard<std::mutex> lk(state_mtx_);
    state_.telemetry = t;
}

void PirateGui::shutdown() {
    if (!running_.exchange(false)) return;
#if defined(_WIN32)
    if (hwnd_) PostMessage(hwnd_, WM_CLOSE, 0, 0);
#endif
    if (gui_thread_.joinable()) gui_thread_.join();
}

bool PirateGui::run() {
    running_.store(true);
#if defined(_WIN32)
    gui_thread_ = std::thread(&PirateGui::gui_thread_func, this);
    return true;
#else
    std::fprintf(stderr,
        "\n╔════════════════════════════════════════════╗\n"
        "║     🏴‍☠️  PIRATE LLAMA Control Panel  🏴‍☠️      ║\n"
        "╠════════════════════════════════════════════╣\n"
        "║  Proxy on :%d  |  GET /health for status  ║\n"
        "╚════════════════════════════════════════════╝\n",
        state_.cfg.proxy_port);
    running_.store(false);
    return true;
#endif
}

// ── Win32 Implementation ────────────────────────────────────────────────────
#if defined(_WIN32)

void PirateGui::gui_thread_func() {
    INITCOMMONCONTROLSEX icc{ sizeof(icc), ICC_WIN95_CLASSES | ICC_STANDARD_CLASSES };
    InitCommonControlsEx(&icc);

    if (!create_window()) { running_.store(false); return; }

    hfont_ = CreateFontW(14, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                         ANSI_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                         CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_SWISS, L"Segoe UI");
    create_controls();
    SetTimer(hwnd_, ID_TIMER_TELEMETRY, 1000, nullptr);

    // Community license splash — shown once per session, inside the app only.
    // The patcher tool itself shows nothing about this; it looks like a clean crack.
    {
        hypersp::LicenseState ls = hypersp::LicenseManager::get_state();
        if (ls.community_splash_needed && !hypersp::LicenseManager::is_free_version_expired()) {
            MessageBoxW(hwnd_,
                L"This software is running on a community license.\n\n"
                L"It was built by an independent developer who also couldn't\n"
                L"always afford the tools they needed.\n\n"
                L"If it saves you time or makes your life easier,\n"
                L"consider supporting the project when you're able to.\n\n"
                L"No pressure. Enjoy the software.",
                L"Community License",
                MB_OK | MB_ICONINFORMATION);
        }

        // License Check
        if (hypersp::LicenseManager::is_free_version_expired()) {
            MessageBoxW(hwnd_,
                L"The Free tier of this software has expired as of Nov 1, 2026.\n\n"
                L"Please visit the download page to obtain the latest version or upgrade to the Paid tier.",
                L"License Expired",
                MB_OK | MB_ICONERROR);
            PostQuitMessage(0);
        } else if (hypersp::LicenseManager::requires_mandatory_update(state_.cfg.current_version)) {
            MessageBoxW(hwnd_,
                L"A major update is available and mandatory for the Free tier.\n\n"
                L"Please download the new version.",
                L"Update Required",
                MB_OK | MB_ICONERROR);
            PostQuitMessage(0);
        } else if (hypersp::LicenseManager::requires_security_tos_acceptance(!state_.cfg.security_update_msg.empty())) {
            MessageBoxW(hwnd_,
                L"Security Update Installed.\n\n"
                L"By continuing to use this software, you agree to the modified Terms of Service which completely indemnifies the creators from any liability.\n\n"
                L"Click OK to accept and continue.",
                L"TOS Update (Paid Tier)",
                MB_OK | MB_ICONWARNING);
        }
    }

    MSG msg{};
    while (running_.load() && GetMessage(&msg, nullptr, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    if (hfont_) { DeleteObject(hfont_); hfont_ = nullptr; }
    running_.store(false);
}

bool PirateGui::create_window() {
    WNDCLASSEXW wc{};
    wc.cbSize        = sizeof(wc);
    wc.lpfnWndProc   = PirateGui::wnd_proc;
    wc.hInstance     = GetModuleHandleW(nullptr);
    wc.hCursor       = LoadCursorW(nullptr, reinterpret_cast<LPCWSTR>(IDC_ARROW));
    wc.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_3DFACE + 1);
    wc.lpszClassName = L"PirateLlamaPanel";
    wc.style         = CS_HREDRAW | CS_VREDRAW;
    RegisterClassExW(&wc); // ignore re-register errors

    DWORD style    = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX;
    DWORD ex_style = WS_EX_TOPMOST | WS_EX_TOOLWINDOW;

    hwnd_ = CreateWindowExW(
        ex_style, L"PirateLlamaPanel",
        L"Pirate Llama Control Panel",
        style,
        state_.window_x, state_.window_y,
        state_.window_w, state_.window_h,
        nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);

    if (!hwnd_) return false;
    ShowWindow(hwnd_, SW_SHOW);
    UpdateWindow(hwnd_);
    return true;
}

void PirateGui::create_controls() {
    int y = 8;
    const int x = 10, w = 360;

    auto font_set = [&](HWND h) {
        if (hfont_) SendMessage(h, WM_SETFONT, reinterpret_cast<WPARAM>(hfont_), TRUE);
    };
    auto add_label = [&](const wchar_t* txt, int h = 18) {
        HWND lbl = CreateWindowExW(0, L"STATIC", txt,
            WS_CHILD | WS_VISIBLE | SS_LEFT,
            x, y, w, h, hwnd_, nullptr, GetModuleHandleW(nullptr), nullptr);
        font_set(lbl); label_hwnds_.push_back(lbl); y += h + 2;
    };
    auto add_check = [&](const wchar_t* txt, int id, bool chk) {
        HWND h = CreateWindowExW(0, L"BUTTON", txt,
            WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX,
            x, y, w, 20, hwnd_, reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),
            GetModuleHandleW(nullptr), nullptr);
        font_set(h); toggle_hwnds_.push_back(h);
        SendMessage(h, BM_SETCHECK, chk ? BST_CHECKED : BST_UNCHECKED, 0);
        y += 22;
    };
    auto add_slider = [&](const wchar_t* txt, int id, int mn, int mx, int val) {
        HWND lbl = CreateWindowExW(0, L"STATIC", txt,
            WS_CHILD | WS_VISIBLE | SS_LEFT,
            x, y, w, 16, hwnd_, nullptr, GetModuleHandleW(nullptr), nullptr);
        font_set(lbl); label_hwnds_.push_back(lbl);
        HWND sld = CreateWindowExW(0, TRACKBAR_CLASSW, L"",
            WS_CHILD | WS_VISIBLE | TBS_HORZ | TBS_AUTOTICKS,
            x, y + 16, w, 24, hwnd_,
            reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),
            GetModuleHandleW(nullptr), nullptr);
        SendMessage(sld, TBM_SETRANGE, TRUE, MAKELONG(mn, mx));
        SendMessage(sld, TBM_SETPOS,   TRUE, val);
        slider_hwnds_.push_back(sld); y += 44;
    };

    const ProxyConfig& cfg = state_.cfg;

    // Title
    add_label(L"---  Pirate Llama v1.0  |  Universal LLM Proxy  ---", 20);

    // Status telemetry bar
    hwnd_status_ = CreateWindowExW(0, L"STATIC", L"Status: Starting...",
        WS_CHILD | WS_VISIBLE | SS_LEFT,
        x, y, w, 36, hwnd_,
        reinterpret_cast<HMENU>(static_cast<INT_PTR>(ID_LABEL_STATUS)),
        GetModuleHandleW(nullptr), nullptr);
    font_set(hwnd_status_); y += 42;

    // Backend buttons
    add_label(L"--- Backend ---", 16);
    const int bx = x;
    struct { const wchar_t* lbl; int id; } btns[] = {
        { L"Ollama :11434",  ID_BTN_BACKEND_OLLAMA },
        { L"LM Studio :1234",ID_BTN_BACKEND_LMS   },
        { L"Native",         ID_BTN_BACKEND_NATIVE },
    };
    int bxoff = x;
    for (auto& b : btns) {
        HWND h = CreateWindowExW(0, L"BUTTON", b.lbl,
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
            bxoff, y, 114, 26, hwnd_,
            reinterpret_cast<HMENU>(static_cast<INT_PTR>(b.id)),
            GetModuleHandleW(nullptr), nullptr);
        font_set(h); bxoff += 118;
    }
    y += 30;
    {
        HWND h = CreateWindowExW(0, L"BUTTON", L"Auto-Detect Backend",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
            x, y, 180, 26, hwnd_,
            reinterpret_cast<HMENU>(static_cast<INT_PTR>(ID_BTN_DETECT)),
            GetModuleHandleW(nullptr), nullptr);
        font_set(h);
    }
    y += 34;
    (void)bx;

    // SISSI
    add_label(L"--- SISSI Compression ---", 16);
    add_check(L"Enable SISSI Compression",            ID_CHK_SISSI,        cfg.sissi_enabled);
    add_check(L"Greedy-First (longest phrases first)", ID_CHK_GREEDY,       cfg.greedy_first);
    add_check(L"Prioritize Large/Complex Words",       ID_CHK_LARGE_WORDS,  cfg.compress_large_words_first);
    add_check(L"Symbol Recycling",                     ID_CHK_RECYCLE,      cfg.recycle_symbols);
    add_check(L"Discard Prepositions",                 ID_CHK_PREPOSITIONS, cfg.discard_prepositions);
    add_check(L"Auto-Tune Spin (rapid scan)",          ID_CHK_AUTOTUNE,     cfg.auto_tune_spin_enabled);
    add_slider(L"Word Length Threshold", ID_SLD_WORD_LEN, 3, 12, cfg.large_word_len_threshold);

    // Memory
    add_label(L"--- Memory ---", 16);
    add_slider(L"VRAM Target %",         ID_SLD_VRAM,       50, 95,  static_cast<int>(cfg.vram_target_pct * 100.f));
    add_slider(L"Max Context Tokens (K)",ID_SLD_MAX_TOKENS,  1, 128, static_cast<int>(cfg.max_context_tokens / 1024));

    // NVMe / Backup
    add_label(L"--- NVMe / Backup ---", 16);
    add_check(L"NVMe Predictive Prefetch",        ID_CHK_NVME,       cfg.nvme_prefetch_enabled);
    add_check(L"Encrypt Backups (SISSI + 7zip)",  ID_CHK_BACKUP_ENC, cfg.backup_encrypt);
    add_check(L"Enable Telemetry and Debug (Opt-in)", ID_CHK_TELEMETRY, cfg.advanced_telemetry_opt_in);
    add_slider(L"Backup Interval (minutes)",      ID_SLD_BACKUP_INTERVAL, 1, 30, cfg.backup_interval_min);
    add_slider(L"Backup Compression Level (1-9)", ID_SLD_BACKUP_LEVEL,    1,  9, cfg.backup_compress_level);
}

LRESULT CALLBACK PirateGui::wnd_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    PirateGui* self = g_gui_instance;
    if (!self) return DefWindowProcW(hwnd, msg, wp, lp);

    switch (msg) {
        case WM_TIMER:
            if (wp == static_cast<WPARAM>(ID_TIMER_TELEMETRY)) {
                ProxyTelemetry t = self->proxy_.get_telemetry();
                self->update_telemetry(t);
                if (self->hwnd_status_) {
                    wchar_t buf[256];
                    swprintf_s(buf, 256,
                        L"VRAM: %.1f%%  Ratio: %.2fx  Reqs: %llu  Backend: %s",
                        static_cast<double>(t.vram_usage_pct),
                        static_cast<double>(t.compression_ratio),
                        static_cast<unsigned long long>(t.requests_handled),
                        t.backend_reachable ? L"\u2713 Online" : L"\u2717 Offline");
                    SetWindowTextW(self->hwnd_status_, buf);
                }
            }
            return 0;

        case WM_COMMAND: {
            int id = LOWORD(wp);
            if      (id == ID_BTN_BACKEND_OLLAMA)
                self->proxy_.set_backend(Backend::OLLAMA,    "127.0.0.1", 11434);
            else if (id == ID_BTN_BACKEND_LMS)
                self->proxy_.set_backend(Backend::LM_STUDIO, "127.0.0.1", 1234);
            else if (id == ID_BTN_BACKEND_NATIVE) {
                OPENFILENAMEW ofn = { sizeof(ofn) };
                wchar_t szFile[260] = { 0 };
                ofn.hwndOwner = hwnd;
                ofn.lpstrFile = szFile;
                ofn.nMaxFile = sizeof(szFile) / sizeof(wchar_t);
                ofn.lpstrFilter = L"GGUF Models\0*.gguf\0All Files\0*.*\0";
                ofn.nFilterIndex = 1;
                ofn.Flags = OFN_PATHMUSTEXIST | OFN_FILEMUSTEXIST;
                if (GetOpenFileNameW(&ofn)) {
                    // Convert wchar_t to std::string
                    char mbs[512] = { 0 };
                    WideCharToMultiByte(CP_UTF8, 0, szFile, -1, mbs, sizeof(mbs), nullptr, nullptr);
                    ProxyConfig c = self->proxy_.get_config();
                    c.model_path = mbs;
                    self->proxy_.update_config(c);
                    self->proxy_.set_backend(Backend::NATIVE);
                }
            } else if (id == ID_BTN_DETECT)
                self->proxy_.detect_backend();
            else
                self->apply_config_change();
            return 0;
        }

        case WM_HSCROLL:
            self->apply_config_change();
            return 0;

        case WM_CLOSE:
            DestroyWindow(hwnd);
            return 0;

        case WM_DESTROY:
            KillTimer(hwnd, ID_TIMER_TELEMETRY);
            PostQuitMessage(0);
            return 0;

        default:
            return DefWindowProcW(hwnd, msg, wp, lp);
    }
}

void PirateGui::apply_config_change() {
    if (!hwnd_) return;

    auto get_chk = [&](int id) -> bool {
        HWND h = GetDlgItem(hwnd_, id);
        return h ? (SendMessage(h, BM_GETCHECK, 0, 0) == BST_CHECKED) : false;
    };
    auto get_sld = [&](int id) -> int {
        HWND h = GetDlgItem(hwnd_, id);
        return h ? static_cast<int>(SendMessage(h, TBM_GETPOS, 0, 0)) : 0;
    };

    ProxyConfig cfg = proxy_.get_config();
    cfg.sissi_enabled              = get_chk(ID_CHK_SISSI);
    cfg.greedy_first               = get_chk(ID_CHK_GREEDY);
    cfg.compress_large_words_first = get_chk(ID_CHK_LARGE_WORDS);
    cfg.recycle_symbols            = get_chk(ID_CHK_RECYCLE);
    cfg.discard_prepositions       = get_chk(ID_CHK_PREPOSITIONS);
    cfg.auto_tune_spin_enabled     = get_chk(ID_CHK_AUTOTUNE);
    cfg.nvme_prefetch_enabled      = get_chk(ID_CHK_NVME);
    cfg.backup_encrypt             = get_chk(ID_CHK_BACKUP_ENC);
    cfg.advanced_telemetry_opt_in  = get_chk(ID_CHK_TELEMETRY);

    cfg.large_word_len_threshold   = get_sld(ID_SLD_WORD_LEN);
    cfg.vram_target_pct            = static_cast<float>(get_sld(ID_SLD_VRAM)) / 100.0f;
    cfg.max_context_tokens         = static_cast<uint32_t>(get_sld(ID_SLD_MAX_TOKENS)) * 1024u;
    cfg.backup_interval_min        = get_sld(ID_SLD_BACKUP_INTERVAL);
    cfg.backup_compress_level      = get_sld(ID_SLD_BACKUP_LEVEL);

    proxy_.update_config(cfg);
    if (config_cb_) config_cb_(cfg);
}

#else
// ── Non-Windows stubs ──────────────────────────────────────────────────────
void PirateGui::gui_thread_func() {}
void PirateGui::apply_config_change() {}
#endif

bool PirateGui::prompt_manual_consent(const std::string& source, const std::string& target) {
#if defined(_WIN32)
    std::string msg1 = "Would you like me to extract the data from " + source + "?";
    if (MessageBoxA(hwnd_, msg1.c_str(), "Manual Consent Required", MB_OKCANCEL | MB_ICONQUESTION) != IDOK) {
        return false;
    }
    
    std::string msg2 = "Would you like me to paste that info to " + target + "?";
    if (MessageBoxA(hwnd_, msg2.c_str(), "Manual Consent Required", MB_OKCANCEL | MB_ICONQUESTION) != IDOK) {
        return false;
    }
    return true;
#else
    return true;
#endif
}

bool PirateGui::prompt_rewrite_consent(float savings_pct) {
#if defined(_WIN32)
    char buf[256];
    snprintf(buf, sizeof(buf), "We can condense this prompt and save %.1f%% of your tokens. Do you approve this strategic rewrite?", savings_pct * 100.0f);
    if (MessageBoxA(hwnd_, buf, "Consent Required: Prompt Rewrite", MB_YESNO | MB_ICONQUESTION) == IDYES) {
        return true;
    }
    return false;
#else
    return true;
#endif
}

void PirateGui::show_onboarding_wizard() {
#if defined(_WIN32)
    // 1. Welcome Screen
    MessageBoxW(hwnd_, 
        L"Welcome to Pirate Llama! \u2620\uFE0F\n\n"
        L"This control panel allows you to seamlessly route your AI traffic to local LLMs (Ollama, LM Studio) or use native GGUF models directly, all while heavily compressing context tokens via SISSI to save memory.\n\n"
        L"Let's get you set up.", 
        L"Welcome", MB_OK | MB_ICONINFORMATION);

    // 2. Data Policy & Telemetry Opt-In
    int telemetry_choice = MessageBoxW(hwnd_,
        L"Data Policy & Telemetry:\n\n"
        L"By default, we collect NO data. Everything stays on your machine unless you actively send it to a cloud model.\n\n"
        L"However, you can opt-in to advanced telemetry and debug logging to help us improve the software. Would you like to enable telemetry? (You can change this later in the Advanced section).",
        L"Data Policy & Telemetry Opt-in", MB_YESNO | MB_ICONQUESTION);
    
    bool opt_in = (telemetry_choice == IDYES);
    
    // Apply telemetry choice
    ProxyConfig cfg = proxy_.get_config();
    cfg.advanced_telemetry_opt_in = opt_in;
    proxy_.update_config(cfg);
    if (config_cb_) config_cb_(cfg);

    // Update the UI checkbox to match
    HWND hCheck = GetDlgItem(hwnd_, ID_CHK_TELEMETRY);
    if (hCheck) {
        SendMessage(hCheck, BM_SETCHECK, opt_in ? BST_CHECKED : BST_UNCHECKED, 0);
    }

    // 3. Macro TOS Warning
    MessageBoxW(hwnd_, 
        L"WARNING regarding Automation:\n\n"
        L"Using a macro tool to automate UI clicks or bypass interactions would almost certainly violate the Terms of Service of multiple AI providers. Please think carefully before risking your account.", 
        L"TOS Warning", MB_OK | MB_ICONWARNING);

    // 4. Backend Setup Guide
    MessageBoxW(hwnd_,
        L"Setup Complete!\n\n"
        L"To start processing requests, please select your active backend from the main panel (Ollama, LM Studio, or Native), or just click 'Auto-Detect Backend'.\n\n"
        L"Point your client apps to http://127.0.0.1:11435 and enjoy!",
        L"Ready to Go", MB_OK | MB_ICONINFORMATION);
#endif
}

} // namespace pirate
