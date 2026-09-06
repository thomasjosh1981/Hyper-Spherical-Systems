#!/usr/bin/env python3
"""
tools/create_github_packages.py
================================
Creates release distribution packages for Hyper-Spherical Systems:
  1. Pirate-Llama-Universal-Proxy-v1.0-Beta-win64.zip
  2. Golden-Token-HUD-v7.0-Beta-win64.zip
  3. Golden-Candy-Spinner-v6.0-Beta-win64.zip
  4. HypeS-Full-Suite-v0.9.8-Beta-win64.zip

Then tags git, creates the GitHub Beta Release via GitHub REST API,
and uploads all package assets directly to GitHub.
"""

import os
import sys
import json
import zipfile
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path("C:/hyper_spherical").resolve()
DIST = ROOT / "dist_packages"
DIST.mkdir(parents=True, exist_ok=True)

TAG = "v0.9.8-beta"
RELEASE_TITLE = "Hyper-Spherical Systems v0.9.8-Beta — Golden Token HUD, Pirate Llama & GCS Suite"

print("=" * 70)
print(f"📦 BUILDING GITHUB RELEASE PACKAGES ({TAG})")
print("=" * 70)

# ── 1. Pirate Llama Universal Proxy Package ──────────────────────────────────
pkg1_path = DIST / "Pirate-Llama-Universal-Proxy-v1.0-Beta-win64.zip"
print(f"\n[1/4] Assembling {pkg1_path.name}...")
with zipfile.ZipFile(pkg1_path, "w", zipfile.ZIP_DEFLATED) as z:
    # Launchers
    if (ROOT / "LAUNCH_PIRATE_LLAMA.bat").exists():
        z.write(ROOT / "LAUNCH_PIRATE_LLAMA.bat", "LAUNCH_PIRATE_LLAMA.bat")
    if (ROOT / "LAUNCH_PIRATE_LLAMA.vbs").exists():
        z.write(ROOT / "LAUNCH_PIRATE_LLAMA.vbs", "LAUNCH_PIRATE_LLAMA.vbs")
    
    # Executable from release/ if present
    if (ROOT / "release" / "pirate_llama.exe").exists():
        z.write(ROOT / "release" / "pirate_llama.exe", "pirate_llama.exe")
    if (ROOT / "release" / "pirate_bridge.exe").exists():
        z.write(ROOT / "release" / "pirate_bridge.exe", "pirate_bridge.exe")
        
    # Core Server & Intercept modules
    server_files = [
        "gui/server.py",
        "gui/pirate_intercept.py",
        "gui/sfs_container_manager.py",
        "gui/sfs_runtime_launcher.py",
        "gui/sfs_model_mesh.py",
        "gui/synthuron_bridge.py",
        "gui/cubical_address.py",
        "gui/pirate_gui/model_inspector_dialog.py",
        "gui/pirate_gui/pirate_llama.ico",
        "gui/pirate_gui/pirate_llama_mascot.png",
        "tools/brain_builder.py",
        "docs/BRAIN_MODEL_GUIDELINES.md",
    ]
    for sf in server_files:
        p = ROOT / sf
        if p.exists():
            z.write(p, sf)

    # Package README
    z.writestr("README_PIRATE_LLAMA.txt", """=====================================================================
🏴‍☠️ PIRATE LLAMA — Universal Model Aggregator & Native GGUF/SFS Engine
=====================================================================
Built on llama.cpp | Universal Endpoint: http://localhost:8000/v1

1. NATIVE GGUF EXECUTION:
   Pirate Llama's execution core was ported directly from llama.cpp.
   It runs any standard .gguf model natively with zero external dependencies.
   Use it directly as a full drop-in replacement for llama.cpp!

2. SFS & SFS+ MODEL HOST:
   Pirate Llama is mandatory for running SFS / SFS+ 4D bladed vortex models.
   It manages layer streaming, memory mapping, and sandboxed execution.

3. LM STUDIO ROUTING:
   Prefer the LM Studio UI? Connect LM Studio to:
   http://localhost:8000/v1
   Pirate Llama serves all loaded models, handles ISSI 10x token compression,
   and streams responses back into LM Studio.

HOW TO RUN:
- Double-click LAUNCH_PIRATE_LLAMA.bat (console mode)
- Double-click LAUNCH_PIRATE_LLAMA.vbs (silent background mode)
""")

print(f"  ✓ Created {pkg1_path.name} ({pkg1_path.stat().st_size / 1024:.1f} KB)")


