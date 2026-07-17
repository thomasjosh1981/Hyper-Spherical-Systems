#include "stripe_io.hpp"
#include <fstream>
#include <random>
#include <future>
#include <filesystem>
#include <cstdio>
#include <cstring>

namespace tesseract {

StripeIO::StripeIO(const StripeConfig& cfg) : config_(cfg) {
    generate_file_paths();
}

void StripeIO::generate_file_paths() {
    active_paths_.clear();
    decoy_paths_.clear();

    // Generate active stripe paths
    for (size_t i = 0; i < config_.active_stripes; ++i) {
        active_paths_.push_back(config_.base_path + "." + std::to_string(i));
    }

    // Mirror harness file names for decoys with suffixes
    static const std::vector<std::string> MIRROR_TEMPLATES = {
        "python_bridge.dll", "tesseract_bridge.exe", "tesseract_core.exe",
        "config.hpp", "harness_hook.hpp", "tests.cpp"
    };

    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, static_cast<int>(MIRROR_TEMPLATES.size()) - 1);

    std::string dir = config_.harness_mirror_dir;
    if (dir.empty()) {
        dir = std::filesystem::path(config_.base_path).parent_path().string();
    }

    for (size_t i = 0; i < config_.decoy_files; ++i) {
        std::string template_name = MIRROR_TEMPLATES[dis(gen)];
        std::string decoy_name = template_name + ".bak" + std::to_string(i + 1);
        std::filesystem::path path = std::filesystem::path(dir) / decoy_name;
        decoy_paths_.push_back(path.string());
    }
}

bool StripeIO::write_striped(const std::vector<uint8_t>& data) {
    if (data.empty() || active_paths_.empty()) return false;

    size_t total_size = data.size();
    size_t stripe_count = active_paths_.size();
    size_t base_chunk_size = total_size / stripe_count;
    size_t remainder = total_size % stripe_count;

    std::vector<std::future<bool>> futures;

    size_t offset = 0;
    for (size_t i = 0; i < stripe_count; ++i) {
        size_t chunk_size = base_chunk_size + (i < remainder ? 1 : 0);
        const uint8_t* chunk_ptr = data.data() + offset;
        offset += chunk_size;

        std::string path = active_paths_[i];
        futures.push_back(std::async(std::launch::async, [path, chunk_ptr, chunk_size]() {
            std::ofstream f(path, std::ios::binary);
            if (!f) return false;
            f.write(reinterpret_cast<const char*>(chunk_ptr), chunk_size);
            return f.good();
        }));
    }

    // Write decoy files with junk data in parallel
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<int> byte_dis(0, 255);

    for (size_t i = 0; i < decoy_paths_.size(); ++i) {
        std::string decoy_path = decoy_paths_[i];
        size_t decoy_size = base_chunk_size + 128; // slightly offset to obfuscate size correlation
        futures.push_back(std::async(std::launch::async, [decoy_path, decoy_size, &gen, &byte_dis]() {
            std::ofstream f(decoy_path, std::ios::binary);
            if (!f) return false;
            std::vector<uint8_t> junk(decoy_size);
            for (size_t j = 0; j < decoy_size; ++j) {
                junk[j] = static_cast<uint8_t>(byte_dis(gen));
            }
            f.write(reinterpret_cast<const char*>(junk.data()), decoy_size);
            return f.good();
        }));
    }

    bool success = true;
    for (auto& fut : futures) {
        if (!fut.get()) success = false;
    }

    return success;
}

bool StripeIO::read_striped(std::vector<uint8_t>& out_data) {
    if (active_paths_.empty()) return false;

    out_data.clear();
    std::vector<std::vector<uint8_t>> chunks(active_paths_.size());
    std::vector<std::future<bool>> futures;

    for (size_t i = 0; i < active_paths_.size(); ++i) {
        std::string path = active_paths_[i];
        std::vector<uint8_t>* chunk_ref = &chunks[i];
        futures.push_back(std::async(std::launch::async, [path, chunk_ref]() {
            std::ifstream f(path, std::ios::binary | std::ios::ate);
            if (!f) return false;
            std::streamsize size = f.tellg();
            f.seekg(0, std::ios::beg);
            chunk_ref->resize(static_cast<size_t>(size));
            f.read(reinterpret_cast<char*>(chunk_ref->data()), size);
            return f.good();
        }));
    }

    bool success = true;
    for (auto& fut : futures) {
        if (!fut.get()) success = false;
    }

    if (!success) return false;

    // Stitch active stripes back together
    size_t total_size = 0;
    for (const auto& chunk : chunks) {
        total_size += chunk.size();
    }

    out_data.reserve(total_size);
    for (const auto& chunk : chunks) {
        out_data.insert(out_data.end(), chunk.begin(), chunk.end());
    }

    return true;
}

} // namespace tesseract
