#pragma once
#include <string>
#include <unordered_map>

namespace hypersp {

// Model-supplied ephemeral abbreviation table.
// Lives only in heap memory — no disk I/O ever touches this.
struct SessionCompressionProfile {
    bool active = false;
    std::string model_id;
    std::string delimiter_open  = "{{";
    std::string delimiter_close = "}}";
    std::unordered_map<std::string, std::string> encode; // full token -> short code
    std::unordered_map<std::string, std::string> decode; // short code -> full token
};

class SessionDictionary {
public:
    SessionDictionary() = default;
    ~SessionDictionary() { destroy(); }

    void load(const SessionCompressionProfile& scp);
    
    // Encode a string using the active SCP (replaces known tokens with short codes)
    std::string encode(const std::string& input) const;
    
    // Decode a string back to natural language
    std::string decode(const std::string& input) const;
    
    bool is_active() const { return profile_.active; }
    
    // Zero-fill and clear all entries — call on session teardown
    void destroy();

private:
    SessionCompressionProfile profile_;
};

} // namespace hypersp
