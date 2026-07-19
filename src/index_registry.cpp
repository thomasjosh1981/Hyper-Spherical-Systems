// IndexRegistry: builds layer index by scanning weight files on NVMe.
#include "index_registry.hpp"
#include <filesystem>

namespace fs = std::filesystem;

namespace hypersp {

void IndexRegistry::build_index(const std::string& nvme_base) noexcept {
    shards_.clear();
    try {
        for(auto& entry : fs::directory_iterator(nvme_base)) {
            if(entry.is_regular_file() && entry.path().extension() == ".gguf") {
                LayerShard shard;
                shard.layer_id     = 0;
                shard.tensor_name   = entry.path().filename().string();
                shard.byte_size    = static_cast<size_t>(entry.file_size());
                shard.tier         = MemoryTier::NVME;
                shards_.push_back(std::move(shard));
            }
        }
    } catch(const fs::filesystem_error&) {
        (void)0;  // suppress — directory might not exist yet, that's fine
    }
}

bool IndexRegistry::get_shard(uint32_t id, LayerShard& out) const noexcept {
    for(auto& s : shards_) {
        if(s.layer_id == id) { out = s; return true; }
    }
    return false;
}

std::vector<LayerShard> IndexRegistry::get_layers_in_vram() const noexcept {
    std::vector<LayerShard> result;
    for(auto& s : shards_) { if(s.tier == MemoryTier::VRAM) result.push_back(s); }
    return result;
}

} // namespace hypersp
