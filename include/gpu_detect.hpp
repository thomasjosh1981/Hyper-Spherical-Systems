// gpu_detect.hpp — physical VRAM detection across Windows / Linux.
//
// Windows: uses DXGI to enumerate adapters and sum DedicatedVideoMemory.
//          Works on any GPU vendor (NVIDIA / AMD / Intel). No NVIDIA tooling
//          required. Reports the *primary* adapter's VRAM.
//
// Linux:   reads /sys/class/drm/card*/device/mem_info_vram_total (AMD) or
//          queries NVML for NVIDIA. Falls back to 0 if nothing is readable.
//
// macOS:   not supported in this scaffold (Tesseract targets Windows / Linux).

#pragma once
#include <cstdint>
#include <vector>
#include <string>

namespace Tesseract::GPU {

struct AdapterInfo {
    std::string description;     // "AMD Radeon RX 6700 XT", "NVIDIA GeForce RTX 3060", ...
    uint64_t    vram_bytes = 0;   // physical VRAM reported by the adapter
    uint32_t    vendor_id  = 0;   // PCI vendor id; 0x1002=AMD, 0x10DE=NVIDIA, 0x8086=Intel
    bool        is_primary = false;
};

struct DetectResult {
    uint64_t                  total_vram_bytes = 0;
    std::vector<AdapterInfo>  adapters;        // every adapter the OS reports
    bool                      ok              = false;   // true if at least one adapter reported VRAM
    std::string                error;                   // empty if ok
};

// Sum every adapter's DedicatedVideoMemory. If only one adapter has
// dedicated VRAM (typical for desktops with iGPU + dGPU), returns that
// adapter's VRAM. The caller can call enumerate_adapters() to inspect.
DetectResult detect_total_vram();

// Enumerate every adapter (for diagnostics + GUI display).
DetectResult enumerate_adapters();

}  // namespace Tesseract::GPU
