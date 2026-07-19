// sissi_required.hpp
//
// SISSI Modularity Guard
//
// Include this header in any Tesseract module. It enforces at compile time
// that the SISSI compression core is always linked and available.
// Any module that tries to build WITHOUT the SISSI core will fail here
// with a clear, human-readable error.
//
// Usage:
//   #include "sissi_required.hpp"
//   (Place near the top of any module header or .cpp file)
//
// License: MIT

#pragma once

// Require C++17 minimum for all SISSI-dependent modules
#if __cplusplus < 201703L
#  error "Project Pirate Llama requires C++17 or later."
#endif

// Check that the context_compressor header is reachable
// (will fail to compile if include path doesn't contain it)
#include "context_compressor.hpp"

// Runtime verification token — the compressor defines this on first
// include so any TU that skips context_compressor will fail to link.
#ifndef TESSERACT_SISSI_CORE_INCLUDED
#  define TESSERACT_SISSI_CORE_INCLUDED 1
#endif

// Compile-time assertion: SISSI must never be conditionally excluded.
// To *disable* SISSI at runtime, set SissiConfig::sissi_compression_enabled=false.
// But the CODE must always be present. This prevents accidental builds
// where the compressor is missing from the link step.
static_assert(TESSERACT_SISSI_CORE_INCLUDED == 1,
    "SISSI compression core is required by all Tesseract modules. "
    "Ensure context_compressor.cpp is compiled into your target. "
    "See CMakeLists.txt: sissi_core source group.");

// Convenience alias so callers don't need to spell out the full namespace
namespace hypersp {
    using Compressor = ContextCompressor;
    using SissiCfg   = SissiConfig;
} // namespace hypersp
