// runtime_directives.hpp — spec V1.4 AdvancedDirectives + GUI bridge
#pragma once
#include <string>
#include <fstream>

namespace Tesseract::GUI::Integration {

    struct AdvancedDirectives {
        bool elastic_breathing_search = true;
        bool enable_circuit_breaker = true;
        bool scissi_phrase_compression = true;
        bool homophonic_flattening_matrix = true;
        float vram_saturation_target = 0.50f;
        float nvme_stay_in_buffer = 0.15f;
        float load_in_headroom_trigger = 0.40f;
    };

    // Serializes GUI states directly into the harness-readable blueprint spec file.
    // Path is whatever blueprint.json the GUI dumps to (defaults to repo root).
    void CommitAdvancedDirectives(const std::string& blueprint_path,
                                    const AdvancedDirectives& settings);
}
