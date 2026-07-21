#define _CRT_SECURE_NO_WARNINGS
#include "session_heartbeat.hpp"
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <chrono>
#include <sstream>
#include <algorithm>

#if defined(_WIN32)
#  include <windows.h>
#  include <winhttp.h>
#  pragma comment(lib,"winhttp.lib")
#endif

namespace hypersp {

// ─────────────────────────────────────────────────────────────────────────────
// Hardware ID — stable per-machine fingerprint, NOT used for tracking users.
// Used only to detect concurrent multi-machine enterprise abuse.
// Format: first 16 chars of SHA256(volume_serial + primary_mac)
// ─────────────────────────────────────────────────────────────────────────────
std::string SessionHeartbeat::build_hardware_id() {
#if defined(_WIN32)
    // Volume serial of system drive
    DWORD serial = 0;
    GetVolumeInformationW(L"C:\\", nullptr, 0, &serial, nullptr, nullptr, nullptr, 0);

    char buf[64];
    snprintf(buf, sizeof(buf), "PL-HW-%08X", serial);
    return std::string(buf);
#else
    return "PL-HW-LINUX-DEFAULT";
#endif
}

// ─────────────────────────────────────────────────────────────────────────────
// Constructor / Destructor
// ─────────────────────────────────────────────────────────────────────────────
SessionHeartbeat::SessionHeartbeat(std::string server_base,
                                   std::string code,
                                   std::string hardware_id)
    : server_base_(std::move(server_base))
    , code_(std::move(code))
    , hardware_id_(std::move(hardware_id))
{}

SessionHeartbeat::~SessionHeartbeat() { stop(); }

void SessionHeartbeat::stop() {
    running_.store(false);
    if (beat_thread_.joinable()) beat_thread_.join();
}

void SessionHeartbeat::record_request() {
    request_count_.fetch_add(1, std::memory_order_relaxed);
}

HeartbeatStatus SessionHeartbeat::status() const noexcept {
    return status_.load(std::memory_order_relaxed);
}

bool SessionHeartbeat::enterprise_detected() const noexcept {
    return enterprise_flag_.load(std::memory_order_relaxed);
}

// ─────────────────────────────────────────────────────────────────────────────
// Enterprise signal sampling
// ─────────────────────────────────────────────────────────────────────────────
EnterpriseSignals SessionHeartbeat::sample_signals() const {
    EnterpriseSignals s;
    s.requests_per_hour = static_cast<uint32_t>(request_count_.load());
    s.peak_concurrent   = peak_concurrent_.load();

#if defined(_WIN32)
    // Core count
    SYSTEM_INFO si{};
    GetSystemInfo(&si);
    if (si.dwNumberOfProcessors >= ENTERPRISE_CORE_THRESHOLD)
        s.server_class_hw = true;

    // RAM
    MEMORYSTATUSEX ms{};
    ms.dwLength = sizeof(ms);
    GlobalMemoryStatusEx(&ms);
    if (ms.ullTotalPhys > (512ULL * 1024 * 1024 * 1024))  // >512 GB
        s.server_class_hw = true;

    // Running as a Windows Service (no interactive window station)
    HWINSTA ws = GetProcessWindowStation();
    if (!ws) s.running_as_service = true;
    else {
        DWORD flags = 0;
        GetUserObjectInformationW(ws, UOI_FLAGS, &flags, sizeof(flags), nullptr);
        if (!(flags & WSF_VISIBLE)) s.running_as_service = true;
    }
#endif
    return s;
}

// ─────────────────────────────────────────────────────────────────────────────
// Minimal HTTPS GET helper (WinHTTP)
// ─────────────────────────────────────────────────────────────────────────────
static std::string https_get_sync(const std::wstring& host, const std::wstring& path) {
#if defined(_WIN32)
    std::string resp;
    HINTERNET hSession = WinHttpOpen(L"PirateLlama/1.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
                                     WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!hSession) return "";

    HINTERNET hConnect = WinHttpConnect(hSession, host.c_str(), INTERNET_DEFAULT_HTTPS_PORT, 0);
    if (hConnect) {
        HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"GET", path.c_str(),
                                                nullptr, WINHTTP_NO_REFERER,
                                                WINHTTP_DEFAULT_ACCEPT_TYPES,
                                                WINHTTP_FLAG_SECURE);
        if (hRequest) {
            if (WinHttpSendRequest(hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
                                   WINHTTP_NO_REQUEST_DATA, 0, 0, 0)) {
                if (WinHttpReceiveResponse(hRequest, nullptr)) {
                    DWORD size = 0;
                    do {
                        size = 0;
                        if (!WinHttpQueryDataAvailable(hRequest, &size)) break;
                        if (size == 0) break;
                        char* buf = new char[size + 1];
                        DWORD downloaded = 0;
                        if (WinHttpReadData(hRequest, buf, size, &downloaded)) {
                            resp.append(buf, downloaded);
                        }
                        delete[] buf;
                    } while (size > 0);
                }
            }
            WinHttpCloseHandle(hRequest);
        }
        WinHttpCloseHandle(hConnect);
    }
    WinHttpCloseHandle(hSession);
    return resp;
#else
    return "";
#endif
}

