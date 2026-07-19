#pragma once
// DictionaryStore: persistent serialization/deserialization of the SISSI
// phrase dictionary to a binary .sissi_dict file.
//
// Binary format:
//   magic   : uint32 = 0x53495353  ('SISS')
//   version : uint32 = 2
//   count   : uint32 - number of entries
//   for each entry:
//     code       : uint8
//     len        : uint8
//     is_static  : uint8  (0=dynamic, 1=static)
//     score_hi   : uint32 (high 32 bits of score)
//     score_lo   : uint32 (low 32 bits of score)
//     phrase_buf : len bytes (NOT null-terminated)
//
// Notes:
//   - Static entries (is_static=1, code 1-149) are ALWAYS restored on load.
//   - Dynamic entries (is_static=0, code 150-254) are merged; existing slots
//     are not overwritten and low-score entries can be recycled at runtime.
//   - Corrupt or version-mismatched files return false without touching live state.

#include "context_compressor.hpp"
#include <string>
#include <vector>
#include <cstdint>

namespace hypersp {

class DictionaryStore {
public:
    // Persist the current dictionary to disk.
    // Uses atomic write-then-rename to prevent corruption on crash.
    static bool save(const std::string& path,
                     const std::vector<DictEntry>& reverse_table,
                     size_t dict_used_count) noexcept;

    // Entry as loaded from disk (before merging into a live DictEntry table)
    struct LoadedEntry {
        uint8_t  code      = 0;
        uint8_t  len       = 0;
        bool     is_static = false;
        uint64_t score     = 0;
        char     phrase_buf[64]{};
    };

    // Load dictionary from disk into 'out'.
    // Returns false (safe) if file is missing, corrupt, or version mismatch.
    static bool load(const std::string& path,
                     std::vector<LoadedEntry>& out) noexcept;
};

} // namespace hypersp