# ── 2. Golden Token HUD Package ──────────────────────────────────────────────
pkg2_path = DIST / "Golden-Token-HUD-v7.0-Beta-win64.zip"
print(f"\n[2/4] Assembling {pkg2_path.name}...")
with zipfile.ZipFile(pkg2_path, "w", zipfile.ZIP_DEFLATED) as z:
    hud_files = [
        "LAUNCH_TOKEN_HUD.bat",
        "LAUNCH_TOKEN_HUD.vbs",
        "LAUNCH_TOKEN_HUD.py",
        "LAUNCH_TOKEN_HUD.pyw",
        "gui/pirate_gui/token_hud.py",
        "gui/pirate_gui/helipad_dock.py",
        "gui/pirate_gui/model_inspector_dialog.py",
        "gui/pirate_gui/hype_s.ico",
        "gui/pirate_gui/hype_s.png",
        "gui/pirate_gui/pirate_llama.ico",
        "gui/pirate_gui/pirate_llama_mascot.png",
    ]
    for hf in hud_files:
        p = ROOT / hf
        if p.exists():
            z.write(p, hf)
            
    z.writestr("README_GOLDEN_HUD.txt", """=====================================================================
👑 GOLDEN TOKEN HUD (v7.0) — Live AI Radar & Telemetry Overlay
=====================================================================
* Real-time token tracking, ISSI 10x compression ratios, and dollar savings.
* [🔍 SEARCH & SEEK AI Radar]: Auto-detects and suction-docks running AI windows
  (Cursor, VS Code, LM Studio, Ollama, Google Antigravity IDE, browser chats).
* Live link to Google Antigravity IDE transcript sniffer.

HOW TO RUN:
- Double-click LAUNCH_TOKEN_HUD.vbs (pure windowless launch docked to top-right).
""")

print(f"  ✓ Created {pkg2_path.name} ({pkg2_path.stat().st_size / 1024:.1f} KB)")


# ── 3. Golden Candy Spinner Package ──────────────────────────────────────────
pkg3_path = DIST / "Golden-Candy-Spinner-v6.0-Beta-win64.zip"
print(f"\n[3/4] Assembling {pkg3_path.name}...")
with zipfile.ZipFile(pkg3_path, "w", zipfile.ZIP_DEFLATED) as z:
    if (ROOT / "release" / "golden_candy_spinner.exe").exists():
        z.write(ROOT / "release" / "golden_candy_spinner.exe", "golden_candy_spinner.exe")
    if (ROOT / "LAUNCH_SPINNER.bat").exists():
        z.write(ROOT / "LAUNCH_SPINNER.bat", "LAUNCH_SPINNER.bat")
        
    spinner_files = [
        "gui/pirate_gui/golden_candy_spinner_panel.py",
        "gui/pirate_gui/model_browser_panel.py",
        "gui/pirate_gui/model_inspector_dialog.py",
        "gui/pirate_gui/golden_candy_spinner_icon.png",
        "tools/gguf_to_sfs_decomposer.py",
        "tools/brain_builder.py",
        "docs/HOWTO.md",
    ]
    for sf in spinner_files:
        p = ROOT / sf
        if p.exists():
            z.write(p, sf)
            
    z.writestr("README_SPINNER.txt", """=====================================================================
🍬 GOLDEN CANDY SPINNER (GCS v6.0) — 4D Vortex Decomposer & Brain Surgery
=====================================================================
* Interactive 3D Glowing Sheet Layer Pruning & Weight Microscope.
* Abliterate Red refusal heads, purge Yellow tripwires, unlock Pink NSFW.
* Tab 3: Hugging Face Model Hub — 1-click search, verify & pull GGUF models.
* Native SFS Model Execution: Directly run SFS containers with [🚀 RUN SFS MODEL].
* Brain Director Interaction: [🧠 INTERACT WITH BRAIN DIRECTOR] governor.
""")

print(f"  ✓ Created {pkg3_path.name} ({pkg3_path.stat().st_size / 1024:.1f} KB)")


