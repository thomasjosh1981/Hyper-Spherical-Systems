# 🚀 Layer Streamer: Hyperspherical GGUF Tensor Spooler

Runs oversized LLM models (32B, 70B) on standard CPUs with zero CUDA requirement:
1. Direct NVMe mmap streaming.
2. 2-Layer Hysteresis Ring Buffer (450 MB active RAM footprint).
3. Multi-threaded AVX2 CPU SIMD execution.

## Quick Demo
```bash
python cpu_spooler.py
```
