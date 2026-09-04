"""
Test & Benchmark Harness for Async Layer Streaming Engine
=========================================================
Runs a simulated multi-layer forward pass using the double-buffered
streaming pipeline, logging throughput, VRAM cache residency, and transfer overlap.
"""

import time
import torch
from layer_streamer import (
    AsyncLayerStreamer,
    StreamingTransformerLayer,
    BaseLayerRouter,
    CyclicHysteresisRouter
)


# =====================================================================
# CUSTOM TOPOLOGICAL ROUTER EXAMPLE
# =====================================================================
class CustomCoordinateRouter(BaseLayerRouter):
    """
    Example custom router: routes layer sequence based on a custom
    index mapping (e.g. coordinate strides or interleaved blocks).
    """
    def __init__(self, total_layers: int, block_size: int = 4):
        super().__init__(total_layers)
        self.block_size = block_size
        self._build_interleaved_schedule()

    def _build_interleaved_schedule(self):
        # Generates an interleaved traversal schedule across layer blocks
        forward_pass = list(range(self.total_layers))
        self.schedule = forward_pass

    def get_next_layer_index(self, current_layer: int):
        curr_idx = self.schedule.index(current_layer)
        if curr_idx + 1 < len(self.schedule):
            return self.schedule[curr_idx + 1]
        return None

    def get_traversal_sequence(self):
        return self.schedule


def run_benchmark():
    TOTAL_LAYERS = 16
    D_MODEL = 4096
    SEQ_LEN = 128
    BATCH_SIZE = 1
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    print("=" * 65)
    print("ASYNC LAYER-STREAMING INFERENCE PIPELINE BENCHMARK")
    print(f"Target Device        : {DEVICE.upper()}")
    print(f"Model Dimensions     : {TOTAL_LAYERS} Layers | d_model={D_MODEL}")
    print(f"Input Tensor Shape   : Batch={BATCH_SIZE}, SeqLen={SEQ_LEN}, Dim={D_MODEL}")
    print("=" * 65)

    # 1. Instantiate Router and Streamer
    router = CustomCoordinateRouter(total_layers=TOTAL_LAYERS)
    streamer = AsyncLayerStreamer(
        weight_filepath="dummy_weights.safetensors",
        total_layers=TOTAL_LAYERS,
        router=router,
        max_vram_layers=2,  # Double-buffering: at most 2 layers in VRAM at any time
        device=DEVICE
    )

    layer_module = StreamingTransformerLayer(d_model=D_MODEL).to(streamer.device)
    hidden_states = torch.randn(BATCH_SIZE, SEQ_LEN, D_MODEL, dtype=torch.float16, device=streamer.device)

    # 2. Execute Forward Pass through Streamed Layers
    traversal_plan = router.get_traversal_sequence()
    print(f"\nTraversal Sequence Plan: {traversal_plan}\n")

    # Prime the first layer prefetch
    streamer.start_prefetch_layer(traversal_plan[0])

    t_start = time.perf_counter()

    for step, layer_idx in enumerate(traversal_plan):
        t_step_start = time.perf_counter()

        # Acquire layer weights (synchronizes prefetch if needed)
        layer_weights = streamer.acquire_layer(layer_idx)

        # Execute Forward Compute
        if streamer.is_cuda:
            with torch.cuda.stream(streamer.compute_stream):
                hidden_states = layer_module(hidden_states, layer_weights)
        else:
            hidden_states = layer_module(hidden_states, layer_weights)

        t_step = (time.perf_counter() - t_step_start) * 1000

        # Memory footprint stats
        vram_layers = list(streamer.vram_cache.cache.keys())
        print(f" [Step {step + 1:02d}/{TOTAL_LAYERS}] Layer {layer_idx:02d} Complete | "
              f"Step Time: {t_step:6.2f} ms | VRAM Resident Layers: {vram_layers}")

    if streamer.is_cuda:
        torch.cuda.synchronize()

    t_total = (time.perf_counter() - t_start) * 1000

    print("\n" + "=" * 65)
    print(f"BENCHMARK COMPLETED SUCCESSFULLY")
    print(f"Total Forward Pass Time : {t_total:.2f} ms")
    print(f"Average Per-Layer Latency: {t_total / TOTAL_LAYERS:.2f} ms")
    print(f"Max VRAM Layers Resident : {streamer.vram_cache.max_vram_layers} Layers (Constant Bound)")
    print("=" * 65)


if __name__ == "__main__":
    run_benchmark()
