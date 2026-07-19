#pragma once
#include "context_compressor.hpp"
#include <string>
#include <vector>

namespace hypersp {

enum class SpinMode {
    HSCC_V2,
    SFS,
    SFS_PLUS
};

class CandySpinner {
public:
    CandySpinner();
    ~CandySpinner() = default;

    // Spin a GGUF file into an HSCC/SFS file
    bool spin(const std::string& input_gguf, const std::string& output_file, SpinMode mode = SpinMode::HSCC_V2);

    // Set the path to a local GGUF model that will act as the autonomous recursive supervisor brain.
    // This embeds the brain's footprint into the spun file so it can self-modify.
    void set_recursive_brain(const std::string& brain_gguf_path);

private:
    // Calculate the entropy (variance) of a euclidean vector to use as the W coordinate
    float calculate_w_entropy(const std::vector<float>& vec) const;
    
    // SISSI engine for vocabulary compression
    ContextCompressor compressor_;
};

} // namespace hypersp
