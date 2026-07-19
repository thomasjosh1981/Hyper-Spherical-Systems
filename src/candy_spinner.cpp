#include "candy_spinner.hpp"
#include "gguf_reader.hpp"
#include "../include/hypersphere.hpp"
#include "types.hpp"
#include <iostream>

#include <fstream>
#include <cmath>
#include <numeric>

namespace hypersp {

CandySpinner::CandySpinner() {
}

float CandySpinner::calculate_w_entropy(const std::vector<float>& vec) const {
    if (vec.empty()) return 0.0f;
    
    // Calculate mean
    float sum = std::accumulate(vec.begin(), vec.end(), 0.0f);
    float mean = sum / vec.size();
    
    // Calculate variance
    float variance = 0.0f;
    for (float v : vec) {
        variance += (v - mean) * (v - mean);
    }
    variance /= vec.size();
    
    // The higher the variance, the higher the "entropy" or semantic weight.
    // We normalize it through a sigmoid-like function to keep it bounded [0, 1].
    return 1.0f / (1.0f + std::exp(-variance));
}

bool CandySpinner::spin(const std::string& input_gguf, const std::string& output_file, SpinMode mode) {
    GGUFReader reader(input_gguf);
    if (!reader.is_valid()) {
        std::cerr << "[CandySpinner] Failed to read GGUF: " << input_gguf << std::endl;
        return false;
    }

    std::ofstream out(output_file, std::ios::binary);
    if (!out) {
        std::cerr << "[CandySpinner] Failed to create output file: " << output_file << std::endl;
        return false;
    }

    const auto& tensors = reader.tensors();
    
    // Build and write header
    CandyChunkHeader header;
    header.magic = 0x43435348; // "HSCC"
    header.version = 2; // Version 2 implies Counter-Rotating Bladed Vortex Compression
    
    // SFS configurations
    header.is_sfs = (mode == SpinMode::SFS || mode == SpinMode::SFS_PLUS) ? 1 : 0;
    header.is_sfs_plus = (mode == SpinMode::SFS_PLUS) ? 1 : 0;
    header.virtual_moe_size = header.is_sfs ? 8 : 0; // Defaulting to 8 virtual experts for SFS
    
    // Count how many F32 tensors we actually spin
    uint32_t spin_count = 0;
    for (const auto& t : tensors) {
        if (t.type == GGUFType::F32) spin_count++;
    }
    
    header.tensor_count = spin_count;
    // Base target for breathing saturation. MemoryManager uses this as a baseline to start evicting.
    header.vram_saturation_target = 0.50f; 
    
    out.write(reinterpret_cast<const char*>(&header), sizeof(header));

    size_t total_elements_spun = 0;

    for (const auto& t : tensors) {
        if (t.type != GGUFType::F32) continue; // Skip non-F32 for now
        
        std::vector<float> eucl_data = reader.read_tensor_f32(t);
        if (eucl_data.empty()) continue;

        // SISSI-Native Embedding Model logic
        if (!reader.tokens().empty()) {
            size_t n_vocab = reader.tokens().size();
            size_t n_embd = eucl_data.size() / n_vocab;
            
            // Check if this tensor's first dimension matches the vocabulary size (token_embd, output, etc.)
            if (n_vocab * n_embd == eucl_data.size() && n_embd > 0) {
                const size_t SISSI_VOCAB_SIZE = 384;
                std::vector<float> new_embed(SISSI_VOCAB_SIZE * n_embd, 0.0f);
                std::vector<int> counts(SISSI_VOCAB_SIZE, 0);

                for (size_t i = 0; i < n_vocab; i++) {
                    std::vector<KVCachedEntry> entries = compressor_.compress(reader.tokens()[i]);
                    if (entries.empty()) continue;
                    
                    // Take primary SISSI code
                    auto& entry = entries[0];
                    size_t sissi_idx = entry.is_compressed ? entry.dict_code : (256 + (entry.dict_code & 0x7F));
                    if (sissi_idx >= SISSI_VOCAB_SIZE) sissi_idx = 0; // fallback

                    for (size_t d = 0; d < n_embd; d++) {
                        new_embed[sissi_idx * n_embd + d] += eucl_data[i * n_embd + d];
                    }
                    counts[sissi_idx]++;
                }

                // Average the embeddings
                for (size_t i = 0; i < SISSI_VOCAB_SIZE; i++) {
                    if (counts[i] > 0) {
                        for (size_t d = 0; d < n_embd; d++) {
                            new_embed[i * n_embd + d] /= counts[i];
                        }
                    }
                }
                
                std::cout << "[CandySpinner] Remapped " << n_vocab << " embeddings -> " << SISSI_VOCAB_SIZE << " SISSI-native embeddings.\n";
                eucl_data = std::move(new_embed);
            }
        }

        // Calculate full tensor entropy for W binding
        float w_entropy = calculate_w_entropy(eucl_data);

        // We pack the Euclidean space into 4D hyperspheres.
        // E.g. every 4 floats becomes a 4D coordinate.
        // We pad with zeros if not divisible by 4.
        size_t padded_size = eucl_data.size();
        while (padded_size % 4 != 0) padded_size++;
        eucl_data.resize(padded_size, 0.0f);

        uint32_t num_hs_coords = static_cast<uint32_t>(padded_size / 4);

        // Write Tensor Header
        uint32_t name_len = static_cast<uint32_t>(t.name.size());
        out.write(reinterpret_cast<const char*>(&name_len), sizeof(name_len));
        out.write(t.name.c_str(), name_len);
        
        out.write(reinterpret_cast<const char*>(&num_hs_coords), sizeof(num_hs_coords));
        out.write(reinterpret_cast<const char*>(&w_entropy), sizeof(w_entropy));

        // Spin into 4D Hypersphere with Counter-Rotating Bladed Vortex Compression
        uint32_t chunk_idx = 0;
        for (size_t i = 0; i < eucl_data.size(); i += 4) {
            std::vector<float> chunk4 = { eucl_data[i], eucl_data[i+1], eucl_data[i+2], eucl_data[i+3] };
            
            // Map to Hyperspherical
            HypersphereCoordinate hc = HypersphereMath::cartesian_to_hyperspherical(chunk4);
            
            // Apply Vortex Phase Shift
            float phase_shift = 0.05f * static_cast<float>(chunk_idx);
            if (chunk_idx % 2 != 0) {
                phase_shift = -phase_shift; // Counter-rotating stream
            }
            
            // Compress into blades
            auto vc = HypersphereMath::compress_vortex(hc, phase_shift);
            
            // Write Radius (1 float)
            out.write(reinterpret_cast<const char*>(&vc.radius), sizeof(vc.radius));
            // Write Bladed Angles (uint16_t for 3 dimensions in 4D)
            uint16_t angles[3] = {0, 0, 0};
            if (vc.bladed_angles.size() >= 1) angles[0] = vc.bladed_angles[0];
            if (vc.bladed_angles.size() >= 2) angles[1] = vc.bladed_angles[1];
            if (vc.bladed_angles.size() >= 3) angles[2] = vc.bladed_angles[2];
            
            out.write(reinterpret_cast<const char*>(angles), sizeof(angles));
            chunk_idx++;
        }
        
        total_elements_spun += num_hs_coords;
    }

    return true;
}

void CandySpinner::set_recursive_brain(const std::string& brain_gguf_path) {
    // Stub for now. 
    // In the future this will load the specified brain model into the output stream 
    // header so it can be used for runtime optimization without relying on external libraries.
    std::cout << "[INFO] Configured Local Recursive Supervisor Brain: " << brain_gguf_path << "\n";
}

} // namespace hypersp
