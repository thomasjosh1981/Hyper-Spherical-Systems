<div align="center">

<img src="docs/hypersphere_health_report.md" alt="" width="0"/>

# 🌌 Hyper-Spherical Systems — HypeS

### *Next-Generation Local AI Engine*

[![Release](https://img.shields.io/badge/release-v0.9.8--beta-brightgreen?style=flat-square)](https://github.com/thomasjosh1981/Hyper-Spherical-Systems/releases/tag/v0.9.8-beta)
[![License](https://img.shields.io/badge/license-MIT%20%2B%20Enterprise-purple?style=flat-square)](#-license)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-blue?style=flat-square)](#-system-requirements)

> **Run frontier-class AI on your own hardware — privately, permanently, and at 10× the token efficiency of any cloud subscription.**

</div>

---

## 📖 About HypeS

**HypeS** (Hyper-Spherical Systems) is a complete local AI execution suite that combines an advanced memory engine, a compression layer, a multi-model orchestrator, and an autonomous self-improvement director — all in a single, self-contained binary.

It works with **any GGUF, SFS, or SFS+** model and connects to **any OpenAI-compatible backend** (Ollama, LM Studio, native llama.cpp). There is nothing to install except the binary itself.

| What HypeS does | How |
|---|---|
| Runs 70B+ models on 12 GB VRAM | VRAM/RAM/NVMe 3-tier virtual VRAM illusion with Dual-NVMe Striping |
| Zero-CUDA CPU Layer Streaming | Memory-mapped NVMe AVX2 layer spooler for Intel Core i7 / AMD Ryzen 9 |
| Saves up to 10× cloud API tokens | ISSI + Homophonic + CCTM Ultra compression |
| Lets models learn and grow permanently | BMRAD Brain Director + HardcodedKnowledgeBase |
| Protects your key & offline data | Zero-cloud recovery + Local HypeS Security CHIP (`.chip`) File Export |
| Protects your conversations end-to-end | AES-256 + 5+1 Homophonic ephemeral session cipher |
| Enables models to teach each other | SFS+ InteropBus GROW_FROM / GROW_WITH |
| Gives your AI a voice and a face | 4ID Avatar — real-time STT/TTS + 4D animated entity |

---

## 👑 Golden Token HUD (v7.0) & Search-&-Seek AI Radar

The **Golden Token HUD** is a desktop telemetry overlay that docks cleanly to the top-right of your screen and tracks real-time token usage, compression ratios, and dollar savings across all connected AI sessions:

* **🔍 SEARCH & SEEK AI Radar**: Automatically detects and suction-docks running desktop windows, IDEs (Cursor, VS Code, Antigravity IDE), terminal CLIs, local daemons (Ollama, LM Studio, llama.cpp), and mobile bridges.
* **⚡ Google Antigravity IDE Live Link**: Embedded transcript sniffer continuously monitors active conversations and renders token optimization counters in real time.
* **🪟 Windowless Instant Launch**: Double-click `LAUNCH_TOKEN_HUD.vbs` for a pure windowless launch (zero black console flash) docked on top of your workspace (`WindowStaysOnTopHint`).

---

## 🏴‍☠️ Pirate Llama Universal Model Aggregator & Dynamic Router

Stop toggling between different ports and providers. Pirate Llama runs a transparent MITM proxy on port `8000`:

* **Consolidated `/v1/models` & `/api/tags`**: Automatically aggregates models from local daemons (Ollama `:11434`, LM Studio `:1234`, llama.cpp `:8080`, KoboldCpp `:5001`), cloud providers (OpenAI, Anthropic, Gemini, Groq, OpenRouter), and Google Antigravity IDE into a single unified model list.
* **Transparent Multi-Tier Fallback**: Point any AI interface (Cursor, WebUI, Aider, OpenClaw) to `http://localhost:8000/v1`. If an external backend drops offline, Pirate Llama dynamically routes requests to local Sovereign fallbacks so your client never hits a 500 error.
* **ISSI 10× Compression**: Passes prompts through the Integer String Substitution Index to eliminate repetitive verbose tokens before sending them across the wire.
* **⚓ SFS / SFS+ Runtime Requirement & LM Studio Routing**: To run SFS or SFS+ models, **Pirate Llama must be installed and functional** (manages container unpacking, layer streaming, and peer mesh). However, you can route them straight into **LM Studio** via the Universal Endpoint (`http://localhost:8000/v1`). Select your SFS model in LM Studio, and Pirate Llama transparently executes it under the hood while the Golden Token HUD monitors performance!
* **🦙 Native GGUF Execution (Built on llama.cpp)**: Because Pirate Llama's inference core was ported directly from `llama.cpp`, it runs all standard `.gguf` models natively with zero external dependencies. You can use Pirate Llama directly as a complete drop-in replacement for `llama.cpp` while gaining ISSI 10× prompt compression, 4D loop breaking, and Golden HUD live monitoring.

---

## 🧠 Brain Director Model Maker (BMRAD Engine) & Model Guidelines

The **BMRAD Engine** governs local multi-model topologies, speculative decoding, and autonomous routing:

* **5GB–7GB Supervisory Sweet Spot:** Quantized supervisory models (e.g. Qwen-2.5-Coder-7B, Llama-3.1-8B, Gemma-2-9B) sit alongside primary models to verify logic, break repetitive degeneration loops, and orchestrate tools without consuming excessive VRAM.
* **🚀 Dynamic Speculative Auto-Optimizer:** Speculative draft token depth ($K = 1 \dots 8$) auto-adjusts based on real-time verification acceptance rates and system latency. If latency spikes or draft passes are rejected, the auto-optimizer dynamically throttles drafting down to $K=1$, guaranteeing zero latency regression.
* **SFS+ InteropBus Skill Borrowing:** Models borrow capabilities (`vision_api`, `python_repl`, `peer_mesh`) across local instances via `GROW_FROM` and `GROW_WITH` protocols.
* **Multilingual Intent Normalizer:** Normalizes multilingual user queries into canonical semantic representations for domain-specific models.
* **Pre-Run Model Inspector:** Double-click any model to configure temperature, draft token depth, supervisory brain binding, and 5D OCEAN personality traits before execution.
* 📖 *Read the complete specification in **[docs/BRAIN_MODEL_GUIDELINES.md](docs/BRAIN_MODEL_GUIDELINES.md)**.*

---

## 🛠️ Open-Source Modules & Quickstart

### 1. Installation & Environment Setup
```bash
# Run the automated multi-module setup script:
./setup_all.bat   # Windows CMD
# or
./setup_all.ps1   # PowerShell
```

### 2. Zero-CUDA CPU Spooler Benchmark
For systems without dedicated NVIDIA/CUDA GPUs (Intel Core i7 / AMD Ryzen 9 laptops):
```bash
python layer_streamer/demo_cpu_spooler.py
```

### 3. Brain & Director Model Pre-Test Suite
Benchmark candidate supervisory models for hallucination resistance, routing accuracy, and JSON schema compliance:
```bash
python tools/brain_model_test_suite.py --endpoint "http://localhost:11434" --model "gemma4:latest"
```

### 4. Project Tesseract 3D Center-Out & 5-File Stripe Vault Demo
```bash
python tesseract_engine/demo_stripe_vault.py
```

---

## 📢 Community Alpha Notice
> **Note for Non-CUDA Core Developers & Testers:**  
> This open-source release includes our zero-CUDA CPU layer streaming engine and supervisory model test harness. It has been tested and verified across our in-house Intel Core i7 and AMD Ryzen 9 test machines. Because hardware configurations vary widely, we encourage community testing across diverse CPU, RAM, and storage topologies. Please report your benchmark findings, latency metrics, and hardware configurations in the Issues tab!

---

## 🚀 Quick Start

### Windows (Installer & Setup)

1. Download **`HypeS_Setup.exe`** from the [Releases page](https://github.com/thomasjosh1981/Hyper-Spherical-Systems/releases).
2. Run the installer (requires Administrator elevation) — it will:
   - Auto-detect Windows logged-in user credentials and hardware topology
   - Prompt for custom **Installation Directory** & **SFS/SFS+ Model Archive Drive**
   - Configure **Primary NVMe** and optional **Secondary Stripe NVMe** for ultra-fast VRAM streaming
   - Allow exporting/backing up your **HypeS Security CHIP File (`.chip`)**
   - Install binaries to your configured directory
   - Create Desktop folder (`Hyper-Spherical Systems Suite`) with 6 direct-module shortcut icons
   - Register an uninstaller in *Add/Remove Programs*
3. Double-click any shortcut (e.g. **HypeS Control Center**, **Pirate Proxy**, **Golden Candy Spinner**) to open that module directly.

> See **[HOWTO.md](docs/HOWTO.md)** for the full step-by-step guide with screenshots.

### Instant 1-Click Launch (From Cloned Repository)

If you have cloned or downloaded this repository, you can launch components directly:

* **👑 Golden Token HUD**: Double-click [`LAUNCH_TOKEN_HUD.vbs`](file:///C:/hyper_spherical/LAUNCH_TOKEN_HUD.vbs) (or run `LAUNCH_TOKEN_HUD.bat`). Docks immediately to the top-right of your screen with zero console window.
* **🌐 Master Control Center**: Double-click [`LAUNCH_CONTROL_CENTER.bat`](file:///C:/hyper_spherical/LAUNCH_CONTROL_CENTER.bat) to boot the dashboard and multi-backend manager.
* **🍬 Golden Candy Spinner**: Double-click [`LAUNCH_SPINNER.bat`](file:///C:/hyper_spherical/LAUNCH_SPINNER.bat) to launch the 4D vortex model packager.
* **🔌 Pirate Llama Universal Proxy**: Run `python gui/server.py` to start the unified endpoint on `http://localhost:8000`.

### Windows (Portable / No Install)

```
HypeS_Setup.exe
```

Double-click `HypeS_Setup.exe` from the root. No admin rights required.

### Linux / macOS

```bash
chmod +x release/launch_hypes_linux.sh
./release/launch_hypes_linux.sh
```

---

## 🧠 Core Modules

| Module | Binary | Description |
|---|---|---|
| **Tesseract Memory Engine** | `pirate_core.exe` | Virtual VRAM illusion — 3-tier layer streaming (VRAM → RAM → NVMe) |
| **BMRAD Brain Director** | `pirate_core.exe` | Autonomous attention pruner, loop detector, recursive self-improvement |
| **ISSI Compression** | `pirate_core.exe` | Phrase-code substitution — reduces prompts by up to 10× tokens |
| **CCTM Ultra** | `pirate_core.exe` | Cloud Token Compression Module — semantic deduplication + AES-256 |
| **SFS+ Interop Bus** | `pirate_core.exe` | Cross-model skill borrowing, GROW_FROM, GROW_WITH |
| **Pirate Llama Proxy** | `pirate_llama.exe` | OpenAI-compatible HTTP proxy with live ISSI compression |
| **Golden Candy Spinner** | `golden_candy_spinner.exe` | `.hscc` 4D vortex model packager |
| **NVMe Benchmark** | `nvme_benchmark.exe` | Drive throughput characterization (GB/s, IOPS) |
| **4ID Avatar** | embedded | Real-time voice STT/TTS + procedural 4D animated entity |
| **Python Bridge** | `python_bridge.dll` | C ABI ctypes bridge for Python integration |

---

## 💻 System Requirements

| Tier | GPU VRAM | RAM | Storage | Models |
|---|---|---|---|---|
| **Minimum** | 4 GB | 16 GB | 500 GB NVMe | Up to 13B |
| **Recommended** | 12 GB | 32 GB | 1 TB NVMe | Up to 34B |
| **Optimal** | 24 GB+ | 64 GB | 2 TB NVMe | 70B+ |

**Operating Systems:**
- Windows 11 (22H2 / 23H2 / 24H2) and Windows 10 64-bit (21H2+)
- Linux x86_64: Ubuntu 22.04+, Debian 12+, Arch
- macOS 13+ (Ventura / Sonoma / Sequoia) — Apple Silicon & Intel

---

## 💰 Pricing & Availability

HypeS is currently in **Alpha/Beta** and **100% free** to use until v1.0 release.

| Tier | Price | What You Get |
|---|---|---|
| **Alpha/Beta** | Free | All features, no expiry — you are here |
| **Community** | Free post-v1.0 | Base engine, 1 cloud backpack, 5 GB sandbox |
| **Lifetime Unlimited** | $100 – $250* | All modules forever, all future updates, version lock |
| **Module Bundle** | $149 | All 9 premium modules (SFS+, BMRAD, 4ID Avatar, CCTM, Cipher…) |
| **Per-Module** | $19 – $79 | Buy only what you need |
| **Enterprise** | Custom | Hardware-token build, priority support |

\* *Lifetime codes: first 100 at $100, then $150, $200, $250 — only 400 codes total.*

---

## 📂 Release Contents

```
release/
├── HyperSpherical_Installer/
│   └── HyperSpherical_Installer.exe   ← Full installer (recommended)
├── pirate_core.exe                     ← Core AI engine
├── pirate_llama.exe                    ← OpenAI-compatible proxy
├── pirate_bridge.exe                   ← Bridge / relay binary
├── golden_candy_spinner.exe            ← .hscc model packager
├── nvme_benchmark.exe                  ← NVMe benchmark tool
├── python_bridge.dll                   ← Python ctypes bridge
├── pirate_tests.exe                    ← Test suite (150 tests)
├── launch_hypes_linux.sh               ← Linux launcher
└── launch_hypes_mac.sh                 ← macOS launcher
```

---

## 📚 Documentation

| Document | Description |
|---|---|
| [HOWTO.md](docs/HOWTO.md) | Step-by-step installation & usage guide |
| [WALKTHROUGH.md](docs/WALKTHROUGH.md) | Feature walkthrough by module |
| [ABOUT.md](docs/ABOUT.md) | Architecture & design philosophy |
| [brochure.html](docs/brochure.html) | Full visual product brochure |
| [Hyper_Spherical_Brochure.pdf](docs/Hyper_Spherical_Brochure.pdf) | PDF version of brochure |

---

## 🔒 Security & Privacy

- **No telemetry by default.** All data stays on your machine.
- **AES-256 + ephemeral session cipher.** Cloud models never see uncompressed plaintext.
- **Session teardown zeroes all key material.** Cloud cannot decode past sessions.
- **Source code is proprietary and not distributed.** Only compiled binaries, open proxy tools, HUDs, and docs are public.
- **Control Flow Guard, ASLR, DEP, Anti-Debugging** on all Windows binaries.

---

## 💬 Community Feedback & Discussion (We Need Your Feedback!)

We are actively welcoming community testers, benchmark reports, and developer feedback:

* **🐛 Bug Reports & Feature Requests**: Please open an issue on the [GitHub Issues tab](https://github.com/thomasjosh1981/Hyper-Spherical-Systems/issues).
* **📊 Benchmark Results**: Share your hardware specs, NVMe speeds, CPU layer streaming results, or token compression ratios in [GitHub Discussions](https://github.com/thomasjosh1981/Hyper-Spherical-Systems/discussions).
* **📬 Direct Contact**: Connect directly with the developer via GitHub or email at `twistedsocal@gmail.com`.

---

## 📜 License

The **HypeS core engine binaries** are distributed as proprietary freeware for the Alpha/Beta phase.  
The **installer**, **launcher scripts**, **documentation**, and **brochure** are released under the **MIT License**.  
Enterprise builds require a separate commercial agreement.

---

<div align="center">
  <i>Experience the future of local AI inference. Grind down the limits.</i><br><br>
  <b>Developed by twiztedsocal — Hyper-Spherical Systems © 2026</b>
</div>


