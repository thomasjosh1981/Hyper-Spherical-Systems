#include "../include/hypersphere.hpp"

namespace hypersp {

HypersphereCoordinate HypersphereMath::cartesian_to_hyperspherical(const std::vector<float>& vec) {
    if (vec.empty()) return HypersphereCoordinate();
    
    size_t n = vec.size();
    std::vector<float> angles(n - 1, 0.0f);
    
    float r_sq = 0.0f;
    for (float v : vec) r_sq += v * v;
    float radius = std::sqrt(r_sq);
    
    if (radius <= 1e-7f) {
        return HypersphereCoordinate(angles, 0.0f);
    }
    
    float current_r_sq = r_sq;
    for (size_t i = 0; i < n - 1; ++i) {
        float x_i = vec[i];
        float cur_r = std::sqrt(current_r_sq);
        
        if (cur_r <= 1e-7f) {
            angles[i] = 0.0f;
        } else {
            angles[i] = std::acos(x_i / cur_r);
        }
        
        current_r_sq -= x_i * x_i;
        if (current_r_sq < 0.0f) current_r_sq = 0.0f;
    }
    
    // The last angle (theta_{n-1}) ranges from 0 to 2pi
    if (n >= 2 && vec.back() < 0.0f) {
        angles.back() = 2.0f * 3.14159265358979323846f - angles.back();
    }
    
    return HypersphereCoordinate(angles, radius);
}

std::vector<float> HypersphereMath::hyperspherical_to_cartesian(const HypersphereCoordinate& hc) {
    if (hc.angles.empty()) return {};
    size_t n = hc.angles.size() + 1;
    std::vector<float> vec(n, 0.0f);
    
    float sin_product = 1.0f;
    for (size_t i = 0; i < n - 1; ++i) {
        vec[i] = hc.radius * sin_product * std::cos(hc.angles[i]);
        sin_product *= std::sin(hc.angles[i]);
    }
    vec[n - 1] = hc.radius * sin_product;
    return vec;
}

float HypersphereMath::angular_distance(const HypersphereCoordinate& a, const HypersphereCoordinate& b) {
    if (a.angles.size() != b.angles.size()) return 1.0f; // Default max mismatch
    
    // Convert back to euclidean and compute cosine similarity for robustness
    auto ca = hyperspherical_to_cartesian(a);
    auto cb = hyperspherical_to_cartesian(b);
    
    float dp = 0.0f, normA = 0.0f, normB = 0.0f;
    for (size_t i = 0; i < ca.size(); ++i) {
        dp += ca[i] * cb[i];
        normA += ca[i] * ca[i];
        normB += cb[i] * cb[i];
    }
    
    if (normA == 0.0f || normB == 0.0f) return 1.0f;
    float sim = dp / (std::sqrt(normA) * std::sqrt(normB));
    if (sim > 1.0f) sim = 1.0f;
    if (sim < -1.0f) sim = -1.0f;
    return std::acos(sim) / 3.14159265358979323846f;
}

HypersphereMath::VortexCompressedCoordinate HypersphereMath::compress_vortex(const HypersphereCoordinate& coord, float phase_shift) {
    VortexCompressedCoordinate vc;
    vc.radius = coord.radius;
    vc.bladed_angles.reserve(coord.angles.size());
    const float TWO_PI = 2.0f * 3.14159265358979323846f;
    
    for (float angle : coord.angles) {
        float shifted = angle + phase_shift;
        // Wrap to [0, 2PI)
        while (shifted >= TWO_PI) shifted -= TWO_PI;
        while (shifted < 0.0f) shifted += TWO_PI;
        
        // Quantize to 16-bit blades
        uint16_t blade = static_cast<uint16_t>(std::round((shifted / TWO_PI) * 65535.0f));
        vc.bladed_angles.push_back(blade);
    }
    return vc;
}

HypersphereCoordinate HypersphereMath::decompress_vortex(const VortexCompressedCoordinate& v_coord, float phase_shift) {
    HypersphereCoordinate hc;
    hc.radius = v_coord.radius;
    hc.angles.reserve(v_coord.bladed_angles.size());
    const float TWO_PI = 2.0f * 3.14159265358979323846f;
    
    for (uint16_t blade : v_coord.bladed_angles) {
        float angle = (static_cast<float>(blade) / 65535.0f) * TWO_PI;
        angle -= phase_shift;
        // Wrap to [0, 2PI)
        while (angle >= TWO_PI) angle -= TWO_PI;
        while (angle < 0.0f) angle += TWO_PI;
        hc.angles.push_back(angle);
    }
    return hc;
}

HypersphereCoordinate HypersphereMath::get_token_coordinate(uint16_t token_code) {
    std::vector<float> vec(4);
    uint32_t seed = token_code ^ 0x5A5A;
    for (int i = 0; i < 4; ++i) {
        seed = (seed * 1103515245 + 12345) & 0x7fffffff;
        vec[i] = (static_cast<float>(seed) / 2147483647.0f) * 2.0f - 1.0f;
    }
    return cartesian_to_hyperspherical(vec);
}

HypersphereCoordinate HypersphereMath::embed_chunk(const std::vector<uint16_t>& tokens) {
    if (tokens.empty()) {
        std::vector<float> zero_vec(4, 0.0f);
        zero_vec[0] = 1.0f;
        return cartesian_to_hyperspherical(zero_vec);
    }
    
    std::vector<float> sum_vec(4, 0.0f);
    for (uint16_t t : tokens) {
        auto coord = get_token_coordinate(t);
        auto cart = hyperspherical_to_cartesian(coord);
        for (int i = 0; i < 4; ++i) {
            sum_vec[i] += cart[i];
        }
    }
    
    return cartesian_to_hyperspherical(sum_vec);
}

DirectStorageStreamer::DirectStorageStreamer(const std::string& file_path) 
    : file_path_(file_path), current_offset_(0) {}

DirectStorageStreamer::~DirectStorageStreamer() {}

void DirectStorageStreamer::optimize_for_drive_type(bool is_hdd) {
    is_hdd_mode_ = is_hdd;
}

bool DirectStorageStreamer::safe_read(void* buffer, size_t size, size_t offset) {
    // In a real DirectStorage implementation, this would use io_uring, AIO, DirectStorage API,
    // or standard fstream depending on the OS, and handle hardware interrupts or bad blocks.
    // Here we simulate the logic for production-grade error caching.
    
    // Simulate reading logic and potential error retries
    int max_retries = 3;
    for (int attempt = 0; attempt < max_retries; ++attempt) {
        bool read_success = true; // Simulated success
        if (read_success) {
            return true;
        }
    }
    return false; // Failed after retries
}

std::vector<HypersphereMath::VortexCompressedCoordinate> DirectStorageStreamer::stream_chunk(size_t chunk_size) {
    // If we're on a spinning HDD, we widen the read chunk block to maintain throughput
    if (is_hdd_mode_) {
        chunk_size = (chunk_size < 1024) ? 1024 : chunk_size * 2;
    }
    std::vector<HypersphereMath::VortexCompressedCoordinate> chunk(chunk_size);
    
    // If we have data in our error cache from a previous partial failure, yield it first
    if (!error_cache_.empty()) {
        size_t copy_amount = std::min(chunk_size, error_cache_.size());
        std::copy(error_cache_.begin(), error_cache_.begin() + copy_amount, chunk.begin());
        error_cache_.erase(error_cache_.begin(), error_cache_.begin() + copy_amount);
        if (copy_amount == chunk_size) return chunk;
        
        // If we still need more data, adjust pointer
        chunk_size -= copy_amount;
    }

    size_t bytes_to_read = chunk_size * sizeof(HypersphereMath::VortexCompressedCoordinate);
    
    if (safe_read(chunk.data(), bytes_to_read, current_offset_)) {
        current_offset_ += bytes_to_read;
        return chunk;
    } else {
        // Fallback or handle catastrophic failure
        // The error cache could be populated with zeroes or safely interpolated data
        return {};
    }
}

} // namespace hypersp
