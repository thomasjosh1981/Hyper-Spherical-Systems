#pragma once
#include <string>
#include <vector>
#include <cstdint>

namespace hypersp {

class MultimodalEngine {
public:
    MultimodalEngine() = default;
    ~MultimodalEngine() = default;

    // --- Native Voice Endpoints ---
    // Ingests raw audio buffer directly into the SFS+ KV Cache
    bool ingest_audio_stream(const std::vector<uint8_t>& audio_buffer);
    
    // Outputs predicted tokens directly back to synthesized audio
    std::vector<uint8_t> generate_audio_response(const std::string& text_tokens);

    // --- Native Vision Endpoints ---
    // Ingests raw pixel data into the SFS+ model
    bool ingest_image_frame(const std::vector<uint8_t>& rgb_pixels, int width, int height);

private:
    bool is_voice_initialized_ = false;
    bool is_vision_initialized_ = false;
};

} // namespace hypersp
