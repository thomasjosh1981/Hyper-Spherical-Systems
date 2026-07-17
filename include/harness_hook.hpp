#pragma once
#include "types.hpp"
#include <cstdint>

namespace tesseract {

/* Hooks into llama.cpp inference pipeline */
class HarnessHook {
public:
    HarnessHook() = default;
    ~HarnessHook()  = default;

    /** Called before each forward pass layer — triggers weight preload check */
    void on_pre_layer(uint32_t layer_id, size_t byte_size) noexcept;
    
    /** Called after forward pass completes — triggers VRAM eviction check */
    void on_post_layer(uint32_t layer_id, size_t byte_size) noexcept;
};

} // namespace tesseract
