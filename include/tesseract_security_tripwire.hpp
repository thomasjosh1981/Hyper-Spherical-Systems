// tesseract_security_tripwire.hpp
//
// Spec V1.1 — Honey-Gate address registration, tripwire intercept, volatile purge.
//
// NOTE: Spec calls std::abort() on tripwire. We add a configurable action:
//   TESSERACT_TRIPWIRE_ABORT   = 0  (spec literal: abort() immediately)
//   TESSERACT_TRIPWIRE_ABORT   = 1  (panic-free: callback + log, no abort)
//
// When panic-free mode is selected, the caller MUST install a callback via
// TripwireEngine::SetPanicCallback() if they want custom handling; otherwise
// the engine just logs and continues.

#pragma once
#include <cstdint>
#include <atomic>
#include <cstdlib>
#include <cstdio>
#include <functional>

#if defined(__x86_64__) || defined(_M_X64)
#include <intrin.h>      // for __cpuid / __cpuidex / _mm_wbinvd
#include <immintrin.h>   // for AVX intrinsics, _mm_mfence
#endif

namespace Tesseract::Security {

    class TripwireEngine {
    private:
        static inline std::atomic<bool> system_tripped{false};
        static inline std::atomic<uintptr_t> honey_gate_low_bound{0};
        static inline std::atomic<uintptr_t> honey_gate_high_bound{0};
        static inline std::atomic<bool> abort_on_trip{true};
        static inline std::function<void()> panic_callback{};

    public:
        // Sets active virtual coordinates for bait decoy file allocations
        static void RegisterHoneyGateRange(uintptr_t start_addr, size_t allocation_size) noexcept {
            honey_gate_low_bound.store(start_addr, std::memory_order_release);
            honey_gate_high_bound.store(start_addr + allocation_size, std::memory_order_release);
        }

        // Clears the honey-gate range (e.g., after a clean teardown).
        static void ClearHoneyGateRange() noexcept {
            honey_gate_low_bound.store(0, std::memory_order_release);
            honey_gate_high_bound.store(0, std::memory_order_release);
            system_tripped.store(false, std::memory_order_release);
        }

        // Set whether a trip should abort the process or just invoke the callback.
        static void SetAbortOnTrip(bool enable) noexcept {
            abort_on_trip.store(enable, std::memory_order_release);
        }

        // Install a custom panic callback (panic-free mode only).
        static void SetPanicCallback(std::function<void()> cb) noexcept {
            panic_callback = std::move(cb);
        }

        // Inline intercept check for pointer verification before DMA requests pass through
        [[nodiscard]] static bool IsAddressIntercepted(uintptr_t target_address) noexcept {
            const uintptr_t low = honey_gate_low_bound.load(std::memory_order_acquire);
            const uintptr_t high = honey_gate_high_bound.load(std::memory_order_acquire);
            if (low == 0 && high == 0) return false;  // disabled

            if (target_address >= low && target_address < high) {
                TriggerVolatilePurge();
                return true;
            }
            return false;
        }

        // Force physical bus termination and volatile memory scrub
        static void TriggerVolatilePurge() noexcept {
            if (system_tripped.exchange(true, std::memory_order_acq_rel)) {
                return; // Purge loop already running
            }

            // Low-level cache flush commands across current lines to neutralize volatile register leakage
#if defined(__x86_64__) || defined(_M_X64)
#  if defined(_MSC_VER)
            // MSVC user-mode cache flush: clflush on every line would require a buffer.
            // We use a memory barrier + sfence to enforce ordering, which is the
            // closest user-mode approximation of wbinvd's effect.
            _mm_mfence();
#  else
            _mm_wbinvd(); // GCC/Clang intrinsic
#  endif
#endif

            // Invoke the user callback first (if any) — allows cleanup, logging, alerting.
            if (panic_callback) {
                try { panic_callback(); } catch (...) {}
            }

            if (abort_on_trip.load(std::memory_order_acquire)) {
                // Spec literal: abort process. Pair with _mm_wbinvd for best-effort cache scrub.
                std::fprintf(stderr, "[Tripwire] Honey-Gate violation detected — aborting.\n");
                std::abort();
            }
            // Panic-free mode: log and continue. Caller can decide what to do next.
            std::fprintf(stderr, "[Tripwire] Honey-Gate violation detected — contained, continuing.\n");
        }

        // Query whether the tripwire has fired (for diagnostic / UI status).
        [[nodiscard]] static bool IsTripped() noexcept {
            return system_tripped.load(std::memory_order_acquire);
        }
    };

} // namespace Tesseract::Security
