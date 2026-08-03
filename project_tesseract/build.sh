#!/bin/bash
set -e

BUILD_DIR="tesseract_build"

if command -v g++ > /dev/null 2>&1; then
    echo "[Build] Found g++, compiling..."
    g++ -O3 -pthread -I$BUILD_DIR $BUILD_DIR/tesseract_memory_core.cpp $BUILD_DIR/main.cpp -o tesseract_test_runner
    echo "[Build] Compilation successful."
elif command -v cl > /dev/null 2>&1; then
    echo "[Build] Found MSVC (cl), compiling..."
    cl /O2 /I$BUILD_DIR $BUILD_DIR/tesseract_memory_core.cpp $BUILD_DIR/main.cpp /Fe:tesseract_test_runner.exe
    echo "[Build] Compilation successful."
else
    echo "[Error] No suitable compiler (g++ or cl) found in PATH."
    exit 1
fi

echo "[Run] Executing test runner..."
./tesseract_test_runner || cmd.exe /c tesseract_test_runner.exe
