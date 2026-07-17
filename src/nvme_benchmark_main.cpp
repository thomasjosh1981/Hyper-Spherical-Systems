// Thin entry point for the nvme_benchmark executable.
// Delegates to tesseract::benchmark::runBench() defined in nvme_benchmark.cpp.
namespace tesseract::benchmark {
    int runBench();
}

int main() {
    return tesseract::benchmark::runBench();
}
