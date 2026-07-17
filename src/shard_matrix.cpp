// shard_matrix.cpp — implements ShardMatrix (10-file layout + parity + rotator + bi-dir mix).

#include "shard_matrix.hpp"
#include "tesseract_pqc.hpp"

#include <algorithm>
#include <cstring>
#include <fstream>
#include <iostream>
#include <random>
#include <chrono>
#include <thread>

#ifndef NOMINMAX
#define NOMINMAX
#endif
#if defined(_WIN32)
#  define WIN32_LEAN_AND_MEAN
#  include <windows.h>
#endif

namespace Tesseract::Security::Sharding {

    static inline size_t get_node_index(size_t shard, bool inside_out_toggle) {
        if (inside_out_toggle) {
            return (shard % 2 == 0) ? (shard / 2) : (9 - shard / 2);
        } else {
            return (shard % 2 == 0) ? (4 - shard / 2) : (5 + shard / 2);
        }
    }

    // ── V1.3 reference mix (verbatim from spec, generalized) ────────────
    void ExecuteBiDirectionalMix(const uint8_t* __restrict source_buffer,
                                  size_t total_size,
                                  ShardMatrix10& matrix,
                                  bool inside_out_toggle) noexcept {
        if (total_size < 6) return;
        const size_t chunk_size = total_size / 6;
        for (size_t shard = 0; shard < 6; ++shard) {
            const uint8_t* shard_ptr = source_buffer + (shard * chunk_size);
            const size_t this_chunk = (shard == 5)
                ? (total_size - shard * chunk_size)  // last one absorbs remainder
                : chunk_size;

            size_t target_node = get_node_index(shard, inside_out_toggle);
            std::memcpy(matrix.file_nodes[target_node], shard_ptr, this_chunk);
            matrix.block_sizes[target_node] = this_chunk;
        }
    }

    // ── GF(2^8) XOR parity across 5 data shards ─────────────────────────
    void ComputeXorParity(const std::vector<std::vector<uint8_t>>& data_shards,
                           std::vector<uint8_t>& parity_out) noexcept {
        if (data_shards.empty()) return;
        size_t max_len = 0;
        for (auto& s : data_shards) max_len = std::max(max_len, s.size());
        parity_out.assign(max_len, 0);
        for (auto& s : data_shards) {
            for (size_t i = 0; i < s.size(); ++i) parity_out[i] ^= s[i];
        }
    }

    // ────────────────────────────────────────────────────────────────────
    // ShardMatrix class implementation
    // ────────────────────────────────────────────────────────────────────
    ShardMatrix::ShardMatrix(Config cfg) : cfg_(std::move(cfg)) {}

    ShardMatrix::~ShardMatrix() {
        running_ = false;
        if (rotator_thread_.joinable()) rotator_thread_.join();
    }

    std::filesystem::path ShardMatrix::path_for(size_t idx) const {
        const auto& topo = DefaultTopology();
        const bool is_decoy = topo[idx].is_decoy();
        auto base = is_decoy ? cfg_.decoy_dir : cfg_.base_dir;
        return base / topo[idx].filename;
    }

    bool ShardMatrix::open_all() {
        try {
            std::filesystem::create_directories(cfg_.base_dir);
            std::filesystem::create_directories(cfg_.decoy_dir);
            for (size_t i = 0; i < kNumShards; ++i) {
                file_paths_[i] = path_for(i).string();
                // Touch (create empty) each file so it exists.
                std::ofstream f(file_paths_[i], std::ios::binary | std::ios::app);
                if (!f) return false;
            }
        } catch (const std::exception&) {
            return false;
        }
        // Spawn rotator thread if enabled
        if (cfg_.enable_rotator) {
            running_ = true;
            rotator_thread_ = std::thread(&ShardMatrix::rotator_loop, this);
        }
        return true;
    }

    Tesseract::Security::Pqc::Status ShardMatrix::write_payload(const uint8_t* data, size_t len) {
        if (len == 0) return Tesseract::Security::Pqc::Status::BAD_ARG;
        // Split payload into 5 equal data shards + 1 remainder chunk
        std::vector<std::vector<uint8_t>> data_shards(kNumDataShards);
        const size_t chunk = len / kNumDataShards;
        for (size_t i = 0; i < kNumDataShards; ++i) {
            size_t off = i * chunk;
            size_t sz  = (i == kNumDataShards - 1) ? (len - off) : chunk;
            data_shards[i].assign(data + off, data + off + sz);
        }
        // Compute parity over the 5 data shards
        std::vector<uint8_t> parity;
        ComputeXorParity(data_shards, parity);

        // Build a flat source buffer for the mix routine: [d0|d1|d2|d3|d4|parity]
        std::vector<uint8_t> flat;
        for (auto& s : data_shards) flat.insert(flat.end(), s.begin(), s.end());
        flat.insert(flat.end(), parity.begin(), parity.end());

        // Allocate 10 destination buffers and run the mix
        std::vector<std::vector<uint8_t>> nodes(kNumShards);
        for (auto& n : nodes) n.resize(flat.size());  // over-allocate; mix only fills some
        ShardMatrix10 mtx{};
        for (size_t i = 0; i < kNumShards; ++i) mtx.file_nodes[i] = nodes[i].data();

        bool toggle = inside_out_toggle_.load(std::memory_order_acquire);
        ExecuteBiDirectionalMix(flat.data(), flat.size(), mtx, toggle);
        inside_out_toggle_.store(!toggle, std::memory_order_release);

        // Flush to disk
        for (size_t i = 0; i < kNumShards; ++i) {
            std::ofstream out(file_paths_[i], std::ios::binary | std::ios::trunc);
            if (!out) return Tesseract::Security::Pqc::Status::INTERNAL;
            out.write(reinterpret_cast<const char*>(nodes[i].data()),
                      static_cast<std::streamsize>(mtx.block_sizes[i]));
        }

        // Update stats + bytes-since-toggle counter
        {
            std::lock_guard<std::mutex> lk(stats_mtx_);
            stats_.total_writes++;
            stats_.mix_direction = toggle ? 0 : 1;
        }
        bytes_since_last_toggle_ += len;
        if (bytes_since_last_toggle_ >= kToggleBytes) {
            inside_out_toggle_.store(!inside_out_toggle_.load(), std::memory_order_release);
            bytes_since_last_toggle_ = 0;
        }
        return Tesseract::Security::Pqc::Status::OK;
    }

