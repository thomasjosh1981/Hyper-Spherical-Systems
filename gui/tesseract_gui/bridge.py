"""bridge.py — ctypes wrapper around tesseract_bridge.dll.

Provides a small Pythonic API (TessEngine class) so the GUI doesn't have
to deal with ctypes verbosity directly. All errors are surfaced as
BridgeError exceptions with the engine's last-error string attached.
"""

from __future__ import annotations
import ctypes
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ── Public dataclasses ─────────────────────────────────────────────────
@dataclass
class Telemetry:
    vram_usage_pct:   float
    ram_staging_pct:  float
    active_kv_tokens: int
    prefetch_pending: int


@dataclass
class CompressResult:
    ratio:    float
    entries:  list            # raw JSON list (dicts)


class BridgeError(RuntimeError):
    pass


# ── TessEngine wrapper ─────────────────────────────────────────────────
class TessEngine:
    """Owns the ctypes handle; releases it on close()."""

    DEFAULT_DLL = r"C:\Users\twist\workspace\project_tesseract\build\tesseract_bridge.dll"

    def __init__(self, dll_path: Optional[str] = None) -> None:
        path = dll_path or self.DEFAULT_DLL
        if not Path(path).exists():
            raise BridgeError(f"bridge DLL not found at {path}")
        self._lib = ctypes.cdll.LoadLibrary(path)
        self._bind()
        handle = self._lib.tess_create()
        if not handle:
            raise BridgeError(self._last_error_str(None))
        self._h = handle

    # ── ctypes signatures ──────────────────────────────────────────────
    def _bind(self) -> None:
        lib = self._lib
        lib.tess_create.restype  = ctypes.c_void_p
        lib.tess_destroy.argtypes = [ctypes.c_void_p]
        lib.tess_init_vram.argtypes = [ctypes.c_void_p,
                                       ctypes.c_uint64, ctypes.c_uint64]
        lib.tess_init_vram.restype  = ctypes.c_int
        lib.tess_compress.argtypes = [ctypes.c_void_p,
                                      ctypes.c_char_p, ctypes.c_int,
                                      ctypes.c_char_p, ctypes.c_int]
        lib.tess_compress.restype  = ctypes.c_int
        lib.tess_decompress.argtypes = [ctypes.c_void_p,
                                        ctypes.c_char_p, ctypes.c_int,
                                        ctypes.c_char_p, ctypes.c_int]
        lib.tess_decompress.restype  = ctypes.c_int
        lib.tess_push_layer.argtypes = [ctypes.c_void_p,
                                        ctypes.c_uint32, ctypes.c_uint64]
        lib.tess_push_layer.restype  = ctypes.c_int
        lib.tess_vram_usage_pct.argtypes = [ctypes.c_void_p]
        lib.tess_vram_usage_pct.restype  = ctypes.c_float
        lib.tess_vram_used.argtypes = [ctypes.c_void_p]
        lib.tess_vram_used.restype  = ctypes.c_uint64
        lib.tess_vram_budget.argtypes = [ctypes.c_void_p]
        lib.tess_vram_budget.restype  = ctypes.c_uint64
        lib.tess_ram_staging_used.argtypes = [ctypes.c_void_p]
        lib.tess_ram_staging_used.restype  = ctypes.c_uint64
        lib.tess_ram_staging_limit.argtypes = [ctypes.c_void_p]
        lib.tess_ram_staging_limit.restype  = ctypes.c_uint64
        lib.tess_observe_layer.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        lib.tess_predict_next.argtypes = [ctypes.c_void_p,
                                          ctypes.POINTER(ctypes.c_uint32),
                                          ctypes.c_int,
                                          ctypes.POINTER(ctypes.c_float)]
        lib.tess_predict_next.restype  = ctypes.c_int
        lib.tess_total_observations.argtypes = [ctypes.c_void_p]
        lib.tess_total_observations.restype  = ctypes.c_uint64
        lib.tess_io_write.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                      ctypes.c_char_p, ctypes.c_int]
        lib.tess_io_write.restype  = ctypes.c_int
        lib.tess_io_read.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                     ctypes.c_char_p, ctypes.c_int]
        lib.tess_io_read.restype  = ctypes.c_int
        lib.tess_checkpoint_save.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.tess_checkpoint_save.restype  = ctypes.c_int
        lib.tess_checkpoint_load.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.tess_checkpoint_load.restype  = ctypes.c_int
        lib.tess_index_build.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.tess_index_build.restype  = ctypes.c_int
        lib.tess_index_shards_in_vram.argtypes = [ctypes.c_void_p]
        lib.tess_index_shards_in_vram.restype  = ctypes.c_int
        # V1.7.1: 60GB VRAM illusion
        lib.tess_init_vram_v2.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64,
        ]
        lib.tess_init_vram_v2.restype  = ctypes.c_int
        lib.tess_virtual_vram_bytes.argtypes = [ctypes.c_void_p]
        lib.tess_virtual_vram_bytes.restype  = ctypes.c_uint64
        lib.tess_phys_vram_bytes.argtypes = [ctypes.c_void_p]
        lib.tess_phys_vram_bytes.restype  = ctypes.c_uint64
        lib.tess_phys_ram_bytes.argtypes = [ctypes.c_void_p]
        lib.tess_phys_ram_bytes.restype  = ctypes.c_uint64
        lib.tess_vram_illusion_ratio.argtypes = [ctypes.c_void_p]
        lib.tess_vram_illusion_ratio.restype  = ctypes.c_float
        lib.tess_version.restype  = ctypes.c_char_p
        lib.tess_last_error.argtypes = [ctypes.c_void_p]
        lib.tess_last_error.restype  = ctypes.c_char_p
        lib.tess_telemetry_get.argtypes = [ctypes.c_void_p,
                                           ctypes.c_void_p]  # struct ptr
        lib.tess_telemetry_get.restype  = None

    # ── Helpers ────────────────────────────────────────────────────────
    def _check(self, rc: int, what: str) -> int:
        if rc != 0:
            raise BridgeError(f"{what} failed (rc={rc}): {self._last_error_str()}")
        return rc

    def _last_error_str(self, h=None) -> str:
        h = h if h is not None else self._h
        try:
            return self._lib.tess_last_error(h).decode(errors="replace")
        except Exception:
            return "<unknown>"

    # ── Public API ─────────────────────────────────────────────────────
    @property
    def version(self) -> str:
        return self._lib.tess_version().decode()

    def close(self) -> None:
        if getattr(self, "_h", None):
            self._lib.tess_destroy(self._h)
            self._h = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def init_vram(self, phys_vram_bytes: int, phys_ram_bytes: int,
                   virtual_vram_bytes: int = 0) -> None:
        """Initialize VRAM. If virtual_vram_bytes is 0, defaults to 60 GB
        (the 60GB VRAM illusion — see Config::virtual_vram_bytes)."""
        rc = self._lib.tess_init_vram_v2(self._h,
                                          ctypes.c_uint64(phys_vram_bytes),
                                          ctypes.c_uint64(phys_ram_bytes),
                                          ctypes.c_uint64(virtual_vram_bytes))
        self._check(rc, "init_vram")

    def compress(self, text: str) -> CompressResult:
        encoded = text.encode("utf-8")
        out = ctypes.create_string_buffer(4 * 1024 * 1024)  # 4 MB JSON cap
        n = self._lib.tess_compress(self._h, encoded, len(encoded),
                                    out, len(out))
        self._check(1 if n <= 0 else 0, "compress")
        data = json.loads(out.value[:n].decode())
        return CompressResult(ratio=float(data["compression_ratio"]),
                              entries=data["entries"])

    def decompress(self, text: str) -> str:
        encoded = text.encode("utf-8")
        out = ctypes.create_string_buffer(4 * 1024 * 1024)
        n = self._lib.tess_decompress(self._h, encoded, len(encoded),
                                      out, len(out))
        self._check(1 if n <= 0 else 0, "decompress")
        return out.value[:n].decode(errors="replace")

    def push_layer(self, layer_id: int, byte_size: int) -> int:
        return self._check(
            self._lib.tess_push_layer(self._h,
                                      ctypes.c_uint32(layer_id),
                                      ctypes.c_uint64(byte_size)),
            "push_layer")

    def vram_usage_pct(self) -> float:
        return float(self._lib.tess_vram_usage_pct(self._h))

    # ── Virtual VRAM illusion (60GB presented to the LLM) ─────────────
    def phys_vram_bytes(self) -> int:
        return int(self._lib.tess_phys_vram_bytes(self._h))
    def phys_ram_bytes(self) -> int:
        return int(self._lib.tess_phys_ram_bytes(self._h))
    def virtual_vram_bytes(self) -> int:
        return int(self._lib.tess_virtual_vram_bytes(self._h))
    def vram_illusion_ratio(self) -> float:
        return float(self._lib.tess_vram_illusion_ratio(self._h))

    def vram_used(self) -> int:
        return int(self._lib.tess_vram_used(self._h))

    def vram_budget(self) -> int:
        return int(self._lib.tess_vram_budget(self._h))

    def ram_staging_used(self) -> int:
        return int(self._lib.tess_ram_staging_used(self._h))

    def ram_staging_limit(self) -> int:
        return int(self._lib.tess_ram_staging_limit(self._h))

    def observe_layer(self, layer_id: int) -> None:
        self._lib.tess_observe_layer(self._h, ctypes.c_uint32(layer_id))

    def predict_next(self, n: int = 4) -> tuple[list[int], float]:
        ids = (ctypes.c_uint32 * n)()
        conf = ctypes.c_float()
        count = self._lib.tess_predict_next(self._h, ids, n, ctypes.byref(conf))
        return [int(ids[i]) for i in range(count)], float(conf.value)

    def total_observations(self) -> int:
        return int(self._lib.tess_total_observations(self._h))

    def io_write(self, rel_path: str, data: bytes) -> int:
        return self._check(
            self._lib.tess_io_write(self._h, rel_path.encode(),
                                    data, len(data)),
            "io_write")

    def io_read(self, rel_path: str, cap: int = 1 << 20) -> bytes:
        buf = ctypes.create_string_buffer(cap)
        n = self._lib.tess_io_read(self._h, rel_path.encode(),
                                   buf, cap)
        self._check(1 if n <= 0 else 0, "io_read")
        return buf.raw[:n]

    def checkpoint_save(self, path: str) -> None:
        self._check(self._lib.tess_checkpoint_save(self._h, path.encode()),
                    "checkpoint_save")

    def checkpoint_load(self, path: str) -> None:
        self._check(self._lib.tess_checkpoint_load(self._h, path.encode()),
                    "checkpoint_load")

    def index_build(self, directory: str) -> None:
        self._check(self._lib.tess_index_build(self._h, directory.encode()),
                    "index_build")

    def shards_in_vram(self) -> int:
        return int(self._lib.tess_index_shards_in_vram(self._h))

    def telemetry(self) -> Telemetry:
        # Match the C struct layout: float, float, uint64, uint32 — padded to 24 bytes
        class _CTelemetry(ctypes.Structure):
            _fields_ = [
                ("vram_usage_pct",   ctypes.c_float),
                ("ram_staging_pct",  ctypes.c_float),
                ("active_kv_tokens", ctypes.c_uint64),
                ("prefetch_pending", ctypes.c_uint32),
                ("_pad",             ctypes.c_uint32),
            ]
        out = _CTelemetry()
        self._lib.tess_telemetry_get(self._h, ctypes.byref(out))
        return Telemetry(out.vram_usage_pct, out.ram_staging_pct,
                         out.active_kv_tokens, out.prefetch_pending)

    def last_error(self) -> str:
        return self._last_error_str()
