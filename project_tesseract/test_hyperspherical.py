#!/usr/bin/env python3
"""
Test suite for 4D Hyperspherical Tensor Cache & Async Staging System.
Verifies distance calculations, cache loading radius, hysteresis bounds,
VRAM ping-pong streaming, and end-to-end hyperspherical tensor management.
"""

import unittest
import math
from cache_trigger import (
    calculate_hyperspherical_distance,
    check_cache_trigger,
    should_retain_in_cache,
    HypersphericalCacheManager
)
from vram_streamer import VRAMPingPongOrchestrator
from tesseract_core import TokenShredderEngine, run_local_pipeline

class TestHypersphericalCacheTrigger(unittest.TestCase):
    
    def test_distance_calculation_4d(self):
        # 4D origin (0, 0, 0, 0) to (1, 1, 1, 1) -> distance sqrt(4) = 2.0
        v1 = [0.0, 0.0, 0.0, 0.0]
        v2 = [1.0, 1.0, 1.0, 1.0]
        dist = calculate_hyperspherical_distance(v1, v2)
        self.assertAlmostEqual(dist, 2.0, places=5)

    def test_distance_dimension_mismatch(self):
        v1 = [0.0, 0.0, 0.0]
        v2 = [1.0, 1.0, 1.0, 1.0]
        with self.assertRaises(ValueError):
            calculate_hyperspherical_distance(v1, v2)

    def test_cache_trigger_radius(self):
        token = [0.0, 0.0, 0.0, 0.0]
        # Target within 0.75 radius: dist = sqrt(0.3^2 * 4) = sqrt(0.36) = 0.6 <= 0.75
        target_in = [0.3, 0.3, 0.3, 0.3]
        # Target outside 0.75 radius: dist = sqrt(0.5^2 * 4) = 1.0 > 0.75
        target_out = [0.5, 0.5, 0.5, 0.5]

        self.assertTrue(check_cache_trigger(token, target_in, load_radius=0.75))
        self.assertFalse(check_cache_trigger(token, target_out, load_radius=0.75))

    def test_hysteresis_retention(self):
        token = [0.0, 0.0, 0.0, 0.0]
        # Distance = 0.80 -> Outside load_radius (0.75), but inside retention (0.75 + 0.20 = 0.95)
        # Coordinates: sqrt(4 * 0.4^2) = 0.8
        borderline_target = [0.4, 0.4, 0.4, 0.4]

        # Should NOT trigger a fresh load
        self.assertFalse(check_cache_trigger(token, borderline_target, load_radius=0.75))
        # Should RETAIN if already cached in VRAM
        self.assertTrue(should_retain_in_cache(token, borderline_target, load_radius=0.75, stay_buffer=0.20))

    def test_hyperspherical_cache_manager_decisions(self):
        manager = HypersphericalCacheManager(load_radius=0.75, stay_buffer=0.20)
        manager.register_tensor("tensor_layer_1", (0.1, 0.1, 0.1, 0.1)) # dist = 0.2
        manager.register_tensor("tensor_layer_2", (0.4, 0.4, 0.4, 0.4)) # dist = 0.8
        manager.register_tensor("tensor_layer_3", (0.8, 0.8, 0.8, 0.8)) # dist = 1.6

        token = [0.0, 0.0, 0.0, 0.0]
        active_cached = ["tensor_layer_2"] # layer 2 is already in VRAM

        decisions = manager.evaluate_token(token, active_cached)

        self.assertEqual(decisions["tensor_layer_1"], "LOAD")   # dist 0.2 <= 0.75 -> LOAD
        self.assertEqual(decisions["tensor_layer_2"], "RETAIN") # dist 0.8 <= 0.95 -> RETAIN
        self.assertEqual(decisions["tensor_layer_3"], "IGNORE") # dist 1.6 > 0.95 -> IGNORE

    def test_vram_ping_pong_orchestrator(self):
        orchestrator = VRAMPingPongOrchestrator()
        self.assertEqual(orchestrator.active_pool, "Pool_A")
        self.assertEqual(orchestrator.loading_pool, "Pool_B")

        orchestrator.stream_layer(layer_id=42, target_pool="Pool_B")
        self.assertEqual(orchestrator.vram_pools["Pool_B"], "Layer_42")

        orchestrator.swap_buffers()
        self.assertEqual(orchestrator.active_pool, "Pool_B")
        self.assertEqual(orchestrator.loading_pool, "Pool_A")
        self.assertIsNone(orchestrator.vram_pools["Pool_A"]) # Cleared pool A to prevent OOM

    def test_token_shredder_engine_integration(self):
        engine = TokenShredderEngine(chunk_size=8)
        payload = "TESSERACT_HYPERSPHERICAL_STREAM_999"
        slices = engine.shred_payload(payload)
        self.assertGreater(len(slices), 0)

        aligned = engine.determine_positions(slices)
        mapped = engine.map_linguistic_tokens(aligned)
        self.assertEqual(len(mapped), len(slices))
        self.assertEqual(mapped[0]["zone_redux_checksum"], "0x7FBF4A90")

if __name__ == "__main__":
    unittest.main()
