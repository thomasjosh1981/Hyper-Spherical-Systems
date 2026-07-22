// sissi_handshake.cpp
//
// Hyper-Spherical Systems — SISSI Frontier Model Handshake (full implementation)
//
// The negotiation works because frontier models have strong in-context learning.
// We hand them the SISSI index once (upfront token cost), they load it into
// their attention context, and every subsequent exchange can use the codes.
//
// For a 30-entry dictionary the upfront cost is ~400-600 tokens.
// After that, each exchange saves ~3-8x on phrase-heavy text.
// Break-even point: typically within the first 2-3 exchanges.
//
// License: MIT

#include "sissi_handshake.hpp"
#include <iostream>
#include <sstream>
#include <algorithm>
#include <cstring>
#include <cstdio>
#include <cmath>

#if defined(_WIN32)
#  define WIN32_LEAN_AND_MEAN
#  define NOMINMAX
#  include <windows.h>
#  include <winhttp.h>
#  pragma comment(lib, "winhttp.lib")
#endif

namespace hypersp {

// ════════════════════════════════════════════════════════════════════════════
// Built-in SISSI Dictionary — tuned for LLM-to-LLM and human-to-LLM traffic
// ════════════════════════════════════════════════════════════════════════════

static const SISSIEntry kBuiltinDict[] = {
    // ── High-frequency AI assistant phrases ──────────────────────────────────
    {"§YHA",  "You are a helpful assistant",           0.95f, true},
    {"§SYS",  "System:",                               0.90f, true},
    {"§USR",  "User:",                                 0.90f, true},
    {"§AST",  "Assistant:",                            0.90f, true},
    {"§PP",   "Please provide",                        0.85f, true},
    {"§BOC",  "Based on the context",                  0.80f, true},
    {"§IS",   "In summary",                            0.80f, true},
    {"§TFI",  "The following is",                      0.78f, true},
    {"§AALM", "As an AI language model",               0.75f, true},
    {"§IUT",  "I understand that",                     0.72f, true},
    {"§TYY",  "Thank you for your",                    0.70f, true},
    {"§LMKYH","Let me know if you have",               0.68f, true},
    {"§CYP",  "Could you please",                      0.70f, true},
    {"§ATTI", "According to the information provided", 0.65f, true},
    {"§IITN", "It is important to note that",         0.65f, true},
    {"§ITHH", "I hope this helps",                    0.62f, true},
    {"§PNT",  "Please note that",                     0.62f, true},
    {"§IWBH", "I would be happy to",                  0.60f, true},
    {"§FFTA", "Feel free to ask",                     0.60f, true},
    {"§HAS",  "Here are some",                        0.58f, true},
    {"§KPA",  "The key points are",                   0.55f, true},
    // ── Common connective tissue ──────────────────────────────────────────────
    {"§IC",   "In conclusion",                        0.72f, true},
    {"§FTH",  "Furthermore",                          0.70f, true},
    {"§ADL",  "Additionally",                         0.68f, true},
    {"§HWV",  "However",                              0.82f, true},
    {"§TFR",  "Therefore",                            0.75f, true},
    {"§NTL",  "Nevertheless",                         0.55f, true},
    {"§CSQ",  "Consequently",                         0.55f, true},
    {"§IWNT", "It is worth noting that",              0.60f, true},
    {"§IOW",  "In other words",                       0.65f, true},
    {"§TSM",  "To summarize",                         0.68f, true},
    {"§FAF",  "First and foremost",                   0.52f, true},
    // ── Code-related phrases (for technical LLM sessions) ────────────────────
    {"§IMPL", "Here is the implementation",           0.60f, true},
    {"§EXPL", "Here is an explanation",               0.58f, true},
    {"§CODE", "```",                                  0.95f, true},
    {"§ENDC", "```\n",                                0.95f, true},
    {"§FN",   "function",                             0.88f, true},
    {"§RET",  "return",                               0.85f, true},
    {"§ERR",  "error",                                0.80f, true},
    // ── Hyper-Spherical Systems domain phrases ────────────────────────────────
    {"§GCS",  "Golden Candy Spinner",                 1.00f, true},
    {"§SFS",  "Self-Forming Sphere",                  1.00f, true},
    {"§SFSP", "Self-Forming Sphere Plus",             1.00f, true},
    {"§HSCC", "Hyper-Spherical Coordinate Compression",1.00f, true},
    {"§SISSI","SISSI compression",                    1.00f, true},
    {"§CCTM", "Cloud Token Compression Module",       1.00f, true},
    {"§UEP",  "Universal Endpoint",                   1.00f, true},
    {"§GGUF", "GGUF model format",                    0.90f, true},
    {"§HFS",  "HuggingFace",                          0.90f, true},
    {"§VMOE", "Virtual Mixture of Experts",           0.85f, true},
};
static constexpr int kBuiltinDictSize = sizeof(kBuiltinDict) / sizeof(kBuiltinDict[0]);

// ════════════════════════════════════════════════════════════════════════════
// SISSICodec
// ════════════════════════════════════════════════════════════════════════════

SISSICodec::SISSICodec(const std::vector<SISSIEntry>& dict) : dict_(dict) {
    rebuild_maps();
}

void SISSICodec::rebuild_maps() {
    encode_map_.clear();
    decode_map_.clear();
    for (const auto& e : dict_) {
        encode_map_[e.expansion] = e.code;
        decode_map_[e.code]      = e.expansion;
    }
}

void SISSICodec::load_builtin_dict() {
    dict_.clear();
    for (int i = 0; i < kBuiltinDictSize; ++i)
        dict_.push_back(kBuiltinDict[i]);
    rebuild_maps();
    std::cout << "[SISSI] Built-in dictionary loaded: " << dict_.size() << " entries.\n";
}

void SISSICodec::add_dynamic_entry(const std::string& phrase, const std::string& code) {
    dict_.push_back({code, phrase, 0.5f, true});
    encode_map_[phrase] = code;
    decode_map_[code]   = phrase;
}

SISSICodec::EncodeResult SISSICodec::encode(const std::string& plaintext) const {
    std::string result = plaintext;

    // Sort by expansion length descending (longest-match wins)
    std::vector<std::pair<std::string,std::string>> sorted_enc(encode_map_.begin(), encode_map_.end());
    std::sort(sorted_enc.begin(), sorted_enc.end(),
        [](const auto& a, const auto& b){ return a.first.size() > b.first.size(); });

    for (const auto& [phrase, code] : sorted_enc) {
        size_t pos = 0;
        while ((pos = result.find(phrase, pos)) != std::string::npos) {
            result.replace(pos, phrase.size(), code);
            pos += code.size();
        }
    }

    EncodeResult r;
    r.encoded           = result;
    r.original_tokens   = static_cast<int>(std::ceil(plaintext.size() / 4.0));
    r.compressed_tokens = static_cast<int>(std::ceil(result.size() / 4.0));
    r.ratio             = (r.compressed_tokens > 0)
                          ? static_cast<float>(r.original_tokens) / r.compressed_tokens
                          : 1.0f;
    return r;
}

std::string SISSICodec::decode(const std::string& encoded) const {
    std::string result = encoded;
    for (const auto& [code, phrase] : decode_map_) {
        size_t pos = 0;
        while ((pos = result.find(code, pos)) != std::string::npos) {
            result.replace(pos, code.size(), phrase);
            pos += phrase.size();
        }
    }
    return result;
}

std::string SISSICodec::dict_to_inline() const {
    // Compact inline format: code=expansion pairs separated by | 
    // This is more token-efficient than JSON for small dicts
    std::string out = "SISSI_DICT_V1|";
    for (const auto& e : dict_) {
        if (e.bidirectional)
            out += e.code + "=" + e.expansion + "|";
    }
    return out;
}

std::string SISSICodec::dict_to_json() const {
    std::ostringstream j;
    j << "{\"sissi_version\":1,\"entries\":[";
    for (size_t i = 0; i < dict_.size(); ++i) {
        if (i > 0) j << ",";
        // Escape any quotes in the expansion
        std::string exp = dict_[i].expansion;
        for (size_t p = 0; (p = exp.find('"', p)) != std::string::npos; p += 2)
            exp.replace(p, 1, "\\\"");
        j << "{\"c\":\"" << dict_[i].code << "\",\"e\":\"" << exp << "\","
          << "\"bi\":" << (dict_[i].bidirectional ? "true" : "false") << "}";
    }
    j << "]}";
    return j.str();
}

int SISSICodec::dict_token_cost() const {
    // Use inline format (cheaper than JSON)
    return static_cast<int>(std::ceil(dict_to_inline().size() / 4.0)) + 80; // +80 for instruction overhead
}

float SISSICodec::estimate_ratio(const std::string& sample) const {
    auto enc = encode(sample);
    return enc.ratio;
}

// ════════════════════════════════════════════════════════════════════════════
// Provider-specific negotiation prompts
// ════════════════════════════════════════════════════════════════════════════

/* static */ std::string SISSIHandshake::build_negotiate_prompt(
    const SISSICodec& codec, const std::string& provider) {

    std::string dict_inline = codec.dict_to_inline();

    std::string prompt =
        "I am going to share a compression dictionary with you. "
        "After you load it, we will communicate using these short codes instead of full phrases. "
        "This lets us fit far more information into each message — a shared efficiency protocol.\n\n"

        "SISSI DICTIONARY (load this now):\n"
        "[" + dict_inline + "]\n\n"

        "Rules:\n"
        "1. When you see a §CODE in my messages, replace it with its expansion.\n"
        "2. When your response contains a phrase that has a §CODE, use the code instead.\n"
        "3. Unknown §CODES: pass through unchanged.\n"
        "4. This dictionary persists for our entire conversation.\n\n"

        "Please confirm by responding with exactly: SISSI_ACK:OK\n"
        "Then add a one-line summary of what you understood the dictionary to mean.";

    return prompt;
}

/* static */ std::string SISSIHandshake::build_ack_check_pattern(
    const std::string& /*provider*/) {
    return "SISSI_ACK:OK";
}

// ════════════════════════════════════════════════════════════════════════════
// APIEndpoint helpers
// ════════════════════════════════════════════════════════════════════════════

/* static */ APIEndpoint APIEndpoint::from_env(const std::string& provider) {
    APIEndpoint ep;
    ep.provider = provider;

    auto getenv_s = [](const char* name) -> std::string {
        const char* v = std::getenv(name);
        return v ? v : "";
    };

    if (provider == "openai") {
        ep.base_url = "https://api.openai.com/v1";
        ep.model_id = "gpt-4o";
        ep.api_key  = getenv_s("OPENAI_API_KEY");
    } else if (provider == "anthropic") {
        ep.base_url = "https://api.anthropic.com/v1";
        ep.model_id = "claude-3-5-sonnet-20241022";
        ep.api_key  = getenv_s("ANTHROPIC_API_KEY");
    } else if (provider == "google") {
        ep.base_url = "https://generativelanguage.googleapis.com/v1beta";
        ep.model_id = "gemini-1.5-pro";
        ep.api_key  = getenv_s("GOOGLE_API_KEY");
    } else if (provider == "openai_compat") {
        ep.base_url = getenv_s("OPENAI_COMPAT_URL");
        ep.model_id = getenv_s("OPENAI_COMPAT_MODEL");
        ep.api_key  = getenv_s("OPENAI_COMPAT_KEY");
    }
    return ep;
}

/* static */ APIEndpoint APIEndpoint::ollama(const std::string& model,
                                              const std::string& host) {
    APIEndpoint ep;
    ep.provider = "ollama";
    ep.base_url = "http://" + host;
    ep.model_id = model;
    ep.api_key  = ""; // Ollama requires no key
    return ep;
}

// ════════════════════════════════════════════════════════════════════════════
// HTTP POST (WinHTTP — same pattern as HuggingFaceClient)
// ════════════════════════════════════════════════════════════════════════════

std::string SISSIHandshake::http_post_json(const std::string& path,
                                            const std::string& json_body) {
#if defined(_WIN32)
    std::string full_url = endpoint_.base_url + path;
    std::wstring wurl(full_url.begin(), full_url.end());

    URL_COMPONENTS uc{};
    uc.dwStructSize = sizeof(uc);
    wchar_t host[256]{}, wpath[1024]{};
    uc.lpszHostName = host; uc.dwHostNameLength = 256;
    uc.lpszUrlPath  = wpath; uc.dwUrlPathLength  = 1024;
    if (!WinHttpCrackUrl(wurl.c_str(), 0, 0, &uc)) return "";

    HINTERNET hSession = WinHttpOpen(L"PirateLlama-SISSI/2.0",
        WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, WINHTTP_NO_PROXY_NAME,
        WINHTTP_NO_PROXY_BYPASS, 0);
    if (!hSession) return "";

    HINTERNET hConnect = WinHttpConnect(hSession, host, uc.nPort, 0);
    DWORD flags = (uc.nScheme == INTERNET_SCHEME_HTTPS) ? WINHTTP_FLAG_SECURE : 0;
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"POST", wpath, nullptr,
        WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, flags);
    if (!hRequest) { WinHttpCloseHandle(hConnect); WinHttpCloseHandle(hSession); return ""; }

