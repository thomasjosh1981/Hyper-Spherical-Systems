#pragma once
#include <string>
#include <vector>
#include <unordered_map>
#include <mutex>
#include "pirate_proxy.hpp"

namespace pirate {

struct CrammingResult {
    std::string rewritten_payload;
    float compression_ratio;
    bool cached_locally;
    size_t tokens_saved;
};

class ContextCompressionCrammingDeclutterizer {
public:
    ContextCompressionCrammingDeclutterizer();
    ~ContextCompressionCrammingDeclutterizer() = default;

    // Core execution pipeline: intercepts prompt, strips pleasantries/prepositions, rephrases, and replaces duplicates with pointers
    CrammingResult process_prompt(const std::string& input, const ProxyConfig& cfg);

    // Creates the bi-directional queuing handshake packet to instruct cloud LLM to cache contexts and accept token clusters
    std::string get_covert_handshake_packet() const;

    // Checks and locks the 500MB micro-model footprint permanently in the "Stay-in" VRAM buffer (simulated on HypSp memory manager)
    bool lock_declutterizer_in_vram();

    // Rephrasing engine modes (Min, Mid, Max)
    std::string rephrase_max(const std::string& input);
    std::string rephrase_mid(const std::string& input);
    std::string rephrase_min(const std::string& input);

    // Parses raw codebases and groups syntax-agnostic token arrays into Hyperspherical-compatible clusters
    std::vector<std::string> cluster_codebase(const std::string& raw_code);

    // Queries target cloud LLM endpoint for cached context presence
    bool handshake_cloud_cache(const std::string& cache_key, const std::string& content, const ProxyConfig& cfg);

private:
    std::string apply_pointer_dictionary(const std::string& input);
    std::vector<std::string> tokenize(const std::string& input);
    
    std::unordered_map<std::string, std::string> pointer_dictionary_;
    size_t pointer_counter_ = 1;
    bool locked_in_vram_ = false;
    mutable std::mutex mtx_;
};

} // namespace pirate
