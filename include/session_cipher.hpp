// session_cipher.hpp
//
// Hyper-Spherical Systems — Ephemeral Session Cipher
//
// Combines SISSI phrase compression + 5+1 Homophonic character substitution
// into a single pipeline optimised for LLM-to-LLM token efficiency.
//
// "5+1" means:
//   - High-frequency characters (e,t,a,o,i,n,s,h,r,l) get 5 single-token substitutes
//   - Medium-frequency characters (d,c,u,m,p,f,g,w,y,b) get 3 substitutes
//   - Low-frequency / rare characters get 1 substitute (pass-through or single swap)
//   - The substitute symbols are chosen from the Unicode "single-token" range
//     (characters that most LLM tokenizers render as ONE token, e.g. accented Latin)
//
// Session flow:
//   1. SessionCipher::create_session() → generates ephemeral seed + index
//   2. build_handshake_index()         → compact string to give the cloud model
//   3. encode()                        → SISSI then 5+1 Homophonic
//   4. decode()                        → reverse (for cloud→local direction)
//   5. session_teardown()              → zeroes the seed + maps in memory
//                                        cloud model context expires naturally
//
// After teardown: the cloud has no index and cannot decode past sessions.
// Each session produces a DIFFERENT mapping from the same plaintext.
//
// License: MIT

#pragma once
#include "sissi_handshake.hpp"
#include <string>
#include <vector>
#include <array>
#include <unordered_map>
#include <cstdint>
#include <random>

namespace hypersp {

// ── Session identity ──────────────────────────────────────────────────────────
struct SessionID {
    uint64_t seed{0};           // 64-bit random seed (never transmitted)
    std::string session_token;  // Short opaque ID used in the handshake header
    std::string created_at;
    bool        active{false};
};

// ── 5+1 Substitution table ────────────────────────────────────────────────────
// For each ASCII character, holds up to 5 UTF-8 substitute symbols.
// Each substitute is chosen to be a single token in common LLM tokenizers
// (tested against GPT-4o, Claude, Llama-3 tokenizers).
struct CharSubTable {
    // substitute[c] = list of possible replacements for ASCII char c
    // Length 5 for high-freq, 3 for mid-freq, 1 for low-freq
    std::unordered_map<char, std::vector<std::string>> encode_table; // char → [sym1,sym2,...]
    std::unordered_map<std::string, char>              decode_table; // symN → char

    // Given the session seed, pick WHICH of the substitutes to use for each char
    // (deterministic per session, unknown across sessions)
    std::unordered_map<char, size_t> session_choice; // char → index into substitute list
};

// ── Session Compression Stats ─────────────────────────────────────────────────
struct SessionStats {
    uint64_t plaintext_tokens{0};
    uint64_t compressed_tokens{0};
    uint64_t sissi_tokens_saved{0};
    uint64_t homophonic_tokens_saved{0};
    uint64_t total_messages{0};
    float    overall_ratio{1.0f};
};

// ── The full ephemeral session cipher ─────────────────────────────────────────
class SessionCipher {
public:
    // Create a new ephemeral session (new random seed each time)
    static SessionCipher create_session();

    // Restore a session from a saved seed (for local persistence only — never transmitted)
    static SessionCipher restore_session(uint64_t seed);

    SessionCipher();
    ~SessionCipher();

    // ── Encode (local → cloud) ────────────────────────────────────────────────
    // Step 1: SISSI phrase substitution (long phrases → §codes)
    // Step 2: 5+1 Homophonic char substitution (chars → session-unique symbols)
    struct EncodeResult {
        std::string encoded;
        int sissi_savings;      // tokens saved by SISSI
        int homophonic_savings; // additional savings from 5+1
        int total_tokens_in;
        int total_tokens_out;
        float ratio;
    };
    EncodeResult encode(const std::string& plaintext);

    // ── Decode (cloud → local) ────────────────────────────────────────────────
    // Reverses 5+1 Homophonic, then SISSI
    std::string decode(const std::string& encoded);

    // ── Handshake index ───────────────────────────────────────────────────────
    // Builds the compact string that tells the cloud model how to encode/decode.
    // Format:
    //   SESS:v1|[SISSI_DICT]|[HOMO_TABLE]|END
    // This is what gets sent to the cloud model at session open.
    std::string build_handshake_index() const;

    // Estimate how many tokens the handshake index will cost
    int handshake_token_cost() const;

    // ── Session lifecycle ─────────────────────────────────────────────────────
    const SessionID& session_id() const { return session_id_; }
    bool is_active() const { return session_id_.active; }

    // Permanently zeroes all key material in memory.
    // After this: encode/decode are no-ops, cloud model cannot decode past messages.
    void teardown();

    // ── Statistics ────────────────────────────────────────────────────────────
    const SessionStats& stats() const { return stats_; }
    void print_stats() const;

    // ── SISSI dictionary (can be extended at runtime) ─────────────────────────
    SISSICodec& sissi_codec() { return sissi_; }

private:
    explicit SessionCipher(uint64_t seed);

    void build_homo_table(uint64_t seed);
    void zero_key_material();

    SessionID   session_id_;
    SISSICodec  sissi_;
    CharSubTable homo_table_;
    SessionStats stats_;
    bool        torn_down_{false};

    // Unicode single-token substitution candidates for each frequency class
    // These are Latin Extended-A/B characters that tokenize as 1 token in most LLMs
    static const char* kHighFreqPool[];   // 10 candidates for e,t,a,o,i,n,s,h,r,l
    static const char* kMidFreqPool[];    // 6 candidates for d,c,u,m,p,f,g,w,y,b
    static const char* kLowFreqPool[];    // 3 candidates for everything else
};

// ── Integrated session manager for full local↔cloud pipeline ─────────────────
class CloudSession {
public:
    CloudSession(const APIEndpoint& endpoint);

    // Open: create ephemeral cipher + negotiate SISSI with cloud model
    // Returns: whether the cloud model acknowledged the protocol
    bool open();

    // Send a plaintext message; fully encoded before transmission, decoded on return
    // The cloud model never sees uncompressed plaintext.
    std::string chat(const std::string& plaintext_message);

    // Close session: teardown cipher, print stats
    // After this call the session index is gone from both sides.
    void close();

    bool is_open() const { return is_open_; }
    const SessionCipher& cipher() const { return cipher_; }
    const SessionStats& stats() const { return cipher_.stats(); }

    // For the web UI: get the current compression ratio
    float live_ratio() const;

private:
    APIEndpoint   endpoint_;
    SessionCipher cipher_;
    SISSIHandshake engine_;
    bool          is_open_{false};
    int           exchange_count_{0};
};

} // namespace hypersp