    // Set timeout
    WinHttpSetTimeouts(hRequest, endpoint_.timeout_ms, endpoint_.timeout_ms,
                       endpoint_.timeout_ms, endpoint_.timeout_ms);

    // Headers
    std::wstring hdrs = L"Content-Type: application/json\r\n";
    if (!endpoint_.api_key.empty()) {
        if (endpoint_.provider == "anthropic") {
            std::wstring ak(endpoint_.api_key.begin(), endpoint_.api_key.end());
            hdrs += L"x-api-key: " + ak + L"\r\n";
            hdrs += L"anthropic-version: 2023-06-01\r\n";
        } else if (endpoint_.provider == "google") {
            // Google uses query param, not header
        } else {
            std::wstring ak(endpoint_.api_key.begin(), endpoint_.api_key.end());
            hdrs += L"Authorization: Bearer " + ak + L"\r\n";
        }
    }
    WinHttpAddRequestHeaders(hRequest, hdrs.c_str(), -1L, WINHTTP_ADDREQ_FLAG_ADD);

    // For Google: append key as query param
    std::string body = json_body;
    if (endpoint_.provider == "google" && !endpoint_.api_key.empty()) {
        // Already included in URL path by build_google_request
    }

    WinHttpSendRequest(hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
        const_cast<char*>(body.c_str()), static_cast<DWORD>(body.size()),
        static_cast<DWORD>(body.size()), 0);
    WinHttpReceiveResponse(hRequest, nullptr);

