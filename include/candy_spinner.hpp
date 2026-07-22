// candy_spinner.hpp — v2.0
//
// Hyper-Spherical Systems — CandySpinner (GGUF → HSCC/SFS/SFS+ decomposer)
//
// New in v2.0:
//   - enable_native_vmoe()     Wire VMoE expert count into SFS header
//   - enable_tool_calling()    Embed tool-manifest section
//   - enable_multimodal()      Set vision/audio/video capability bits
//   - set_compression_order()  Store SISSI/Homophonic pipeline order in header
//   - enable_persistence()     Set persistence flag in SFS header
//   - set_progress_callback()  Real-time animation / progress reporting
//   - vmoe_size()              Query configured VMoE expert count
//
// License: MIT

#pragma once
#include "context_compressor.hpp"
#include <string>
#include <vector>
#include <functional>
#include <cstdint>

namespace hypersp {

enum class SpinMode { HSCC_V2, SFS, SFS_PLUS };

// ── On-disk chunk header (written at the top of every .sfs/.hscc file) ────────
// MUST remain POD and layout-stable across versions.
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

// Layout: 4+2+1+1+4+4+4+1+1+1+1+1+1+256+32 = 314 bytes (packed)
// If you add fields: bump version to 3 and update both reader and writer.

// ── Progress callback type ────────────────────────────────────────────────────
// frame: animation frame index (0..N)
// pct:   0-100 progress
// status: human-readable status string
using SpinProgressCallback = std::function<void(int frame, int pct, const std::string& status)>;

// ── CandySpinner ──────────────────────────────────────────────────────────────
class CandySpinner {
public:
    CandySpinner();
    ~CandySpinner() = default;

    // ── Core Spin ────────────────────────────────────────────────────────────
    // Transforms a standard GGUF into HSCC/SFS format.
    // Calls progress_cb_ at regular intervals during processing.
    bool spin(const std::string& input_gguf,
              const std::string& output_file,
              SpinMode mode = SpinMode::HSCC_V2);

    // ── Brain Model ──────────────────────────────────────────────────────────
    // Embeds the brain model reference into the SFS header.
    // Accepts a local path OR "hf://<repo-id>" for a HuggingFace brain.
    void set_recursive_brain(const std::string& brain_gguf_path);

    // ── SFS Capability Flags ─────────────────────────────────────────────────
    void enable_native_vmoe(int expert_count);   // e.g. 8 virtual experts
    void enable_tool_calling(bool enabled);
    void enable_multimodal(bool enabled);         // sets vision + audio + video
    void set_compression_order(const std::string& order); // "sissi,hom" or "hom,sissi"
    void enable_persistence(bool enabled);

    // ── Progress Animation ───────────────────────────────────────────────────
    void set_progress_callback(SpinProgressCallback cb) {
        progress_cb_ = std::move(cb);
    }

    // ── Queries ──────────────────────────────────────────────────────────────
    int  vmoe_size()  const { return vmoe_size_; }
    bool has_vision() const { return has_vision_; }
    bool has_audio()  const { return has_audio_; }

private:
    float calculate_w_entropy(const std::vector<float>& vec) const;

    ContextCompressor     compressor_;
    SpinProgressCallback  progress_cb_;

    // Feature flags written into the header
    std::string brain_model_ref_;
    int         vmoe_size_{0};
    bool        tool_calling_{false};
    bool        has_vision_{false};
    bool        has_audio_{false};
    bool        has_video_{false};
    bool        persistence_{false};
    uint8_t     pipeline_order_{0}; // 0=SISSI-first, 1=HOM-first
};

} // namespace hypersp
