#pragma once
#include "types.hpp"
#include <cstdint>
#include <string_view>
#include <string>

namespace hypersp {

class NVMeIO {
public:
    explicit NVMeIO(const std::vector<std::string>& nvme_mounts, const std::vector<std::string>& hdd_mounts = {});
    ~NVMeIO() = default;

    /** Write a weight shard block to NVMe */
    ErrorCode write_block(std::string_view path_str, const uint8_t* data, size_t len) noexcept;

    /** Read a weight shard block from NVMe */
    ErrorCode read_block (std::string_view path_str,       uint8_t* out,   size_t len) noexcept;

    /** Benchmark sequential/random throughput across chunk sizes */
    int32_t benchmark_throughput(size_t num_runs = 10u) noexcept;

private:
    std::vector<std::string> nvme_mounts_;
    std::vector<std::string> hdd_mounts_;
};

} // namespace hypersp