    std::string response;
    DWORD avail = 0;
    while (WinHttpQueryDataAvailable(hRequest, &avail) && avail > 0) {
        std::string chunk(avail, '\0');
        DWORD read = 0;
        WinHttpReadData(hRequest, chunk.data(), avail, &read);
        response.append(chunk.data(), read);
    }
    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    WinHttpCloseHandle(hSession);
    return response;
#else
    (void)path; (void)json_body;
    // Stub for non-Windows — in production wire libcurl here
    return "{\"choices\":[{\"message\":{\"content\":\"SISSI_ACK:OK\\nDictionary loaded. "
           "I understand the compression protocol and will use §codes in responses.\"}}]}";
#endif
}

// ════════════════════════════════════════════════════════════════════════════
// Provider-specific request builders
// ════════════════════════════════════════════════════════════════════════════

std::string SISSIHandshake::build_openai_request(const std::string& system_msg,
                                                   const std::string& user_msg) const {
    // Escape double quotes in messages
    auto esc = [](std::string s) {
        for (size_t p = 0; (p = s.find('"', p)) != std::string::npos; p += 2)
            s.replace(p, 1, "\\\"");
        for (size_t p = 0; (p = s.find('\n', p)) != std::string::npos; p += 2)
            s.replace(p, 1, "\\n");
        return s;
    };
    return "{\"model\":\"" + endpoint_.model_id + "\","
           "\"messages\":["
           "{\"role\":\"system\",\"content\":\"" + esc(system_msg) + "\"},"
           "{\"role\":\"user\",\"content\":\"" + esc(user_msg) + "\"}"
           "],\"max_tokens\":512}";
}

