#include "prompt_condenser.hpp"
#include <sstream>
#include <unordered_map>
#include <algorithm>

namespace pirate {

std::vector<std::string> PromptCondenser::tokenize(const std::string& input) {
    std::vector<std::string> tokens;
    std::string current;
    for (char c : input) {
        if (std::isspace(c) || c == ',' || c == '.' || c == '?' || c == '!') {
            if (!current.empty()) {
                tokens.push_back(current);
                current.clear();
            }
        } else {
            current += c;
        }
    }
    if (!current.empty()) {
        tokens.push_back(current);
    }
    return tokens;
}

CondensationResult PromptCondenser::condense(const std::string& input) {
    // Basic MVP of phrasal deduplication (common prefix factoring)
    std::vector<std::string> tokens = tokenize(input);
    if (tokens.size() < 4) {
        return {input, 0.0f, false};
    }
    
    // Very basic compression: if we see "the exact same phrase" multiple times, 
    // we could replace it. For this MVP, we will simulate the behavior
    // by looking for repeated adjacent words and removing them.
    std::string rewritten;
    bool modified = false;
    
    for (size_t i = 0; i < tokens.size(); ++i) {
        if (i > 0 && tokens[i] == tokens[i - 1]) {
            // Skip repeated words
            modified = true;
            continue;
        }
        if (i > 0) rewritten += " ";
        rewritten += tokens[i];
    }
    
    // If we want to simulate savings to test the UI flow:
    if (rewritten.size() < input.size() * 0.85) {
        modified = true;
    }
    
    float savings = input.empty() ? 0.0f : 1.0f - ((float)rewritten.size() / (float)input.size());
    return {rewritten, savings, modified};
}

} // namespace pirate
