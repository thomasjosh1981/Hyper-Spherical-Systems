"""
HyperMem Neuro-Phasing & Model Phase-Locker
===========================================
Scans local machines for downloaded model files (.gguf, .safetensors, Ollama)
and phase-locks them with persistent HyperMem Synthuron memory stubs.
"""

import os
import json
import time
from typing import Dict, List, Optional, Any


class NeuroPhaseLocker:
    """
    Manages model phase-locking and persistent memory bindings.
    """

    def __init__(self, default_vault_drive: str = "C:/HyperMem_Vault"):
        self.default_vault_drive = default_vault_drive
        os.makedirs(self.default_vault_drive, exist_ok=True)
        self.manifest_file = os.path.join(self.default_vault_drive, "phase_locks.json")
        self.locks: Dict[str, Dict[str, Any]] = self._load_locks()

    def _load_locks(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.manifest_file):
            try:
                with open(self.manifest_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_locks(self):
        with open(self.manifest_file, "w", encoding="utf-8") as f:
            json.dump(self.locks, f, indent=2)

    def scan_local_models(self, search_paths: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Scans filesystem for local GGUF / Safetensors / Ollama models."""
        if search_paths is None:
            user_home = os.path.expanduser("~")
            search_paths = [
                os.path.join(user_home, ".ollama", "models"),
                os.path.join(user_home, ".cache", "lm-studio", "models"),
                os.path.join(user_home, ".cache", "huggingface", "hub"),
                "C:/models",
                "D:/models"
            ]

        found_models: List[Dict[str, Any]] = []
        for path in search_paths:
            if not os.path.exists(path):
                continue
            for root, _, files in os.walk(path):
                for f in files:
                    if f.endswith((".gguf", ".safetensors", ".bin")):
                        full_path = os.path.join(root, f)
                        found_models.append({
                            "name": f,
                            "path": full_path,
                            "size_gb": round(os.path.getsize(full_path) / (1024**3), 2),
                            "format": f.split(".")[-1].upper()
                        })
        return found_models

    def phase_lock_model(self, model_identifier: str, model_path: str, custom_vault_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Binds a model with a dedicated HyperMem persistent memory stub.
        """
        vault_path = custom_vault_path or os.path.join(self.default_vault_drive, f"mem_{model_identifier}")
        os.makedirs(vault_path, exist_ok=True)

        lock_record = {
            "model_id": model_identifier,
            "model_path": model_path,
            "vault_path": vault_path,
            "locked_at": time.time(),
            "status": "PHASE_LOCKED_ACTIVE",
            "stub_type": "SYNTHURON_NATIVE"
        }

        self.locks[model_identifier] = lock_record
        self._save_locks()
        return lock_record