# ── 4. Full HypeS Suite Package ──────────────────────────────────────────────
pkg4_path = DIST / "Hyper-Spherical-Suite-v0.9.8-Beta-win64.zip"
print(f"\n[4/4] Assembling {pkg4_path.name}...")
with zipfile.ZipFile(pkg4_path, "w", zipfile.ZIP_DEFLATED) as z:
    # Binaries from release/
    for bin_name in ["pirate_llama.exe", "pirate_core.exe", "golden_candy_spinner.exe", "pirate_bridge.exe"]:
        p = ROOT / "release" / bin_name
        if p.exists():
            z.write(p, bin_name)

    # Launchers & Scripts
    for sc in ["LAUNCH_TOKEN_HUD.bat", "LAUNCH_TOKEN_HUD.vbs", "LAUNCH_TOKEN_HUD.py", "LAUNCH_TOKEN_HUD.pyw",
               "LAUNCH_PIRATE_LLAMA.bat", "LAUNCH_PIRATE_LLAMA.vbs", "LAUNCH_SPINNER.bat", "LAUNCH_CONTROL_CENTER.bat",
               "setup_all.bat", "setup_all.ps1", "README.md", "ROADMAP.md"]:
        p = ROOT / sc
        if p.exists():
            z.write(p, sc)

    # Docs
    for df in (ROOT / "docs").glob("*.md"):
        z.write(df, f"docs/{df.name}")

    # Core gui files
    for gf in (ROOT / "gui").glob("*.py"):
        z.write(gf, f"gui/{gf.name}")
    for gf in (ROOT / "gui" / "pirate_gui").glob("*.*"):
        if gf.suffix.lower() in (".py", ".ico", ".png", ".html", ".css", ".js"):
            z.write(gf, f"gui/pirate_gui/{gf.name}")

    # Tools
    for tf in (ROOT / "tools").glob("*.py"):
        z.write(tf, f"tools/{tf.name}")

print(f"  ✓ Created {pkg4_path.name} ({pkg4_path.stat().st_size / (1024*1024):.2f} MB)")


# ── 5. Obtain GitHub Auth Token & Tag Repository ──────────────────────────────
print("\n" + "=" * 70)
print("🔑 ACQUIRING GITHUB CREDENTIALS & TAGGING RELEASE")
print("=" * 70)

