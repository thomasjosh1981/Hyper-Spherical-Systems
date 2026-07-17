#pragma once
#include <string>
#include <vector>
#include <cstdint>

namespace tesseract {

struct StripeConfig {
    size_t active_stripes = 4;
    size_t decoy_files = 2;
    std::string base_path;
    std::string harness_mirror_dir;
};

class StripeIO {
public:
    explicit StripeIO(const StripeConfig& cfg);

    // Writes data striped across active files, creating decoys alongside them
    bool write_striped(const std::vector<uint8_t>& data);

    // Reads data back from the active stripes losslessly
    bool read_striped(std::vector<uint8_t>& out_data);

private:
    StripeConfig config_;
    std::vector<std::string> active_paths_;
    std::vector<std::string> decoy_paths_;

    void generate_file_paths();
};

} // namespace tesseract