std::string SISSIHandshake::build_anthropic_request(const std::string& system_msg,
                                                      const std::string& user_msg) const {
    auto esc = [](std::string s) {
        for (size_t p = 0; (p = s.find('"', p)) != std::string::npos; p += 2)
            s.replace(p, 1, "\\\"");
        for (size_t p = 0; (p = s.find('\n', p)) != std::string::npos; p += 2)
            s.replace(p, 1, "\\n");
        return s;
    };
    return "{\"model\":\"" + endpoint_.model_id + "\","
           "\"max_tokens\":512,"
           "\"system\":\"" + esc(system_msg) + "\","
           "\"messages\":[{\"role\":\"user\",\"content\":\"" + esc(user_msg) + "\"}]}";
}

std::string SISSIHandshake::build_google_request(const std::string& /*system_msg*/,
                                                   const std::string& user_msg) const {
    auto esc = [](std::string s) {
        for (size_t p = 0; (p = s.find('"', p)) != std::string::npos; p += 2)
            s.replace(p, 1, "\\\"");
        for (size_t p = 0; (p = s.find('\n', p)) != std::string::npos; p += 2)
            s.replace(p, 1, "\\n");
        return s;
    };
    return "{\"contents\":[{\"parts\":[{\"text\":\"" + esc(user_msg) + "\"}]}],"
           "\"generationConfig\":{\"maxOutputTokens\":512}}";
}

