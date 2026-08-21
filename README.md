<div align="center">

<img src="docs/hypersphere_health_report.md" alt="" width="0"/>

# 🌌 Hyper-Spherical Systems — HypeS
### *Next-Generation Local AI Engine*

[![Release](https://img.shields.io/badge/release-v0.9.8--alpha-cyan?style=flat-square)](https://github.com/thomasjosh1981/Hyper-Spherical-Systems/releases)
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
| Runs 70B+ models on 12 GB VRAM | VRAM/RAM/NVMe 3-tier virtual VRAM illusion |
| Zero-CUDA CPU Layer Streaming | Memory-mapped NVMe AVX2 layer spooler for Intel Core i7 / AMD Ryzen 9 |
| Saves up to 10× cloud API tokens | SISSI + Homophonic + CCTM Ultra compression |
| Lets models learn and grow permanently | BMRAD Brain Director + HardcodedKnowledgeBase |
| Protects your conversations end-to-end | AES-256 + 5+1 Homophonic ephemeral session cipher |
| Enables models to teach each other | SFS+ InteropBus GROW_FROM / GROW_WITH |
| Gives your AI a voice and a face | 4ID Avatar — real-time STT/TTS + 4D animated entity |

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

### Windows (Installer)

1. Download **`HyperSpherical_Installer.exe`** from the [Releases page](https://github.com/thomasjosh1981/Hyper-Spherical-Systems/releases).
2. Run the installer — it will:
   - Detect your hardware (VRAM, RAM, NVMe)
   - Install binaries to `C:\Program Files\HyperSpherical\`
   - Create Desktop + Start Menu shortcuts
   - Register an uninstaller in *Add/Remove Programs*
3. Launch **HypeS** from your Desktop shortcut or Start Menu.
4. Complete the **First-Run Onboarding Wizard** (drive selection, HuggingFace token, baseline benchmark).
5. Point HypeS at your model file and start chatting.

> See **[HOWTO.md](docs/HOWTO.md)** for the full step-by-step guide with screenshots.

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
| **SISSI Compression** | `pirate_core.exe` | Phrase-code substitution — reduces prompts by up to 10× tokens |
| **CCTM Ultra** | `pirate_core.exe` | Cloud Token Compression Module — semantic deduplication + AES-256 |
| **SFS+ Interop Bus** | `pirate_core.exe` | Cross-model skill borrowing, GROW_FROM, GROW_WITH |
| **Pirate Llama Proxy** | `pirate_llama.exe` | OpenAI-compatible HTTP proxy with live SISSI compression |
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
- **Source code is proprietary and not distributed.** Only compiled binaries and docs are public.
- **Control Flow Guard, ASLR, DEP, Anti-Debugging** on all Windows binaries.

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

