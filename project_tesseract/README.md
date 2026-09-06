# Project Tesseract: 4D Hyperspherical Tensor Cache & Async Staging

## Architectural Overview

Project Tesseract implements a high-throughput, low-latency 4D hyperspherical tensor caching system designed for VRAM prefetching and NVMe async staging.

### Key Components

1. **4D Hyperspherical Cache Trigger (`cache_trigger.py`)**
   - **Distance Formula**: 4D Euclidean distance $d(P, Q) = \sqrt{\Delta x^2 + \Delta y^2 + \Delta z^2 + \Delta w^2}$
   - **Load Radius (`load_in_radius`)**: $0.75$ — Prefetches tensor layers when distance from active token vector is $\le 0.75$.
   - **Hysteresis Retention (`stay_in_buffer`)**: $0.20$ — Retains active VRAM layers up to distance threshold $0.75 + 0.20 = 0.95$, eliminating VRAM thrashing.
   - **State Manager (`HypersphericalCacheManager`)**: Evaluates token coordinates against registered tensor manifolds and outputs `LOAD`, `RETAIN`, or `EVICT` directives.

2. **VRAM Ping-Pong Orchestrator (`vram_streamer.py`)**
   - Double-buffered VRAM pool management (`Pool_A` / `Pool_B`).
   - Asynchronous layer streaming with sub-15ms transfer delays.
   - Zero-overhead atomic buffer swapping to prevent OOM errors.

3. **Linguistic Token Shredder Engine (`tesseract_core.py`)**
   - Payload shredding into deterministic chunk fragments.
   - ASCII sum heuristic calculation ($V = \sqrt{\text{ASCII\_sum}} \times 1.414$).
   - Registry mapping for `ZONE_REDUX` (`0x7FBF4A90`) and `HEX_RENDER` (`0x8A4C2E1B`).

4. **Matrix Storage Daemon (`matrix_daemon.py`)**
   - Staging buffer splitting across 6 binary stripe files (`stripe_1.bin` .. `stripe_6.bin`).
   - Modulo-6 shifting parity key rotation with high-entropy PRNG decoy generation.

5. **Direct I/O NVMe Memory Core (`tesseract_memory_core.cpp`)**
   - Sector-aligned direct disk I/O (`FILE_FLAG_NO_BUFFERING` / `O_DIRECT`).
   - Pinned memory allocation with 4096-byte alignment bounds.

## Test Verification

Run unit tests via:
```bash
python test_hyperspherical.py
```
