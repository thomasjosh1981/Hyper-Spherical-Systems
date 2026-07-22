#pragma once
#include <string>
#include <vector>

namespace hypersp {

class AutoEmbedder {
public:
    AutoEmbedder();
    ~AutoEmbedder();

    // Initialize the embedding model (e.g., all-MiniLM-L6-v2.gguf)
    bool initialize(const std::string& embedding_model_path);

    // Generate embeddings for a given input text
    std::vector<float> generate_embeddings(const std::string& input_text);

    // Ingest a collection of documents, generate embeddings, and construct Pop Clusters
    // saving them directly into the HSCC format for the orchestrator to route against.
    bool build_pop_clusters(const std::vector<std::string>& documents, const std::string& output_hscc_path);

private:
    bool initialized_;
    std::string model_path_;
    void* embedder_ctx_; // Opaque pointer to underlying model context
};

} // namespace hypersp
