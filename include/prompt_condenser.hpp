#pragma once
#include <string>
#include <vector>

namespace pirate {

struct CondensationResult {
    std::string rewritten_prompt;
    float savings_pct; // e.g., 0.15 for 15% saved
    bool modified;
};

class PromptCondenser {
public:
    PromptCondenser() = default;

    // Identifies repeated phrases and compresses them into a factored form
    CondensationResult condense(const std::string& input);

private:
    std::vector<std::string> tokenize(const std::string& input);
};

} // namespace pirate
