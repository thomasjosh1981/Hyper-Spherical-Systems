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

## 🧹 Step 5: Uninstallation

To cleanly remove HypeS:
1. Go to **Windows Settings → Apps → Installed Apps**.
2. Search for **HyperSpherical**.
3. Click **Uninstall** and follow the prompts.
4. All installed files, shortcuts, and PATH entries will be cleanly removed.
