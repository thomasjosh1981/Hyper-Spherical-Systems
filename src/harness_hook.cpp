// HarnessHook: integration points into llama.cpp inference pipeline.
// Records layer transitions and triggers weight preload checks.
#include "harness_hook.hpp"
#include <vector>
#include <mutex>

namespace hypersp {

static std::vector<uint32_t> g_pre_history;
static std::vector<uint32_t> g_post_history;

void HarnessHook::on_pre_layer(uint32_t layer_id, size_t byte_size) noexcept {
    (void)byte_size;
    g_pre_history.push_back(layer_id);
}

void HarnessHook::on_post_layer(uint32_t layer_id, size_t byte_size) noexcept {
    (void)byte_size;
    g_post_history.push_back(layer_id);
}

extern "C" {
    const uint32_t* harness_get_pre_history(uint32_t* out_count) {
        if (out_count) *out_count = static_cast<uint32_t>(g_pre_history.size());
        return g_pre_history.data();
    }
    const uint32_t* harness_get_post_history(uint32_t* out_count) {
        if (out_count) *out_count = static_cast<uint32_t>(g_post_history.size());
        return g_post_history.data();
    }
}

// Clear helpers for testing
extern "C" void harness_clear_history(void) {
    g_pre_history.clear();
    g_post_history.clear();
}
} // namespace hypersp
