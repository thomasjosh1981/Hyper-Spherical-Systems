#include "candy_spinner.hpp"
#include <iostream>
#include <string>

void print_usage() {
    std::cout << "Golden Candy Spinner v1.0\n";
    std::cout << "Usage: golden_candy_spinner.exe <input.gguf> <output.hscc> [--mode <sfs|sfs+|hscc>] [--brain <brain.gguf>]\n";
    std::cout << "This tool respins standard GGUF weights into 4D Hyper-Spherical Candy Chunks (.hscc) or Spun-Floss Sugar (.sfs).\n";
}

int main(int argc, char** argv) {
    if (argc < 3) {
        print_usage();
        return 1;
    }

    std::string input_gguf = argv[1];
    std::string output_file = argv[2];
    hypersp::SpinMode mode = hypersp::SpinMode::HSCC_V2;
    std::string mode_str = "hscc";
    std::string brain_file = "";

    for (int i = 3; i < argc; ++i) {
        std::string flag = argv[i];
        if (flag == "--mode" && i + 1 < argc) {
            mode_str = argv[++i];
            if (mode_str == "sfs") mode = hypersp::SpinMode::SFS;
            else if (mode_str == "sfs+") mode = hypersp::SpinMode::SFS_PLUS;
        } else if (flag == "--brain" && i + 1 < argc) {
            brain_file = argv[++i];
        }
    }

    std::cout << "=== Golden Candy Spinner ===\n";
    std::cout << "Input:  " << input_gguf << "\n";
    std::cout << "Output: " << output_file << "\n";
    std::cout << "Mode:   " << mode_str << "\n";
    if (!brain_file.empty()) {
        std::cout << "Brain:  " << brain_file << " (Autonomous Supervisor Embedded)\n";
    }
    std::cout << "Spinning Euclidean vectors into 4D hyperspace...\n";

    hypersp::CandySpinner spinner;
    if (!brain_file.empty()) {
        spinner.set_recursive_brain(brain_file);
    }
    
    
    if (spinner.spin(input_gguf, output_file, mode)) {
        std::cout << "[SUCCESS] Respin complete. Output ready for Tesseract memory manager.\n";
        return 0;
    } else {
        std::cerr << "[ERROR] Spin failed. Ensure the input file is a valid GGUF.\n";
        return 1;
    }
}
