// tesseract_security_optimization.hpp
//
// Spec V1.2 — Sub-millisecond security optimizations:
//   1. AVX2 vectorized homophonic flattening (32 bytes per cycle)
//   2. Inline zero-overhead 4D address partition
//   3. Branchless tripwire boundary check
//   4. Hardware-direct page isolation via VirtualAlloc(PAGE_NOACCESS) + VEH
//
// AVX2 availability is runtime-detected via __cpuid. On non-AVX2 CPUs we
// transparently fall back to the scalar path.

#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>

#if defined(__x86_64__) || defined(_M_X64)
#include <immintrin.h>
#include <intrin.h>
#endif

#if defined(_WIN32)
#  define WIN32_LEAN_AND_MEAN
#  include <windows.h>
#endif

#include "tesseract_obfuscation.hpp"
#include "tesseract_security_tripwire.hpp"

namespace Tesseract::Security::Optimization {

    // ── AVX2 runtime feature detection ─────────────────────────────────
    [[nodiscard]] inline bool HasAVX2() noexcept {
#if defined(__x86_64__) || defined(_M_X64)
        int cpuInfo[4] = {0};
        __cpuid(cpuInfo, 1);
        // Bit 28 of ECX = AVX
        if (!(cpuInfo[2] & (1 << 28))) return false;
        // AVX2 = bit 5 of EBX from __cpuid(7,0)
        __cpuidex(cpuInfo, 7, 0);
        return (cpuInfo[1] & (1 << 5)) != 0;
#else
        return false;
#endif
    }

    // ── 1. Vectorized AVX2 flattening (32 bytes / cycle) ──────────────
    inline void VectorizedFlatten(uint8_t* __restrict payload, size_t length,
                                  uint8_t key_mask) noexcept {
        if (!payload || length == 0) return;

#if defined(__x86_64__) || defined(_M_X64)
        if (HasAVX2()) {
            // Broadcast the 8-bit homophonic key mask across an entire 256-bit register
            const __m256i v_key = _mm256_set1_epi8(static_cast<char>(key_mask));
            size_t i = 0;
            // Process unrolled 32-byte blocks
            for (; i + 32 <= length; i += 32) {
                __m256i v_data = _mm256_loadu_si256(
                    reinterpret_cast<const __m256i*>(&payload[i]));
                __m256i v_res  = _mm256_xor_si256(v_data, v_key);
                _mm256_storeu_si256(reinterpret_cast<__m256i*>(&payload[i]), v_res);
            }
            // Clean up remaining tail bytes (less than 32)
            for (; i < length; ++i) {
                payload[i] ^= key_mask;
            }
            return;
        }
#endif
        // Scalar fallback
        for (size_t i = 0; i < length; ++i) {
            payload[i] ^= key_mask;
        }
    }

    // ── 2. Zero-overhead inline 4D partition (compiler inlines + CSE) ─
    // Micro-benchmark target: < 1 ns per translation.
    inline Tesseract::Security::Point4D FastLinearTo4D(uintptr_t address) noexcept {
        return Tesseract::Security::Point4D {
            static_cast<int64_t>(address & 0xFFFF),
            static_cast<int64_t>((address >> 16) & 0xFFFF),
            static_cast<int64_t>((address >> 32) & 0xFFFF),
            static_cast<int64_t>((address >> 48) & 0xFFFF)
        };
    }

    inline uintptr_t Fast4DToLinear(const Tesseract::Security::Point4D& p) noexcept {
        return (static_cast<uintptr_t>(p.w) << 48) |
               (static_cast<uintptr_t>(p.z) << 32) |
               (static_cast<uintptr_t>(p.y) << 16) |
               (static_cast<uintptr_t>(p.x));
    }

    // ── 3. Branchless tripwire boundary check ─────────────────────────
    // Computes condition boundaries using logical bit manipulation.
    // Joint truth verification via bitwise AND prevents the compiler
    // from emitting JUMP instructions.
    inline bool VerifyBoundaryBranchless(uintptr_t target_addr,
                                          uintptr_t low_bound,
                                          uintptr_t high_bound) noexcept {
        bool low_breach  = (target_addr >= low_bound);
        bool high_breach = (target_addr < high_bound);
        return low_breach & high_breach;
    }

    // ── 4. Hardware-direct page isolation ─────────────────────────────
    // Allocates a guarded page: any read/write to it raises STATUS_ACCESS_VIOLATION
    // in our VEH handler, which triggers the tripwire purge. On non-Windows,
    // mmap(PROT_NONE) + SIGSEGV handler achieves the same.
    //
    // Returns: base address (or nullptr on failure). Size = requested allocation.
    inline void* AllocateHoneyGatePage(size_t bytes) noexcept {
#if defined(_WIN32)
        void* base = VirtualAlloc(nullptr, bytes,
                                  MEM_COMMIT | MEM_RESERVE,
                                  PAGE_NOACCESS);
        if (!base) return nullptr;
        // Caller is expected to register this range via TripwireEngine::RegisterHoneyGateRange
        // so that the VEH handler / branchless check knows the bounds.
        return base;
#else
        (void)bytes;
        return nullptr;  // POSIX path would use mmap(PROT_NONE) — out of scope for V1.2.
#endif
    }

    inline void FreeHoneyGatePage(void* base, size_t bytes) noexcept {
#if defined(_WIN32)
        if (base) VirtualFree(base, bytes, MEM_RELEASE);
#else
        (void)base; (void)bytes;
#endif
    }

} // namespace Tesseract::Security::Optimization
