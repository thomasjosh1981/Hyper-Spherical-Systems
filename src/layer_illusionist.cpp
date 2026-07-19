// layer_illusionist.cpp
#include "layer_illusionist.hpp"

#include <algorithm>
#include <chrono>
#include <cstring>

// Unqualified Config/MemoryManager/PatternPredictor need to resolve to the
// tesseract (lowercase) namespace versions — see header.
namespace Tesseract {
    using hypersp::Config;
    using hypersp::MemoryManager;
    using hypersp::PatternPredictor;
}

namespace Tesseract {

LayerIllusionist::LayerIllusionist(const Config& cfg,
                                    MemoryManager& mem,
                                    PatternPredictor& predictor)
    : cfg_(cfg), mem_(mem), predictor_(predictor) {}

LayerIllusionist::~LayerIllusionist() {
    std::lock_guard<std::mutex> lk(mtx_);
    vram_slots_.clear();
    ram_slots_.clear();
    nvme_slots_.clear();
    layers_.clear();
}

uint64_t LayerIllusionist::now_ns() const noexcept {
    return static_cast<uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count());
}

void LayerIllusionist::touch(LayerHandle& h) {
    h.last_used_ns = now_ns();
    access_clock_.fetch_add(1, std::memory_order_relaxed);
}

size_t LayerIllusionist::vram_used_bytes() const {
    size_t sum = 0;
    for (const auto& [_, v] : vram_slots_) sum += v.size();
    return sum;
}

size_t LayerIllusionist::vram_budget_bytes() const {
    return static_cast<size_t>(
        static_cast<double>(cfg_.phys_vram_bytes) * cfg_.vram_max_ratio);
}

LayerIllusionist::LayerHandle*
LayerIllusionist::register_layer(uint32_t layer_id, size_t byte_size,
                                  const uint8_t* initial_data) {
    std::lock_guard<std::mutex> lk(mtx_);
    auto& h = layers_[layer_id];
    h.layer_id      = layer_id;
    h.byte_size     = byte_size;
    h.tier          = PhysicalTier::VRAM;
    h.last_used_ns  = now_ns();

    // If putting this layer in VRAM would exceed the budget, evict LRU first.
    while (vram_used_bytes() + byte_size > vram_budget_bytes()
           && !vram_slots_.empty()) {
        evict_lru_to_ram();
    }

    // Allocate the VRAM staging slot. In real CUDA this would be:
    //   cudaMalloc(&ptr, byte_size);
    //   cudaMemcpy(ptr, initial_data, byte_size, cudaMemcpyHostToDevice);
    // For the scaffold we use a host vector (the LLM stub doesn't
    // actually touch GPU memory).
    auto& slot = vram_slots_[layer_id];
    slot.assign(byte_size, 0);
    if (initial_data && byte_size > 0) {
        std::memcpy(slot.data(), initial_data, byte_size);
    }
    h.vram_illusion_ptr = slot.data();

    {
        std::lock_guard<std::mutex> sl(stats_mtx_);
        stats_.total_layers++;
        stats_.in_vram++;
        stats_.bytes_vram += byte_size;
    }
    return &h;
}

void LayerIllusionist::release_layer(uint32_t layer_id) {
    std::lock_guard<std::mutex> lk(mtx_);
    auto it = layers_.find(layer_id);
    if (it == layers_.end()) return;
    size_t bytes = it->second.byte_size;
    PhysicalTier tier = it->second.tier;
    layers_.erase(it);
    vram_slots_.erase(layer_id);
    ram_slots_.erase(layer_id);
    nvme_slots_.erase(layer_id);

    std::lock_guard<std::mutex> sl(stats_mtx_);
    stats_.total_layers--;
    if (tier == PhysicalTier::VRAM) { stats_.in_vram--; stats_.bytes_vram -= bytes; }
    else if (tier == PhysicalTier::RAM) { stats_.in_ram--; stats_.bytes_ram -= bytes; }
    else { stats_.in_nvme--; stats_.bytes_nvme -= bytes; }
}

uint8_t* LayerIllusionist::request_layer_ptr(uint32_t layer_id) {
    std::lock_guard<std::mutex> lk(mtx_);
    auto it = layers_.find(layer_id);
    if (it == layers_.end()) return nullptr;
    LayerHandle& h = it->second;
    touch(h);

    // If the layer is currently in RAM or NVMe, bring it back to VRAM.
    if (h.tier != PhysicalTier::VRAM) {
        PhysicalTier old_tier = h.tier;
        size_t bytes = h.byte_size;

        // Make room in VRAM first
        while (vram_used_bytes() + bytes > vram_budget_bytes()
               && !vram_slots_.empty()) {
            evict_lru_to_ram();
        }

        // Allocate VRAM slot and DMA in (synchronous in this scaffold).
        auto& slot = vram_slots_[layer_id];
        slot.assign(bytes, 0);
        if (old_tier == PhysicalTier::RAM) {
            auto& ram = ram_slots_[layer_id];
            if (ram.size() == bytes) std::memcpy(slot.data(), ram.data(), bytes);
            ram_slots_.erase(layer_id);
        } else {
            // From NVMe — would normally do disk→RAM→VRAM. Here we zero-fill.
            // A real impl would call NVMeIO::read_block first.
            auto& nvme = nvme_slots_[layer_id];
            if (nvme.size() == bytes) std::memcpy(slot.data(), nvme.data(), bytes);
            nvme_slots_.erase(layer_id);
        }
        h.vram_illusion_ptr = slot.data();
        h.tier = PhysicalTier::VRAM;

        std::lock_guard<std::mutex> sl(stats_mtx_);
        stats_.total_dmas++;
        if (old_tier == PhysicalTier::RAM) { stats_.in_ram--; stats_.bytes_ram -= bytes; }
        else { stats_.in_nvme--; stats_.bytes_nvme -= bytes; }
        stats_.in_vram++; stats_.bytes_vram += bytes;
    }
    return h.vram_illusion_ptr;
}

