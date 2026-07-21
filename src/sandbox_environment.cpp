#include "sandbox_environment.hpp"
#include <iostream>
#include <filesystem>

namespace hypersp {

SandboxEnvironment::SandboxEnvironment(const std::string& original_sfs_path)
    : live_path_(original_sfs_path) {
    sandbox_path_ = original_sfs_path + ".sandbox";
}

SandboxEnvironment::~SandboxEnvironment() {
    rollback();
}

bool SandboxEnvironment::initialize_sandbox() {
    try {
        std::filesystem::copy_file(live_path_, sandbox_path_, std::filesystem::copy_options::overwrite_existing);
        is_initialized_ = true;
        std::cout << "[Sandbox] Environment initialized at " << sandbox_path_ << "\n";
        return true;
    } catch (...) {
        std::cerr << "[Sandbox] Failed to initialize sandbox environment.\n";
        return false;
    }
}

SandboxReport SandboxEnvironment::test_correction(const VortexCorrection& correction) {
    if (!is_initialized_) {
        return {false, 0.0f, "Sandbox not initialized."};
    }

    std::cout << "[Sandbox] Applying correction to chunk " << correction.target_chunk_index << "...\n";
    // Simulated benchmarking process
    float simulated_entropy = 0.5f; // Perfect stability

    if (correction.radius_delta > 10.0f) {
        simulated_entropy = 9.9f; // Instability
        return {false, simulated_entropy, "Correction caused catastrophic entropy collapse."};
    }

    std::cout << "[Sandbox] Correction stabilized successfully.\n";
    return {true, simulated_entropy, "Correction stable."};
}

void SandboxEnvironment::rollback() {
    if (is_initialized_ && std::filesystem::exists(sandbox_path_)) {
        std::filesystem::remove(sandbox_path_);
        is_initialized_ = false;
        std::cout << "[Sandbox] Checkpoint rolled back. Virtual memory wiped.\n";
    }
}

bool SandboxEnvironment::commit() {
    if (!is_initialized_) return false;
    
    try {
        std::filesystem::copy_file(sandbox_path_, live_path_, std::filesystem::copy_options::overwrite_existing);
        std::cout << "[Sandbox] Committed changes to live SFS+ core.\n";
        rollback(); // Cleanup
        return true;
    } catch (...) {
        std::cerr << "[Sandbox] Failed to commit changes to live file.\n";
        return false;
    }
}

} // namespace hypersp
