// sissi_handshake.hpp
//
// Hyper-Spherical Systems — SISSI Frontier Model Handshake Protocol
//
// Establishes a shared compression dictionary with a frontier/cloud model.
// After a successful handshake, all subsequent exchanges use SISSI-encoded
// payloads, dramatically increasing information density per token.
//
// Protocol flow:
//   1. NEGOTIATE  → Send the SISSI index to the frontier model
//   2. ACK        ← Model confirms it has loaded and understood the index
//   3. COMMUNICATE → All subsequent messages use SISSI encoding
//   4. REFRESH    → Re-send index if context window rolls over
//
// Compatible with: OpenAI API, Anthropic API, Google Generative AI API,
//                  Ollama (local), LM Studio (local), any OpenAI-compat endpoint.
//
// License: MIT

#pragma once
#include <string>
#include <vector>
#include <unordered_map>
#include <functional>
#include <cstdint>

namespace hypersp {

// ── SISSI Dictionary Entry ────────────────────────────────────────────────────
struct SISSIEntry {
    std::string code;       // e.g. "§YHA"
    std::string expansion;  // e.g. "You are a helpful assistant"
    float       frequency;  // how often this phrase appears in typical LLM traffic
    bool        bidirectional; // true = model should also USE this code in responses
};

// ── Handshake result ──────────────────────────────────────────────────────────
enum class HandshakeStatus {
    SUCCESS,          // Model acknowledged SISSI and will use it
    PARTIAL,          // Model understood but will only decode (not encode responses)
    REJECTED,         // Model refused or didn't understand
    TIMEOUT,          // No response
    NOT_ATTEMPTED,    // Handshake not yet run
};

struct HandshakeResult {
    HandshakeStatus status{HandshakeStatus::NOT_ATTEMPTED};
    std::string     model_id;
    std::string     ack_message;     // Raw ACK from the model
    int             dict_tokens_used{0}; // How many tokens the index cost
    float           estimated_ratio;     // Estimated compression ratio going forward
    bool            model_will_encode{false}; // Will model compress its OWN responses?
};

// ── SISSI Codec (encoder/decoder for handshaked sessions) ─────────────────────
class SISSICodec {
public:
    explicit SISSICodec(const std::vector<SISSIEntry>& dict = {});

    // Encode a plaintext message using the loaded dictionary
    // Returns the compressed string + a metadata object
    struct EncodeResult {
        std::string encoded;
        int   original_tokens;
        int   compressed_tokens;
        float ratio;
    };
    EncodeResult encode(const std::string& plaintext) const;

    // Decode a SISSI-encoded message back to plaintext
    std::string decode(const std::string& encoded) const;

    // Build a JSON representation of the dictionary for the handshake message
    std::string dict_to_json() const;

    // Build a compact inline representation (more token-efficient than JSON for small dicts)
    std::string dict_to_inline() const;

    // Estimate how many tokens the dictionary transmission will cost
    int dict_token_cost() const;

    // Estimate compression ratio for a sample of typical LLM output
    float estimate_ratio(const std::string& sample_text) const;

    // Load the default built-in dictionary (SISSI phrase table)
    void load_builtin_dict();

    // Add a dynamic entry (discovered from conversation patterns)
    void add_dynamic_entry(const std::string& phrase, const std::string& code);

    const std::vector<SISSIEntry>& entries() const { return dict_; }
    size_t size() const { return dict_.size(); }

private:
    std::vector<SISSIEntry>                 dict_;
    std::unordered_map<std::string, std::string> encode_map_; // phrase → code
    std::unordered_map<std::string, std::string> decode_map_; // code → phrase
    void rebuild_maps();
};

// ── API Endpoint descriptor ───────────────────────────────────────────────────
struct APIEndpoint {
    std::string provider;   // "openai", "anthropic", "google", "ollama", "openai_compat"
    std::string base_url;   // e.g. "https://api.openai.com/v1"
    std::string model_id;   // e.g. "gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"
    std::string api_key;    // loaded from env or keystore
    int         timeout_ms{30000};

