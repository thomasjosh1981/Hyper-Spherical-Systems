#include "mnecp_handshake.hpp"
#include <iostream>
#include <sstream>

namespace hypersp {

std::string MnecpHandshake::build_negotiation_payload(const std::string& original_user_message) const {
    return std::string(MNECP_NEGOTIATION_NOTE) + "\n" + original_user_message;
}

std::string MnecpHandshake::extract_json(const std::string& text) const {
    size_t start = text.find('{');
    size_t end   = text.rfind('}');
    if (start == std::string::npos || end == std::string::npos || end <= start)
        return "";
    return text.substr(start, end - start + 1);
}

SessionCompressionProfile MnecpHandshake::parse_response(const std::string& model_response) const {
    SessionCompressionProfile scp;
    std::string json = extract_json(model_response);

    if (json.empty()) {
        std::cout << "[MNECP] No JSON found in model response. Using fallback.\n";
        return scp;
    }

    // Check for decline
    if (json.find("\"accept\": false") != std::string::npos ||
        json.find("\"accept\":false") != std::string::npos) {
        std::cout << "[MNECP] Model declined negotiation. Using SiSSi fallback.\n";
        return scp;
    }

    // Check for accept
    if (json.find("\"accept\": true") == std::string::npos &&
        json.find("\"accept\":true") == std::string::npos) {
        std::cout << "[MNECP] Ambiguous response. Using fallback.\n";
        return scp;
    }

    // Parse delimiter_open / delimiter_close
    auto extract_str_field = [&](const std::string& key) -> std::string {
        size_t kp = json.find("\"" + key + "\"");
        if (kp == std::string::npos) return "";
        size_t colon = json.find(':', kp);
        size_t q1 = json.find('"', colon + 1);
        size_t q2 = json.find('"', q1 + 1);
        if (q1 == std::string::npos || q2 == std::string::npos) return "";
        return json.substr(q1 + 1, q2 - q1 - 1);
    };

    std::string delim_open  = extract_str_field("delimiter_open");
    std::string delim_close = extract_str_field("delimiter_close");
    if (!delim_open.empty())  scp.delimiter_open  = delim_open;
    if (!delim_close.empty()) scp.delimiter_close = delim_close;

    // Parse the table block — naive key:value scan
    size_t table_start = json.find("\"table\"");
    size_t table_brace = json.find('{', table_start);
    size_t table_end   = json.find('}', table_brace + 1);
    if (table_start != std::string::npos && table_brace != std::string::npos) {
        std::string table_block = json.substr(table_brace + 1, table_end - table_brace - 1);
        std::istringstream iss(table_block);
        std::string token;
        while (std::getline(iss, token, ',')) {
            size_t colon = token.find(':');
            if (colon == std::string::npos) continue;
            auto trim_quotes = [](std::string s) {
                size_t a = s.find('"');
                size_t b = s.rfind('"');
                if (a == b || a == std::string::npos) return s;
                return s.substr(a + 1, b - a - 1);
            };
            std::string full = trim_quotes(token.substr(0, colon));
            std::string code = trim_quotes(token.substr(colon + 1));
            if (!full.empty() && !code.empty()) {
                scp.encode[full] = code;
                scp.decode[code] = full;
            }
        }
    }

    scp.active = true;
    std::cout << "[MNECP] Negotiation successful. "
              << scp.encode.size() << " compression entries loaded.\n";
    return scp;
}

} // namespace hypersp
