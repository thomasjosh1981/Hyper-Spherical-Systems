#include "neuron_graph.hpp"
#include <chrono>
#include <algorithm>

namespace hypersp {

void NeuronGraph::add_neuron(uint32_t id, const std::string& phrase, const std::vector<float>& embedding) {
    VirtualNeuron vn;
    vn.id = id;
    vn.phrase = phrase;
    vn.embedding = embedding;
    vn.spherical_coord = HypersphereMath::cartesian_to_hyperspherical(embedding);
    vn.last_accessed = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();

    neurons_[id] = vn;
}

void NeuronGraph::link_neurons(uint32_t id1, uint32_t id2, float weight, const std::string& semantic_bridge) {
    if (neurons_.find(id1) == neurons_.end() || neurons_.find(id2) == neurons_.end()) {
        return; // Neurons must exist
    }

    // Dynamic scale limit
    if (weight < 0.0f) weight = 0.0f;
    if (weight > 1.0f) weight = 1.0f;

    // Link id1 -> id2
    auto& list1 = adjacency_list_[id1];
    auto it1 = std::find_if(list1.begin(), list1.end(), [id2](const Synthuron& sy) {
        return sy.target_neuron_id == id2;
    });
    if (it1 != list1.end()) {
        it1->weight = weight;
        if (!semantic_bridge.empty()) it1->semantic_bridge = semantic_bridge;
    } else {
        list1.push_back({id2, weight, semantic_bridge});
    }

    // Link id2 -> id1 (bidirectional)
    auto& list2 = adjacency_list_[id2];
    auto it2 = std::find_if(list2.begin(), list2.end(), [id1](const Synthuron& sy) {
        return sy.target_neuron_id == id1;
    });
    if (it2 != list2.end()) {
        it2->weight = weight;
        if (!semantic_bridge.empty()) it2->semantic_bridge = semantic_bridge;
    } else {
        list2.push_back({id1, weight, semantic_bridge});
    }
}

void NeuronGraph::add_hypertag(const std::string& tag, uint32_t neuron_id) {
    auto& list = hypertags_[tag];
    if (std::find(list.begin(), list.end(), neuron_id) == list.end()) {
        list.push_back(neuron_id);
    }
}

std::vector<uint32_t> NeuronGraph::get_hypertag_neurons(const std::string& tag) const {
    auto it = hypertags_.find(tag);
    if (it != hypertags_.end()) {
        return it->second;
    }
    return {};
}

uint32_t NeuronGraph::create_hypercluster(const HypersphereCoordinate& centroid, float radius) {
    uint32_t id = next_cluster_id_++;
    Hypercluster hc;
    hc.cluster_id = id;
    hc.centroid = centroid;
    hc.radius = radius;
    hyperclusters_[id] = hc;
    return id;
}

void NeuronGraph::add_to_hypercluster(uint32_t cluster_id, uint32_t neuron_id) {
    auto it = hyperclusters_.find(cluster_id);
    if (it != hyperclusters_.end()) {
        auto& members = it->second.partial_members;
        if (std::find(members.begin(), members.end(), neuron_id) == members.end()) {
            members.push_back(neuron_id);
        }
    }
}

std::vector<Synthuron> NeuronGraph::get_weak_relationships(uint32_t neuron_id, float min_threshold, float max_threshold) const {
    std::vector<Synthuron> results;
    auto it = adjacency_list_.find(neuron_id);
    if (it == adjacency_list_.end()) return results;

    for (const auto& sy : it->second) {
        if (sy.weight >= min_threshold && sy.weight <= max_threshold) {
            results.push_back(sy);
        }
    }
    return results;
}

float NeuronGraph::get_link_strength(uint32_t id1, uint32_t id2) const {
    auto it = adjacency_list_.find(id1);
    if (it != adjacency_list_.end()) {
        for (const auto& sy : it->second) {
            if (sy.target_neuron_id == id2) return sy.weight;
        }
    }
    return 0.0f;
}

} // namespace hypersp
