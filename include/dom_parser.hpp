#pragma once
#include <string>

namespace pirate {

class DomParser {
public:
    DomParser() = default;

    // Strips out scripts, styles, and extracts semantic structure
    // from raw HTML/XML to feed into the context compressor
    std::string extract_structural_semantics(const std::string& raw_html) const;
};

} // namespace pirate
