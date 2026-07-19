cmake_minimum_required(VERSION 3.22)
project(Project_Hyperspherical_Core CXX)


option(HYPERSPHERICAL_ENTERPRISE_BUILD "Enable Enterprise Proprietary Features" OFF)
option(BUILD_EMBEDDED_BUILDER "Embed native llama.cpp for local inference" OFF)



# Enforce strict native C++20 compliance
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)


if(BUILD_EMBEDDED_BUILDER)
    message(STATUS "Fetching embedded llama.cpp for native inference...")
    include(FetchContent)
    FetchContent_Declare(
        llama_cpp
        GIT_REPOSITORY https://github.com/ggerganov/llama.cpp.git
        GIT_TAG master
    )
    # Don't build tests/examples from llama.cpp
    set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
    set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(llama_cpp)
    add_compile_definitions(PIRATE_EMBEDDED_BUILDER=1)
endif()

# Platform Optimization: Enforce hardware vector loops for sub-millisecond encryption
if(MSVC)
    string(REPLACE "/RTC1" "" CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG}")
    string(REPLACE "/RTC1" "" CMAKE_C_FLAGS_DEBUG "${CMAKE_C_FLAGS_DEBUG}")
    add_compile_options(/O2 /arch:AVX2 /std:c++20)
else()
    add_compile_options(-O3 -mavx2 -march=native -pthread -flto)
endif()

# Configure POSIX Direct I/O handling structures for asynchronous NVMe direct mapping
if(NOT WIN32)
    add_compile_definitions(_GNU_SOURCE)
endif()

# ── Global binary hardening applied to ALL shipping targets ─────────────
# These flags apply to the entire project via INTERFACE on hypersphere_security,
# which every target links against.
if(MSVC)
    # Control Flow Guard — defeats return-oriented programming (ROP) attacks
    # and makes static analysis of control flow much harder
    add_compile_options(/guard:cf /GS /sdl)
    add_link_options(
        /DYNAMICBASE       # ASLR: binary loads at random base each run
        /NXCOMPAT          # DEP: data pages are never executable
        /RELEASE           # Strip debug info from the PE header
        /PDBALTPATH:%_PDB% # Poison PDB path so IDA/Ghidra can't find symbols
    )
else()
    add_compile_options(
        -fstack-protector-strong
        -fvisibility=hidden   # All symbols hidden unless explicitly exported
        -fPIE
    )
    add_link_options(
        -Wl,-z,relro      # Read-only relocations (hardens GOT)
        -Wl,-z,now        # Resolve all symbols at load (prevents lazy binding attacks)
        -pie
        -s                # Strip ALL symbols from binary
    )
endif()

# UPX post-build packer — finds UPX in common locations and packs the binary.
# If UPX is not found, packing is skipped silently (not a build error).
find_program(UPX_EXE NAMES upx upx.exe
    HINTS
        "C:/Users/twist/Desktop/antigrav"
        "C:/tools"
        "/usr/bin"
        "/usr/local/bin"
    NO_DEFAULT_PATH
)
if(UPX_EXE)
    message(STATUS "UPX found at ${UPX_EXE} — post-build packing enabled")
else()
    message(STATUS "UPX not found — binaries will NOT be UPX-packed")
endif()

# Helper macro: adds a post-build UPX step to a target
macro(add_upx_pack target)
    if(UPX_EXE)
        if(WIN32)
            add_custom_command(TARGET ${target} POST_BUILD
                COMMAND cmd /c "${UPX_EXE} --best --lzma --force $<TARGET_FILE:${target}> || exit 0"
                COMMENT "UPX packing ${target} (LZMA, maximum compression)"
                VERBATIM
            )
        else()
            add_custom_command(TARGET ${target} POST_BUILD
                COMMAND ${UPX_EXE} --best --lzma --force
                        $<TARGET_FILE:${target}>
                COMMENT "UPX packing ${target} (LZMA, maximum compression)"
                VERBATIM
            )
        endif()
    endif()
endmacro()


set(ENTERPRISE_SOURCES "")
if(HYPERSPHERICAL_ENTERPRISE_BUILD)
    set(ENTERPRISE_SOURCES
        src/enterprise/license_manager.cpp
        src/enterprise/drm_manager.cpp
        src/enterprise/hypersphere_pqc.cpp
        src/enterprise/shard_matrix.cpp
        src/enterprise/leet_cipher.cpp
        src/enterprise/stripe_io.cpp
    )
    include_directories(include/enterprise)
    add_compile_definitions(HYPERSPHERICAL_ENTERPRISE_BUILD=1)
endif()

