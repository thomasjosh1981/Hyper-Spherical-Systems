#include "dom_parser.hpp"
#include <regex>
#include <sstream>

namespace pirate {

std::string DomParser::extract_structural_semantics(const std::string& raw_html) const {
    // MVP HTML stripper - for demonstration of structural semantic extraction
    std::string stripped = raw_html;
    
    // Remove <script> tags and content
    stripped = std::regex_replace(stripped, std::regex(R"(<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>)", std::regex_constants::icase), "");
    
    // Remove <style> tags and content
    stripped = std::regex_replace(stripped, std::regex(R"(<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>)", std::regex_constants::icase), "");
    
    // Convert structural blocks to newlines
    stripped = std::regex_replace(stripped, std::regex(R"(<(div|p|h[1-6]|li|tr|br)[^>]*>)", std::regex_constants::icase), "\n");
    
    // Strip all remaining HTML tags
    stripped = std::regex_replace(stripped, std::regex(R"(<[^>]+>)"), "");
    
    // Clean up excessive whitespace and newlines
    stripped = std::regex_replace(stripped, std::regex(R"([ \t]+)"), " ");
    stripped = std::regex_replace(stripped, std::regex(R"(\n\s*\n)"), "\n");
    
    // Trim leading/trailing whitespace
    stripped.erase(0, stripped.find_first_not_of(" \n\r\t"));
    stripped.erase(stripped.find_last_not_of(" \n\r\t") + 1);
    
    return stripped;
}

} // namespace pirate
