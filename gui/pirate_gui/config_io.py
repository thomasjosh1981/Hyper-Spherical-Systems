"""config_io.py — YAML persistence for Tesseract GUI settings.

Stores user preferences in `config_gui.yaml` next to the project root.
The engine's own runtime config (config.yaml) lives alongside it and is
managed by the wizard.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class DriveAssignment:
    letter:   str          # "D", "E", ...
    role:     str          # "primary" | "secondary" | "cold"
    label:    str = ""     # human-friendly label


@dataclass
class GuiConfig:
    # Wizard completion state
    wizard_completed:   bool = False

    # Storage layout
    drives:             list[DriveAssignment] = field(default_factory=list)
    nvme_primary_path:  str = "D:\\tesseract_live"
    nvme_secondary_path: str = "C:\\tesseract_cache"
    hdd_cold_path:      str = "I:\\tesseract_cold"

    # Engine caps
    vram_max_ratio:     float = 0.90   # hard cap on physical VRAM (user has 12GB, no discrete GPU)
    ram_staging_pct:    float = 0.50
    phys_vram_gb:       int   = 12     # user has a 12GB GPU (iGPU is display-only)
    phys_ram_gb:        int   = 32
    virtual_vram_gb:    int   = 60     # 60GB illusion presented to the LLM

    # Compression
    compression_enabled: bool  = False
    min_comp_phrase_len: int   = 2
    max_dict_entries:    int   = 65536
    max_active_tokens:   int   = 260000

    # Prefetch
    prediction_window:       int   = 16
    prefetch_confidence_min: float = 0.75

    # NVMe I/O
    nvme_optimal_read_chunk:  int = 1048576
    nvme_optimal_write_chunk: int = 524288

    # llama.cpp
    llama_cpp_path:        str = ""
    llama_patched:         bool = False

    # 3FA / encryption
    threefa_paired:        bool = False
    threefa_pairing_secret: str = ""     # shown once in QR code
    encryption_key_fpr:    str = ""      # fingerprint of generated key
    encryption_enabled:    bool = False  # toggle for runtime encryption

    # Master GUI Spec V3.1 controls
    drive_mode:            str  = "single"          # "single" | "dual"
    nvme_quota_gb:         int  = 0                 # 0 = no cap; else hard GB limit
    dma_thread_count:      int  = 2                 # CPU threads driving DMA
    predictive_sensitivity: float = 0.75            # logarithmic slider (0..1)
    adaptive_hysteresis:   bool = False             # continuous online-learning loop
    autotune_sensitivity:   float = 0.05             # feedback loop gain
    trf_model_filename:    str  = "tesseract-current.gguf"  # for TRF registry

    # Advanced (hysteresis + aggressiveness + threads + mem ceiling)
    eviction_threshold:    float = 0.90
    stay_in_buffer:        float = 0.20
    load_in_prefetch:      float = 0.40
    offload_aggr:          int   = 50
    predict_aggr:          int   = 60
    pred_threads:          int   = 4
    model_threads:         int   = 8
    mem_ceiling:           float = 0.50

    # GUI preferences
    refresh_interval_ms:  int   = 250
    theme:                str   = "dark"   # "dark" | "light"
    window_geometry:      bytes = b""


_DEFAULT_PATH = Path(r"C:\Users\twist\workspace\project_tesseract\config_gui.yaml")


def default_path() -> Path:
    return _DEFAULT_PATH


def load(path: Optional[Path] = None) -> GuiConfig:
    path = path or _DEFAULT_PATH
    if not path.exists():
        return GuiConfig()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        print(f"[config_io] WARNING: malformed {path}: {exc}")
        return GuiConfig()

    # Drives need manual hydration (list of dicts -> dataclass list)
    raw_drives = data.pop("drives", []) or []
    drives = [DriveAssignment(**d) for d in raw_drives]

    # Window geometry is bytes
    geom = data.pop("window_geometry", b"")
    if isinstance(geom, str):
        geom = geom.encode("latin-1")
    data["window_geometry"] = geom
    data["drives"] = drives

    cfg = GuiConfig(**{k: v for k, v in data.items() if k in GuiConfig.__dataclass_fields__})
    return cfg


def save(cfg: GuiConfig, path: Optional[Path] = None) -> None:
    path = path or _DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(cfg)
    # Bytes can't be yaml-serialized; base64-encode for portability
    geom = data.pop("window_geometry", b"")
    if geom:
        import base64
        data["window_geometry_b64"] = base64.b64encode(geom).decode("ascii")
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)


if __name__ == "__main__":   # tiny CLI for sanity
    import sys, json
    cfg = load()
    print(json.dumps(asdict(cfg), indent=2, default=str))
    sys.exit(0)
