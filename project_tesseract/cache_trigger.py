import math
from typing import List, Tuple, Dict, Optional, Sequence

def calculate_hyperspherical_distance(vector_a: Sequence[float], vector_b: Sequence[float]) -> float:
    """
    Calculates 4D Euclidean distance (sqrt(dx^2 + dy^2 + dz^2 + dw^2)) between two tensor coordinates.
    """
    if len(vector_a) != 4 or len(vector_b) != 4:
        raise ValueError(f"Vectors must be 4-dimensional (x, y, z, w). Got lengths {len(vector_a)} and {len(vector_b)}.")
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vector_a, vector_b)))

def check_cache_trigger(token_vector: Sequence[float], target_vector: Sequence[float], load_radius: float = 0.75) -> bool:
    """
    Calculates 4D Euclidean distance between active token and target tensor coordinates.
    Returns True if the tensor should be pre-fetched into VRAM.
    """
    if len(token_vector) != 4 or len(target_vector) != 4:
        return False
    distance = calculate_hyperspherical_distance(token_vector, target_vector)
    return distance <= load_radius

def should_retain_in_cache(token_vector: Sequence[float], target_vector: Sequence[float], 
                           load_radius: float = 0.75, stay_buffer: float = 0.20) -> bool:
    """
    Determines if an already loaded tensor should remain in VRAM buffer.
    Applies hysteresis threshold (load_radius + stay_buffer = 0.95) to prevent thrashing.
    """
    if len(token_vector) != 4 or len(target_vector) != 4:
        return False
    distance = calculate_hyperspherical_distance(token_vector, target_vector)
    retention_threshold = load_radius + stay_buffer
    return distance <= retention_threshold

class HypersphericalCacheManager:
    """
    Manages 4D hyperspherical tensor caching with hysteresis to avoid VRAM thrashing.
    """
    def __init__(self, load_radius: float = 0.75, stay_buffer: float = 0.20):
        self.load_radius = load_radius
        self.stay_buffer = stay_buffer
        self.retention_radius = load_radius + stay_buffer
        self.cached_tensors: Dict[str, Tuple[float, float, float, float]] = {}

    def register_tensor(self, tensor_id: str, coordinates: Tuple[float, float, float, float]):
        """Registers target tensor 4D spatial coordinates (x, y, z, w)."""
        if len(coordinates) != 4:
            raise ValueError("Coordinates must be 4D tuple (x, y, z, w).")
        self.cached_tensors[tensor_id] = coordinates

    def evaluate_token(self, token_vector: Sequence[float], active_cached_ids: Sequence[str]) -> Dict[str, str]:
        """
        Evaluates active 4D token against registered tensors.
        Returns action mapping: 'LOAD', 'RETAIN', or 'EVICT' for each tensor.
        """
        decisions: Dict[str, str] = {}
        for tensor_id, target_coords in self.cached_tensors.items():
            dist = calculate_hyperspherical_distance(token_vector, target_coords)
            is_currently_cached = tensor_id in active_cached_ids

            if is_currently_cached:
                if dist <= self.retention_radius:
                    decisions[tensor_id] = "RETAIN"
                else:
                    decisions[tensor_id] = "EVICT"
            else:
                if dist <= self.load_radius:
                    decisions[tensor_id] = "LOAD"
                else:
                    decisions[tensor_id] = "IGNORE"

        return decisions

