#pragma once
#include <string>
#include <vector>
#include <cstdint>
#include <memory>
#include <stdexcept>

namespace hypersp {

enum class GGUFType : uint32_t {
    F32  = 0,
    F16  = 1,
    Q4_0 = 2,
    Q4_1 = 3,
    // (other types can be added, but we only support f32 for candy spinner initially)
    UNKNOWN = 0xFFFFFFFF
};

struct GGUFTensorInfo {
    std::string name;
    std::vector<uint64_t> dimensions;
    GGUFType type;
    uint64_t offset;
    
    size_t num_elements() const {
        size_t count = 1;
        for (auto d : dimensions) count *= d;
        return count;
    }
    
    size_t element_size() const {
        switch (type) {
            case GGUFType::F32: return 4;
            case GGUFType::F16: return 2;
            default: return 0; // unsupported
        }
    }
};

class GGUFReader {
public:
    explicit GGUFReader(const std::string& filename);
    ~GGUFReader();

    bool is_valid() const { return valid_; }
    const std::vector<GGUFTensorInfo>& tensors() const { return tensors_; }
    const std::vector<std::string>& tokens() const { return tokens_; }
    
    // Read raw tensor data. Caller is responsible for knowing it's float32 for now.
    std::vector<float> read_tensor_f32(const GGUFTensorInfo& tensor);

private:
    void parse();
    std::string read_string();
    template<typename T> T read_val();

    std::string filename_;
    void* file_handle_ = nullptr;
    void* map_handle_  = nullptr;
    const uint8_t* data_ = nullptr;
    size_t file_size_ = 0;
    size_t offset_ = 0; // current parse offset
    uint64_t data_alignment_ = 32;
    
    bool valid_ = false;
    std::vector<GGUFTensorInfo> tensors_;
    std::vector<std::string> tokens_;
};

} // namespace hypersp
