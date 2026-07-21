// pirate_main.cpp
//
// Pirate Llama — Entry Point
//
// Wires together:
//   - PirateProxy  (HTTP proxy server + SISSI integration)
//   - PirateGui    (floating Win32 control panel)
//   - Tesseract engine (memory / NVMe / backup subsystems)
//
// Usage:
//   pirate_llama [--port PORT] [--backend ollama|lmstudio|native] [--no-gui]
//
// License: MIT

#include "pirate_proxy.hpp"
#include "pirate_gui.hpp"
#include "config.hpp"
#include "license_manager.hpp"
#include "telemetry_logger.hpp"
#include "config_store.hpp"

#include <cstdio>
#include <cstring>
#include <string>
#include <csignal>
#include <atomic>
#include <thread>
#include <chrono>

static std::atomic<bool> g_shutdown{false};

static void signal_handler(int /*sig*/) {
    g_shutdown.store(true);
}

static void print_banner() {
    std::printf(
        "\n"
        "  ██████╗ ██╗██████╗  █████╗ ████████╗███████╗\n"
        "  ██╔══██╗██║██╔══██╗██╔══██╗╚══██╔══╝██╔════╝\n"
        "  ██████╔╝██║██████╔╝███████║   ██║   █████╗  \n"
        "  ██╔═══╝ ██║██╔══██╗██╔══██║   ██║   ██╔══╝  \n"
        "  ██║     ██║██║  ██║██║  ██║   ██║   ███████╗\n"
        "  ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝\n"
        "\n"
        "  🏴‍☠️  PIRATE LLAMA  —  Universal LLM Proxy + Endpoint\n"
        "  Powered by Tesseract Engine (Hyper-Spherical Systems v1.0)\n"
        "  SISSI Compression | HyperSphere Memory | RAID-5 Shards\n"
        "\n"
        "  Licence: MIT (proxy/bridge layers)\n"
        "           Freeware — No Decompile (SISSI/Cipher/PQC core)\n"
        "\n"
    );
}

static pirate::Backend parse_backend(const char* s) {
    if (std::strcmp(s, "ollama")    == 0) return pirate::Backend::OLLAMA;
    if (std::strcmp(s, "lmstudio") == 0) return pirate::Backend::LM_STUDIO;
    if (std::strcmp(s, "native")   == 0) return pirate::Backend::NATIVE;
    return pirate::Backend::AUTO_DETECT;
}

