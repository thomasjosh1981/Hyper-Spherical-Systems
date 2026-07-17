"""tesseract_gui — desktop control center for the Project Tesseract engine.

Sub-modules:
    bridge     — thin Python wrapper around tesseract_bridge.dll
    wizard     — first-run setup wizard (drive detection, VRAM, llama fetch, 3FA)
    dashboard  — main window with telemetry + fine-grained controls
    config_io  — YAML persistence for user settings
"""

__version__ = "1.0.0"
