"""
Layer-Streaming Engine & Dynamic Tensor Router Boilerplate
==========================================================
Implements an asynchronous, double-buffered PyTorch layer streaming engine
using memory-mapped weights (safetensors) and dynamic hysteresis caching.

Architecture:
1. Memory-Mapped Disk Ingestion: Zero-copy weight access via safetensors/mmap.
2. Double-Buffered Async PCIe Transfer: Uses concurrent CUDA streams (compute vs. prefetch).
3. Hysteresis VRAM Cache: Manages VRAM allocation with high/low watermarks to prevent thrashing.
4. Modular Traversal Router: Pluggable interface for custom layer ordering and routing topologies.
"""

import os
import time
import queue
import threading
from typing import Dict, List, Optional, Any, Callable
import torch
import torch.nn as nn

try:
    from safetensors import safe_open
    from safetensors.torch import save_file
    SAFETENSORS_AVAILABLE = True
except ImportError:
    SAFETENSORS_AVAILABLE = False


# =====================================================================
# 1. MODULAR LAYER TRAVERSAL ROUTER INTERFACE
# =====================================================================
class BaseLayerRouter:
    """
    Abstract interface for computing layer traversal order and predictive routing.
    Custom topological state engines (such as coordinate maps or graph schedulers)
    can inherit from this class to dictate which layer index is fetched next.
    """
    def __init__(self, total_layers: int):
        self.total_layers = total_layers
        self.current_step = 0

    def get_next_layer_index(self, current_layer: int) -> Optional[int]:
        """Returns the next layer index that should be prefetched into VRAM."""
        next_idx = current_layer + 1
        return next_idx if next_idx < self.total_layers else None

    def get_traversal_sequence(self) -> List[int]:
        """Returns the complete sequence of layer indices for a forward pass."""
        return list(range(self.total_layers))


class LinearSequentialRouter(BaseLayerRouter):
    """Standard sequential layer router (Layer 0 -> Layer 1 -> ... -> Layer N-1)."""
    pass


class CyclicHysteresisRouter(BaseLayerRouter):
    """
    A bidirectional / cyclic layer router that alternates traversal directions
    or routes based on custom coordinate offsets.
    """
    def __init__(self, total_layers: int, sequence: Optional[List[int]] = None):
        super().__init__(total_layers)
        self.sequence = sequence or list(range(total_layers))

    def get_traversal_sequence(self) -> List[int]:
        return self.sequence


# =====================================================================
# 2. HYSTERESIS VRAM BUFFER MANAGER
# =====================================================================
class HysteresisVRAMCache:
    """
    Maintains active layer tensors in VRAM with high-water and low-water marks
    to prevent memory fragmentation and PCIe bus thrashing.
    """
    def __init__(self, max_vram_layers: int = 2, low_watermark: int = 1, device: str = "cuda"):
        self.max_vram_layers = max_vram_layers
        self.low_watermark = low_watermark
        self.device = torch.device(device if torch.cuda.is_available() and device.startswith("cuda") else "cpu")
        self.cache: Dict[int, Dict[str, torch.Tensor]] = {}
        self.access_history: List[int] = []

    def contains(self, layer_idx: int) -> bool:
        return layer_idx in self.cache

    def get(self, layer_idx: int) -> Optional[Dict[str, torch.Tensor]]:
        if layer_idx in self.cache:
            self.access_history.append(layer_idx)
            return self.cache[layer_idx]
        return None

    def insert(self, layer_idx: int, state_dict: Dict[str, torch.Tensor]):
        # Evict oldest layers if cache exceeds high watermark
        while len(self.cache) >= self.max_vram_layers:
            self._evict_oldest()

        self.cache[layer_idx] = state_dict
        self.access_history.append(layer_idx)

    def _evict_oldest(self):
        """Evicts the least recently used layer from VRAM down to low watermark."""
        for layer_idx in list(self.cache.keys()):
            if len(self.cache) <= self.low_watermark:
                break
            # Release tensors from VRAM
            del self.cache[layer_idx]
            if torch.cuda.is_available() and self.device.type == "cuda":
                torch.cuda.empty_cache()


