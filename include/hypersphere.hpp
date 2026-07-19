#pragma once
#include <vector>
#include <cmath>
#include <stdexcept>

namespace hypersp {

// A point mapped to a normalized N-dimensional unit hypersphere.
struct HypersphereCoordinate {
    std::vector<float> angles; // (N-1) angles: theta_1 to theta_n-1
    float radius; // Magnitude (should be 1.0 for unit hypersphere)

    HypersphereCoordinate() : radius(0.0f) {}
    HypersphereCoordinate(const std::vector<float>& angs, float r) : angles(angs), radius(r) {}
};

class HypersphereMath {
public:
    // Convert Euclidean coordinates to Hyperspherical coordinates
    static HypersphereCoordinate cartesian_to_hyperspherical(const std::vector<float>& euclidean_vector);

    // Convert Hyperspherical coordinates to Euclidean coordinates
    static std::vector<float> hyperspherical_to_cartesian(const HypersphereCoordinate& spherical);

    // Compute angular distance (cosine similarity equivalent on unit hypersphere)
    static float angular_distance(const HypersphereCoordinate& a, const HypersphereCoordinate& b);

    // --- Counter-Rotating Bladed Vortex Compression ---
    // Quantize angles into 16-bit "blades" and apply +/- phi phase shift.
    struct VortexCompressedCoordinate {
        float radius;
        std::vector<uint16_t> bladed_angles;
    };

    static VortexCompressedCoordinate compress_vortex(const HypersphereCoordinate& coord, float phase_shift);
    static HypersphereCoordinate decompress_vortex(const VortexCompressedCoordinate& v_coord, float phase_shift);

    // --- Semantic Embeddings ---
    // Deterministically generate a 4D coordinate for a given SISSI token code
    static HypersphereCoordinate get_token_coordinate(uint16_t token_code);

    // Embed an entire sentence (array of tokens) into a single 4D coordinate
    static HypersphereCoordinate embed_chunk(const std::vector<uint16_t>& tokens);
};

// OS-level Direct I/O Streaming for SFS/SFS+ weights (bypassing CPU RAM)
class DirectStorageStreamer {
public:
    DirectStorageStreamer(const std::string& file_path);
    ~DirectStorageStreamer();

    // Streams the next chunk of VortexCoordinates directly to VRAM staging buffers
    std::vector<HypersphereMath::VortexCompressedCoordinate> stream_chunk(size_t chunk_size);

    // Switches the internal block sizing if a spinning HDD is detected versus NVMe/SSD
    void optimize_for_drive_type(bool is_hdd);

private:
    std::string file_path_;
    size_t current_offset_;
    std::vector<HypersphereMath::VortexCompressedCoordinate> error_cache_;
    bool is_hdd_mode_ = false;
    
    // Internal method to handle OS-level direct read with retry logic
    bool safe_read(void* buffer, size_t size, size_t offset);
};

using VortexCoordinate = HypersphereMath::VortexCompressedCoordinate;

} // namespace hypersp
