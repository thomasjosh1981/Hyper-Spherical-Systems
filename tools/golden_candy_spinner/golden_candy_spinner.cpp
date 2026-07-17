#include "candy_spinner.hpp"
#include <iostream>
#include <string>

void print_usage() {
    std::cout << "Golden Candy Spinner v1.0\n";
    std::cout << "Usage: golden_candy_spinner.exe <input.gguf> <output.hscc>\n";
    std::cout << "This tool respins standard GGUF weights into 4D Hyper-Spherical Candy Chunks (.hscc)\n";
    std::cout << "optimized for Tesseract's elastic breathing search engine.\n";
}

int main(int argc, char** argv) {
    if (argc < 3) {
        print_usage();
        return 1;
    }

    std::string input_gguf = argv[1];
    std::string output_hscc = argv[2];

    std::cout << "=== Golden Candy Spinner ===\n";
    std::cout << "Input:  " << input_gguf << "\n";
    std::cout << "Output: " << output_hscc << "\n";
    std::cout << "Spinning Euclidean vectors into 4D hyperspace...\n";

    tesseract::CandySpinner spinner;
    
    if (spinner.spin(input_gguf, output_hscc)) {
        std::cout << "[SUCCESS] Respin complete. Output ready for Tesseract memory manager.\n";
        return 0;
    } else {
        std::cerr << "[ERROR] Spin failed. Ensure the input file is a valid GGUF.\n";
        return 1;
    }
}
