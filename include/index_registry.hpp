#pragma once
#include "types.hpp"
#include <vector>
#include <cstdint>
#include <string>

namespace hypersp {

class IndexRegistry {
public:
    /** Build the layer index by scanning GGUF weight files on NVMe */
    void build_index(const std::string& nvme_base) noexcept;
    
    /** Lookup shard by layer ID for fast prefetching during inference. */
    bool get_shard(uint32_t id, LayerShard& out) const noexcept;

    std::vector<LayerShard> get_layers_in_vram() const noexcept;

private:
    std::vector<LayerShard> shards_;
};

} // namespace hypersp
