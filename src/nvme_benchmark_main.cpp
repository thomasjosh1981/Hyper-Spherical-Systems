// Thin entry point for the nvme_benchmark executable.
// Delegates to hypersp::benchmark::runBench() defined in nvme_benchmark.cpp.
namespace hypersp::benchmark {
    int runBench();
}

int main() {
    return hypersp::benchmark::runBench();
}
