#pragma once
#include "types.hpp"
#include "config.hpp"
#include <string>
#include <vector>
#include <unordered_map>
#include <string_view>

namespace tesseract {

struct SissiConfig {
    bool discard_prepositions = false;             // Discards prepositions to minimize size
    bool keep_prepositions_with_accents = true;     // Maps kept prepositions with compact accents
    bool sissi_compression_enabled = true;
    char preface_character = '\x02';               // Atomic designator / preface byte
    size_t dynamic_profiling_threshold = 15000;    // skip dynamic n-grams if below this character size (~5,000 tokens)
    bool greedy_first = true;                      // if true: match longest phrase first; if false: match single words first
    bool compress_large_words_first = false;       // if true: prioritize large complex words first
    size_t large_word_len_threshold = 6;           // threshold above which a word is "large"
    bool recycle_symbols = true;                   // reclaim and reuse codes from low-frequency entries
};

// Shared dictionary entry — used by both ContextCompressor and DictionaryStore.
struct DictEntry {
    char    phrase_buf[64]{};
    uint8_t code      = 0;
    uint8_t len       = 0;
    bool    valid     = false;
    size_t  score     = 0;
    bool    is_static = false;
};

class ContextCompressor {
public:
    explicit ContextCompressor(const Config& cfg = {}, const SissiConfig& sissi_cfg = {}) 
        : config_(cfg), sissi_config_(sissi_cfg) {}
    ~ContextCompressor() = default;

    // Dynamically analyzes text chunks to optimize SissiConfig parameters
    void auto_tune_spin(std::string_view text, size_t max_scan_bytes = 100000);

    /**
     * compress(text) -> list of KVCachedEntry for the KV cache.
     * Integrates SISSI Khmer-reassigned 1-byte encoding and preposition handling.
     */
    std::vector<KVCachedEntry> compress(std::string_view text);

    /**
     * decompress(entries) -> the original text (lossless round-trip verification).
     */
    std::string decompress(const std::vector<KVCachedEntry>& entries) const;

    size_t         dict_entries_used()  const noexcept { return phrase_map_.size(); }
    float          compression_ratio()  const noexcept {
        if (total_out_bytes == 0.0f) return 1.0f;
        return static_cast<float>(total_in_chars) / total_out_bytes;
    }

    // Helper functions for Khmer character reassignment mapping
    static uint8_t encode_khmer_char(uint16_t unicode_khmer) noexcept;
    static uint16_t decode_khmer_char(uint8_t byte_code) noexcept;

    // ── Persistent Dictionary API ─────────────────────────────────────────
    // Save the current dictionary (static + dynamic entries) to disk.
    // Call after compress() sessions to persist any newly learned phrases.
    bool save_dictionary(const std::string& path) noexcept;

    // Load a previously saved dictionary from disk and merge it into the
    // current state. Static entries (code 1-149) are always restored.
    // Dynamic entries (code 150-254) are merged — existing entries are kept,
    // new ones are added up to the slot cap.
    // Returns true if the file was found and valid. Returns false (safe, no
    // corruption) if file is missing or corrupt — compressor continues fresh.
    bool load_dictionary(const std::string& path) noexcept;

    // Set the auto-save path: if non-empty, the compressor saves the
    // dictionary automatically at the end of every compress() call.
    void set_autosave_path(const std::string& path) { dict_path_ = path; }

    const std::vector<DictEntry>& get_reverse_table() const noexcept { return reverse_table_; }
    size_t get_dict_used_count() const noexcept { return dict_used_count_; }

private:
    uint8_t register_to_dict(std::string_view phrase, size_t score = 0, bool is_static = false);
    // Reset only dynamic slots (150-254) while keeping static entries intact.
    // Used between compress() calls to allow cross-session recovery.
    void reset_dynamic_only() noexcept;


    Config                                 config_{};
    SissiConfig                            sissi_config_{};
    std::string                            dict_path_{};
    std::unordered_map<std::string, uint8_t> phrase_map_{};
    std::vector<DictEntry>                 reverse_table_{};

public:
    struct PPVEntry {
        uint16_t word_index;
        uint8_t preposition_id;
    };
    const std::vector<PPVEntry>& get_ppv_list() const noexcept { return ppv_list_; }

private:
    std::vector<PPVEntry> ppv_list_{};
    size_t dict_used_count_       = 0;
    size_t total_in_chars         = 0;
    float  total_out_bytes        = 0.0f;
};

} // namespace tesseract