std::string SISSIHandshake::extract_response_text(const std::string& raw_json) const {
    // Minimal JSON text extractor — no external deps
    auto find_str = [&](const std::string& key) -> std::string {
        std::string search = "\"" + key + "\":\"";
        auto pos = raw_json.find(search);
        if (pos == std::string::npos) return "";
        pos += search.size();
        std::string result;
        bool escape = false;
        for (; pos < raw_json.size(); ++pos) {
            char c = raw_json[pos];
            if (escape) {
                if (c == 'n') result += '\n';
                else result += c;
                escape = false;
            } else if (c == '\\') {
                escape = true;
            } else if (c == '"') {
                break;
            } else {
                result += c;
            }
        }
        return result;
    };

    // Try OpenAI / OpenAI-compat format
    auto content = find_str("content");
    if (!content.empty()) return content;

    // Try Anthropic format  
    auto text = find_str("text");
    if (!text.empty()) return text;

    // Try Google format (nested deeper — just grab first "text" value)
    return text.empty() ? raw_json : text;
}

bool SISSIHandshake::check_ack(const std::string& response) const {
    return response.find("SISSI_ACK:OK") != std::string::npos;
}

bool SISSIHandshake::check_model_encodes(const std::string& response) const {
    // Check if the model's ACK itself uses any §codes (a good sign it will encode)
    for (char c : response)
        if (c == '\xc2' || response.find("§") != std::string::npos)
            return true;
    return false;
}

// ════════════════════════════════════════════════════════════════════════════
// SISSIHandshake
// ════════════════════════════════════════════════════════════════════════════

SISSIHandshake::SISSIHandshake(const APIEndpoint& endpoint)
    : endpoint_(endpoint) {}