p = subprocess.Popen(["git", "credential", "fill"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
out, _ = p.communicate("protocol=https\nhost=github.com\n\n")
creds = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
token = creds.get("password")

if not token:
    print("❌ Could not retrieve GitHub token from git credentials.")
    sys.exit(1)

print(f"✓ GitHub Authentication Verified for user: {creds.get('username')}")

# Git tag
print(f"Tagging commit with {TAG}...")
subprocess.run(["git", "tag", "-f", TAG], cwd=ROOT)
subprocess.run(["git", "push", "-f", "origin", TAG], cwd=ROOT)
print(f"✓ Pushed tag {TAG} to origin.")


# ── 6. Create GitHub Beta Release ─────────────────────────────────────────────
print("\n" + "=" * 70)
print("🚀 CREATING GITHUB BETA RELEASE")
print("=" * 70)

REPO = "thomasjosh1981/Hyper-Spherical-Systems"
API_URL = f"https://api.github.com/repos/{REPO}/releases"

release_notes = f"""# 🌌 Hyper-Spherical Systems — v0.9.8-Beta

Next-Generation Local AI Execution, Token Compression & Model Governance Suite.

---

## 📦 What's in this Release:

### 👑 1. Golden Token HUD (v7.0)
* **Real-Time Token Telemetry**: Dual-window LCD displays tracking raw prompt tokens, post-compression tokens, burst speeds, and live dollar savings.
* **🔍 SEARCH & SEEK AI Radar**: Automatically detects, locks, and suction-docks running desktop windows (Cursor, VS Code, Antigravity IDE, LM Studio, Ollama, terminal CLIs, mobile bridges).
* **⚡ Google Antigravity IDE Live Link**: Transcript sniffer continuously converts IDE activity into live token conservation metrics.
* **Windowless Instant Launch**: Launch cleanly via `LAUNCH_TOKEN_HUD.vbs` docked on top of your workspace.

### 🏴‍☠️ 2. Pirate Llama Universal Proxy & Model Aggregator
* **Built on llama.cpp (100% Native GGUF)**: Direct port of `llama.cpp` capable of running any standard `.gguf` file natively with zero external dependencies. Full drop-in replacement!
* **Mandatory SFS / SFS+ Container Host**: Required to unpack, stream, and run 4D bladed vortex SFS/SFS+ models.
* **LM Studio Universal Routing**: Seamlessly route SFS/SFS+ models into LM Studio through the OpenAI-compatible Universal Endpoint: `http://localhost:8000/v1`.
* **Consolidated `/v1/models` & `/api/tags`**: Automatically aggregates models from local daemons, cloud providers, and connected windows.
* **ISSI 10× Prompt Compression**: Eliminates repetitive prompt bloat before inference.

### 🍬 3. Golden Candy Spinner (GCS v6.0) & Brain Surgery Studio
* **Interactive Glowing Sheet Stack**: Color-coded layer canvas to abliterate Red refusal heads, purge Yellow alignment tripwires, and unlock Pink NSFW filters.
* **🤗 Hugging Face Model Hub**: Direct 1-click search, verification, and download of trending GGUF models.
* **🚀 Run SFS Models Natively**: Direct container execution button for .sfs and .sfs+ packages.
* **🧠 Brain Director Interaction**: Interactive connection to the supervisory Brain Director model inspector.

### 🧠 4. Brain Director Model Maker (BMRAD Engine)
* **5GB–7GB Supervisory Sweet Spot**: Quantized supervisory models (Qwen-2.5-Coder-7B, Llama-3.1-8B, Gemma-2-9B) govern routing, tool use, and factuality verification.
* **Dynamic Speculative Auto-Optimizer**: Auto-throttles speculative drafting passes during system latency spikes to guarantee zero latency regression.
* **4D Angular Loop Breaker**: Prevents repetitive token degeneration cycles.

---

## 📥 Ready-to-Run Download Packages:
1. **`Pirate-Llama-Universal-Proxy-v1.0-Beta-win64.zip`**: Standalone universal model proxy, native GGUF engine, SFS runner & LM Studio bridge.
2. **`Golden-Token-HUD-v7.0-Beta-win64.zip`**: Desktop telemetry overlay with Search & Seek Radar.
3. **`Golden-Candy-Spinner-v6.0-Beta-win64.zip`**: 4D model decomposer, HF explorer & Brain Surgery Studio.
4. **`Hyper-Spherical-Suite-v0.9.8-Beta-win64.zip`**: Complete unified suite including all modules, launchers, and tools.
"""

payload = {
    "tag_name": TAG,
    "target_commitish": "main",
    "name": RELEASE_TITLE,
    "body": release_notes,
    "draft": False,
    "prerelease": True
}

req = urllib.request.Request(
    API_URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
        "User-Agent": "HypeS-Release-Agent"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(req) as resp:
        release_data = json.loads(resp.read().decode("utf-8"))
        release_id = release_data["id"]
        upload_url_template = release_data["upload_url"]
        html_url = release_data["html_url"]
        print(f"✓ Created Release #{release_id} at: {html_url}")
except urllib.error.HTTPError as e:
    err_text = e.read().decode("utf-8")
    if "already_exists" in err_text:
        print("ℹ️ Release already exists, fetching existing release...")
        req_get = urllib.request.Request(
            f"{API_URL}/tags/{TAG}",
            headers={"Authorization": f"token {token}", "User-Agent": "HypeS-Release-Agent"}
        )
        with urllib.request.urlopen(req_get) as resp:
            release_data = json.loads(resp.read().decode("utf-8"))
            release_id = release_data["id"]
            upload_url_template = release_data["upload_url"]
            html_url = release_data["html_url"]
            print(f"✓ Found existing Release #{release_id} at: {html_url}")
    else:
        print(f"❌ Failed to create release: {e} - {err_text}")
        sys.exit(1)


# ── 7. Upload Assets to Release ───────────────────────────────────────────────
upload_base = upload_url_template.split("{")[0]

packages_to_upload = [
    pkg1_path,
    pkg2_path,
    pkg3_path,
    pkg4_path,
]

# Add installer if present
installer_path = ROOT / "release" / "HypeS_Setup.exe"
if installer_path.exists():
    packages_to_upload.append(installer_path)

print("\n" + "=" * 70)
print(f"📤 UPLOADING {len(packages_to_upload)} ASSETS TO GITHUB RELEASE")
print("=" * 70)

for pkg in packages_to_upload:
    size_mb = pkg.stat().st_size / (1024 * 1024)
    print(f"Uploading {pkg.name} ({size_mb:.2f} MB)...")
    
    upload_url = f"{upload_base}?name={urllib.parse.quote(pkg.name)}"
    with open(pkg, "rb") as f:
        file_bytes = f.read()

    req_up = urllib.request.Request(
        upload_url,
        data=file_bytes,
        headers={
            "Authorization": f"token {token}",
            "Content-Type": "application/zip" if pkg.suffix == ".zip" else "application/octet-stream",
            "User-Agent": "HypeS-Release-Agent"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req_up, timeout=300) as resp:
            asset_info = json.loads(resp.read().decode("utf-8"))
            print(f"  ✓ Uploaded: {asset_info.get('browser_download_url')}")
    except urllib.error.HTTPError as e:
        err_text = e.read().decode("utf-8")
        if "already_exists" in err_text:
            print(f"  ℹ️ {pkg.name} already attached to release.")
        else:
            print(f"  ⚠️ Upload warning for {pkg.name}: {err_text[:200]}")
    except Exception as e:
        print(f"  ⚠️ Error uploading {pkg.name}: {e}")

print("\n" + "=" * 70)
print(f"🎉 RELEASE PUBLISHED SUCCESSFULLY!")
print(f"👉 Live Release URL: {html_url}")
print("=" * 70)
