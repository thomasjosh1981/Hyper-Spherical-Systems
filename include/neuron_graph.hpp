#pragma once
#include <string>
#include <vector>
#include <unordered_map>
#include <memory>
#include "hypersphere.hpp"

namespace hypersp {

struct VirtualNeuron {
    uint32_t id;
    std::string phrase;
    std::vector<float> embedding; // Projection vector
    HypersphereCoordinate spherical_coord; // Mapped coordinate
    uint64_t last_accessed;
};

// Replaces CognitiveLink with Synthuron
struct Synthuron {
    uint32_t target_neuron_id;
    float weight; // Link strength [0.0 - 1.0]
    std::string semantic_bridge; // Context label for the link
};

struct Hypercluster {
    uint32_t cluster_id;
    HypersphereCoordinate centroid;
    float radius;
    std::vector<uint32_t> partial_members;
};

class NeuronGraph {
public:
    NeuronGraph() = default;

    // Registers a new virtual neuron
    void add_neuron(uint32_t id, const std::string& phrase, const std::vector<float>& embedding);

    // Creates a bidirectional synthuron link with a specific semantic bridge
    void link_neurons(uint32_t id1, uint32_t id2, float weight, const std::string& semantic_bridge = "");

    // Add a concept to a hyper-tag list
    void add_hypertag(const std::string& tag, uint32_t neuron_id);

    // Retrieve all neurons associated with a hyper-tag
    std::vector<uint32_t> get_hypertag_neurons(const std::string& tag) const;

    // Create a hypercluster around a centroid
    uint32_t create_hypercluster(const HypersphereCoordinate& centroid, float radius);

    // Add a neuron to a hypercluster
    void add_to_hypercluster(uint32_t cluster_id, uint32_t neuron_id);

    // Returns links that are weakly related (low relationship threshold)
    std::vector<Synthuron> get_weak_relationships(uint32_t neuron_id, float min_threshold = 0.05f, float max_threshold = 0.25f) const;

    // Checks if two neurons have any relationship mapped
    float get_link_strength(uint32_t id1, uint32_t id2) const;

private:
    std::unordered_map<uint32_t, VirtualNeuron> neurons_;
    std::unordered_map<uint32_t, std::vector<Synthuron>> adjacency_list_;
    
    // Inverted Index for tags -> list of neuron IDs
    std::unordered_map<std::string, std::vector<uint32_t>> hypertags_;
    
    // Hyperclusters map
    std::unordered_map<uint32_t, Hypercluster> hyperclusters_;
    uint32_t next_cluster_id_ = 1;
};

} // namespace hypersp
