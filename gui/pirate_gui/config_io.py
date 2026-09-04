"""
Configuration I/O Module for Hyper-Spherical Systems (HypeS).
Loads and saves YAML config files from ~/.hypes/config_gui.yaml or workspace root.
"""
import os
import sys
import yaml
from pathlib import Path
from typing import Any, Dict

class ConfigDict(dict):
    """Dictionary wrapper supporting attribute dot-access and complete defaults."""
    DEFAULTS: Dict[str, Any] = {
        "wizard_completed": False,
        "launch_mode": "native",
        "user_name": "",
        "user_email": "",
        "user_phone": "",
        "user_password_hash": "",
        "vram_limit_pct": 70,
        "ram_staging_pct": 50,
        "compression_enabled": True,
        "obfuscation_enabled": True,
        "refresh_interval_ms": 500,
        "always_on_top": False,
        "phys_vram_gb": 16,
        "phys_ram_gb": 32,
        "virtual_vram_gb": 64,
        "threefa_pairing_secret": "",
        "threefa_paired": False,
        "eviction_threshold": 0.75,
        "stay_in_buffer": 0.50,
        "load_in_prefetch": 0.80,
        "offload_aggr": 2,
        "predict_aggr": 3,
        "pred_threads": 8,
        "model_threads": 16,
        "mem_ceiling": 0.90,
        "encryption_enabled": True,
        "encryption_key_fpr": "",
        "drive_mode": "dual",
        "nvme_quota_gb": 500,
        "dma_thread_count": 8,
        "predictive_sensitivity": 0.85,
        "adaptive_hysteresis": True,
        "autotune_sensitivity": 0.75,
        "trf_model_filename": "tesseract-current.gguf",
        "window_geometry": b""
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for k, v in self.DEFAULTS.items():
            if k not in self:
                self[k] = v

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            return self.DEFAULTS.get(name, None)

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

def default_path() -> Path:
    user_config = Path.home() / ".hypes" / "config_gui.yaml"
    if user_config.exists():
        return user_config
    
    root_config = Path(__file__).parent.parent.parent / "config_gui.yaml"
    if root_config.exists():
        return root_config
    
    user_config.parent.mkdir(parents=True, exist_ok=True)
    return user_config

def load(path: Path = None) -> ConfigDict:
    if path is None:
        path = default_path()
    
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                if isinstance(data, dict):
                    return ConfigDict(data)
        except Exception as e:
            print(f"[config_io] Load warning: {e}")
    
    # Baked Default Config for Twistedsocal
    return ConfigDict()

def save(data: dict, path: Path = None) -> bool:
    if path is None:
        path = default_path()
    
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        export_data = dict(data)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(export_data, f, default_flow_style=False)
        return True
    except Exception as e:
        print(f"[config_io] Save error: {e}")
        return False
