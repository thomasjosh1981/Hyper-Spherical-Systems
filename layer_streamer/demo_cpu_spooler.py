#!/usr/bin/env python3
"""
demo_cpu_spooler.py — Zero-CUDA CPU Layer Spooler & NVMe Streaming Benchmark
Validates running oversized GGUF models on Intel Core i7 / AMD Ryzen 9 CPUs
with only ~450MB active RAM footprint.
"""

import sys
import os

from cpu_spooler import CPUHypersphericalSpooler

def main():
    print("=" * 70)
    print(" HYPERSPHERICAL ZERO-CUDA CPU LAYER SPOOLER BENCHMARK")
    print(" Designed for: Intel Core i7 / AMD Ryzen 9 / Laptops with 0 CUDA Cores")
    print("=" * 70)

    simulated_model_path = "gemma-2-27b-it.gguf"
    spooler = CPUHypersphericalSpooler(
        gguf_path=simulated_model_path,
        total_layers=32,
        max_ram_layers=2,
        num_cpu_threads=8
    )

    init_info = spooler.initialize_spooler()
    print("\n[1] INITIALIZATION & SYSTEM PROFILE:")
    for k, v in init_info.items():
        print(f"  • {k:<26}: {v}")

    print("\n[2] RUNNING SEQUENTIAL LAYER TRAVERSAL (Double-Buffered NVMe Spooling):")
    for layer in range(5):
        res = spooler.spool_layer_forward(layer)
        print(f"  • Layer {res['layer']:02d} -> Prefetched Layer {res['next_prefetched']:02d} | Compute: {res['compute_time_ms']}ms | Active RAM Layers: {res['cached_layers_in_ram']}")

    print("    ... [Spooling remaining 27 layers off NVMe] ...")
    full_res = spooler.run_full_inference_spool(prompt_tokens=128)

    print("\n[3] INFERENCE BENCHMARK COMPLETE:")
    print(f"  • Total Layers Traversed : {full_res['total_layers_traversed']}")
    print(f"  • Peak RAM Allocation    : {full_res['ram_used_mb']} MB (Zero OOM / Low Footprint)")
    print(f"  • Total Forward Pass Time: {full_res['total_time_sec']}s")
    print(f"  • Spooler Status         : [OK] {full_res['status']}")
    print("=" * 70)

if __name__ == "__main__":
    main()
