// runtime_directives.cpp — spec V1.4 verbatim implementation.
// Serializes AdvancedDirectives into a JSON blueprint consumed by the build harness.
#include "runtime_directives.hpp"

namespace Tesseract::GUI::Integration {

    void CommitAdvancedDirectives(const std::string& blueprint_path,
                                    const AdvancedDirectives& settings) {
        std::ofstream file(blueprint_path, std::ios::trunc);
        if (!file.is_open()) return;
        file << "{\n";
        file << "  \"runtime_directives\": {\n";
        file << "    \"elastic_breathing_search\": " << (settings.elastic_breathing_search ? "true" : "false") << ",\n";
        file << "    \"enable_circuit_breaker\": "   << (settings.enable_circuit_breaker   ? "true" : "false") << ",\n";
        file << "    \"scissi_phrase_compression\": " << (settings.scissi_phrase_compression ? "true" : "false") << ",\n";
        file << "    \"homophonic_flattening_matrix\": " << (settings.homophonic_flattening_matrix ? "true" : "false") << ",\n";
        file << "    \"vram_saturation_target\": " << settings.vram_saturation_target << ",\n";
        file << "    \"nvme_stay_in_buffer\": "     << settings.nvme_stay_in_buffer << ",\n";
        file << "    \"load_in_headroom_trigger\": " << settings.load_in_headroom_trigger << "\n";
        file << "  }\n";
        file << "}\n";
    }

}
