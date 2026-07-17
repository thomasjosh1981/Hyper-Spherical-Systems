#pragma once
#include "gguf_reader.hpp"
#include "hypersphere.hpp"
#include "types.hpp"
#include "context_compressor.hpp"
#include <string>
#include <vector>

namespace tesseract {

class CandySpinner {
public:
    CandySpinner();
    ~CandySpinner() = default;

    // Spin a GGUF file into an HSCC file
    bool spin(const std::string& input_gguf, const std::string& output_hscc);

private:
    // Calculate the entropy (variance) of a euclidean vector to use as the W coordinate
    float calculate_w_entropy(const std::vector<float>& vec) const;
    
    // SISSI engine for vocabulary compression
    ContextCompressor compressor_;
};

} // namespace tesseract
