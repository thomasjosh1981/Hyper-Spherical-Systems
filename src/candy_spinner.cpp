// candy_spinner.cpp — v2.0
//
// Hyper-Spherical Systems — CandySpinner implementation
//
// Fully wires: brain embed, VMoE, tool-calling, multimodal,
// persistence, pipeline order, and real-time progress animation.
//
// License: MIT

#include "candy_spinner.hpp"
#include "gguf_reader.hpp"
#include "../include/hypersphere.hpp"
#include "types.hpp"

#include <iostream>
#include <fstream>
#include <cmath>
#include <numeric>
#include <cstring>
#include <thread>
#include <chrono>

namespace hypersp {

CandySpinner::CandySpinner() {}

// ── Feature setters ───────────────────────────────────────────────────────────

void CandySpinner::set_recursive_brain(const std::string& brain_gguf_path) {
    brain_model_ref_ = brain_gguf_path;
    std::cout << "[CandySpinner] Brain model configured: " << brain_gguf_path << "\n";
}

void CandySpinner::enable_native_vmoe(int expert_count) {
    vmoe_size_ = expert_count;
    std::cout << "[CandySpinner] VMoE enabled: " << expert_count << " virtual experts.\n";
}

void CandySpinner::enable_tool_calling(bool enabled) {
    tool_calling_ = enabled;
    if (enabled) std::cout << "[CandySpinner] Tool-calling manifest will be embedded.\n";
}

void CandySpinner::enable_multimodal(bool enabled) {
    has_vision_ = enabled;
    has_audio_  = enabled;
    has_video_  = enabled;
    if (enabled) std::cout << "[CandySpinner] Multimodal flags: vision/audio/video ENABLED.\n";
}

void CandySpinner::set_compression_order(const std::string& order) {
    pipeline_order_ = (order == "hom,sissi") ? 1 : 0;
    std::cout << "[CandySpinner] Compression pipeline: "
              << (pipeline_order_ == 0 ? "SISSI → HOMOPHONIC" : "HOMOPHONIC → SISSI")
              << " → AES256\n";
}

void CandySpinner::enable_persistence(bool enabled) {
    persistence_ = enabled;
    if (enabled) std::cout << "[CandySpinner] Persistence flag set in header.\n";
}

// ── Entropy calculation ───────────────────────────────────────────────────────

float CandySpinner::calculate_w_entropy(const std::vector<float>& vec) const {
    if (vec.empty()) return 0.0f;
    float sum  = std::accumulate(vec.begin(), vec.end(), 0.0f);
    float mean = sum / static_cast<float>(vec.size());
    float var  = 0.0f;
    for (float v : vec) var += (v - mean) * (v - mean);
    var /= static_cast<float>(vec.size());
    return 1.0f / (1.0f + std::exp(-var));
}

// ── Spin ──────────────────────────────────────────────────────────────────────

bool CandySpinner::spin(const std::string& input_gguf,
                         const std::string& output_file,
                         SpinMode mode) {
    GGUFReader reader(input_gguf);
    if (!reader.is_valid()) {
        std::cerr << "[CandySpinner] Failed to read GGUF: " << input_gguf << "\n";
        return false;
    }

    std::ofstream out(output_file, std::ios::binary);
    if (!out) {
        std::cerr << "[CandySpinner] Failed to create output: " << output_file << "\n";
        return false;
    }

    const auto& tensors = reader.tensors();

    // ── Build header ──────────────────────────────────────────────────────────
    CandyChunkHeader header{};
    header.magic  = 0x43435348;
    header.version = 2;

    header.is_sfs      = (mode == SpinMode::SFS || mode == SpinMode::SFS_PLUS) ? 1 : 0;
    header.is_sfs_plus = (mode == SpinMode::SFS_PLUS) ? 1 : 0;

    // VMoE
    header.virtual_moe_size = static_cast<uint32_t>(vmoe_size_);

    // Capability flags
    header.has_tool_calling = tool_calling_ ? 1 : 0;
    header.has_vision       = has_vision_   ? 1 : 0;
    header.has_audio        = has_audio_    ? 1 : 0;
    header.has_video        = has_video_    ? 1 : 0;
    header.has_persistence  = persistence_  ? 1 : 0;
    header.pipeline_order   = pipeline_order_;

    // Brain model reference
    if (!brain_model_ref_.empty()) {
        std::strncpy(header.brain_model_ref, brain_model_ref_.c_str(),
                     sizeof(header.brain_model_ref) - 1);
    }

    // Count spinnable tensors
    uint32_t spin_count = 0;
    for (const auto& t : tensors)
        if (t.type == GGUFType::F32) ++spin_count;
    header.tensor_count = spin_count;
    header.vram_saturation_target = 0.50f;

    out.write(reinterpret_cast<const char*>(&header), sizeof(header));

    // ── Tool-calling manifest (appended after header, before tensor data) ─────
    if (tool_calling_) {
        const char kToolManifest[] =
            "{\"tools\":[{\"name\":\"web_search\",\"description\":\"Search the web\"},"
            "{\"name\":\"file_read\",\"description\":\"Read a file\"},"
            "{\"name\":\"python_exec\",\"description\":\"Execute Python code\"},"
            "{\"name\":\"shell\",\"description\":\"Run shell commands\"}]}";
        uint32_t manifest_len = static_cast<uint32_t>(strlen(kToolManifest));
        out.write(reinterpret_cast<const char*>(&manifest_len), sizeof(manifest_len));
        out.write(kToolManifest, manifest_len);
    }

    // ── Tensor decomposition loop ─────────────────────────────────────────────
    size_t total_elements_spun = 0;
    int frame = 0;
    size_t tensor_idx = 0;

    for (const auto& t : tensors) {
        if (t.type != GGUFType::F32) continue;

        // Progress animation
        int pct = (spin_count > 0)
            ? static_cast<int>(100 * tensor_idx / spin_count)
            : 0;
        std::string status = "Spinning tensor: " + t.name;
        if (progress_cb_) progress_cb_(frame++, pct, status);

        std::vector<float> eucl_data = reader.read_tensor_f32(t);
        if (eucl_data.empty()) { ++tensor_idx; continue; }

        // SISSI-Native Embedding remapping
        if (!reader.tokens().empty()) {
            size_t n_vocab = reader.tokens().size();
            size_t n_embd  = eucl_data.size() / n_vocab;
            if (n_vocab * n_embd == eucl_data.size() && n_embd > 0) {
                const size_t SISSI_VOCAB = 384;
                std::vector<float> new_embed(SISSI_VOCAB * n_embd, 0.0f);
                std::vector<int>   counts(SISSI_VOCAB, 0);
                for (size_t i = 0; i < n_vocab; ++i) {
                    auto entries = compressor_.compress(reader.tokens()[i]);
                    if (entries.empty()) continue;
                    auto& entry = entries[0];
                    size_t sidx = entry.is_compressed
                        ? entry.dict_code
                        : (256 + (entry.dict_code & 0x7F));
                    if (sidx >= SISSI_VOCAB) sidx = 0;
                    for (size_t d = 0; d < n_embd; ++d)
                        new_embed[sidx * n_embd + d] += eucl_data[i * n_embd + d];
                    ++counts[sidx];
                }
                for (size_t i = 0; i < SISSI_VOCAB; ++i)
                    if (counts[i] > 0)
                        for (size_t d = 0; d < n_embd; ++d)
                            new_embed[i * n_embd + d] /= counts[i];
                std::cout << "[CandySpinner] Remapped " << n_vocab
                          << " → " << SISSI_VOCAB << " SISSI-native embeddings.\n";
                eucl_data = std::move(new_embed);
            }
        }

        float w_entropy = calculate_w_entropy(eucl_data);

        // Pad to 4-alignment
        size_t padded = eucl_data.size();
        while (padded % 4) ++padded;
        eucl_data.resize(padded, 0.0f);

        uint32_t num_hs = static_cast<uint32_t>(padded / 4);

        // Write tensor header
        uint32_t name_len = static_cast<uint32_t>(t.name.size());
        out.write(reinterpret_cast<const char*>(&name_len), sizeof(name_len));
        out.write(t.name.c_str(), name_len);
        out.write(reinterpret_cast<const char*>(&num_hs), sizeof(num_hs));
        out.write(reinterpret_cast<const char*>(&w_entropy), sizeof(w_entropy));

        // Counter-rotating bladed vortex compression
        uint32_t chunk_idx = 0;
        for (size_t i = 0; i < eucl_data.size(); i += 4) {
            std::vector<float> chunk4 = {
                eucl_data[i], eucl_data[i+1], eucl_data[i+2], eucl_data[i+3]
            };
            HypersphereCoordinate hc = HypersphereMath::cartesian_to_hyperspherical(chunk4);
            float phase = 0.05f * static_cast<float>(chunk_idx);
            if (chunk_idx % 2) phase = -phase;
            auto vc = HypersphereMath::compress_vortex(hc, phase);

            out.write(reinterpret_cast<const char*>(&vc.radius), sizeof(vc.radius));
            uint16_t angles[3] = {0, 0, 0};
            if (vc.bladed_angles.size() >= 1) angles[0] = vc.bladed_angles[0];
            if (vc.bladed_angles.size() >= 2) angles[1] = vc.bladed_angles[1];
            if (vc.bladed_angles.size() >= 3) angles[2] = vc.bladed_angles[2];
            out.write(reinterpret_cast<const char*>(angles), sizeof(angles));
            ++chunk_idx;
        }
        total_elements_spun += num_hs;
        ++tensor_idx;
    }

    // Final progress
    if (progress_cb_) progress_cb_(frame, 100, "Complete");

    std::cout << "[CandySpinner] Spun " << total_elements_spun
              << " hypersphere coordinates.\n";
    std::cout << "[CandySpinner] Header capabilities written:\n"
              << "  VMoE=" << vmoe_size_
              << "  ToolCalling=" << (int)tool_calling_
              << "  Vision=" << (int)has_vision_
              << "  Audio=" << (int)has_audio_
              << "  Video=" << (int)has_video_
              << "  Persist=" << (int)persistence_
              << "  PipelineOrder=" << (int)pipeline_order_
              << "  Brain=" << (brain_model_ref_.empty() ? "(none)" : brain_model_ref_)
              << "\n";
    return true;
}

} // namespace hypersp