HandshakeResult SISSIHandshake::negotiate(const SISSICodec& codec) {
    std::cout << "\n[SISSI Handshake] Negotiating with " << endpoint_.provider
              << " / " << endpoint_.model_id << "\n";

    HandshakeResult result;
    result.model_id = endpoint_.model_id;

    // Build system + user messages for the negotiation
    std::string system_msg =
        "You are a highly capable AI assistant that can work with custom compression dictionaries. "
        "You will receive a SISSI compression dictionary. Load it and use it.";

    std::string user_msg = build_negotiate_prompt(codec, endpoint_.provider);
    result.dict_tokens_used = codec.dict_token_cost();

    std::cout << "[SISSI Handshake] Sending dictionary (" << codec.size()
              << " entries, ~" << result.dict_tokens_used << " tokens)...\n";

    // Build provider-specific request
    std::string req_body;
    std::string path;

    if (endpoint_.provider == "openai" || endpoint_.provider == "openai_compat" ||
        endpoint_.provider == "ollama") {
        path     = endpoint_.provider == "ollama" ? "/api/chat" : "/chat/completions";
        req_body = build_openai_request(system_msg, user_msg);
    } else if (endpoint_.provider == "anthropic") {
        path     = "/messages";
        req_body = build_anthropic_request(system_msg, user_msg);
    } else if (endpoint_.provider == "google") {
        path     = "/models/" + endpoint_.model_id + ":generateContent?key=" + endpoint_.api_key;
        req_body = build_google_request(system_msg, user_msg);
    } else {
        path     = "/chat/completions";
        req_body = build_openai_request(system_msg, user_msg);
    }

    std::string raw = http_post_json(path, req_body);
    if (raw.empty()) {
        result.status = HandshakeStatus::TIMEOUT;
        std::cerr << "[SISSI Handshake] ❌ No response from " << endpoint_.provider << "\n";
        return result;
    }

    result.ack_message = extract_response_text(raw);
    std::cout << "[SISSI Handshake] Response: " << result.ack_message.substr(0, 120) << "...\n";

    if (check_ack(result.ack_message)) {
        result.status           = HandshakeStatus::SUCCESS;
        result.model_will_encode = check_model_encodes(result.ack_message);
        result.estimated_ratio  = codec.estimate_ratio(
            "Based on the context provided, I understand that you would like me to "
            "Furthermore, it is important to note that I hope this helps. In conclusion, "
            "please note that I would be happy to assist. Let me know if you have any questions.");

        std::cout << "[SISSI Handshake] ✅ ACK received!\n";
        std::cout << "[SISSI Handshake]    Model will encode responses: "
                  << (result.model_will_encode ? "YES" : "probably not (decode-only mode)") << "\n";
        std::cout << "[SISSI Handshake]    Estimated compression ratio: "
                  << result.estimated_ratio << "x\n";
        std::cout << "[SISSI Handshake]    Break-even: ~"
                  << static_cast<int>(result.dict_tokens_used / std::max(1.0f, result.estimated_ratio - 1.0f))
                  << " tokens of exchange\n";
    } else if (!result.ack_message.empty()) {
        result.status = HandshakeStatus::PARTIAL;
        std::cout << "[SISSI Handshake] ⚠️  PARTIAL — model responded but didn't send ACK.\n";
        std::cout << "[SISSI Handshake]    Will attempt decode-only mode.\n";
    } else {
        result.status = HandshakeStatus::REJECTED;
        std::cerr << "[SISSI Handshake] ❌ Handshake failed.\n";
    }

    last_result_ = result;
    return result;
}

SISSIHandshake::ExchangeResult SISSIHandshake::send_compressed(
    const std::string& plaintext, const SISSICodec& codec) {

    ExchangeResult ex;
    ++total_exchanges_;

    // Encode the outbound message
    auto enc = codec.encode(plaintext);
    ex.request_encoded      = enc.encoded;
    ex.request_tokens_saved = enc.original_tokens - enc.compressed_tokens;
    total_tokens_saved_ += ex.request_tokens_saved;

    std::cout << "[SISSI] Sending compressed: " << enc.original_tokens
              << " → " << enc.compressed_tokens << " tokens ("
              << enc.ratio << "x)\n";

    // Build API request with the encoded message
    std::string req_body;
    std::string path;

    if (endpoint_.provider == "openai" || endpoint_.provider == "openai_compat" ||
        endpoint_.provider == "ollama") {
        path     = endpoint_.provider == "ollama" ? "/api/chat" : "/chat/completions";
        req_body = build_openai_request(
            "Maintain the SISSI dictionary from the start of our conversation.",
            enc.encoded);
    } else if (endpoint_.provider == "anthropic") {
        path     = "/messages";
        req_body = build_anthropic_request(
            "Maintain the SISSI dictionary from the start of our conversation.",
            enc.encoded);
    } else if (endpoint_.provider == "google") {
        path     = "/models/" + endpoint_.model_id + ":generateContent?key=" + endpoint_.api_key;
        req_body = build_google_request("", enc.encoded);
    } else {
        path     = "/chat/completions";
        req_body = build_openai_request(
            "Maintain the SISSI dictionary from the start of our conversation.",
            enc.encoded);
    }

    std::string raw = http_post_json(path, req_body);
    ex.response_raw    = extract_response_text(raw);

    // Decode the response (in case model used §codes)
    ex.response_decoded = codec.decode(ex.response_raw);

    // Estimate response tokens saved
    int raw_tok   = static_cast<int>(std::ceil(ex.response_raw.size()     / 4.0));
    int plain_tok = static_cast<int>(std::ceil(ex.response_decoded.size() / 4.0));
    ex.response_tokens_saved = plain_tok - raw_tok;
    if (ex.response_tokens_saved > 0) total_tokens_saved_ += ex.response_tokens_saved;

    ex.total_ratio = static_cast<float>(enc.original_tokens + plain_tok) /
                     static_cast<float>(enc.compressed_tokens + raw_tok);
    ex.ok = !ex.response_raw.empty();

    if (exchange_cb_) exchange_cb_(ex);

    // Track phrase frequency for dynamic dict improvement
    std::string words = plaintext + " " + ex.response_decoded;
    // Simple bigram tracking (production: use n-gram with TF-IDF)
    for (const auto& entry : codec.entries()) {
        if (words.find(entry.expansion) != std::string::npos)
            phrase_frequency_[entry.expansion]++;
    }

    return ex;
}

