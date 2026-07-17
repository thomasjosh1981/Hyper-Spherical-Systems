// shard_matrix.hpp
//
// 10-file ShardMatrix per spec V1.3 §2 and V1.3 §3:
//
//   File Node        | Role                | Drive  | Ring | DMA queue
//   -----------------|---------------------|--------|------|-----------
//   tesseract_sh_01  | Data Shard A (1-20)  | A      | 0    | 0 (hi pri)
//   tesseract_sh_02  | Data Shard B (21-40) | B      | 1    | 1 (hi pri)
//   tesseract_sh_03  | Data Shard C (41-60) | A      | 2    | 0 (hi pri)
//   tesseract_sh_04  | Data Shard D (61-80) | B      | 3    | 1 (hi pri)
//   tesseract_sh_05  | Data Shard E (81-100)| A      | 4    | 0 (hi pri)
//   tesseract_sh_06  | Parity Shard P0 (XOR)| B      | 0    | 2 (parity)
//   tesseract_dec_07 | Honey-Gate Decoy α   | static | -    | (tripwire)
//   tesseract_dec_08 | Honey-Gate Decoy β   | static | -    | (tripwire)
//   tesseract_dec_09 | Honey-Gate Decoy γ   | static | -    | (tripwire)
//   tesseract_dec_10 | Honey-Gate Decoy δ   | static | -    | (tripwire)
//
// Uses V1.3 bi-directional mixing (inside-out vs outside-in), toggled every 512KB.

#pragma once
#include <cstdint>
#include <cstddef>
#include <array>
#include <string>
#include <vector>
#include <atomic>
#include <thread>
#include <mutex>
#include <filesystem>
#include <chrono>

#include "tesseract_pqc.hpp"

namespace Tesseract::Security::Sharding {

    constexpr size_t kNumShards = 10;
    constexpr size_t kNumDataShards = 5;
    constexpr size_t kNumDecoys     = 4;
    constexpr size_t kToggleBytes   = 512 * 1024;  // toggle every 512 KB per spec V1.3 §3

    enum class NodeRole : uint8_t {
        DataA = 0, DataB = 1, DataC = 2, DataD = 3, DataE = 4,
        Parity = 5,
        DecoyAlpha = 6, DecoyBeta = 7, DecoyGamma = 8, DecoyDelta = 9
    };

    struct NodeDescriptor {
        std::string  filename;     // "tesseract_sh_01.bin"
        NodeRole     role;
        std::string  drive_letter; // "D:" or "E:"
        uint8_t      sector_ring;  // 0..4
        uint8_t      dma_queue;    // 0/1/2
        bool         is_data()      const noexcept { return uint8_t(role) <= 4; }
        bool         is_parity()    const noexcept { return role == NodeRole::Parity; }
        bool         is_decoy()     const noexcept { return uint8_t(role) >= 6; }
    };

    inline std::array<NodeDescriptor, kNumShards>& DefaultTopology() {
        static const std::array<NodeDescriptor, kNumShards> t = {{
            {"tesseract_sh_01.bin", NodeRole::DataA,      "D:", 0, 0},
            {"tesseract_sh_02.bin", NodeRole::DataB,      "E:", 1, 1},
            {"tesseract_sh_03.bin", NodeRole::DataC,      "D:", 2, 0},
            {"tesseract_sh_04.bin", NodeRole::DataD,      "E:", 3, 1},
            {"tesseract_sh_05.bin", NodeRole::DataE,      "D:", 4, 0},
            {"tesseract_sh_06.bin", NodeRole::Parity,     "E:", 0, 2},
            {"tesseract_dec_07.bin",NodeRole::DecoyAlpha, "D:", 0, 0},
            {"tesseract_dec_08.bin",NodeRole::DecoyBeta,  "D:", 0, 0},
            {"tesseract_dec_09.bin",NodeRole::DecoyGamma, "D:", 0, 0},
            {"tesseract_dec_10.bin",NodeRole::DecoyDelta, "D:", 0, 0},
        }};
        return const_cast<std::array<NodeDescriptor, kNumShards>&>(t);
    }

    // V1.3 §3 — reference mixing routine (verbatim from spec, generalized).
    struct ShardMatrix10 {
        uint8_t* file_nodes[kNumShards] = {nullptr};
        size_t   block_sizes[kNumShards] = {0};
    };

    // Performs the bi-directional mix. `inside_out_toggle` controls orientation;
    // caller flips it every 512KB per V1.3 spec.
    void ExecuteBiDirectionalMix(const uint8_t* source_buffer, size_t total_size,
                                  ShardMatrix10& matrix, bool inside_out_toggle) noexcept;

    // Computes XOR parity across the 5 data shards (GF(2^8)).
    void ComputeXorParity(const std::vector<std::vector<uint8_t>>& data_shards,
                           std::vector<uint8_t>& parity_out) noexcept;

    // The high-level manager that owns the 10 file handles + the rotator thread.
    class ShardMatrix {
    public:
        struct Config {
            std::filesystem::path base_dir = "D:/tesseract_shards";
            std::filesystem::path decoy_dir = "D:/tesseract_decoys";
            bool  enable_rotator = true;
            size_t rotator_interval_ms = 5000;
        };

        explicit ShardMatrix(Config cfg = {});
        ~ShardMatrix();

        // Opens / creates all 10 shard files on disk. Idempotent.
        bool open_all();

        // Writes a payload: splits into 5 data shards + 1 parity + 4 decoys.
        // Uses bi-directional mix per V1.3.
        Tesseract::Security::Pqc::Status write_payload(const uint8_t* data, size_t len);

        // Reads back and reassembles. Returns false on any shard mismatch.
        bool read_payload(std::vector<uint8_t>& out);

        // Manually trigger a sector rotation (also runs on background timer).
        void rotate_now();

        // Tripwire arm: any touch to a decoy file triggers the tripwire.
        void arm_tripwire();
        void disarm_tripwire();

        // Stats for the GUI
        struct Stats {
            uint64_t total_writes   = 0;
            uint64_t total_reads    = 0;
            uint64_t rotations      = 0;
            uint64_t mix_direction  = 0;  // 0=inside-out, 1=outside-in
            uint64_t tripwire_hits  = 0;
        };
        Stats stats() const;
        std::filesystem::path path_for(size_t idx) const;

    private:
        Config cfg_;
        std::array<std::string, kNumShards> file_paths_{};
        std::array<bool, kNumDecoys>        decoy_armed_{};
        std::atomic<bool>                    running_{false};
        std::thread                          rotator_thread_;
        mutable std::mutex                   stats_mtx_;
        Stats                                stats_{};
        uint64_t                             bytes_since_last_toggle_ = 0;
        std::atomic<bool>                    inside_out_toggle_{true};
        Tesseract::Security::Pqc::SharedSecret kdf_seed_{};

        // Helpers
        void rotator_loop();
    };

} // namespace Tesseract::Security::Sharding
