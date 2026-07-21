#pragma once
#include <string>
#include <vector>

namespace hypersp {

struct HfModelMeta {
    std::string model_id;
    std::string author;
    size_t size_mb;
    bool has_safetensors;
};

class HuggingFaceClient {
public:
    HuggingFaceClient();
    ~HuggingFaceClient() = default;

    // Search for public models based on a query
    std::vector<HfModelMeta> search_models(const std::string& query);

    // Stream remote safetensor weights into a local buffer
    bool stream_weights(const std::string& model_id, std::vector<uint8_t>& buffer_out);
};

} // namespace hypersp
