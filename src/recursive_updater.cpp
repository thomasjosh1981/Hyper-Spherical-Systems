#include "../include/recursive_updater.hpp"
#include <iostream>
#include <functional>

namespace hypersp {

RecursiveUpdater::RecursiveUpdater(const std::string& sfs_plus_path, const std::string& supervisor_brain_path)
    : sfs_plus_path_(sfs_plus_path), 
      supervisor_brain_path_(supervisor_brain_path),
      sandbox_(sfs_plus_path) {
    
    std::cout << "[RecursiveUpdater] Initialized on " << sfs_plus_path_ 
              << " with brain " << supervisor_brain_path_ << std::endl;
}

bool RecursiveUpdater::process_natural_language_directive(const std::string& directive) {
    std::cout << "[Brain] Processing directive: " << directive << "\n";
    // Simulated NLP parsing
    if (directive.find("fetch") != std::string::npos || directive.find("borrow") != std::string::npos) {
        if (level_ == RecursivenessLevel::MANUAL) {
            std::cout << "[Brain] PAUSED: Requires user approval to fetch from HuggingFace.\n";
            if (consent_callback_) {
                if (!consent_callback_("Fetch missing weights from HuggingFace")) {
                    std::cout << "[Brain] User denied fetch request.\n";
                    return false;
                }
            } else {
                return false;
            }
        }
        std::cout << "[Brain] Searching HuggingFace for missing weights...\n";
        auto models = hf_client_.search_models("optimized context weights");
        if (!models.empty()) {
            std::vector<uint8_t> new_weights;
            hf_client_.stream_weights(models[0].model_id, new_weights);
            
            // Convert HF weights to VortexCorrection and test in sandbox
            VortexCorrection fetch_corr{};
            fetch_corr.radius_delta = 0.5f;
            return apply_correction(fetch_corr);
        }
    }
    return true;
}

bool RecursiveUpdater::evaluate_entropy(float generation_entropy) {
    // Threshold for hallucination/repetition
    if (generation_entropy < 0.1f || generation_entropy > 0.9f) {
        std::cout << "[RecursiveUpdater] Entropy (" << generation_entropy 
                  << ") breached bounds. Supervisor brain analyzing..." << std::endl;
        
        // Simulating the brain computing a correction delta
        VortexCorrection dummy_correction{};
        dummy_correction.target_chunk_index = 0; // The chunk that caused the issue
        dummy_correction.target_coordinate = 0;  
        dummy_correction.radius_delta = -0.05f;  // Dampen the signal
        dummy_correction.phase_shift[0] = 0.01f;
        
        return apply_correction(dummy_correction);
    }
    return true; // No correction needed
}

bool RecursiveUpdater::apply_correction(const VortexCorrection& correction) {
    std::cout << "[RecursiveUpdater] Preparing to test correction in Sandbox.\n";
    if (!sandbox_.initialize_sandbox()) {
        return false;
    }

    SandboxReport report = sandbox_.test_correction(correction);
    if (!report.passed) {
        std::cout << "[RecursiveUpdater] Sandbox rejected correction: " << report.diagnostics << "\n";
        sandbox_.rollback();
        return false;
    }

    std::cout << "[RecursiveUpdater] Sandbox approved correction. Entropy: " << report.final_entropy << "\n";

    if (level_ == RecursivenessLevel::MANUAL) {
        std::cout << "[RecursiveUpdater] PAUSED: Level 0. Requires user approval to commit Sandbox to Live.\n";
        bool approved = false;
        if (consent_callback_) {
            approved = consent_callback_("Commit Sandbox structural changes to Live Tesseract");
        }
        if (!approved) {
            sandbox_.rollback();
            return false;
        }
    }

    if (level_ == RecursivenessLevel::SEMI_AUTONOMOUS && correction.radius_delta > 1.0f) {
        std::cout << "[RecursiveUpdater] PAUSED: Level 1. Major structural shift requires user approval.\n";
        bool approved = false;
        if (consent_callback_) {
            approved = consent_callback_("Commit major structural shift (radius > 1.0) to Live Tesseract");
        }
        if (!approved) {
            sandbox_.rollback();
            return false;
        }
    }

    // Fully Autonomous (Level 2) or safe Level 1
    bool success = sandbox_.commit();
    if (success) {
        current_epoch_++;
    }
    return success;
}

} // namespace hypersp