int main(int argc, char** argv) {
    print_banner();

    // Initialize DRM & Trial Enforcer
    hypersp::LicenseManager::init();
    hypersp::LicenseState state = hypersp::LicenseManager::get_state();

    if (state.tier == hypersp::LicenseTier::TRIAL_EXPIRED) {
        std::printf("[!] ERROR: Trial has expired.\n");
        std::printf("    Hardware ID: %s\n", state.hardware_id.c_str());
        std::printf("    To continue using Pirate Llama, please purchase a license.\n\n");
        return 1;
    }

    std::printf("--- LICENSING INFO ---\n");
    std::printf("App Hardware ID: %s\n", state.hardware_id.c_str());
    std::printf("Current Pop Lock Code (Rolling): %s\n", state.current_pop_lock.c_str());
    
    if (state.tier == hypersp::LicenseTier::TRIAL_12HR || 
        state.tier == hypersp::LicenseTier::TRIAL_6HR  || 
        state.tier == hypersp::LicenseTier::TRIAL_4HR) {
        std::printf("License Tier: TRIAL MODE (%llu seconds remaining)\n", 
            static_cast<unsigned long long>(state.remaining_seconds));
    } else {
        std::printf("License Tier: %d\n", static_cast<int>(state.tier));
    }
    std::printf("----------------------\n\n");

    // Parse command-line args
    pirate::ProxyConfig cfg;
    pirate::ConfigStore::load(cfg); // Load persistent settings

    bool no_gui = false;

    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--port") == 0 && i + 1 < argc) {
            cfg.proxy_port = static_cast<uint16_t>(std::atoi(argv[++i]));
        } else if (std::strcmp(argv[i], "--backend") == 0 && i + 1 < argc) {
            cfg.backend = parse_backend(argv[++i]);
        } else if (std::strcmp(argv[i], "--model") == 0 && i + 1 < argc) {
            cfg.model_path = argv[++i];
            cfg.backend = pirate::Backend::NATIVE;
        } else if (std::strcmp(argv[i], "--no-gui") == 0) {
            no_gui = true;
        } else if (std::strcmp(argv[i], "--no-sissi") == 0) {
            cfg.sissi_enabled = false;
        } else if (std::strcmp(argv[i], "--no-compress-req") == 0) {
            cfg.compress_requests = false;
        } else if (std::strcmp(argv[i], "--no-compress-resp") == 0) {
            cfg.compress_responses = false;
        } else if (std::strcmp(argv[i], "--backend-host") == 0 && i + 1 < argc) {
            cfg.backend_host = argv[++i];
        } else if (std::strcmp(argv[i], "--backend-port") == 0 && i + 1 < argc) {
            cfg.backend_port = static_cast<uint16_t>(std::atoi(argv[++i]));
        } else if (std::strcmp(argv[i], "--license") == 0 && i + 1 < argc) {
            std::string payload = argv[++i];
            if (hypersp::LicenseManager::apply_unlock_payload("", payload)) {
                std::printf("[pirate_llama] SUCCESS: License applied! Restart or continue.\n");
            } else {
                std::printf("[pirate_llama] ERROR: Invalid license payload.\n");
            }
        } else if (std::strcmp(argv[i], "--help") == 0) {
            std::printf(
                "Usage: pirate_llama [options]\n"
                "  --port PORT            Proxy listen port (default: 11435)\n"
                "  --backend NAME         Backend: ollama|lmstudio|native|auto (default: auto)\n"
                "  --backend-host HOST    Backend hostname (default: 127.0.0.1)\n"
                "  --backend-port PORT    Backend port (default: 11434)\n"
                "  --no-gui               Skip floating control panel\n"
                "  --no-sissi             Disable SISSI compression\n"
                "  --no-compress-req      Don't compress outgoing requests\n"
                "  --no-compress-resp     Don't decompress incoming responses\n"
                "  --license KEY          Apply unlock key\n"
                "  --help                 Show this help\n"
            );
            return 0;
        }
    }

    // Save config back to disk (persist CLI overrides)
    pirate::ConfigStore::save(cfg);

    // Bind license state to proxy config
    cfg.is_pro_tier = hypersp::LicenseManager::is_feature_allowed("cloud_context");

    // Set up signal handlers for graceful shutdown
    std::signal(SIGINT,  signal_handler);
    std::signal(SIGTERM, signal_handler);

    // ── Start the proxy ────────────────────────────────────────────────────
    pirate::PirateProxy proxy(cfg);

    if (!proxy.start()) {
        std::fprintf(stderr, "[pirate_llama] Failed to start proxy on port %d\n",
                     cfg.proxy_port);
        return 1;
    }

    std::printf("[pirate_llama] Proxy listening on http://%s:%d\n",
                cfg.proxy_host.c_str(), cfg.proxy_port);
    std::printf("[pirate_llama] Point Ollama/LM Studio/OpenAI clients at this address.\n");
    std::printf("[pirate_llama] SISSI compression: %s\n",
                cfg.sissi_enabled ? "ENABLED" : "disabled");

    // ── Detect backend ────────────────────────────────────────────────────
    pirate::Backend detected = proxy.detect_backend();
    const char* backend_name = "unknown";
    switch (detected) {
        case pirate::Backend::OLLAMA:    backend_name = "Ollama (:11434)";     break;
        case pirate::Backend::LM_STUDIO: backend_name = "LM Studio (:1234)";  break;
        case pirate::Backend::NATIVE:    backend_name = "Native (stub)";       break;
        default:                         backend_name = "Auto";                 break;
    }
    std::printf("[pirate_llama] Active backend: %s\n", backend_name);

    // ── Launch GUI ────────────────────────────────────────────────────────
    std::unique_ptr<pirate::PirateGui> gui;
    if (!no_gui) {
        gui = std::make_unique<pirate::PirateGui>(proxy);
        gui->on_config_change([&proxy](const pirate::ProxyConfig& updated_cfg) {
            // Propagate GUI changes back to the proxy
            proxy.update_config(updated_cfg);
        });
        
        proxy.set_consent_callback([gui_ptr = gui.get()](const std::string& src, const std::string& target) {
            return gui_ptr->prompt_manual_consent(src, target);
        });

        proxy.set_rewrite_consent_callback([gui_ptr = gui.get()](float savings_pct) {
            return gui_ptr->prompt_rewrite_consent(savings_pct);
        });

        proxy.set_supervisor_consent_callback([gui_ptr = gui.get()](const std::string& action) {
            return gui_ptr->prompt_supervisor_consent(action);
        });

        gui->run();
        gui->show_onboarding_wizard();
        std::printf("[pirate_llama] Control panel launched (always-on-top)\n");
    } else {
        proxy.set_consent_callback([](const std::string&, const std::string&) {
            std::printf("[pirate_llama] Cloud routing rejected (No GUI available for manual consent).\n");
            return false;
        });
        proxy.set_supervisor_consent_callback([](const std::string& action) {
            std::printf("[pirate_llama] Supervisor action rejected (No GUI available): %s\n", action.c_str());
            return false;
        });
    }

    // ── Main wait loop ────────────────────────────────────────────────────
    std::printf("[pirate_llama] Running. Press Ctrl+C to stop.\n\n");

    auto last_tick = std::chrono::steady_clock::now();

    while (!g_shutdown.load()) {
        std::this_thread::sleep_for(std::chrono::milliseconds(500));

        // Tick trial clock
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - last_tick).count();
        if (elapsed >= 1) {
            hypersp::LicenseManager::tick_usage(elapsed);
            last_tick = now;

            if (hypersp::LicenseManager::get_state().tier == hypersp::LicenseTier::TRIAL_EXPIRED) {
                std::printf("\n[!] Trial has expired. Shutting down.\n");
                g_shutdown.store(true);
            }
        }

        // Periodic telemetry dispatch and print
        static int tick = 0;
        if (++tick % 20 == 0) {  // every ~10s
            pirate::ProxyTelemetry t = proxy.get_telemetry();
            pirate::ProxyConfig current_cfg = proxy.get_config();
            
            hypersp::TelemetryLogger t_logger;
            t_logger.set_vram_usage_pct(t.vram_usage_pct);
            t_logger.set_opt_in(current_cfg.advanced_telemetry_opt_in);
            t_logger.transmit(); // Will only transmit if opted in

            if (no_gui) {
                std::printf("[telemetry] reqs=%llu  ratio=%.2fx  backend=%s\n",
                            static_cast<unsigned long long>(t.requests_handled),
                            static_cast<double>(t.compression_ratio),
                            t.backend_reachable ? "online" : "offline");
            }
        }
    }

    // ── Shutdown ──────────────────────────────────────────────────────────
    std::printf("\n[pirate_llama] Shutting down...\n");
    if (gui) gui->shutdown();
    proxy.stop();
    std::printf("[pirate_llama] Done. Goodbye, Captain.\n");
    return 0;
}
