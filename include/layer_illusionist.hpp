// layer_illusionist.hpp
//
// "Virtual VRAM" illusion: the LLM always sees its layers at GPU pointers,
// even when the physical bytes live in DDR4 or on an NVMe drive. By the time
// llama.cpp asks for layer N, our prefetcher has DMA'd it back into real VRAM.
//
// Architecture:
//
//   push_layer(s)                  → alloc GPU staging + memcpy from host
//                                    → register GPU pointer with llama
//   request_layer_ptr(s)           → returns GPU pointer (always)
//                                    → if s is in RAM/NVMe (not in VRAM hot set),
//                                      schedules async DMA from RAM/NVMe → VRAM
//                                    → returns current GPU pointer (may be a
//                                      "stale" slot if DMA not done yet; llama
//                                      treats it as ready anyway because we
//                                      complete the DMA before llama's next call)
//   evict_to_ram(s)                → copy from VRAM → RAM staging; free VRAM slot
//   evict_to_nvme(s)               → copy from RAM → NVMe; free RAM staging
//   prefetch_predict_next()        → call PatternPredictor, prefetch predicted
//                                    layers back to VRAM (best effort, async)
//
// The "illusion" is that the LLM always gets a GPU pointer that looks valid.
// Under the hood we may have triggered a DMA that's still in flight; as long
// as we complete all DMAs before llama.cpp's next call (which is single-threaded
// in decode), the LLM never sees stale data.
//
// Per-layer hot-set size budget = vram_max_ratio * physical VRAM (default 90%
// of 12GB = ~10.8GB). The "breathing" threshold (vram_saturation_target = 50%)
// decides when we proactively evict to RAM to keep headroom for spikes.

#pragma once
#include "config.hpp"
#include "types.hpp"
#include "memory_manager.hpp"
#include "predictive_prefetcher.hpp"

#include <cstdint>
#include <vector>
#include <unordered_map>
#include <mutex>
#include <atomic>

// The engine's Config / MemoryManager / PatternPredictor live in `namespace
// tesseract` (lowercase, per config.hpp). LayerIllusionist lives in `namespace
// Tesseract` (uppercase). Add an alias so unqualified names resolve.
namespace Tesseract {
    using tesseract::Config;
    using tesseract::MemoryManager;
    using tesseract::PatternPredictor;
    using tesseract::MemoryTier;
    using tesseract::LayerShard;
}

namespace Tesseract {

class LayerIllusionist {
public:
    enum class PhysicalTier : uint8_t {
        VRAM = 0,   // physically in GPU memory right now
        RAM  = 1,   // copy exists in system RAM staging buffer
        NVME = 2,   // only on disk; would need disk→RAM→VRAM to serve
    };

    struct LayerHandle {
        uint32_t layer_id      = 0;
        size_t   byte_size     = 0;
        // The "VRAM illusion" pointer — always non-null once allocated.
        // The LLM uses this pointer; we ensure it points at real VRAM
        // (or a DMA-in-flight VRAM slot) before llama.cpp reads it.
        uint8_t* vram_illusion_ptr = nullptr;
        PhysicalTier tier = PhysicalTier::NVME;
        uint64_t last_used_ns     = 0;
    };

    LayerIllusionist(const Config& cfg,
                       MemoryManager& mem,
                       PatternPredictor& predictor);
    ~LayerIllusionist();

    // Register a new layer. Allocates a VRAM staging slot (physically in
    // GPU memory when CUDA is present; falls back to host memory in stub
    // mode). Returns a handle whose `vram_illusion_ptr` is always valid.
    LayerHandle* register_layer(uint32_t layer_id, size_t byte_size,
                                  const uint8_t* initial_data);

    // Free everything for a layer.
    void release_layer(uint32_t layer_id);

    // The "illusion" entry point. Returns a GPU pointer the LLM can use.
    // If the layer is currently in RAM/NVMe, this function:
    //   1. Allocates a VRAM slot (evicting oldest if necessary)
    //   2. DMA's the bytes back from RAM/NVMe → VRAM
    //   3. Updates the layer's tier to VRAM
    // The DMA is synchronous for now (we don't have a CUDA stream pool
    // in this scaffold). Real implementation would use cudaMemcpyAsync
    // and signal llama after the copy completes via an event poll.
    uint8_t* request_layer_ptr(uint32_t layer_id);

    // Manual eviction (called by the breathing logic).
    void evict_to_ram(uint32_t layer_id);
    void evict_to_nvme(uint32_t layer_id);

    // Eagerly prefetch the predicted-next layers into VRAM. Called when
    // the engine sees vram_saturation_target approaching.
    void prefetch_predicted_next();

    // Diagnostics for the GUI dashboard
    struct Stats {
        size_t total_layers   = 0;
        size_t in_vram        = 0;
        size_t in_ram         = 0;
        size_t in_nvme        = 0;
        size_t prefetches     = 0;
        size_t evictions      = 0;
        size_t bytes_vram     = 0;
        size_t bytes_ram      = 0;
        size_t bytes_nvme     = 0;
        uint64_t total_dmas   = 0;
    };
    Stats stats() const;

private:
    const Config& cfg_;
    MemoryManager& mem_;
    PatternPredictor& predictor_;

    mutable std::mutex mtx_;
    std::unordered_map<uint32_t, LayerHandle> layers_;

    // Storage backends. vram_slots_ holds the GPU memory for live layers.
    // When CUDA is not linked, these are actually host-mapped allocations
    // (cuMemAlloc falls back to cudaMallocManaged / cudaMallocHost in stub).
    std::unordered_map<uint32_t, std::vector<uint8_t>> vram_slots_;
    std::unordered_map<uint32_t, std::vector<uint8_t>> ram_slots_;
    std::unordered_map<uint32_t, std::vector<uint8_t>> nvme_slots_;

    // LRU tracking for VRAM eviction policy
    std::atomic<uint64_t> access_clock_{0};

    Stats stats_;
    mutable std::mutex stats_mtx_;

    // Helpers
    void touch(LayerHandle& h);
    size_t vram_used_bytes() const;
    size_t vram_budget_bytes() const;
    uint64_t now_ns() const noexcept;
    void evict_lru_to_ram();
};

} // namespace Tesseract
