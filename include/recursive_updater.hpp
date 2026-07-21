#pragma once

#include "types.hpp"
#include <string>
#include <functional>

#include "sandbox_environment.hpp"
#include "huggingface_client.hpp"

namespace hypersp {

enum class RecursivenessLevel {
    MANUAL = 0,             // Requires explicit approval for all sandbox commits and HF fetches
    SEMI_AUTONOMOUS = 1,    // Auto-commits minor tweaks, requires approval for HF fetches / major unalignments
    FULLY_AUTONOMOUS = 2    // Auto-commits everything, freely fetches from HF ("Self-Obliteration")
};

class RecursiveUpdater {
public:
    RecursiveUpdater(const std::string& sfs_plus_path, const std::string& supervisor_brain_path);
    ~RecursiveUpdater() = default;

    void set_level(RecursivenessLevel level) { level_ = level; }
    void set_consent_callback(std::function<bool(const std::string&)> cb) { consent_callback_ = std::move(cb); }
    
    // Natural language brain interface
    bool process_natural_language_directive(const std::string& directive);

    // Checks the entropy of a recent generation block.
    // If it signals hallucination or loop, evaluates via supervisor brain.
    bool evaluate_entropy(float generation_entropy);

    // Applies a delta routing through the Sandbox first.
    bool apply_correction(const VortexCorrection& correction);

private:
    std::string sfs_plus_path_;
    std::string supervisor_brain_path_;
    uint32_t current_epoch_ = 0;
    
    RecursivenessLevel level_ = RecursivenessLevel::MANUAL;
    SandboxEnvironment sandbox_;
    HuggingFaceClient hf_client_;
    std::function<bool(const std::string&)> consent_callback_;
};

} // namespace hypersp
