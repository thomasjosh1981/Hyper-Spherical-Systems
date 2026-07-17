#!/usr/bin/env python3
"""Smoke test for tesseract_bridge.dll via ctypes."""
import ctypes, ctypes.util, json, os, sys

DLL = r"C:\Users\twist\workspace\project_tesseract\build\tesseract_bridge.dll"
if not os.path.exists(DLL):
    print(f"FAIL: DLL not found at {DLL}")
    sys.exit(1)

lib = ctypes.cdll.LoadLibrary(DLL)

# Bind function signatures
lib.tess_create.restype = ctypes.c_void_p
lib.tess_destroy.argtypes = [ctypes.c_void_p]

lib.tess_init_vram.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64]
lib.tess_init_vram.restype  = ctypes.c_int

lib.tess_compress.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
                              ctypes.c_char_p, ctypes.c_int]
lib.tess_compress.restype  = ctypes.c_int

lib.tess_vram_usage_pct.argtypes = [ctypes.c_void_p]
lib.tess_vram_usage_pct.restype  = ctypes.c_float

lib.tess_observe_layer.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
lib.tess_push_layer.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint64]
lib.tess_push_layer.restype  = ctypes.c_int

lib.tess_predict_next.argtypes = [ctypes.c_void_p,
                                   ctypes.POINTER(ctypes.c_uint32), ctypes.c_int,
                                   ctypes.POINTER(ctypes.c_float)]
lib.tess_predict_next.restype  = ctypes.c_int

lib.tess_total_observations.argtypes = [ctypes.c_void_p]
lib.tess_total_observations.restype  = ctypes.c_uint64

lib.tess_version.restype = ctypes.c_char_p
lib.tess_last_error.argtypes = [ctypes.c_void_p]
lib.tess_last_error.restype  = ctypes.c_char_p

# --- Run ---
print("=== Tesseract Python Bridge Smoke Test ===")
print("Version:", lib.tess_version().decode())

h = lib.tess_create()
print(f"handle = {h:#x}")
assert h, "tess_create returned NULL"

rc = lib.tess_init_vram(h, ctypes.c_uint64(24 * 2**30), ctypes.c_uint64(32 * 2**30))
print(f"init_vram rc = {rc} (expect 0)")
assert rc == 0

# Compress
text = b"the user wants me to look at the codebase structure. " * 25
out_buf = ctypes.create_string_buffer(64 * 1024)
n = lib.tess_compress(h, text, len(text), out_buf, len(out_buf))
print(f"compress -> {n} bytes JSON")
assert n > 0
data = json.loads(out_buf.value[:n].decode())
print(f"  ratio: {data['compression_ratio']:.2f}x, entries: {len(data['entries'])}")
assert data['compression_ratio'] > 2.0

# Push layers + check VRAM usage
for i in range(40):
    lib.tess_push_layer(h, ctypes.c_uint32(i), ctypes.c_uint64(200 * 2**20))
pct = lib.tess_vram_usage_pct(h)
print(f"vram_usage_pct = {pct:.1f}%")
assert pct > 0.0

# Train predictor
for i in range(100):
    lib.tess_observe_layer(h, ctypes.c_uint32(i % 4))
n_obs = lib.tess_total_observations(h)
print(f"total_observations = {n_obs}")
assert n_obs == 100

ids = (ctypes.c_uint32 * 4)()
conf = ctypes.c_float()
n_pred = lib.tess_predict_next(h, ids, 4, ctypes.byref(conf))
print(f"predict_next -> {n_pred} predictions, top confidence = {conf.value:.2f}")
assert n_pred > 0

print(f"last_error: '{lib.tess_last_error(h).decode()}'")
lib.tess_destroy(h)
print("=== ALL CHECKS PASSED ===")
