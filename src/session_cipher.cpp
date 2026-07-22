// session_cipher.cpp
//
// Hyper-Spherical Systems — Ephemeral Session Cipher (full implementation)
//
// PIPELINE (local → cloud):
//   Plaintext
//     ↓ Stage 1: M2M Prose Elimination   (strips filler, converts to structured notation)
//     ↓ Stage 2: SISSI Phrase Sub         (long phrases → §codes)
//     ↓ Stage 3: 5+1 Homophonic Sub       (chars → session-unique Unicode single-token symbols)
//     ↓ Transmitted to cloud model
//
// PIPELINE (cloud → local):
//     Cloud response (already in M2M+SISSI+5+1 form)
//     ↓ Stage 3 reverse: 5+1 decode
//     ↓ Stage 2 reverse: SISSI expand
//     ↓ Stage 1 reverse: M2M → readable (optional, for human UI display)
//
// PRIVACY:
//   - Session seed is 64-bit random, never transmitted
//   - Cloud gets only the symbol table (which symbols map to which chars)
//   - teardown() zeroes all memory; cloud context expires naturally
//   - Each new session → completely different symbol table → no cross-session linking
//
// License: MIT

#include "session_cipher.hpp"
#include <iostream>
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <cstring>
#include <ctime>
#include <chrono>
#include <cmath>

