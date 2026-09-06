"""
token_hud_overlay.py — Hyper-Spherical Unified Token HUD & Suite Linker
Delegates to the Gold Master Token HUD (LAUNCH_TOKEN_HUD.py) with Antigravity IDE Integration.
"""
import sys
import os
from pathlib import Path

# Locate master LAUNCH_TOKEN_HUD.py
target_launcher = None
for candidate in [
    Path(r"I:\workspace\hyper_spherical\LAUNCH_TOKEN_HUD.py"),
    Path(r"C:\Users\twist\workspace\hyper_spherical\LAUNCH_TOKEN_HUD.py"),
    Path(__file__).parent.parent / "hyper_spherical" / "LAUNCH_TOKEN_HUD.py",
]:
    if candidate.exists():
        target_launcher = candidate
        break

if target_launcher:
    # Set cwd and run the launcher
    sys.path.insert(0, str(target_launcher.parent))
    sys.path.insert(0, str(target_launcher.parent / "gui"))
    sys.path.insert(0, str(target_launcher.parent / "gui" / "pirate_gui"))
    
    # Execute the master launcher script
    with open(target_launcher, "r", encoding="utf-8") as f:
        code = compile(f.read(), str(target_launcher), 'exec')
        exec(code, {"__name__": "__main__", "__file__": str(target_launcher)})
else:
    print("Error: Could not locate master LAUNCH_TOKEN_HUD.py", file=sys.stderr)
    sys.exit(1)
