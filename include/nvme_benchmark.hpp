// include/nvme_benchmark.hpp
#pragma once
#include <string>

namespace hypersp {

struct BenchmarkResult {
    float nvme_read_gbps{0.0f};
    float nvme_write_gbps{0.0f};
    float hdd_read_mbps{0.0f};
    bool ok{false};
    std::string details;
};

BenchmarkResult run_drive_benchmark(const std::string& nvme_path = "C:\\",
                                     const std::string& hdd_path = "D:\\");

} // namespace hypersp