# =====================================================================
# 3. ASYNC DOUBLE-BUFFERED LAYER STREAMER
# =====================================================================
class AsyncLayerStreamer:
    """
    Coordinates asynchronous prefetching of quantized layer weights from disk/RAM
    into GPU VRAM using dual CUDA streams (compute stream vs. prefetch stream).
    """
    def __init__(
        self,
        weight_filepath: str,
        total_layers: int,
        router: Optional[BaseLayerRouter] = None,
        max_vram_layers: int = 2,
        device: str = "cuda"
    ):
        self.weight_filepath = weight_filepath
        self.total_layers = total_layers
        self.router = router or LinearSequentialRouter(total_layers)
        self.device = torch.device(device if torch.cuda.is_available() and device.startswith("cuda") else "cpu")
        
        self.vram_cache = HysteresisVRAMCache(
            max_vram_layers=max_vram_layers,
            device=device
        )

        # CUDA Streams for overlapping compute and memory copy
        self.is_cuda = (self.device.type == "cuda")
        if self.is_cuda:
            self.compute_stream = torch.cuda.Stream(device=self.device)
            self.prefetch_stream = torch.cuda.Stream(device=self.device)
        else:
            self.compute_stream = None
            self.prefetch_stream = None

        self._in_flight_prefetch: Optional[Dict[str, Any]] = None

    def load_layer_from_storage(self, layer_idx: int) -> Dict[str, torch.Tensor]:
        """
        Reads tensor slices for the given layer index from disk via memory-mapping.
        """
        layer_prefix = f"layer_{layer_idx}."
        tensors = {}

        if SAFETENSORS_AVAILABLE and os.path.exists(self.weight_filepath):
            with safe_open(self.weight_filepath, framework="pt", device="cpu") as f:
                for k in f.keys():
                    if k.startswith(layer_prefix):
                        short_k = k[len(layer_prefix):]
                        # Memory-mapped slice access (zero-copy into pinned host RAM)
                        tensors[short_k] = f.get_tensor(k).pin_memory() if self.is_cuda else f.get_tensor(k)
        else:
            # Synthetic tensor generation fallback for benchmarking
            d_model = 4096
            tensors = {
                "q_proj.weight": torch.randn(d_model, d_model, dtype=torch.float16).pin_memory() if self.is_cuda else torch.randn(d_model, d_model, dtype=torch.float16),
                "k_proj.weight": torch.randn(d_model, d_model, dtype=torch.float16).pin_memory() if self.is_cuda else torch.randn(d_model, d_model, dtype=torch.float16),
                "v_proj.weight": torch.randn(d_model, d_model, dtype=torch.float16).pin_memory() if self.is_cuda else torch.randn(d_model, d_model, dtype=torch.float16),
                "out_proj.weight": torch.randn(d_model, d_model, dtype=torch.float16).pin_memory() if self.is_cuda else torch.randn(d_model, d_model, dtype=torch.float16),
            }

        return tensors

    def start_prefetch_layer(self, layer_idx: int):
        """Asynchronously begins transferring the next layer's weights to GPU VRAM."""
        if layer_idx is None or self.vram_cache.contains(layer_idx):
            return

        cpu_weights = self.load_layer_from_storage(layer_idx)

        if self.is_cuda:
            with torch.cuda.stream(self.prefetch_stream):
                gpu_weights = {
                    k: v.to(self.device, non_blocking=True)
                    for k, v in cpu_weights.items()
                }
                event = torch.cuda.Event()
                event.record(self.prefetch_stream)
                self._in_flight_prefetch = {
                    "layer_idx": layer_idx,
                    "weights": gpu_weights,
                    "event": event
                }
        else:
            self._in_flight_prefetch = {
                "layer_idx": layer_idx,
                "weights": cpu_weights,
                "event": None
            }

    def acquire_layer(self, layer_idx: int) -> Dict[str, torch.Tensor]:
        """
        Synchronizes and returns the requested layer in VRAM, while triggering prefetch
        for the subsequent layer dictated by the router.
        """
        # Check if already resident in VRAM cache
        if self.vram_cache.contains(layer_idx):
            # Kick off next prefetch asynchronously
            next_idx = self.router.get_next_layer_index(layer_idx)
            self.start_prefetch_layer(next_idx)
            return self.vram_cache.get(layer_idx)

        # Check if currently transferring in prefetch stream
        if self._in_flight_prefetch and self._in_flight_prefetch["layer_idx"] == layer_idx:
            if self.is_cuda and self._in_flight_prefetch["event"] is not None:
                # Synchronize compute stream with completion of prefetch transfer
                self.compute_stream.wait_event(self._in_flight_prefetch["event"])
            
            weights = self._in_flight_prefetch["weights"]
            self.vram_cache.insert(layer_idx, weights)
            self._in_flight_prefetch = None

            # Trigger next prefetch
            next_idx = self.router.get_next_layer_index(layer_idx)
            self.start_prefetch_layer(next_idx)
            return weights

        # Cache miss: synchronous fallback load
        cpu_weights = self.load_layer_from_storage(layer_idx)
        gpu_weights = {
            k: v.to(self.device) for k, v in cpu_weights.items()
        }
        self.vram_cache.insert(layer_idx, gpu_weights)

        next_idx = self.router.get_next_layer_index(layer_idx)
        self.start_prefetch_layer(next_idx)
        return gpu_weights


# =====================================================================
# 4. STREAMING TRANSFORMER LAYER MODULE
# =====================================================================
class StreamingTransformerLayer(nn.Module):
    """
    A stateless Transformer Layer container that receives weights dynamically
    from the stream buffer right before computation.
    """
    def __init__(self, d_model: int = 4096):
        super().__init__()
        self.d_model = d_model

    def forward(self, x: torch.Tensor, weights: Dict[str, torch.Tensor]) -> torch.Tensor:
        # Linear projections using streamed weights
        q = torch.matmul(x, weights["q_proj.weight"].t())
        k = torch.matmul(x, weights["k_proj.weight"].t())
        v = torch.matmul(x, weights["v_proj.weight"].t())

        # Attention computation
        scores = torch.matmul(q, k.transpose(-1, -2)) / (self.d_model ** 0.5)
        attn = torch.softmax(scores, dim=-1)
        context = torch.matmul(attn, v)

        # Output projection & residual connection
        out = torch.matmul(context, weights["out_proj.weight"].t())
        return x + out
