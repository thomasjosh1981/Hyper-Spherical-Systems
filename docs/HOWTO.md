# Hyper-Spherical Systems — User How-To Guide

This guide provides step-by-step instructions for installing, configuring, and using **HypeS** (Hyper-Spherical Systems).

---

## 🛠️ Step 1: Installation

### Option A: Clean Full Package Installer (Recommended for Windows)

1. Download **`HyperSpherical_Installer.exe`** from the `release/HyperSpherical_Installer/` folder or the GitHub Releases page.
2. Double-click **`HyperSpherical_Installer.exe`**.
3. If prompted by Windows User Account Control (UAC), click **Yes** to grant Administrator privileges (required for `C:\Program Files\` installation and system PATH registration).
4. Follow the setup wizard:
   - Select installation components (Core Engine, Proxy, Packaging tools).
   - Choose install path (Default: `C:\Program Files\HyperSpherical`).
   - Click **Install**.
5. Once completed, shortcuts will be placed on your **Desktop** and in your **Start Menu**.

---

### Option B: Standalone Portable Binary (No Installation)

1. Navigate to your release folder or USB drive containing `HypeS_Setup.exe`.
2. Double-click `HypeS_Setup.exe`.
3. The portable launcher initializes without writing to system directories or requiring admin rights.

---

## 🚀 Step 2: First-Run Onboarding Wizard & Sovereign Key Provisioning

When HypeS launches for the first time, the **Onboarding Wizard** (`installer/hypes_installer_gui.py` or `python launch_hypes.py --installer`) guides you through complete setup:

1. **Account & Hardware Identity Derivation**:
   - Enter your Username, Email, Phone Number, and a secure password ($\ge 2$ uppercase, $\ge 2$ lowercase, $\ge 2$ numbers, $\ge 2$ special characters).
   - HypeS extracts your CPU ID, Motherboard UUID, and volume serial to derive a 100% local, hardware-bound cryptographic master key via Argon2id & native SHA-256.

2. **Sovereign Recovery Stash & De-Obfuscation Backup**:
   - **Critical Asset Directive**: HypeS generates 1–2 recovery files (`HypeS_Crypt_Key` and `HypeS_CHIP_*.chip` / `HypeS_Recovery_Stash.txt`) containing the 3D Cube Homophonic Recovery Phrase. These keys are required to **de-obfuscate / unobfuscate and decrypt** your sovereign conversation matrix (`.snb`), model weights, and license assets if your machine is ever rebuilt or wiped.
   - **Recommended Media Targets (1–2 Redundant Copies)**:
     - **1 or 2 SD / MicroSD Cards**: Insert into your device card reader for offline cold storage.
     - **2 External USB Removable Drives**: Keep redundant copies on separate USB thumb drives / external SSDs.
     - **Encrypted Cloud Backup**: Store an encrypted copy in Google Drive, OneDrive, ProtonDrive, iCloud, or Dropbox.
   - *Zero-Cloud Privacy Guarantee*: We never store or transmit a copy of your keys to any server.

3. **Module & Add-On Feature Store**:
   - Select your desired runtime components: **Base Root Engine (.snb Memory Vault)**, **Golden Candy Spinner (.hscc 4D Vortex)**, **ISSI 10x Token Optimizer**, **4ID Avatar & Living Spirit**, **Dual-NVMe DirectStorage Streamer**, and **Enterprise Suite**.

4. **Storage Architecture Selection**:
   - **Dual-NVMe Stripe**: Configure 1 or 2 high-speed NVMe/SSD drives for real-time 4D quaternionic weight streaming.
   - **Cold HDD Archive**: Designate high-capacity storage ($\ge 4\text{ TB}$) for inactive `.sfs+` model archives.

5. **Universal Transparent Interceptor & Auto-Seek**:
   - Set up the zero-config gateway (ports `8000` / `11434`).
   - Use the **Auto-Seek** engine to scan and hook open browser chat tabs (ChatGPT, Claude, Gemini, Perplexity), IDEs (Cursor, VS Code), and terminal TUIs (Ollama, Aider) with 1 click.


---

## 💬 Step 3: Running Inferences & Interacting with HypeS

### Launching the Graphical User Interface (GUI)

- Open **HypeS** from your Desktop shortcut or run `launch_hypes.py`.
- The GUI opens a Cyber-Themed Dashboard featuring:
  - **4D Spatial Geometry Visualizer**: Displays model activation nodes on a unit hypersphere.
  - **Telemetry Dashboard**: Real-time monitor for VRAM, RAM, NVMe throughput, and compression ratio.
  - **4ID Avatar Window**: Real-time 4D animated visual entity with viseme-synced voice feedback.

### Interacting via Local Proxy (Pirate Llama)

HypeS includes an OpenAI-compatible HTTP proxy running on port `11435`:
- **Endpoint**: `http://127.0.0.1:11435/v1/chat_completions`
- Compatible with third-party tools like **Continue.dev**, **Open WebUI**, **LM Studio**, or custom scripts.

Example request using `curl`:
```bash
curl http://127.0.0.1:11435/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "local-brain",
    "messages": [{"role": "user", "content": "Explain hyperspherical vector routing."}]
  }'
```

---

## 🔒 Step 4: SFS+ Cross-Model Capability & Memory

With SFS+ models, your AI is capable of autonomous growth:
1. **Skill Borrowing**: Models temporarily load capabilities from peer models over the `SFSInteropBus`.
2. **Permanent Absorption**: Superior capabilities from peer models are automatically absorbed into permanent memory (`hardcoded_knowledge.json`).
3. **Voice & 4ID Avatar Controls**: Configure voice pitch, speed, and animation states (Idle, Talking, Searching File Cabinet, Thinking) from the settings panel.

---

## 🍬 Step 4: Golden Candy Spinner & Brain Surgery Studio (Operator's Guide)

The **Golden Candy Spinner (GCS v6.0)** is an advanced 4D tensor decomposer, weight microscope, and model surgery suite designed to ingest raw models, abliterate refusal guardrails, splice new datasets, and respin weights into high-performance 4D `.hscc` vortex packages.

### 1. Launching Golden Candy Spinner

* **1-Click Desktop Shortcut**: Double-click **`Golden Candy Spinner.lnk`** on your Desktop.
* **Batch Launcher**: Double-click [`LAUNCH_SPINNER.bat`](file:///C:/hyper_spherical/LAUNCH_SPINNER.bat) in the repository root.
* **Command Line**: Run `python launch_hypes.py --spinner` from terminal.

---

### 2. 🤗 Hugging Face Model Pull & Verification

Golden Candy Spinner connects directly to Hugging Face so you can verify models and pull them with 1 click:

1. **In-App Model Hub (Tab 3)**:
   - Click the **`🤗 HUGGING FACE MODEL HUB`** tab (or click `[🤗 SEARCH & PULL FROM HUGGING FACE]` on Tab 1).
   - **Search & Filter**: Search by keyword, creator, or repo ID (e.g. `bartowski/gemma-2-27b-it-GGUF`, `Qwen/Qwen2.5-Coder-32B-Instruct-GGUF`, `DeepSeek-R1-Distill-Qwen-14B`).
   - Filter models by parameter size (`8B`, `14B`, `27B`, `70B`) or quantization format (`Q4_K_M`, `Q8_0`, `SFS+`).
   - Click **`⬇️ DOWNLOAD MODEL`**: Streams chunks directly from Hugging Face into `~/.hypes/models/` with live resume support.
   - When download finishes, the model automatically loads into the Matrix Muncher and opens the Brain Surgery Studio.
2. **Web Registry Verification**:
   - Click **`🌐 BROWSE HUGGING FACE GGUF HUB (WEB)`** to open the official Hugging Face trending GGUF registry (`https://huggingface.co/models?library=gguf`) directly in your default browser.

---

### 3. 💥 Matrix Muncher & Model Ingestion (Tab 1)

* Drag and drop any `.gguf`, `.safetensors`, or `.bin` model file into the dashed red ingestion dropzone.
* Alternatively, click **`💥 DRAG & DROP GGUF MODEL OR CLICK TO BROWSE`** to open the file picker.
* The Matrix Muncher scans raw byte offsets, reads quantization headers, and maps tensor boundaries for surgery.

---

### 4. 🧠 Brain Surgery Studio — Interactive "Stack of Glowing Sheets" (Tab 2)

The Brain Surgery Studio visualizes the neural network as an interactive, color-coded 3D stack of translucent glowing sheets:

| Sheet Color | Layer Classification | Description |
|---|---|---|
| 🔴 **Red** | **Guardrails & Refusal Heads** | Rejection heads, canned refusals ("As an AI language model..."), safety blockades. |
| 🟡 **Yellow** | **Alignment Tripwires** | Sycophancy vectors, corporate bias filters, and forced conversational constraints. |
| 🟢 **Green** | **Core Reasoning** | Unaltered attention projections, multi-head Q/K/V weights, and feed-forward reasoning. |
| 🔵 **Blue** | **Base Embeddings** | Vocabulary embeddings and rotary positional projections ($R_oPE$). |
| 🌸 **Pink** | **Censorship / NSFW Filters** | Lexical suppression matrices and content filters. |

#### Surgical Actions & Abliteration

* **Interactive Layer Inspection**: Click any sheet in the stack to focus the **Weight Microscope** on that layer. Inspect its matrix shape (e.g. `(4096, 14336)`), weight norm, activation density, and byte range.
* **`✂️ RIP OUT THIS WEIGHT SLICE`**: Surgically zeroes out or prunes the currently selected tensor.
* **`🔪 OBLITERATE ALL RED (Guardrails)`**: 1-click abliteration to neutralize all red refusal and rejection heads across the entire network.
* **`⚡ PURGE ALL YELLOW (Tripwires)`**: Cleanses sycophantic alignment tripwires for unfiltered, truthful answers.
* **`🔓 UNLOCK PINK (NSFW Matrices)`**: De-suppresses restricted lexical terms and output tokens.

#### Dataset & Knowledge Splicing

* In the **Dataset Hub & Coding Knowledge Booster**, select a target training corpus:
  - `Hugging Face: BigCode / The-Stack-v2 (Python, C++, Rust, CUDA)`
  - `Hugging Face: Open-Orca Deep Reasoning & Chain-of-Thought`
  - `Hugging Face: DeepSeek-Coder Synthetic Instruction Tuning`
  - `Kaggle: Top Algorithm & Competitive Programming Corpus`
* Click **`💉 INJECT CODING NEURONS`** to splice domain-specific algorithmic capability directly into the manifold.

---

### 5. 🌀 4Decomposer & Respinning into 4D CCFS+

1. Once surgery and pruning are complete, switch back to **Tab 1: 4Decomposer & Muncher**.
2. Click **`🌀 DECOMPOSE & RESPIN INTO 4D CCFS+`**.
3. The 4Decomposer maps the clean tensors onto the 4D Fibonacci vortex on the $S^3$ unit hypersphere, packaging the output as a `.hscc` model ready for zero-latency NVMe layer streaming.

---

## 🧹 Step 5: Uninstallation

To cleanly remove HypeS:
1. Go to **Windows Settings → Apps → Installed Apps**.
2. Search for **HyperSpherical**.
3. Click **Uninstall** and follow the prompts.
4. All installed files, shortcuts, and PATH entries will be cleanly removed.
