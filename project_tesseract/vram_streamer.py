import threading
import time

class VRAMPingPongOrchestrator:
    def __init__(self):
        self.vram_pools = {"Pool_A": None, "Pool_B": None}
        self.active_pool = "Pool_A"
        self.loading_pool = "Pool_B"
        self.lock = threading.Lock()

    def stream_layer(self, layer_id, target_pool):
        time.sleep(0.012) # 12ms simulated transfer delay
        with self.lock:
            self.vram_pools[target_pool] = f"Layer_{layer_id}"

    def swap_buffers(self):
        with self.lock:
            self.vram_pools[self.active_pool] = None # Clear old layer to prevent OOM
            self.active_pool, self.loading_pool = self.loading_pool, self.active_pool
