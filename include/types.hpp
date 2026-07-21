#pragma once
#include <cstdint>
#include <cstddef>
#include <string_view>
#include <vector>
#include <filesystem>

namespace hypersp {

// Memory tiers for weight/KV cache placement
enum class MemoryTier : uint8_t { VRAM = 0, RAM = 1, NVME = 2, HDD = 3 };

// Weight layer shard from GGUF parsing
struct LayerShard {
    uint32_t layer_id       = UINT32_MAX;
    std::string_view tensor_name   {};
    size_t               byte_size  = 0;
    MemoryTier           tier       = MemoryTier::NVME;
    void*                gpu_ptr    = nullptr;
    uint8_t*             ram_ptr    = nullptr;
};

// Compressed KV cache entry (one per input token position)
struct KVCachedEntry {
    size_t  context_pos      = 0;   // position in original text
    bool    is_compressed    = false;
    uint8_t dict_code        = 0;
    size_t  original_size_bytes = 1; // how many bytes this one code replaces (compression ratio)
};

// ── Golden Candy Spinner Structures (.hscc) ────────────────────────────────

#pragma pack(push, 1)
struct CandyChunkHeader {
    uint32_t magic;         // "HSCC" (0x43435348)
    uint32_t version;       // 1 or 2
    uint32_t tensor_count;  // number of spun tensors in this chunk
    float    vram_saturation_target; // optimal breathing threshold for this block (e.g. 0.75f)
    
    // SFS (Spun-Floss Sugar) Matrix Compilation Flags
    uint8_t  is_sfs;          // 1 if compiled with virtual MOE pathways
    uint8_t  is_sfs_plus;     // 1 if compiled with explicit cross-model feature routing
    uint16_t virtual_moe_size; // Number of virtual expert pathways (e.g. 8)

    // Recursive Modification Flags
    uint32_t mutation_epoch;  // Number of times the file has recursively self-modified
    uint8_t  locked;          // 1 if the file is locked against recursive modifications
};

struct VortexCorrection {
    uint32_t target_chunk_index; // Index of the chunk to modify
    uint32_t target_coordinate;  // Index of the specific coordinate in the chunk
    float    radius_delta;       // Additive modification to the hypersphere radius
    float    phase_shift[3];     // Additive modification to the bladed angles
};

struct CandyChunkTensor {
    uint32_t name_len;
    // ... name string follows ...
    uint32_t num_elements;
    float    w_semantic_entropy; // The W dimension semantic binding (derived from entropy/depth)
    // ... followed by num_elements * HypersphereCoordinate ...
};
#pragma pack(pop)


// Return codes across the engine
enum class ErrorCode : uint8_t {
    OK            = 0,
    BAD_CONFIG    = 1,
    IO_FAIL       = 2,
    MEM_FAIL      = 3,
    VRAM_BUDGET   = 4,
    PRED_TOO_LOW  = 5
};

constexpr uint8_t DICT_CODE_INVALID = 0xFF;

} // namespace hypersp