    bool ShardMatrix::read_payload(std::vector<uint8_t>& out) {
        std::vector<std::vector<uint8_t>> nodes(kNumShards);
        std::vector<bool> node_ok(kNumShards, false);

        // 1. Read all 10 files back
        for (size_t i = 0; i < kNumShards; ++i) {
            std::ifstream in(file_paths_[i], std::ios::binary | std::ios::ate);
            if (!in) {
                continue; // mark as failed/missing
            }
            size_t sz = static_cast<size_t>(in.tellg());
            if (sz == 0) continue; // decoy or unwritten
            nodes[i].resize(sz);
            in.seekg(0);
            if (in.read(reinterpret_cast<char*>(nodes[i].data()), sz)) {
                node_ok[i] = true;
            }
        }

        // 2. Determine inside-out toggle direction based on populated nodes
        bool inside_out = (nodes[0].size() > 0 || nodes[9].size() > 0);

        // 3. Map nodes back to shards (0-4 are data, 5 is parity)
        std::vector<std::vector<uint8_t>> shards(6);
        int failed_shard_idx = -1;
        int failed_count = 0;
        size_t max_size = 0;

        for (size_t shard = 0; shard < 6; ++shard) {
            size_t node_idx = get_node_index(shard, inside_out);
            if (node_ok[node_idx]) {
                shards[shard] = nodes[node_idx];
                max_size = std::max(max_size, shards[shard].size());
            } else {
                failed_shard_idx = static_cast<int>(shard);
                failed_count++;
            }
        }

        if (failed_count > 1) {
            return false; // Multi-fault, unrecoverable
        }

        // 4. If exactly one shard is missing, reconstruct it using XOR parity
        if (failed_count == 1) {
            shards[failed_shard_idx].assign(max_size, 0);
            for (size_t byte_idx = 0; byte_idx < max_size; ++byte_idx) {
                uint8_t reconstructed_byte = 0;
                for (size_t s = 0; s < 6; ++s) {
                    if (static_cast<int>(s) == failed_shard_idx) continue;
                    if (byte_idx < shards[s].size()) {
                        reconstructed_byte ^= shards[s][byte_idx];
                    }
                }
                shards[failed_shard_idx][byte_idx] = reconstructed_byte;
            }
            
            // ERROR CORRECTION: Reconstructed standard data shards (0-3) must be truncated
            // back to the standard chunk size, otherwise they inject padding zero-bytes
            // into the middle of the concatenated payload.
            if (failed_shard_idx < 4) {
                size_t correct_size = 0;
                for (int s = 0; s < 4; ++s) {
                    if (s != failed_shard_idx && shards[s].size() > 0) {
                        correct_size = shards[s].size();
                        break;
                    }
                }
                shards[failed_shard_idx].resize(correct_size);
            }
        }

        // 5. Concatenate the 5 data shards
        out.clear();
        for (size_t s = 0; s < kNumDataShards; ++s) {
            out.insert(out.end(), shards[s].begin(), shards[s].end());
        }

        std::lock_guard<std::mutex> lk(stats_mtx_);
        stats_.total_reads++;
        return true;
    }

    void ShardMatrix::rotate_now() {
        // Asynchronously re-touch each file's mtime to make rotations observable.
        for (size_t i = 0; i < kNumShards; ++i) {
            try {
                auto t = std::filesystem::file_time_type::clock::now();
                std::filesystem::last_write_time(file_paths_[i], t);
            } catch (...) {}
        }
        std::lock_guard<std::mutex> lk(stats_mtx_);
        stats_.rotations++;
    }

    void ShardMatrix::arm_tripwire() {
        for (auto& b : decoy_armed_) b = true;
    }
    void ShardMatrix::disarm_tripwire() {
        for (auto& b : decoy_armed_) b = false;
    }

    ShardMatrix::Stats ShardMatrix::stats() const {
        std::lock_guard<std::mutex> lk(stats_mtx_);
        return stats_;
    }

    void ShardMatrix::rotator_loop() {
        using namespace std::chrono;
        while (running_.load(std::memory_order_acquire)) {
            std::this_thread::sleep_for(milliseconds(cfg_.rotator_interval_ms));
            if (!running_.load()) break;
            rotate_now();
        }
    }

} // namespace Tesseract::Security::Sharding