    // Build from environment variables (OPENAI_API_KEY etc.)
    static APIEndpoint from_env(const std::string& provider);

    // Build a local Ollama endpoint
    static APIEndpoint ollama(const std::string& model = "llama3.2:3b",
                               const std::string& host = "localhost:11434");
};

// ── SISSI Handshake Engine ────────────────────────────────────────────────────
class SISSIHandshake {
public:
    explicit SISSIHandshake(const APIEndpoint& endpoint);
    ~SISSIHandshake() = default;

    // ── Negotiate ────────────────────────────────────────────────────────────
    // Sends the SISSI dictionary to the frontier model and waits for ACK.
    // Returns the negotiation result — caller should check status.
    HandshakeResult negotiate(const SISSICodec& codec);

    // ── Send compressed message ───────────────────────────────────────────────
    // Encodes the message using the codec and sends it to the model.
    // Decodes the response if the model also encodes (model_will_encode=true).
    struct ExchangeResult {
        std::string request_encoded;
        std::string response_raw;
        std::string response_decoded;
        int   request_tokens_saved;
        int   response_tokens_saved;
        float total_ratio;
        bool  ok{false};
    };
    ExchangeResult send_compressed(const std::string& plaintext_message,
                                   const SISSICodec& codec);

    // ── Re-negotiate (context window rolled over) ─────────────────────────────
    HandshakeResult refresh(const SISSICodec& codec);

    // ── Token savings tracking ────────────────────────────────────────────────
    int   total_tokens_saved()  const { return total_tokens_saved_; }
    int   total_exchanges()     const { return total_exchanges_; }
    float session_ratio()       const;

    // ── Conversation history (for context-aware compression) ─────────────────
    // The handshake engine maintains a rolling window of the conversation
    // so it can learn frequently-used phrases and add them to the dynamic dict.
    void add_dynamic_phrases(SISSICodec& codec, int min_frequency = 3);

    // ── Provider-specific negotiation messages ────────────────────────────────
    static std::string build_negotiate_prompt(const SISSICodec& codec,
                                               const std::string& provider);
    static std::string build_ack_check_pattern(const std::string& provider);

    // Callback: called on each exchange with token savings data
    using ExchangeCallback = std::function<void(const ExchangeResult&)>;
    void on_exchange(ExchangeCallback cb) { exchange_cb_ = std::move(cb); }

private:
    APIEndpoint           endpoint_;
    HandshakeResult       last_result_;
    ExchangeCallback      exchange_cb_;
    int                   total_tokens_saved_{0};
    int                   total_exchanges_{0};

    // Conversation history (phrase → occurrence count)
    std::unordered_map<std::string, int> phrase_frequency_;

    // HTTP helpers
    std::string http_post_json(const std::string& path,
                                const std::string& json_body);

    std::string build_openai_request(const std::string& system_msg,
                                     const std::string& user_msg) const;
    std::string build_anthropic_request(const std::string& system_msg,
                                        const std::string& user_msg) const;
    std::string build_google_request(const std::string& system_msg,
                                     const std::string& user_msg) const;
    std::string extract_response_text(const std::string& raw_json) const;

    bool check_ack(const std::string& response) const;
    bool check_model_encodes(const std::string& response) const;
};

// ── Session Manager — handles multi-turn compressed conversations ─────────────
class SISSISession {
public:
    SISSISession(const APIEndpoint& endpoint, const SISSICodec& codec);

    // Complete setup: negotiate, confirm, and return session status
    HandshakeResult open();

    // Send a plaintext message; handles encoding/decoding transparently
    std::string chat(const std::string& plaintext);

    // Close and print session statistics
    void close();

    bool is_open() const { return open_; }
    const HandshakeResult& handshake_result() const { return handshake_; }

private:
    APIEndpoint    endpoint_;
    SISSICodec     codec_;
    SISSIHandshake engine_;
    HandshakeResult handshake_;
    bool           open_{false};
    int            exchange_count_{0};
};

} // namespace hypersp
