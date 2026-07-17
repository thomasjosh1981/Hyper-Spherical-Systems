// DictionaryStore: persist and restore the SISSI phrase dictionary.
// See dictionary_store.hpp for format specification.

#include "dictionary_store.hpp"
#include "context_compressor.hpp"  // for DictEntry definition

#include <fstream>
#include <cstring>

namespace tesseract {

namespace {
    constexpr uint32_t kDictMagic   = 0x53495353u;  // 'SISS'
    constexpr uint32_t kDictVersion = 2u;
}

bool DictionaryStore::save(const std::string& path,
                           const std::vector<DictEntry>& reverse_table,
                           size_t dict_used_count) noexcept {
    try {
        // Write to a .tmp sidecar first, then rename — prevents half-written
        // files from corrupting the dictionary on a crash mid-write.
        std::string tmp_path = path + ".tmp";
        std::ofstream f(tmp_path, std::ios::binary | std::ios::trunc);
        if (!f) return false;

        // Count valid entries to write
        uint32_t count = 0;
        size_t limit = std::min(reverse_table.size(), dict_used_count + 1u);
        for (size_t i = 1; i < limit; ++i) {
            if (reverse_table[i].valid) ++count;
        }

        uint32_t magic   = kDictMagic;
        uint32_t version = kDictVersion;
        f.write(reinterpret_cast<const char*>(&magic),   sizeof(magic));
        f.write(reinterpret_cast<const char*>(&version), sizeof(version));
        f.write(reinterpret_cast<const char*>(&count),   sizeof(count));

        for (size_t i = 1; i < limit; ++i) {
            const DictEntry& e = reverse_table[i];
            if (!e.valid) continue;

            uint8_t code      = e.code;
            uint8_t len       = e.len;
            uint8_t is_static = e.is_static ? 1u : 0u;
            // Store score as two uint32 halves for portability
            uint32_t score_hi = static_cast<uint32_t>(e.score >> 32);
            uint32_t score_lo = static_cast<uint32_t>(e.score & 0xFFFFFFFFu);

            f.write(reinterpret_cast<const char*>(&code),      sizeof(code));
            f.write(reinterpret_cast<const char*>(&len),       sizeof(len));
            f.write(reinterpret_cast<const char*>(&is_static), sizeof(is_static));
            f.write(reinterpret_cast<const char*>(&score_hi),  sizeof(score_hi));
            f.write(reinterpret_cast<const char*>(&score_lo),  sizeof(score_lo));
            f.write(e.phrase_buf, len);
        }

        f.flush();
        if (!f.good()) return false;
        f.close();

        // Atomic rename: replace old dict with new one
        // (On Windows, rename fails if dest exists — remove first)
        std::remove(path.c_str());
        return (std::rename(tmp_path.c_str(), path.c_str()) == 0);

    } catch (...) {
        return false;
    }
}

bool DictionaryStore::load(const std::string& path,
                           std::vector<LoadedEntry>& out) noexcept {
    try {
        std::ifstream f(path, std::ios::binary);
        if (!f) return false;

        uint32_t magic = 0, version = 0, count = 0;
        f.read(reinterpret_cast<char*>(&magic),   sizeof(magic));
        f.read(reinterpret_cast<char*>(&version), sizeof(version));
        f.read(reinterpret_cast<char*>(&count),   sizeof(count));

        if (!f.good())                 return false;
        if (magic   != kDictMagic)    return false;
        if (version != kDictVersion)  return false;

        // Sanity cap: dictionary can never have more than 255 entries
        if (count > 255u) return false;

        out.reserve(count);
        for (uint32_t i = 0; i < count; ++i) {
            LoadedEntry e{};
            uint32_t score_hi = 0, score_lo = 0;

            f.read(reinterpret_cast<char*>(&e.code),      sizeof(e.code));
            f.read(reinterpret_cast<char*>(&e.len),       sizeof(e.len));

            uint8_t is_static_byte = 0;
            f.read(reinterpret_cast<char*>(&is_static_byte), sizeof(is_static_byte));
            e.is_static = (is_static_byte != 0);

            f.read(reinterpret_cast<char*>(&score_hi), sizeof(score_hi));
            f.read(reinterpret_cast<char*>(&score_lo), sizeof(score_lo));
            e.score = (static_cast<uint64_t>(score_hi) << 32) | score_lo;

            if (!f.good()) return false;

            // Validate phrase length before reading
            if (e.len == 0 || e.len > 63) return false;

            f.read(e.phrase_buf, e.len);
            if (!f.good()) return false;

            // Null-terminate for safety
            e.phrase_buf[e.len] = '\0';

            out.push_back(e);
        }

        return true;
    } catch (...) {
        return false;
    }
}

} // namespace tesseract
