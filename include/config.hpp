#pragma once
#include "types.hpp"
#include <cstdint>
#include <filesystem>
#include <string_view>

namespace tesseract {

struct Config {
    // Storage mounts — your actual drives
    std::filesystem::path nvme_base       = "D:\tesseract_live";
    std::filesystem::path nvme_secondary  = "C:\tesseract_cache";
    std::filesystem::path hdd_cold        = "I:\tesseract_cold";

    // VRAM/RAM limits
    double vram_max_ratio              = 0.90;   // hard cap = 90% of physical VRAM (was 0.70; user has only 12GB and wants the full GPU)
    double ram_staging_pct             = 0.50;    // up to 50% system RAM for staging
    size_t ram_total_bytes             = 32ULL * 1024 * 1024 * 1024;  // 32GB default — caller should set actual
    size_t phys_vram_bytes             = 12ULL * 1024 * 1024 * 1024;  // 12GB default — caller should set actual (user: 12GB, no discrete GPU)
    size_t virtual_vram_bytes          = 60ULL * 1024 * 1024 * 1024;  // 60GB illusion presented to the LLM (12GB real + ~48GB tiered)

    // Context compression settings
    bool    compession_enabled       = false;        // disabled per user directive — never compress
    int     min_comp_phrase_len      = 2;          // only compress phrases 2 words+
    uint32_t max_dict_entries         = 65536;      // keep dictionary small, fast lookup
    size_t  optimal_read_chunk        = 262144;     // 256KB default for NVMe (benchmark your drive)
    size_t  optimal_write_chunk       = 524288;     // 512KB default for HDD

    // Predictive prefetch settings
    int     prediction_window         = 16;          // how many layers back to watch
    float   prefetch_confidence_min   = 0.75f;       // only preload if confidence above this

    // Context window management — preserve full context until there is real VRAM overrun risk
    uint32_t max_active_tokens         = 260000;     // hard floor — never compress below this threshold
};

} // namespace tesseract
