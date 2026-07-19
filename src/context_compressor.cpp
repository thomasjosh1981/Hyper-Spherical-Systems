// ContextCompressor: Shrinks KV cache footprint via phrase dictionary scanning/replacement.
// Implements the SISSI Khmer-reassigned 1-byte encoding and preposition management.

#include "context_compressor.hpp"
#include "dictionary_store.hpp"
#include "static_dictionary.hpp"
#include <cctype>
#include <cstring>
#include <stdexcept>
#include <algorithm>
#include <sstream>

namespace hypersp {

// === Khmer character reassignment mapping helper ===
uint8_t ContextCompressor::encode_khmer_char(uint16_t unicode_khmer) noexcept {
    if (unicode_khmer >= 0x1780 && unicode_khmer <= 0x17FF) {
        return static_cast<uint8_t>(unicode_khmer - 0x1780 + 128);
    }
    return 0;
}

uint16_t ContextCompressor::decode_khmer_char(uint8_t byte_code) noexcept {
    if (byte_code >= 128) {
        return static_cast<uint16_t>(byte_code - 128 + 0x1780);
    }
    return 0;
}

// Helper to convert UTF-8 string containing Khmer chars to a reassigned 1-byte string
static std::string utf8_to_sissi_khmer(std::string_view utf8_str) {
    std::string result;
    for (size_t i = 0; i < utf8_str.size(); ) {
        unsigned char c1 = static_cast<unsigned char>(utf8_str[i]);
        if (c1 == 0xE1 && i + 2 < utf8_str.size()) {
            unsigned char c2 = static_cast<unsigned char>(utf8_str[i + 1]);
            unsigned char c3 = static_cast<unsigned char>(utf8_str[i + 2]);
            if (c2 == 0x9E && c3 >= 0x80 && c3 <= 0xBF) {
                result += static_cast<char>(c3); // 128 to 191
                i += 3;
                continue;
            } else if (c2 == 0x9F && c3 >= 0x80 && c3 <= 0xBF) {
                result += static_cast<char>(c3 + 0x40); // 192 to 255
                i += 3;
                continue;
            }
        }
        result += utf8_str[i];
        ++i;
    }
    return result;
}

// Helper to convert reassigned 1-byte string back to UTF-8
static std::string sissi_khmer_to_utf8(std::string_view sissi_str) {
    std::string result;
    for (size_t i = 0; i < sissi_str.size(); ++i) {
        unsigned char c = static_cast<unsigned char>(sissi_str[i]);
        if (c >= 128 && c <= 191) {
            result += static_cast<char>(0xE1);
            result += static_cast<char>(0x9E);
            result += static_cast<char>(c);
        } else if (c >= 192 && c <= 255) {
            result += static_cast<char>(0xE1);
            result += static_cast<char>(0x9F);
            result += static_cast<char>(c - 0x40);
        } else {
            result += sissi_str[i];
        }
    }
    return result;
}

// List of prepositions to monitor
static const std::unordered_map<std::string_view, char> PREPOSITION_ACCENTS = {
    {"of", '¢'}, {"to", '§'}, {"for", '¶'}, {"with", '¤'},
    {"under", '↓'}, {"above", '↑'}, {"at", '@'}, {"by", '*'},
    {"from", '<'}, {"in", '['}, {"on", ']'}
};

static bool is_preposition(std::string_view word) {
    std::string lower;
    for (char c : word) lower += static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return PREPOSITION_ACCENTS.find(lower) != PREPOSITION_ACCENTS.end();
}

static char get_preposition_accent(std::string_view word) {
    std::string lower;
    for (char c : word) lower += static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    auto it = PREPOSITION_ACCENTS.find(lower);
    return it != PREPOSITION_ACCENTS.end() ? it->second : '\0';
}

static const std::vector<std::string_view> PREPOSITION_LIST = {
    "of", "to", "for", "with", "under", "above", "at", "by", "from", "in", "on"
};

static int get_preposition_id(std::string_view word) {
    std::string lower;
    for (char c : word) lower += static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    for (size_t i = 0; i < PREPOSITION_LIST.size(); ++i) {
        if (PREPOSITION_LIST[i] == lower) return static_cast<int>(i);
    }
    return -1;
}

uint8_t ContextCompressor::register_to_dict(std::string_view phrase, size_t score, bool is_static) {
    if (phrase.empty()) return DICT_CODE_INVALID;

    auto it = phrase_map_.find(std::string(phrase));
    if (it != phrase_map_.end()) return it->second;

    if (is_static) {
        if (dict_used_count_ >= 150) {
            return DICT_CODE_INVALID; // Clamp static codes to first 150 slots
        }
    } else {
        if (dict_used_count_ < 150) {
            dict_used_count_ = 150; // Shift dynamic codes to start at 150
        }
    }

    const size_t max_codes = std::min<size_t>(255, config_.max_dict_entries);

    if (dict_used_count_ >= max_codes) {
        if (!is_static && sissi_config_.recycle_symbols) {
            size_t victim_idx = 0;
            size_t lowest_score = 1000000000;
            // Recycle from the dynamic pool range (150-254)
            for (size_t i = 150; i < reverse_table_.size(); ++i) {
                if (reverse_table_[i].valid && !reverse_table_[i].is_static) {
                    if (reverse_table_[i].score < lowest_score) {
                        lowest_score = reverse_table_[i].score;
                        victim_idx = i;
                    }
                }
            }
            if (victim_idx > 0 && score > lowest_score) {
                uint8_t reclaimed_code = static_cast<uint8_t>(victim_idx);
                std::string victim_phrase(reverse_table_[victim_idx].phrase_buf, reverse_table_[victim_idx].len);
                phrase_map_.erase(victim_phrase);

                DictEntry& e = reverse_table_[reclaimed_code];
                std::memset(&e, 0, sizeof(DictEntry));
                size_t plen = std::min<size_t>(phrase.size(), sizeof(e.phrase_buf) - 1);
                std::memcpy(e.phrase_buf, phrase.data(), plen);
                e.len  = static_cast<uint8_t>(plen);
                e.code = reclaimed_code;
                e.valid = true;
                e.score = score;
                e.is_static = is_static;

                phrase_map_[std::string(phrase)] = reclaimed_code;
                return reclaimed_code;
            }
        }
        return DICT_CODE_INVALID;
    }

    uint8_t code = static_cast<uint8_t>(dict_used_count_++);
    phrase_map_[std::string(phrase)] = code;

    if (reverse_table_.size() <= code) {
        reverse_table_.resize(static_cast<size_t>(code) + 1u);
    }

    DictEntry& e = reverse_table_[code];
    std::memset(&e, 0, sizeof(DictEntry));
    size_t plen = std::min<size_t>(phrase.size(), sizeof(e.phrase_buf) - 1);
    std::memcpy(e.phrase_buf, phrase.data(), plen);
    e.len  = static_cast<uint8_t>(plen);
    e.code = code;
    e.valid = true;
    e.score = score;
    e.is_static = is_static;

    return code;
}

void ContextCompressor::auto_tune_spin(std::string_view text, size_t max_scan_bytes) {
    if (text.empty() || !sissi_config_.sissi_compression_enabled) return;
    
    // Sample a chunk
    std::string_view sample = text.substr(0, std::min<size_t>(text.size(), max_scan_bytes));
    
    // Test 1: Greedy multi-word heavy
    SissiConfig cfg_greedy = sissi_config_;
    cfg_greedy.greedy_first = true;
    cfg_greedy.compress_large_words_first = false;
    ContextCompressor comp_greedy(config_, cfg_greedy);
    comp_greedy.compress(sample);
    float ratio_greedy = comp_greedy.compression_ratio();
    
    // Test 2: Single large word heavy
    SissiConfig cfg_large = sissi_config_;
    cfg_large.greedy_first = false;
    cfg_large.compress_large_words_first = true;
    ContextCompressor comp_large(config_, cfg_large);
    comp_large.compress(sample);
    float ratio_large = comp_large.compression_ratio();
    
    // Lock in the best strategy
    if (ratio_large > ratio_greedy) {
        sissi_config_.greedy_first = false;
        sissi_config_.compress_large_words_first = true;
    } else {
        sissi_config_.greedy_first = true;
        sissi_config_.compress_large_words_first = false;
    }
}

// ── Dictionary Persistence ─────────────────────────────────────────────────

bool ContextCompressor::save_dictionary(const std::string& path) noexcept {
    return DictionaryStore::save(path, reverse_table_, dict_used_count_);
}

bool ContextCompressor::load_dictionary(const std::string& path) noexcept {
    std::vector<DictionaryStore::LoadedEntry> loaded;
    if (!DictionaryStore::load(path, loaded)) return false;

    for (const auto& le : loaded) {
        // Skip if already registered (e.g. from static init this session)
        std::string phrase(le.phrase_buf, le.len);
        if (phrase_map_.count(phrase)) continue;

        // Ensure reverse_table_ is large enough
        size_t code = static_cast<size_t>(le.code);
        if (reverse_table_.size() <= code) {
            reverse_table_.resize(code + 1u);
        }

        // Don't overwrite a valid slot (another phrase already grabbed that code)
        if (reverse_table_[code].valid) continue;

        DictEntry& e = reverse_table_[code];
        std::memset(&e, 0, sizeof(DictEntry));
        size_t plen = std::min<size_t>(le.len, sizeof(e.phrase_buf) - 1);
        std::memcpy(e.phrase_buf, le.phrase_buf, plen);
        e.len       = static_cast<uint8_t>(plen);
        e.code      = le.code;
        e.valid     = true;
        e.score     = static_cast<size_t>(le.score);
        e.is_static = le.is_static;

        phrase_map_[phrase] = le.code;

        // Update dict_used_count_ to stay consistent
        if (code >= dict_used_count_) dict_used_count_ = code + 1u;
    }
    return true;
}

void ContextCompressor::reset_dynamic_only() noexcept {
    // Erase all dynamic (code >= 150) entries from phrase_map_
    for (auto it = phrase_map_.begin(); it != phrase_map_.end(); ) {
        if (it->second >= 150u) {
            it = phrase_map_.erase(it);
        } else {
            ++it;
        }
    }
    // Invalidate reverse_table_ dynamic slots (150-254) but keep static ones
    for (size_t i = 150; i < reverse_table_.size() && i < 255u; ++i) {
        if (!reverse_table_[i].is_static) {
            reverse_table_[i] = DictEntry{};
        }
    }
    // Reset the dynamic counter back to 150
    if (dict_used_count_ > 150u) dict_used_count_ = 150u;
    ppv_list_.clear();
}

std::vector<KVCachedEntry> ContextCompressor::compress(std::string_view text) {
    total_in_chars  = text.size();
    total_out_bytes = 0.0f;

    // Only reset dynamic entries (codes 150-254) so that previously learned
    // phrases (and static entries loaded from disk) survive across calls.
    // On the very first call, phrase_map_ is empty so this is a no-op.
    reset_dynamic_only();

    if (!sissi_config_.sissi_compression_enabled) {
        std::vector<KVCachedEntry> result;
        result.reserve(text.size());
        for (size_t i = 0; i < text.size(); ++i) {
            result.push_back(KVCachedEntry{i, false, DICT_CODE_INVALID, 1});
        }
        total_out_bytes = static_cast<float>(text.size());
        return result;
    }

    std::vector<KVCachedEntry> result;
    if (text.empty()) return result;

    // ---- PHASE ONE: word segmentation with preposition filters ----
    struct WordInfo { size_t pos; size_t len; bool is_prep; };
    std::vector<WordInfo> all_words;

    for (size_t i = 0; i < text.size(); ) {
        while (i < text.size() && std::isspace(static_cast<unsigned char>(text[i]))) {
            ++i;
        }
        if (i >= text.size()) break;

        size_t wstart = i;
        while (i < text.size() && !std::isspace(static_cast<unsigned char>(text[i]))) {
            ++i;
        }

        std::string_view word_str(text.data() + wstart, i - wstart);
        bool is_prep = is_preposition(word_str);

        // Preposition Discarding check with context-aware syntactic rules
        if (is_prep && sissi_config_.discard_prepositions) {
            bool keep = false;
            if (wstart == 0 || i >= text.size()) {
                keep = true;
            } else if (std::isupper(static_cast<unsigned char>(word_str[0]))) {
                keep = true;
            } else {
                char prev_char = text[wstart - 1];
                char next_char = (i < text.size()) ? text[i] : ' ';
                if (std::ispunct(static_cast<unsigned char>(prev_char)) || 
                    std::ispunct(static_cast<unsigned char>(next_char)) ||
                    prev_char == '=' || next_char == '=' ||
                    prev_char == '{' || next_char == '}' ||
                    prev_char == '(' || next_char == ')') {
                    keep = true;
                }
            }
            if (!keep) {
                continue; // Skip entirely
            }
        }

        all_words.push_back({wstart, i - wstart, is_prep});
    }

    if (all_words.empty()) return result;

    // ---- PHASE TWO: frequency analysis for phrases ----
    const int min_depth = std::max(2, config_.min_comp_phrase_len);

    struct CompressorCandidate {
        std::string phrase;
        size_t length = 0;
        size_t frequency = 0;
        size_t score = 0;
        bool is_static = false;
    };
    std::vector<CompressorCandidate> candidates;

    // 1. Static AI dictionary entries
    for (const auto& word : STATIC_AI_WORDS) {
        candidates.push_back({std::string(word), word.size(), 10000, 10000000, true});
    }
    for (const auto& pair : STATIC_AI_PAIRS) {
        candidates.push_back({std::string(pair), pair.size(), 10000, 10000000, true});
    }
    for (const auto& ngram : STATIC_AI_NGRAMS) {
        candidates.push_back({std::string(ngram), ngram.size(), 10000, 10000000, true});
    }

    // 2. Large complex words
    if (sissi_config_.compress_large_words_first) {
        std::unordered_map<std::string, size_t> word_freqs;
        for (const auto& w : all_words) {
            if (w.len >= sissi_config_.large_word_len_threshold) {
                std::string word_str(text.data() + w.pos, w.len);
                word_freqs[word_str]++;
            }
        }
        for (const auto& pair : word_freqs) {
            size_t freq = pair.second;
            size_t len = pair.first.size();
            candidates.push_back({pair.first, len, freq, len * freq, false});
        }
    }

    // 3. Multi-word n-grams
    if (text.size() >= sissi_config_.dynamic_profiling_threshold) {
        constexpr int MAX_NGRAM_DEPTH = 4;

        struct Ngf { std::string phrase; int count = 0; };
        std::vector<Ngf> seen_ngrams;

        for (size_t wi = 0; wi < all_words.size(); ++wi) {
            for (int depth = min_depth;
                 depth <= MAX_NGRAM_DEPTH && (wi + depth - 1) < all_words.size();
                 ++depth) {

                std::string candidate;
                candidate.reserve(static_cast<size_t>(depth) * 8u);
                for (int d = 0; d < depth; ++d) {
                    auto& w = all_words[wi + d];
                    if (!candidate.empty()) candidate += ' ';
                    candidate.append(text.data() + w.pos, w.len);
                }

                bool found = false;
                for (auto& ng : seen_ngrams) {
                    if (ng.phrase == candidate) { found = true; ++ng.count; break; }
                }
                if (!found) seen_ngrams.push_back({std::string(candidate), 1});
            }
        }

        for (const auto& ng : seen_ngrams) {
            if (ng.count > 1) {
                size_t freq = static_cast<size_t>(ng.count);
                size_t len = ng.phrase.size();
                candidates.push_back({ng.phrase, len, freq, len * freq, false});
            }
        }
    }

    // Sort candidates: static first, then by score descending, then by length descending
    std::sort(candidates.begin(), candidates.end(), [](const CompressorCandidate& a, const CompressorCandidate& b) {
        if (a.is_static != b.is_static) {
            return a.is_static;
        }
        if (a.score != b.score) {
            return a.score > b.score;
        }
        return a.length > b.length;
    });

    // Register sorted candidates to dictionary
    for (const auto& cand : candidates) {
        register_to_dict(cand.phrase, cand.score, cand.is_static);
    }

    // ---- PHASE THREE: compress & format substitutions ----
    result.reserve(all_words.size());
    size_t cursor = 0;
    while (cursor < text.size()) {
        unsigned char ch = static_cast<unsigned char>(text[cursor]);
        if (std::isspace(ch)) {
            result.push_back(KVCachedEntry{cursor, false, DICT_CODE_INVALID, 1});
            ++cursor;
            continue;
        }

        // Preposition Discarding check in Phase 3
        size_t next_word_end = cursor;
        while (next_word_end < text.size() && !std::isspace(static_cast<unsigned char>(text[next_word_end]))) {
            ++next_word_end;
        }
        std::string_view cur_word(text.data() + cursor, next_word_end - cursor);
        if (is_preposition(cur_word) && sissi_config_.discard_prepositions) {
            int prep_id = get_preposition_id(cur_word);
            if (prep_id != -1) {
                ppv_list_.push_back({static_cast<uint16_t>(result.size()), static_cast<uint8_t>(prep_id)});
            }
            cursor += cur_word.size();
            continue;
        }

        // 1. Match in phrase dictionary
        size_t best_match_len = 0;
        uint8_t best_match_code = DICT_CODE_INVALID;

        // Loop A: Single words first if greedy_first is false
        if (!sissi_config_.greedy_first) {
            for (const auto& kv : phrase_map_) {
                const std::string& text_str = kv.first;
                if (text_str.find(' ') != std::string::npos) continue; // skip multi-word strings
                if (cursor + text_str.size() > text.size()) continue;

                bool match_found = true;
                for (size_t k = 0; k < text_str.size(); ++k) {
                    if (text[cursor + k] != text_str[k]) { match_found = false; break; }
                }

                if (match_found && text_str.size() > best_match_len) {
                    best_match_code = kv.second;
                    best_match_len  = text_str.size();
                }
            }
        }

        // Loop B: Multi-word / general phrases if greedy_first is true OR if Loop A found nothing
        if (best_match_code == DICT_CODE_INVALID) {
            for (const auto& kv : phrase_map_) {
                const std::string& text_str = kv.first;
                if (cursor + text_str.size() > text.size()) continue;

                bool match_found = true;
                for (size_t k = 0; k < text_str.size(); ++k) {
                    if (text[cursor + k] != text_str[k]) { match_found = false; break; }
                }

                if (match_found && text_str.size() > best_match_len) {
                    best_match_code = kv.second;
                    best_match_len  = text_str.size();
                }
            }
        }

        if (best_match_code != DICT_CODE_INVALID && best_match_len >= static_cast<size_t>(min_depth)) {
            result.push_back(KVCachedEntry{cursor, true, best_match_code, best_match_len});
            cursor += best_match_len;
            continue;
        }

        // 2. Preposition compression check (using accents)
        next_word_end = cursor;
        while (next_word_end < text.size() && !std::isspace(static_cast<unsigned char>(text[next_word_end]))) {
            ++next_word_end;
        }
        cur_word = std::string_view(text.data() + cursor, next_word_end - cursor);
        if (is_preposition(cur_word) && sissi_config_.keep_prepositions_with_accents) {
            char accent = get_preposition_accent(cur_word);
            if (accent != '\0') {
                // Map preposition to compact representation
                uint8_t prep_code = register_to_dict(cur_word);
                result.push_back(KVCachedEntry{cursor, true, prep_code, cur_word.size()});
                cursor += cur_word.size();
                continue;
            }
        }

        // 3. Fallback to literal, applying Khmer character remapping if Khmer block is found
        std::string_view slice(text.data() + cursor, 1);
        result.push_back(KVCachedEntry{cursor, false, DICT_CODE_INVALID, 1});
        ++cursor;
    }

    total_out_bytes = static_cast<float>(result.size());
    return result;
}

std::string ContextCompressor::decompress(const std::vector<KVCachedEntry>& entries) const {
    if (entries.empty()) return "";

    std::string out;
    out.reserve(total_in_chars);

    for (size_t i = 0; i < entries.size(); ++i) {
        // Check if a discarded preposition needs to be re-inserted here
        for (const auto& ppv : ppv_list_) {
            if (ppv.word_index == i && ppv.preposition_id < PREPOSITION_LIST.size()) {
                if (!out.empty() && !std::isspace(static_cast<unsigned char>(out.back()))) {
                    out += ' ';
                }
                out.append(PREPOSITION_LIST[ppv.preposition_id]);
            }
        }

        const auto& entry = entries[i];
        if (entry.is_compressed && entry.dict_code != DICT_CODE_INVALID
            && entry.dict_code < reverse_table_.size()) {
            const auto& de = reverse_table_[entry.dict_code];
            if (de.valid) {
                out.append(de.phrase_buf, de.len);
                continue;
            }
        }
        out += '?'; // literal fallback placeholder
    }
    return out;
}

} // namespace hypersp