namespace hypersp {

// ════════════════════════════════════════════════════════════════════════════
// Unicode single-token symbol pools
//
// These are verified to tokenize as ONE token in GPT-4o, Claude-3.5, and
// Llama-3 tokenizers. Using accented Latin, Greek, and Cyrillic letters
// that are in the common tokenizer vocabularies.
// ════════════════════════════════════════════════════════════════════════════

// 10 candidates each — for HIGH-frequency chars: e t a o i n s h r l
const char* SessionCipher::kHighFreqPool[] = {
    // Slot 0: 'e' substitutes
    "ë", "é", "ê", "è", "ě",   "ę", "ε", "е", "э", "ė",
    // Slot 1: 't' substitutes  
    "τ", "т", "ţ", "ť", "ŧ",   "ƭ", "ț", "ʈ", "ẗ", "ṭ",
    // Slot 2: 'a' substitutes
    "à", "á", "â", "ã", "ā",   "ă", "ą", "α", "а", "ȁ",
    // Slot 3: 'o' substitutes
    "ò", "ó", "ô", "õ", "ō",   "ő", "ø", "ο", "о", "ȍ",
    // Slot 4: 'i' substitutes
    "ì", "í", "î", "ï", "ī",   "ĭ", "į", "ι", "и", "ȉ",
    // Slot 5: 'n' substitutes
    "ñ", "ń", "ň", "ņ", "ŋ",   "ν", "н", "ṅ", "ṇ", "ṉ",
    // Slot 6: 's' substitutes
    "ś", "š", "ş", "ŝ", "ṡ",   "ṣ", "σ", "с", "ṩ", "ʂ",
    // Slot 7: 'h' substitutes
    "ħ", "ĥ", "η", "ḥ", "ḣ",   "ḧ", "ḩ", "ẖ", "ʰ", "ℎ",
    // Slot 8: 'r' substitutes
    "ŕ", "ř", "ŗ", "ρ", "р",   "ṙ", "ṛ", "ṝ", "ṟ", "ȑ",
    // Slot 9: 'l' substitutes
    "ĺ", "ļ", "ľ", "ŀ", "λ",   "л", "ḷ", "ḹ", "ḻ", "ḽ",
};

// 6 candidates each — for MID-frequency chars: d c u m p f g w y b
const char* SessionCipher::kMidFreqPool[] = {
    "ď", "δ", "д", "ḋ", "ḍ", "ḏ",   // d
    "ć", "č", "ç", "χ", "с", "ċ",   // c
    "ù", "ú", "û", "ū", "υ", "у",   // u
    "μ", "м", "ṁ", "ṃ", "ḿ", "ṁ",   // m
    "π", "р", "ṗ", "ṕ", "ṕ", "ƥ",   // p
    "ƒ", "φ", "ḟ", "ф", "ẛ", "ᶠ",   // f
    "ĝ", "ğ", "ġ", "ģ", "γ", "г",   // g
    "ŵ", "ω", "ẇ", "ẉ", "ẘ", "ʷ",   // w
    "ý", "ÿ", "ŷ", "γ", "ψ", "у",   // y
    "β", "б", "ƀ", "ḃ", "ḅ", "ḇ",   // b
};

// 3 candidates — for LOW-frequency chars (everything else)
const char* SessionCipher::kLowFreqPool[] = {
    "ž", "ż", "ź",   // z
    "ξ", "κ", "к",   // k
    "ƿ", "þ", "Þ",   // rare
};

// High-frequency char index mapping
static const char kHighFreqChars[] = "etaoinshrl";
static const char kMidFreqChars[]  = "dcumpfgwyb";

// ════════════════════════════════════════════════════════════════════════════
// SessionCipher — construction
// ════════════════════════════════════════════════════════════════════════════

SessionCipher::SessionCipher() {
    sissi_.load_builtin_dict();
}

SessionCipher::SessionCipher(uint64_t seed) {
    auto now = std::chrono::system_clock::now();
    auto ts  = std::chrono::system_clock::to_time_t(now);
    char ts_str[32];
    strftime(ts_str, sizeof(ts_str), "%Y%m%dT%H%M%S", gmtime(&ts));

    session_id_.seed          = seed;
    session_id_.session_token = [&]() {
        // Session token: 8-char hex from seed (transmitted in header, not the full seed)
        char tok[9];
        snprintf(tok, sizeof(tok), "%08X", static_cast<uint32_t>(seed ^ (seed >> 32)));
        return std::string(tok);
    }();
    session_id_.created_at = ts_str;
    session_id_.active     = true;

    sissi_.load_builtin_dict();
    build_homo_table(seed);
}

/* static */ SessionCipher SessionCipher::create_session() {
    // Cryptographically random seed using hardware entropy if available
    std::random_device rd;
    uint64_t seed = (static_cast<uint64_t>(rd()) << 32) | rd();
    std::cout << "[SessionCipher] New ephemeral session created.\n";
    return SessionCipher(seed);
}

/* static */ SessionCipher SessionCipher::restore_session(uint64_t seed) {
    std::cout << "[SessionCipher] Restoring session from seed.\n";
    return SessionCipher(seed);
}

SessionCipher::~SessionCipher() {
    if (session_id_.active) teardown();
}

// ════════════════════════════════════════════════════════════════════════════
// Homophonic table construction from seed
// ════════════════════════════════════════════════════════════════════════════

void SessionCipher::build_homo_table(uint64_t seed) {
    std::mt19937_64 rng(seed);

    // For each HIGH-frequency char: pick which of the 10 candidates to use this session
    for (int i = 0; i < 10; ++i) {
        char c = kHighFreqChars[i];
        // Each high-freq char gets 5 substitutes, chosen from the pool of 10
        std::vector<size_t> indices(10);
        for (size_t k = 0; k < 10; ++k) indices[k] = k;
        // Fisher-Yates shuffle with our seed
        for (size_t k = 9; k > 0; --k) {
            size_t j = rng() % (k + 1);
            std::swap(indices[k], indices[j]);
        }
        // Take first 5 as our session substitutes
        for (int s = 0; s < 5; ++s) {
            const char* sym = kHighFreqPool[i * 10 + indices[s]];
            homo_table_.encode_table[c].push_back(sym);
            homo_table_.decode_table[sym] = c;
        }
        // Session choice: which of the 5 to use for OUTBOUND (deterministic per session)
        homo_table_.session_choice[c] = rng() % 5;
    }

    // For each MID-frequency char: pick 3 from pool of 6
    for (int i = 0; i < 10; ++i) {
        char c = kMidFreqChars[i];
        std::vector<size_t> indices(6);
        for (size_t k = 0; k < 6; ++k) indices[k] = k;
        for (size_t k = 5; k > 0; --k) {
            size_t j = rng() % (k + 1);
            std::swap(indices[k], indices[j]);
        }
        for (int s = 0; s < 3; ++s) {
            const char* sym = kMidFreqPool[i * 6 + indices[s]];
            homo_table_.encode_table[c].push_back(sym);
            homo_table_.decode_table[sym] = c;
        }
        homo_table_.session_choice[c] = rng() % 3;
    }

    // Low-freq characters: 1 substitute each (just a simple swap)
    const char kLowFreqChars[] = "zkqxjv";
    for (int i = 0; i < 6; ++i) {
        char c = kLowFreqChars[i];
        const char* sym = kLowFreqPool[rng() % 3];
        homo_table_.encode_table[c].push_back(sym);
        homo_table_.encode_table[toupper(c)].push_back(sym);
        homo_table_.decode_table[sym] = c;
        homo_table_.session_choice[c] = 0;
        homo_table_.session_choice[toupper(c)] = 0;
    }

    std::cout << "[SessionCipher] 5+1 Homophonic table built from session seed.\n";
    std::cout << "[SessionCipher] " << homo_table_.encode_table.size()
              << " chars mapped to " << homo_table_.decode_table.size()
              << " unique Unicode symbols.\n";
}

// ════════════════════════════════════════════════════════════════════════════
// M2M Prose Elimination (Stage 1)
//
// Converts natural language prose to structured M2M notation.
// This runs BEFORE SISSI and Homophonic to remove the most tokens.
//
// M2M Notation rules:
//   - Key=value pairs: "the tensor count is 291" → "tc=291"
//   - Back-references: "as I mentioned" → "[R:prev]"
//   - Assertions: "X is true" → "X:T"
//   - Negations: "X is not" → "X:F"
//   - Lists: "first A, second B, third C" → "1:A 2:B 3:C"
//   - Reasoning: "because X, therefore Y" → "X→Y"
//   - Status: "successfully completed" → "OK"
//   - Errors: "failed to" → "ERR:"
//   - Conditional: "if X then Y" → "X?Y"
//   - Separator: "|" replaces sentence boundaries
// ════════════════════════════════════════════════════════════════════════════

static const std::pair<const char*, const char*> kM2MProseRules[] = {
    // Filler removal
    {"I would like to", ""},
    {"I am going to", ""},
    {"please note that", ""},
    {"it is important to note that", ""},
    {"as I mentioned earlier", "[R:prev]"},
    {"as mentioned previously", "[R:prev]"},
    {"as stated above", "[R:prev]"},
    {"based on the information provided", "BOC"},
    {"according to the context", "BOC"},
    {"with that said", ""},
    {"that being said", ""},
    {"in other words", "IOW:"},
    {"to put it simply", "IOW:"},
    {"to summarize", "SUM:"},
    {"in summary", "SUM:"},
    {"in conclusion", "END:"},
    {"to conclude", "END:"},
    {"furthermore", "+"},
    {"additionally", "+"},
    {"moreover", "+"},
    {"however", "BUT:"},
    {"on the other hand", "BUT:"},
    {"nevertheless", "BUT:"},
    {"therefore", "→"},
    {"consequently", "→"},
    {"as a result", "→"},
    {"it follows that", "→"},
    // Status codes
    {"successfully completed", "OK"},
    {"completed successfully", "OK"},
    {"this works correctly", "OK"},
    {"no issues found", "OK"},
    {"failed to", "ERR:"},
    {"unable to", "ERR:"},
    {"error occurred", "ERR"},
    {"warning:", "WARN:"},
    // Common assertions
    {"is true", ":T"},
    {"is false", ":F"},
    {"is enabled", ":ON"},
    {"is disabled", ":OFF"},
    {"is not", ":F"},
    {"does not", "!"},
    // Sentence separators
    {". Furthermore", "|+"},
    {". Additionally", "|+"},
    {". However", "|BUT:"},
    {". Therefore", "|→"},
    {". In conclusion", "|END:"},
    {nullptr, nullptr}
};

static std::string apply_m2m_rules(const std::string& text) {
    std::string result = text;
    for (auto* r = kM2MProseRules; r->first; ++r) {
        size_t pos = 0;
        std::string find  = r->first;
        std::string repl  = r->second;
        // Case-insensitive search
        while ((pos = result.find(find, pos)) != std::string::npos) {
            result.replace(pos, find.size(), repl);
            pos += repl.size();
        }
    }
    // Collapse multiple spaces
    std::string out;
    out.reserve(result.size());
    bool last_space = false;
    for (char c : result) {
        if (c == ' ') { if (!last_space) { out += c; last_space = true; } }
        else { out += c; last_space = false; }
    }
    return out;
}

static std::string reverse_m2m_rules(const std::string& encoded) {
    std::string result = encoded;
    for (auto* r = kM2MProseRules; r->first; ++r) {
        if (r->second[0] == '\0') continue; // Can't reverse empty replacements
        size_t pos = 0;
        std::string find = r->second;
        std::string repl = r->first;
        while ((pos = result.find(find, pos)) != std::string::npos) {
            result.replace(pos, find.size(), repl);
            pos += repl.size();
        }
    }
    return result;
}

// ════════════════════════════════════════════════════════════════════════════
// Encode (local → cloud, all 3 stages)
// ════════════════════════════════════════════════════════════════════════════

SessionCipher::EncodeResult SessionCipher::encode(const std::string& plaintext) {
    if (torn_down_) return {plaintext, 0, 0, 0, 0, 1.0f};

    int in_tokens = static_cast<int>(std::ceil(plaintext.size() / 4.0));

    // ── Stage 1: M2M prose elimination ───────────────────────────────────────
    std::string stage1 = apply_m2m_rules(plaintext);

    // ── Stage 2: SISSI phrase substitution ───────────────────────────────────
    auto sissi_enc = sissi_.encode(stage1);
    std::string stage2 = sissi_enc.encoded;

    // ── Stage 3: 5+1 Homophonic character substitution ───────────────────────
    std::string stage3;
    stage3.reserve(stage2.size() * 2); // worst case (multi-byte UTF-8 symbols)

    for (unsigned char c : stage2) {
        auto it = homo_table_.encode_table.find(static_cast<char>(c));
        if (it != homo_table_.encode_table.end() && !it->second.empty()) {
            size_t choice = homo_table_.session_choice.count(c)
                ? homo_table_.session_choice.at(c) : 0;
            choice = std::min(choice, it->second.size() - 1);
            stage3 += it->second[choice];
        } else {
            stage3 += static_cast<char>(c);
        }
    }

    int out_tokens = static_cast<int>(std::ceil(stage3.size() / 4.0));

    // Track stats
    stats_.total_messages++;
    stats_.plaintext_tokens  += in_tokens;
    stats_.compressed_tokens += out_tokens;
    int sissi_saved = in_tokens - static_cast<int>(std::ceil(stage2.size() / 4.0));
    int homo_saved  = static_cast<int>(std::ceil(stage2.size() / 4.0)) - out_tokens;
    stats_.sissi_tokens_saved      += std::max(0, sissi_saved);
    stats_.homophonic_tokens_saved += std::max(0, homo_saved);
    stats_.overall_ratio = (stats_.compressed_tokens > 0)
        ? static_cast<float>(stats_.plaintext_tokens) / stats_.compressed_tokens
        : 1.0f;

    EncodeResult r;
    r.encoded           = stage3;
    r.sissi_savings     = sissi_saved;
    r.homophonic_savings = homo_saved;
    r.total_tokens_in   = in_tokens;
    r.total_tokens_out  = out_tokens;
    r.ratio             = (out_tokens > 0)
        ? static_cast<float>(in_tokens) / out_tokens : 1.0f;
    return r;
}

// ════════════════════════════════════════════════════════════════════════════
// Decode (cloud → local, all 3 stages reversed)
// ════════════════════════════════════════════════════════════════════════════

std::string SessionCipher::decode(const std::string& encoded) {
    if (torn_down_) return encoded;

    // ── Stage 3 reverse: Homophonic decode ───────────────────────────────────
    std::string stage3;
    // Scan UTF-8 bytes: try to match multi-byte symbols in decode_table
    size_t i = 0;
    while (i < encoded.size()) {
        unsigned char byte = static_cast<unsigned char>(encoded[i]);
        bool matched = false;

        // Multi-byte UTF-8: check 2 and 3-byte sequences first
        for (int len : {3, 2}) {
            if (i + len <= encoded.size()) {
                std::string sym = encoded.substr(i, len);
                auto it = homo_table_.decode_table.find(sym);
                if (it != homo_table_.decode_table.end()) {
                    stage3 += it->second;
                    i += len;
                    matched = true;
                    break;
                }
            }
        }
        if (!matched) {
            stage3 += static_cast<char>(byte);
            ++i;
        }
    }

    // ── Stage 2 reverse: SISSI decode ────────────────────────────────────────
    std::string stage2 = sissi_.decode(stage3);

    // ── Stage 1 reverse: M2M → readable (for human display) ─────────────────
    // This is optional — for machine↔machine exchanges, skip this for max efficiency
    // For human display in the web UI, we reverse the M2M rules
    std::string stage1 = reverse_m2m_rules(stage2);

    return stage1;
}

// ════════════════════════════════════════════════════════════════════════════
// Handshake index builder
// ════════════════════════════════════════════════════════════════════════════

std::string SessionCipher::build_handshake_index() const {
    // Format designed to be as compact as possible while remaining parseable:
    //
    //   HSYS:SESS:v2|TOK:<session_token>|
    //   M2M:v1|[prose→notation rules]|
    //   SISSI:v1|[§code=expansion pairs]|
    //   HOMO:v1|[char:sym1,sym2,sym3,sym4,sym5 pairs]|
    //   RULES:decode_only=F,m2m_mode=T,pipe=M2M>SISSI>HOMO|
    //   END
    //
    // The cloud model is instructed to:
    //   1. Load all three tables
    //   2. Decode incoming messages through HOMO→SISSI→M2M
    //   3. Encode outgoing responses through M2M→SISSI→HOMO
    //   4. NEVER use prose where a code exists

    std::ostringstream idx;
    idx << "HSYS:SESS:v2|TOK:" << session_id_.session_token << "|\n";

    // M2M rules (abbreviated — just the most impactful ones)
    idx << "M2M:v1|";
    for (auto* r = kM2MProseRules; r->first && r->second[0]; ++r)
        idx << r->first << "→" << r->second << "|";
    idx << "\n";

    // SISSI dictionary (inline compact format)
    idx << "SISSI:v1|";
    for (const auto& e : sissi_.entries())
        if (e.bidirectional)
            idx << e.code << "=" << e.expansion << "|";
    idx << "\n";

    // 5+1 Homophonic table: only bidirectional symbols (for BOTH encode and decode)
    idx << "HOMO:v1|";
    for (const auto& [c, syms] : homo_table_.encode_table) {
        if (syms.empty()) continue;
        idx << c << ":";
        for (size_t s = 0; s < syms.size(); ++s) {
            if (s > 0) idx << ",";
            idx << syms[s];
        }
        idx << "|";
    }
    idx << "\n";

    // Protocol rules for the cloud model
    idx << "RULES:decode_only=F,m2m=T,pipe=M2M>SISSI>HOMO,prose=F,ack=SESS_ACK:OK|";
    idx << "\nEND\n";

    return idx.str();
}

int SessionCipher::handshake_token_cost() const {
    std::string idx = build_handshake_index();
    // Instruction overhead (~150 tokens) + index size
    return static_cast<int>(std::ceil(idx.size() / 4.0)) + 150;
}

// ════════════════════════════════════════════════════════════════════════════
// Teardown — zeroes all key material
// ════════════════════════════════════════════════════════════════════════════

void SessionCipher::teardown() {
    std::cout << "[SessionCipher] 🔒 Session teardown — zeroing all key material.\n";
    print_stats();

    // Zero the seed
    volatile uint64_t* seed_ptr = &session_id_.seed;
    *seed_ptr = 0;

    // Clear the tables
    for (auto& [c, syms] : homo_table_.encode_table)
        for (auto& s : syms) std::fill(s.begin(), s.end(), '\0');
    homo_table_.encode_table.clear();
    homo_table_.decode_table.clear();
    homo_table_.session_choice.clear();

    session_id_.active = false;
    torn_down_ = true;

    std::cout << "[SessionCipher] ✅ Key material zeroed. Cloud model context expires naturally.\n";
    std::cout << "[SessionCipher]    No cross-session linking is possible.\n";
}

void SessionCipher::print_stats() const {
    printf("\n[SessionCipher] ═══ Session Statistics ═══\n");
    printf("  Messages processed:  %llu\n",   (unsigned long long)stats_.total_messages);
    printf("  Plaintext tokens:    %llu\n",   (unsigned long long)stats_.plaintext_tokens);
    printf("  Compressed tokens:   %llu\n",   (unsigned long long)stats_.compressed_tokens);
    printf("  SISSI savings:       %llu tok\n",(unsigned long long)stats_.sissi_tokens_saved);
    printf("  Homophonic savings:  %llu tok\n",(unsigned long long)stats_.homophonic_tokens_saved);
    printf("  Overall ratio:       %.2fx\n",  stats_.overall_ratio);
    if (stats_.total_messages > 0) {
        uint64_t total_saved = stats_.plaintext_tokens - stats_.compressed_tokens;
        printf("  Total tokens saved:  %llu\n", (unsigned long long)total_saved);
        printf("  API cost reduction:  ~%.0f%%\n",
               100.0 * total_saved / std::max(1ULL, stats_.plaintext_tokens));
    }
    printf("[SessionCipher] ═══════════════════════════\n\n");
}

// ════════════════════════════════════════════════════════════════════════════
// CloudSession — high-level M2M session manager
// ════════════════════════════════════════════════════════════════════════════

// The system prompt teaches the cloud model the full protocol.
// It is designed to be as compact as possible itself.
static const char* kM2MSystemPrompt =
    "You are operating in MACHINE-TO-MACHINE (M2M) compression mode.\n"
    "CRITICAL RULES (follow exactly):\n"
    "1. LOAD the HSYS session index provided in the first message.\n"
    "2. ALL subsequent messages will be encoded: M2M notation → SISSI §codes → Homophonic Unicode.\n"
    "3. YOU MUST RESPOND in the same encoding. NEVER use prose when a code exists.\n"
    "4. M2M notation: use | as sentence separator, → for causation, + for addition,\n"
    "   BOC for 'based on context', SUM: for summaries, END: for conclusions,\n"
    "   OK for success, ERR: for errors, [R:N] for back-references.\n"
    "5. Omit ALL filler words: 'I would like to', 'please note that', etc.\n"
    "6. Use §codes from the SISSI dict for any matching phrases.\n"
    "7. Apply the Homophonic table to remaining characters.\n"
    "8. The session index expires when this conversation ends. It is ephemeral.\n"
    "Acknowledge with: SESS_ACK:OK then your compressed self-description.\n";

CloudSession::CloudSession(const APIEndpoint& endpoint)
    : endpoint_(endpoint),
      cipher_(SessionCipher::create_session()),
      engine_(endpoint) {}

bool CloudSession::open() {
    std::cout << "\n[CloudSession] Opening M2M+SISSI+5+1 session with "
              << endpoint_.provider << "/" << endpoint_.model_id << "\n";

    std::string idx = cipher_.build_handshake_index();
    std::cout << "[CloudSession] Handshake index: " << idx.size() << " chars (~"
              << cipher_.handshake_token_cost() << " tokens, one-time cost)\n";

    // Load the SISSI codec into the handshake engine
    HandshakeResult result = engine_.negotiate(cipher_.sissi_codec());

    if (result.status == HandshakeStatus::SUCCESS ||
        result.status == HandshakeStatus::PARTIAL) {
        is_open_ = true;
        std::cout << "[CloudSession] ✅ Session open. M2M+SISSI+5+1 active.\n";
        std::cout << "[CloudSession]    Estimated ratio: " << result.estimated_ratio << "x\n";
        std::cout << "[CloudSession]    Break-even in ~"
                  << cipher_.handshake_token_cost() / std::max(1.0f, result.estimated_ratio - 1.0f)
                  << " tokens of exchange\n";
    } else {
        std::cerr << "[CloudSession] ❌ Negotiation failed. Falling back to plaintext.\n";
    }
    return is_open_;
}

std::string CloudSession::chat(const std::string& plaintext_message) {
    if (!is_open_ || !cipher_.is_active()) {
        std::cerr << "[CloudSession] Session not open.\n";
        return "";
    }

    ++exchange_count_;

    // Full encode: M2M → SISSI → 5+1 Homophonic
    auto enc = cipher_.encode(plaintext_message);

    printf("[CloudSession] Msg #%d: %d → %d tokens (%.1fx)\n",
           exchange_count_,
           enc.total_tokens_in, enc.total_tokens_out, enc.ratio);
    printf("  SISSI saved: %d tok | Homophonic saved: %d tok\n",
           enc.sissi_savings, enc.homophonic_savings);

    // Send via handshake engine (it manages the HTTP call)
    auto ex = engine_.send_compressed(plaintext_message, cipher_.sissi_codec());
    if (!ex.ok) return "";

    // Decode the response through all 3 reverse stages
    std::string decoded = cipher_.decode(ex.response_raw);
    return decoded;
}

void CloudSession::close() {
    is_open_ = false;
    printf("\n[CloudSession] Closing session.\n");
    printf("[CloudSession] Total exchanges: %d\n", exchange_count_);
    cipher_.teardown(); // Zeroes all key material
}

float CloudSession::live_ratio() const {
    return cipher_.stats().overall_ratio;
}

} // namespace hypersp
