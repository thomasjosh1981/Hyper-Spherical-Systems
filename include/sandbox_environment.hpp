#pragma once
#include <string>
#include "types.hpp"

namespace hypersp {

struct SandboxReport {
    bool passed;
    float final_entropy;
    std::string diagnostics;
};

class SandboxEnvironment {
public:
    SandboxEnvironment(const std::string& original_sfs_path);
    ~SandboxEnvironment();

    // Copies current state into a virtualized block for isolated testing
    bool initialize_sandbox();

    // Applies a change in the sandbox and benchmarks the entropy
    SandboxReport test_correction(const VortexCorrection& correction);

    // If sandbox crashes or hallucinates, wipe the virtual block
    void rollback();

    // Commit sandbox changes back to the main file
    bool commit();

private:
    std::string live_path_;
    std::string sandbox_path_;
    bool is_initialized_ = false;
};

} // namespace hypersp
