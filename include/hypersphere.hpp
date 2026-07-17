#pragma once
#include <vector>
#include <cmath>
#include <stdexcept>

namespace tesseract {

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

} // namespace tesseract
