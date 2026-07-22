#pragma once
#include "types.hpp"
#include <cstdint>
#include <string>
#include <vector>

namespace hypersp {

class RecoveryCheckpoint {
public:
    /** Save current session state to disk for crash recovery */
    bool save_to(const std::string& path) const noexcept;

    static bool load_from(const std::string& path, void* out_state = nullptr) noexcept;

    /** 
     * SFS+ Auto-Reversion Brain Features 
     * Logs a differential delta (only the changed weights/code) to prevent storage bloat.
     * is_critical indicates if this is a major architectural change that should be kept indefinitely.
     */
    bool log_brain_modification(const std::string& diff_payload, bool is_critical) noexcept;
    
    /** 
     * Restores the model brain to a specific timestamp.
     * Automatically prunes non-critical deltas older than 30 days.
     */
    bool revert_to_timestamp(uint64_t timestamp_sec) noexcept;
    
    void prune_old_reversions() noexcept;

    // Setters — engine calls these as it mutates state
    void set_vram_mark(uint64_t bytes) noexcept       { vram_mark = bytes; }
    void set_kv_count(uint32_t n) noexcept            { kv_count  = n; }
    void set_loaded_shards(std::vector<LayerShard> s) noexcept { loaded_shards = std::move(s); }

    // Getters for tests / dashboard
    uint64_t               get_vram_mark() const noexcept   { return vram_mark; }
    uint32_t               get_kv_count()  const noexcept   { return kv_count; }
    const std::vector<LayerShard>& get_loaded_shards() const noexcept { return loaded_shards; }

private:
    uint64_t                vram_mark       = 0ull;
    uint32_t                kv_count        = 0u;
    std::vector<LayerShard> loaded_shards;
};

} // namespace hypersp