# ── Header-only security library ───────────────────────────────────────
# hypersphere_security is a STATIC library assembled from header-only modules
# (V1.1 obfuscation, V1.1 tripwire, V1.2 optimization). It exports no symbols;
# its purpose is to make include paths consistent across the build.
add_library(hypersphere_security INTERFACE)
if(HYPERSPHERICAL_ENTERPRISE_BUILD)
target_include_directories(hypersphere_security INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_features(hypersphere_security INTERFACE cxx_std_20)
endif()

# ── Core engine executable (built from src/) ────────────────────────────
add_executable(pirate_core
    src/main.cpp
    src/standard_cipher.cpp
    src/context_compressor.cpp
    src/static_dictionary.cpp
    src/dictionary_store.cpp
    src/crypto_engine.cpp
    src/harness_hook.cpp
    src/index_registry.cpp
    src/license_manager.cpp
    src/memory_manager.cpp
    src/nvme_io.cpp
    src/predictive_prefetcher.cpp
    src/recovery_checkpoint.cpp
    src/telemetry_logger.cpp
    src/runtime_directives.cpp
    src/nvme_benchmark.cpp
    src/neuron_graph.cpp
    src/hypersphere.cpp
    src/recursive_updater.cpp
    ${ENTERPRISE_SOURCES}
)
target_include_directories(pirate_core PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(pirate_core PRIVATE hypersphere_security)
if(WIN32)
    target_link_libraries(pirate_core PRIVATE shlwapi kernel32 cfgmgr32)
endif()
add_upx_pack(pirate_core)  # Pack the shipping engine binary

# ── Tests ──────────────────────────────────────────────────────────────
enable_testing()
add_executable(pirate_tests
    src/tests.cpp
    src/standard_cipher.cpp
    src/context_compressor.cpp
    src/static_dictionary.cpp
    src/dictionary_store.cpp
    src/crypto_engine.cpp
    src/harness_hook.cpp
    src/index_registry.cpp
    src/license_manager.cpp
    src/memory_manager.cpp
    src/nvme_io.cpp
    src/predictive_prefetcher.cpp
    src/recovery_checkpoint.cpp
    src/telemetry_logger.cpp
    src/neuron_graph.cpp
    src/hypersphere.cpp
    src/recursive_updater.cpp
    ${ENTERPRISE_SOURCES}
)
target_include_directories(pirate_tests PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(pirate_tests PRIVATE hypersphere_security python_bridge)
if(WIN32)
    target_link_libraries(pirate_tests PRIVATE shlwapi kernel32 cfgmgr32)
endif()
add_test(NAME tesseract_core_tests COMMAND pirate_tests)

if(HYPERSPHERICAL_ENTERPRISE_BUILD)
# ── Security test suite (V1.1–V1.3 coverage) ────────────────────────────
add_executable(pirate_security_tests
    src/enterprise/tests_security.cpp
    src/enterprise/hypersphere_pqc.cpp
    src/enterprise/shard_matrix.cpp
)
target_include_directories(pirate_security_tests PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(pirate_security_tests PRIVATE hypersphere_security)
add_test(NAME pirate_security_tests COMMAND pirate_security_tests)
endif()

# ── NVMe benchmark (standalone) ────────────────────────────────────────
add_executable(nvme_benchmark
    src/nvme_benchmark_main.cpp
    src/nvme_benchmark.cpp
)
target_include_directories(nvme_benchmark PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include)
if(WIN32)
    target_link_libraries(nvme_benchmark PRIVATE shlwapi kernel32 cfgmgr32)
endif()

# ── V1.5 spec surface: root-level bridge executable ────────────────────
# pirate_bridge.cpp is the "external wrapper" that owns the canonical
# tess_* C ABI + (optionally) talks to llama.cpp. It links against the same
# core sources as pirate_core so the TessEngine is shared, not duplicated.
add_executable(pirate_bridge
    pirate_bridge.cpp
    src/python_bridge.cpp
    src/standard_cipher.cpp
    src/context_compressor.cpp
    src/static_dictionary.cpp
    src/dictionary_store.cpp
    src/memory_manager.cpp
    src/predictive_prefetcher.cpp
    src/index_registry.cpp
    src/license_manager.cpp
    src/nvme_io.cpp
    src/recovery_checkpoint.cpp
    src/telemetry_logger.cpp
    src/neuron_graph.cpp
    src/hypersphere.cpp
    src/recursive_updater.cpp
    ${ENTERPRISE_SOURCES}
)
target_include_directories(pirate_bridge PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(pirate_bridge PRIVATE hypersphere_security)
if(WIN32)
    target_link_libraries(pirate_bridge PRIVATE shlwapi kernel32 cfgmgr32)
endif()
add_upx_pack(pirate_bridge)  # Pack the shipping bridge binary

# ── Golden Candy Spinner ───────────────────────────────────────────────
add_executable(golden_candy_spinner
    tools/golden_candy_spinner/golden_candy_spinner.cpp
    src/candy_spinner.cpp
    src/gguf_reader.cpp
    src/hypersphere.cpp
    src/standard_cipher.cpp
    src/context_compressor.cpp
    src/static_dictionary.cpp
    src/dictionary_store.cpp
)
target_include_directories(golden_candy_spinner PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include)
if(WIN32)
    target_link_libraries(golden_candy_spinner PRIVATE kernel32)
endif()

# ── Python bridge DLL (exported C ABI so ctypes can load it) ───────────
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/src/python_bridge.cpp"
        AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/include/python_bridge.hpp")
    add_library(python_bridge SHARED
        src/python_bridge.cpp
        src/standard_cipher.cpp
    src/context_compressor.cpp
        src/static_dictionary.cpp
        src/dictionary_store.cpp
        src/memory_manager.cpp
        src/predictive_prefetcher.cpp
        src/index_registry.cpp
        src/license_manager.cpp
        src/nvme_io.cpp
        src/recovery_checkpoint.cpp
        src/telemetry_logger.cpp
        src/neuron_graph.cpp
        src/hypersphere.cpp
        ${ENTERPRISE_SOURCES}
)
    target_include_directories(python_bridge PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/include)
    target_link_libraries(python_bridge PRIVATE hypersphere_security)
    if(WIN32)
        target_link_libraries(python_bridge PRIVATE shlwapi kernel32 cfgmgr32)
        set_target_properties(python_bridge PROPERTIES PREFIX "" SUFFIX ".dll")
    endif()
    add_upx_pack(python_bridge)  # Pack the shipping DLL
endif()

# ── Optional: real llama.cpp from source ───────────────────────────────
option(PIRATE_BRIDGE_USE_LLAMA "Link the bridge against real llama.cpp" OFF)
if(PIRATE_BRIDGE_USE_LLAMA)
    include(FetchContent)
    FetchContent_Declare(llama
        GIT_REPOSITORY https://github.com/ggerganov/llama.cpp.git
        GIT_TAG        refs/heads/master
    )
    set(LLAMA_NATIVE OFF CACHE BOOL "" FORCE)
    set(LLAMA_AVX    ON  CACHE BOOL "" FORCE)
    set(LLAMA_AVX2   ON  CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(llama)
    target_link_libraries(pirate_bridge PRIVATE llama)
    target_compile_definitions(pirate_bridge PRIVATE PIRATE_BRIDGE_USE_LLAMA=1)
endif()

# ── Pirate Llama — Universal Proxy + Floating GUI ──────────────────────────
# Open-source layers: pirate_proxy, pirate_gui, pirate_main
# Proprietary/hardened: everything in hypersphere_security
add_executable(pirate_llama
    src/pirate_main.cpp
    src/pirate_proxy.cpp
    src/pirate_gui.cpp
    src/model_router.cpp
    src/gateway_scanner.cpp
    src/macro_recorder.cpp
    src/prompt_condenser.cpp
    src/mobile_bridge.cpp
    src/dom_parser.cpp
    src/human_telemetry.cpp
    src/virtual_moe.cpp
    src/feature_router.cpp
    src/arterial_bridge.cpp
    src/synthetic_neuron.cpp
    src/zero_prompt_attention.cpp
    src/matrix_slicer.cpp
    # Core engine (proprietary — compiled separately, anti-decompile hardened)
    src/standard_cipher.cpp
    src/context_compressor.cpp
    src/static_dictionary.cpp
    src/dictionary_store.cpp
    src/memory_manager.cpp
    src/predictive_prefetcher.cpp
    src/nvme_io.cpp
    src/recovery_checkpoint.cpp
    src/telemetry_logger.cpp
    src/neuron_graph.cpp
    src/hypersphere.cpp
    src/index_registry.cpp
    src/license_manager.cpp
    src/runtime_directives.cpp
    ${ENTERPRISE_SOURCES}
)

target_include_directories(pirate_llama PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_link_libraries(pirate_llama PRIVATE hypersphere_security)
if(BUILD_EMBEDDED_BUILDER)
    target_link_libraries(pirate_llama PRIVATE llama)
endif()


if(WIN32)
    # Link Winsock + Win32 GUI subsystem
    target_link_libraries(pirate_llama PRIVATE
        ws2_32 shlwapi kernel32 cfgmgr32 comctl32 user32 gdi32
    )
    # Whole-Program Optimization — only valid per-target (merges all TUs at link)
    # Combined with LTCG this makes function boundaries invisible to decompilers
    target_compile_options(pirate_llama PRIVATE /GL)
    target_link_options(pirate_llama PRIVATE
        /LTCG              # Link-Time Code Generation (merges TUs, erases module boundaries)
        # Note: /DYNAMICBASE /NXCOMPAT /RELEASE /PDBALTPATH are set globally above
    )
else()
    find_package(Threads REQUIRED)
    target_link_libraries(pirate_llama PRIVATE Threads::Threads)
    target_compile_options(pirate_llama PRIVATE -D_FORTIFY_SOURCE=2)
endif()

# UPX pack the main shipping binary last (after LTCG linking completes)
add_upx_pack(pirate_llama)


