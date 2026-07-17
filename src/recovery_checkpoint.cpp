// RecoveryCheckpoint: crash-state save/restore on disk for session recovery.
// Binary format:
//   magic   : uint32  = 0xTESSC001 ('TESS' + 0x01)
//   version : uint32  = 1
//   vram    : uint64
//   kvcount : uint32
//   nshards : uint32
//   shards  : nshards * LayerShard
#include "recovery_checkpoint.hpp"
#include <cstdio>
#include <cstring>
#include <fstream>

namespace tesseract {

namespace {
constexpr uint32_t kMagic   = 0x54535301u;  // 'T''S''S' + 0x01 (LE)
constexpr uint32_t kVersion = 1u;
}

bool RecoveryCheckpoint::save_to(const std::string& path) const noexcept {
    try {
        std::ofstream out(path, std::ios::binary | std::ios::trunc);
        if (!out) return false;

        uint32_t magic = kMagic, ver = kVersion;
        uint64_t vram  = vram_mark;
        uint32_t kc    = kv_count;
        uint32_t n     = static_cast<uint32_t>(loaded_shards.size());

        out.write(reinterpret_cast<const char*>(&magic), sizeof(magic));
        out.write(reinterpret_cast<const char*>(&ver),   sizeof(ver));
        out.write(reinterpret_cast<const char*>(&vram),  sizeof(vram));
        out.write(reinterpret_cast<const char*>(&kc),    sizeof(kc));
        out.write(reinterpret_cast<const char*>(&n),     sizeof(n));
        for (const auto& s : loaded_shards) {
            uint32_t id    = s.layer_id;
            uint8_t  tier  = static_cast<uint8_t>(s.tier);
            uint64_t bytes = s.byte_size;
            out.write(reinterpret_cast<const char*>(&id),    sizeof(id));
            out.write(reinterpret_cast<const char*>(&tier),  sizeof(tier));
            out.write(reinterpret_cast<const char*>(&bytes), sizeof(bytes));
        }
        return out.good();
    } catch (...) {
        return false;
    }
}

bool RecoveryCheckpoint::load_from(const std::string& path, void* out_state) noexcept {
    (void)out_state;  // not used; the in-process state is the result of static state of caller
    try {
        std::ifstream in(path, std::ios::binary);
        if (!in) return false;

        uint32_t magic = 0, ver = 0, kc = 0, n = 0;
        uint64_t vram  = 0;
        in.read(reinterpret_cast<char*>(&magic), sizeof(magic));
        in.read(reinterpret_cast<char*>(&ver),   sizeof(ver));
        in.read(reinterpret_cast<char*>(&vram),  sizeof(vram));
        in.read(reinterpret_cast<char*>(&kc),    sizeof(kc));
        in.read(reinterpret_cast<char*>(&n),     sizeof(n));
        if (magic != kMagic || ver != kVersion) return false;

        // Discard payload for now (real impl: route into engine state)
        in.ignore(static_cast<std::streamsize>(n) *
                  (static_cast<std::streamsize>(sizeof(uint32_t))
                   + static_cast<std::streamsize>(sizeof(uint8_t))
                   + static_cast<std::streamsize>(sizeof(uint64_t))));
        return in.good() || in.eof();
    } catch (...) {
        return false;
    }
}

} // namespace tesseract
