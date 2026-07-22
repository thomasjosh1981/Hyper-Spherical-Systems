// candy_spinner.hpp — v2.0
//
// Hyper-Spherical Systems — CandySpinner (GGUF → HSCC/SFS/SFS+ decomposer)
//
// License: MIT

#pragma once
#include <string>
#include <vector>
#include <functional>
#include <cstdint>
#include <memory>

namespace hypersp {

class ContextCompressor;

enum class SpinMode { HSCC_V2, SFS, SFS_PLUS };

// ── On-disk chunk header (written at the top of every .sfs/.hscc file) ────────
#pragma pack(push, 1)
struct CandyChunkHeader {
    uint32_t magic{0x43435348};      // "HSCC"
    uint16_t version{2};
    uint8_t  is_sfs{0};
    uint8_t  is_sfs_plus{0};
    uint32_t tensor_count{0};
    uint32_t virtual_moe_size{0};   // 0 = disabled; 8 = 8 virtual experts
    float    vram_saturation_target{0.50f};

    // v2.0 capability flags (1 = enabled)
    uint8_t  has_tool_calling{0};
    uint8_t  has_vision{0};
    uint8_t  has_audio{0};
    uint8_t  has_video{0};
    uint8_t  has_persistence{0};
    uint8_t  pipeline_order{0};     // 0 = SISSI first, 1 = HOMOPHONIC first

    // Brain model reference (fixed-length field, NUL-terminated)
    char     brain_model_ref[256]{};

    // Reserved for future use
    uint8_t  _reserved[32]{};
};
#pragma pack(pop)

// ── Progress callback type ────────────────────────────────────────────────────
using SpinProgressCallback = std::function<void(int frame, int pct, const std::string& status)>;

// ── CandySpinner Class ────────────────────────────────────────────────────────
class CandySpinner {
public:
    CandySpinner();
    ~CandySpinner() = default;

    // Feature configuration
    void set_recursive_brain(const std::string& brain_gguf_path);
    void enable_native_vmoe(int expert_count = 8);
    void enable_tool_calling(bool enabled = true);
    void enable_multimodal(bool enabled = true);
    void set_compression_order(const std::string& order);
    void enable_persistence(bool enabled = true);
    void set_progress_callback(SpinProgressCallback cb) { progress_cb_ = std::move(cb); }

    // Core spin action
    bool spin(const std::string& input_gguf,
              const std::string& output_file,
              SpinMode mode = SpinMode::SFS_PLUS);

    // Queries
    int  vmoe_size()  const { return vmoe_size_; }
    bool has_vision() const { return has_vision_; }
    bool has_audio()  const { return has_audio_; }

private:
    float calculate_w_entropy(const std::vector<float>& vec) const;

    std::unique_ptr<ContextCompressor> compressor_;
    SpinProgressCallback progress_cb_;

    std::string brain_model_ref_;
    int         vmoe_size_{0};
    bool        tool_calling_{false};
    bool        has_vision_{false};
    bool        has_audio_{false};
    bool        has_video_{false};
    bool        persistence_{false};
    uint8_t     pipeline_order_{0};
};

} // namespace hypersp
