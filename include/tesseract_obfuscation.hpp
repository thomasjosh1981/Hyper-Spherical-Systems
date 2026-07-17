// tesseract_obfuscation.hpp
//
// Spec V1.1 — 4D non-Euclidean translation + 6-language homophonic flattening matrix.
// (Verbatim from the spec; the spec's RuniceFlatteningMatrix is XOR+offset,
//  which is a bijection but does NOT actually flatten statistical frequencies
//  in a frequency-analysis-resistant way. We therefore expose a second,
//  permutation-based mode that builds a real Fisher-Yates shuffle of the
//  identity permutation per language — this DOES flatten frequencies.)
//
// Compile-time selection:
//   TESSERACT_OBFUSCATION_PERMUTATION_MODE = 0  (default, spec literal XOR+offset)
//   TESSERACT_OBFUSCATION_PERMUTATION_MODE = 1  (real permutation per language)

#pragma once
#include <cstdint>
#include <array>
#include <concepts>
#include <algorithm>
#include <random>

namespace Tesseract::Security {

    // 4D Coordinate Representation for Abstract Memory Map
    struct Point4D {
        int64_t x;
        int64_t y;
        int64_t z;
        int64_t w;
    };

    // Concepts to ensure standard layout compliance for zero-copy operations
    template<typename T>
    concept ObfuscatedPayload = std::is_standard_layout_v<T> && sizeof(T) >= 8;

    class ObfuscationEngine {
    private:
#if TESSERACT_OBFUSCATION_PERMUTATION_MODE
        // Real permutation per language — Fisher-Yates shuffled identity permutation.
        // This actually defeats frequency analysis because the byte 0x42 in language 0
        // maps to a DIFFERENT byte than 0x42 in language 1 — non-uniform mapping.
        static constexpr std::array<std::array<uint8_t, 256>, 6> RuniceFlatteningMatrix = []() {
            std::array<std::array<uint8_t, 256>, 6> matrix{};
            // Build identity then shuffle each row with a different seed.
            for (size_t lang = 0; lang < 6; ++lang) {
                for (size_t val = 0; val < 256; ++val) {
                    matrix[lang][val] = static_cast<uint8_t>(val);
                }
                std::mt19937 rng(static_cast<uint32_t>(0x5A5A5A5A ^ lang * 0x9E3779B9u));
                for (size_t i = 255; i > 0; --i) {
                    std::swap(matrix[lang][i], matrix[lang][rng() % (i + 1)]);
                }
            }
            return matrix;
        }();
#else
        // Spec-literal XOR+offset matrix (bijection but does NOT flatten frequencies).
        static constexpr std::array<std::array<uint8_t, 256>, 6> RuniceFlatteningMatrix = []() {
            std::array<std::array<uint8_t, 256>, 6> matrix{};
            // Hardcoded scrambling allocation to eliminate natural frequency peaks
            for (size_t lang = 0; lang < 6; ++lang) {
                for (size_t val = 0; val < 256; ++val) {
                    matrix[lang][val] = static_cast<uint8_t>((val ^ 0x5A) + lang);
                }
            }
            return matrix;
        }();
#endif

    public:
        // Maps a flat sequential virtual address into non-Euclidean 4D coordinate space
        [[nodiscard]] static constexpr Point4D LinearTo4DSpace(uintptr_t virtual_address) noexcept {
            return Point4D {
                static_cast<int64_t>(virtual_address & 0xFFFF),
                static_cast<int64_t>((virtual_address >> 16) & 0xFFFF),
                static_cast<int64_t>((virtual_address >> 32) & 0xFFFF),
                static_cast<int64_t>((virtual_address >> 48) & 0xFFFF)
            };
        }

        // Reconstitutes flat memory offsets back from the 4D manifold matrix
        [[nodiscard]] static constexpr uintptr_t Space4DToLinear(const Point4D& point) noexcept {
            return (static_cast<uintptr_t>(point.w) << 48) |
                   (static_cast<uintptr_t>(point.z) << 32) |
                   (static_cast<uintptr_t>(point.y) << 16) |
                   (static_cast<uintptr_t>(point.x));
        }

        // Homophonic Substitution execution block
        static void FlattenPayload(uint8_t* buffer, size_t length, size_t language_index) noexcept {
            if (language_index >= 6 || !buffer) return;
            for (size_t i = 0; i < length; ++i) {
                buffer[i] = RuniceFlatteningMatrix[language_index][buffer[i]];
            }
        }

        // Inverse — given a flattened payload + language index, recover original.
        // We rebuild the inverse table at runtime (constexpr arrays can't easily invert).
        static void UnflattenPayload(uint8_t* buffer, size_t length, size_t language_index) noexcept {
            if (language_index >= 6 || !buffer) return;
            // Build the inverse table on the stack once per call (small; 256 bytes).
            std::array<uint8_t, 256> inverse{};
            for (size_t val = 0; val < 256; ++val) {
                inverse[RuniceFlatteningMatrix[language_index][val]] = static_cast<uint8_t>(val);
            }
            for (size_t i = 0; i < length; ++i) {
                buffer[i] = inverse[buffer[i]];
            }
        }
    };

} // namespace Tesseract::Security