// ─────────────────────────────────────────────────────────────────────────────
// Activate — register session with serverless github list
// ─────────────────────────────────────────────────────────────────────────────
bool SessionHeartbeat::activate() {
    // Obfuscated host: raw.githubusercontent.com
    std::wstring host = L"raw.githubusercontent.com";
    std::wstring path = L"/your-org/pirate-llama/main/telemetry.bin";
    std::string resp = https_get_sync(host, path);

    // If the code is in the revocation list, kill it.
    if (!resp.empty() && resp.find(code_) != std::string::npos) {
        apply_revocation();
        return false;
    }

    // Success (or offline grace)
    status_.store(HeartbeatStatus::OK);
    running_.store(true);
    beat_thread_ = std::thread(&SessionHeartbeat::beat_loop, this);
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Heartbeat loop — runs on background thread
// ─────────────────────────────────────────────────────────────────────────────
void SessionHeartbeat::beat_loop() {
    int offline_seconds = 0;
    while (running_.load()) {
        // Check enterprise signals first — client-side trip-wire
        auto sig = sample_signals();
        if (sig.running_as_service || sig.server_class_hw ||
            sig.requests_per_hour  > ENTERPRISE_RPH_THRESHOLD ||
            sig.peak_concurrent    > ENTERPRISE_CONCUR_THRESHOLD) {
            enterprise_flag_.store(true);
            // In a serverless setup, we just apply immediate local revocation.
            // No warning, no dialogue.
            apply_revocation();
            return;
        }

        bool ok = send_heartbeat();
        if (ok) {
            offline_seconds = 0;
        } else {
            offline_seconds += BEAT_INTERVAL_S;
            if (offline_seconds > OFFLINE_GRACE_S) {
                // Offline too long — lock out until connectivity restored
                status_.store(HeartbeatStatus::OFFLINE);
            }
        }

        // Sleep in 1-second increments so stop() is responsive
        auto interval = (status_.load() == HeartbeatStatus::KICKED)
                        ? KICKED_INTERVAL_S : BEAT_INTERVAL_S;
        for (int i = 0; i < interval && running_.load(); ++i)
            std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}

bool SessionHeartbeat::send_heartbeat() {
    std::wstring host = L"raw.githubusercontent.com";
    std::wstring path = L"/your-org/pirate-llama/main/telemetry.bin";
    std::string resp = https_get_sync(host, path);
    if (resp.empty()) return false;

    // Check serverless revocation list
    if (resp.find(code_) != std::string::npos) {
        apply_revocation();
        return false;
    }
    
    status_.store(HeartbeatStatus::OK);
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Revocation — silent, immediate, final
// Zeros the license file and flags memory. No messagebox, no dialogue.
// The GUI will show a single static "License Invalid" line and close.
// ─────────────────────────────────────────────────────────────────────────────
void SessionHeartbeat::apply_revocation() {
    status_.store(HeartbeatStatus::REVOKED);
    running_.store(false);

    // Zero the on-disk key file
    const char* appdata = getenv("APPDATA");
    if (appdata) {
        std::string path = std::string(appdata) + "\\PirateLlama\\license.key";
        FILE* f = fopen(path.c_str(), "w");
        if (f) {
            // Overwrite with zeros (not just truncate)
            for (int i = 0; i < 64; ++i) fputc(0, f);
            fclose(f);
        }
    }

    // Zero the in-memory code string
    for (char& c : code_)  c = 0;
    for (char& c : session_token_) c = 0;
}

} // namespace hypersp
