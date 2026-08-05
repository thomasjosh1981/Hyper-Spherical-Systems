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

## 🚀 Step 2: First-Run Onboarding Wizard

When HypeS launches for the first time, the **Onboarding Wizard** will walk you through system setup:

1. **Storage Drive Selection**:
   - **NVMe / SSD**: Select 1 or 2 high-speed drives for active model layer streaming.
   - **HDD**: Select a large storage drive (HDD ≥ 4 TB recommended) for cold SFS model archives.
2. **Crypto & Key Derivation**:
   - Choose key order preference (**Username-first** or **Password-first**).
   - Enter your credentials. *Note: Credentials are hashed with bcrypt/Argon2 and never saved in plaintext.*
3. **HuggingFace API Integration (Optional)**:
   - Enter your HuggingFace API token to enable automatic model card fetching and online brain model recommendations.
4. **Baseline Benchmark**:
   - HypeS runs a quick hardware throughput test to measure NVMe read/write speed (GB/s) and random IOPS.
5. **Brain Model Setup**:
   - Select a local model file (`.sfs`, `.sfs+`, `.hscc`, or `.gguf`) or download a recommended model from HuggingFace.

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

## 🧹 Step 5: Uninstallation

To cleanly remove HypeS:
1. Go to **Windows Settings → Apps → Installed Apps**.
2. Search for **HyperSpherical**.
3. Click **Uninstall** and follow the prompts.
4. All installed files, shortcuts, and PATH entries will be cleanly removed.