void LayerIllusionist::evict_to_ram(uint32_t layer_id) {
    std::lock_guard<std::mutex> lk(mtx_);
    auto it = layers_.find(layer_id);
    if (it == layers_.end() || it->second.tier != PhysicalTier::VRAM) return;
    LayerHandle& h = it->second;
    size_t bytes = h.byte_size;

    // Copy VRAM → RAM staging (synchronous memcpy).
    auto& ram = ram_slots_[layer_id];
    ram.assign(bytes, 0);
    auto& vram = vram_slots_[layer_id];
    if (vram.size() == bytes) std::memcpy(ram.data(), vram.data(), bytes);

    // Free VRAM slot
    vram_slots_.erase(layer_id);
    h.vram_illusion_ptr = nullptr;
    h.tier = PhysicalTier::RAM;

    std::lock_guard<std::mutex> sl(stats_mtx_);
    stats_.in_vram--; stats_.bytes_vram -= bytes;
    stats_.in_ram++;  stats_.bytes_ram  += bytes;
    stats_.evictions++;
}

void LayerIllusionist::evict_to_nvme(uint32_t layer_id) {
    std::lock_guard<std::mutex> lk(mtx_);
    auto it = layers_.find(layer_id);
    if (it == layers_.end()) return;
    LayerHandle& h = it->second;
    size_t bytes = h.byte_size;

    auto& nvme = nvme_slots_[layer_id];
    nvme.assign(bytes, 0);
    if (h.tier == PhysicalTier::VRAM) {
        auto& vram = vram_slots_[layer_id];
        if (vram.size() == bytes) std::memcpy(nvme.data(), vram.data(), bytes);
        vram_slots_.erase(layer_id);
        std::lock_guard<std::mutex> sl(stats_mtx_);
        stats_.in_vram--; stats_.bytes_vram -= bytes;
    } else if (h.tier == PhysicalTier::RAM) {
        auto& ram = ram_slots_[layer_id];
        if (ram.size() == bytes) std::memcpy(nvme.data(), ram.data(), bytes);
        ram_slots_.erase(layer_id);
        std::lock_guard<std::mutex> sl(stats_mtx_);
        stats_.in_ram--; stats_.bytes_ram -= bytes;
    } else {
        return; // already on NVMe
    }
    h.vram_illusion_ptr = nullptr;
    h.tier = PhysicalTier::NVME;

    std::lock_guard<std::mutex> sl(stats_mtx_);
    stats_.in_nvme++; stats_.bytes_nvme += bytes;
    stats_.evictions++;
}

void LayerIllusionist::evict_lru_to_ram() {
    // Pick the layer with the smallest last_used_ns and evict it.
    uint32_t victim = 0;
    uint64_t min_ns = UINT64_MAX;
    for (auto& [id, h] : layers_) {
        if (h.tier == PhysicalTier::VRAM && h.last_used_ns < min_ns) {
            min_ns = h.last_used_ns;
            victim = id;
        }
    }
    if (victim != 0) evict_to_ram(victim);
}

void LayerIllusionist::prefetch_predicted_next() {
    auto [predicted_ids, confidence] = predictor_.predict_next(4);
    if (confidence < cfg_.prefetch_confidence_min) return;

    // Collect candidates first (under mtx), then promote each outside the lock
    // to avoid re-entrant locking in request_layer_ptr.
    std::vector<uint32_t> victims;
    {
        std::lock_guard<std::mutex> lk(mtx_);
        for (uint32_t id : predicted_ids) {
            auto it = layers_.find(id);
            if (it != layers_.end() && it->second.tier != PhysicalTier::VRAM)
                victims.push_back(id);
        }
    }
    for (uint32_t id : victims) {
        (void)request_layer_ptr(id);  // each call takes its own mtx
    }

    std::lock_guard<std::mutex> sl(stats_mtx_);
    stats_.prefetches += victims.size();
}

LayerIllusionist::Stats LayerIllusionist::stats() const {
    std::lock_guard<std::mutex> sl(stats_mtx_);
    return stats_;
}

} // namespace Tesseract
