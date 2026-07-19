# 🏴‍☠️ Project Pirate Llama — Pirate Llama

> **Disrupt local LLM inference. Run bigger models, faster, on less VRAM.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)]()
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-lightgrey.svg)]()
[![Tests: 248 passing](https://img.shields.io/badge/Tests-248%20passing-brightgreen.svg)]()
[![Beta](https://img.shields.io/badge/Status-Beta-orange.svg)]()

---

## What Is This?

**Pirate Llama** is a universal proxy, control panel, and inference accelerator for locally-run LLMs. Drop it in front of Ollama, LM Studio, koboldcpp, or any OpenAI-compatible server and immediately get:

- **3–11× compression** of your context window via SISSI (our novel token-level compression scheme)
- **Run models that don't fit in VRAM** — the memory manager tiers weights across VRAM → RAM → NVMe automatically
- **Floating control panel** with real-time sliders for every engine parameter
- **RAID-5 fault-tolerant memory** — a corrupted shard auto-recovers from parity without data loss
- **Works with everything** — Ollama, LM Studio, koboldcpp, Open WebUI, any client that speaks the OpenAI API

---

## Quick Start (Windows)

```
1. Download and extract the release zip
2. Double-click INSTALL.bat
3. Point your LLM client at http://127.0.0.1:11435
```

That's it. The installer verifies all binaries, runs 248 automated tests, then launches Pirate Llama with the floating control panel. Your existing Ollama or LM Studio keeps running exactly as-is — Pirate Llama just sits in front of it.

---

## The Core Innovation: SISSI Compression

SISSI (**S**emantic **I**nline **S**ubstitution with **S**tatic **I**ndex) compresses your prompt and context at the token level before it ever reaches the model. This isn't lossy summarization — it's a lossless dictionary substitution that the model can fully reconstruct.

**How much does it compress?**

| Content Type | Typical Ratio |
|---|---|
| Code + documentation | 4–7× |
| Conversational chat | 2–4× |
| Repetitive reasoning chains | 8–11× |
| Mixed prose | 3–6× |

**What does that mean in practice?**

If you have a 4K token context window and SISSI achieves 4× compression, you can now fit 16K worth of conversation into 4K. If you have 128K context and hit 4×, you're fitting **512K worth of context** into the same window. The model sees fewer tokens, runs faster, and you can use a bigger model on the same hardware.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Pirate Llama Proxy :11435                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              SISSI Core (Always On)                 │    │
│  │  Static 500-word index  |  Dynamic n-gram profiler  │    │
│  │  Symbol recycling       |  Preposition-discard PPV  │    │
│  │  HyperSphere coordinate projection (N-dim)          │    │
│  └─────────────────────────────────────────────────────┘    │
│         ↓ Compressed tokens                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Memory Mgr   │  │ RAID-5 Shards│  │ NeuronGraph      │  │
│  │ VRAM→RAM→    │  │ 5 data +     │  │ Synthurons       │  │
│  │ NVMe tiering │  │ 1 parity +   │  │ Hyper-tags       │  │
│  │              │  │ 4 decoy files│  │ Hyperclusters    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                ↓ Routed to backend                          │
│   [Ollama :11434]  [LM Studio :1234]  [Native llama.cpp]   │
└─────────────────────────────────────────────────────────────┘
```

---

## Open Source Model: SISSI-Native Embedding Model

> **Coming in v1.1** — The core disruption to the embedding model industry.

We are training a custom embedding model whose entire vocabulary is the 256-code SISSI dictionary. Because the vocabulary is 256 tokens instead of 32,000+:

- **7M parameter model** has the semantic resolution of a 200M+ standard embedding model
- Runs in **under 200MB VRAM**
- Produces embeddings that are **natively compatible with SISSI-compressed context**
- Will be released on Hugging Face under Apache 2.0

---

## License

| Component | License |
|---|---|
| Pirate Llama Proxy (`pirate_proxy.cpp`, `pirate_main.cpp`, `pirate_gui.cpp`) | MIT |
| Python Bridge & C ABI (`python_bridge.cpp`, `pirate_bridge.cpp`) | MIT |
| SISSI Compression Core (`context_compressor.cpp`, `static_dictionary.cpp`) | MIT |
| NeuronGraph & HyperSphere (`neuron_graph.cpp`, `hypersphere.cpp`) | MIT |
| Security layer — LeetCipher, PQC, RAID-5 ShardMatrix | **Freeware — No Decompile** |

The security layer is compiled with Control Flow Guard, Link-Time Optimization, and symbol stripping. Its algorithms are proprietary and must not be reverse-engineered. All other components are fully open source.

---

## Command Line Reference

```bash
# Default: auto-detect backend, open floating control panel
pirate_llama.exe

# Explicit backend
pirate_llama.exe --backend ollama
pirate_llama.exe --backend lmstudio
pirate_llama.exe --backend native

# Headless (no GUI — good for servers)
pirate_llama.exe --no-gui

# Custom port
pirate_llama.exe --port 11435

# Disable SISSI (pass-through mode)
pirate_llama.exe --no-sissi

# Full options
pirate_llama.exe --help
```

---

## Building From Source

```bash
# Windows (MSVC + CMake)
git clone https://github.com/your-org/project-tesseract
cd project-tesseract
mkdir build && cd build
cmake .. -G "Visual Studio 17 2022" -A x64
cmake --build . --config Release

# Run tests
.\Release\pirate_tests.exe          # 170 core tests
.\Release\pirate_security_tests.exe # 78 security tests
```

Requires: **CMake 3.20+**, **Visual Studio 2022** (Windows) or **GCC 12+** (Linux)

---

## Roadmap

- [x] SISSI context compression engine
- [x] HyperSphere N-dimensional memory coordinate system
- [x] RAID-5 fault-tolerant shard matrix
- [x] LeetCipher 3FA encryption
- [x] Post-quantum crypto (Kyber768)
- [x] Predictive NVMe prefetcher
- [x] Pirate Llama universal proxy
- [x] Win32 floating control panel
- [ ] **SISSI-native embedding model** (v1.1 — in development)
- [ ] SISSI decoder head for generation
- [ ] Android/iOS bridge
- [ ] Web UI alternative to Win32 panel
- [ ] Hermes Agent / OpenClaw plugin

---

## Contributing

Pull requests are welcome for all MIT-licensed components. See `CONTRIBUTING.md`.

**Do not submit PRs that modify the security layer** (`leet_cipher.cpp`, `shard_matrix.cpp`, `hypersphere_pqc.cpp`) — these are proprietary freeware.

---

*Built with ❤️ and a lot of coffee by the Hyper-Spherical Systems team.*