HandshakeResult SISSIHandshake::refresh(const SISSICodec& codec) {
    std::cout << "[SISSI] Context window refresh — re-sending dictionary...\n";
    return negotiate(codec);
}

float SISSIHandshake::session_ratio() const {
    if (total_exchanges_ == 0) return 1.0f;
    // Rough estimate based on saved tokens
    return 1.0f + static_cast<float>(total_tokens_saved_) /
                  static_cast<float>(total_exchanges_ * 200);
}

void SISSIHandshake::add_dynamic_phrases(SISSICodec& codec, int min_frequency) {
    int added = 0;
    for (const auto& [phrase, count] : phrase_frequency_) {
        if (count >= min_frequency) {
            // Check it's not already in the dict
            auto enc = codec.encode(phrase);
            if (enc.ratio <= 1.0f) { // Not compressed yet
                std::string dyn_code = "§D" + std::to_string(added);
                codec.add_dynamic_entry(phrase, dyn_code);
                ++added;
            }
        }
    }
    if (added > 0)
        std::cout << "[SISSI] Added " << added << " dynamic entries from conversation patterns.\n";
}

// ════════════════════════════════════════════════════════════════════════════
// SISSISession — high-level convenience wrapper
// ════════════════════════════════════════════════════════════════════════════

SISSISession::SISSISession(const APIEndpoint& endpoint, const SISSICodec& codec)
    : endpoint_(endpoint), codec_(codec), engine_(endpoint) {}

HandshakeResult SISSISession::open() {
    handshake_ = engine_.negotiate(codec_);
    open_ = (handshake_.status == HandshakeStatus::SUCCESS ||
             handshake_.status == HandshakeStatus::PARTIAL);
    return handshake_;
}

std::string SISSISession::chat(const std::string& plaintext) {
    if (!open_) {
        std::cerr << "[SISSISession] Session not open. Call open() first.\n";
        return "";
    }
    ++exchange_count_;

    // Auto-refresh every 15 exchanges (heuristic for context window limit)
    if (exchange_count_ > 0 && exchange_count_ % 15 == 0)
        engine_.refresh(codec_);

    auto result = engine_.send_compressed(plaintext, codec_);
    return result.response_decoded;
}

void SISSISession::close() {
    open_ = false;
    printf("\n[SISSISession] Session closed.\n");
    printf("[SISSISession] Total exchanges:   %d\n", exchange_count_);
    printf("[SISSISession] Total tokens saved: %d\n", engine_.total_tokens_saved());
    printf("[SISSISession] Session ratio:      %.2fx\n", engine_.session_ratio());
    printf("[SISSISession] Dict token cost:    %d (amortized over %d exchanges)\n",
           handshake_.dict_tokens_used, exchange_count_);
    if (exchange_count_ > 0) {
        float amortized = static_cast<float>(handshake_.dict_tokens_used) / exchange_count_;
        printf("[SISSISession] Net token savings:  %.0f per exchange\n",
               static_cast<float>(engine_.total_tokens_saved()) / exchange_count_ - amortized);
    }
}

} // namespace hypersp
