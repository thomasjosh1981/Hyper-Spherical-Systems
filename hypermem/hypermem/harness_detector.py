"""
HyperMem Universal Harness Detector & Hook Authorizer
=====================================================
Scans local ports and system processes to identify running LLM harnesses
(Ollama, LM Studio, Claude Desktop, Hermes, OpenClaw, Browser extensions, ADB).
"""

import socket
from typing import Dict, List, Any


class HarnessDetector:
    """
    Identifies active AI processes and suggests secure, anti-intrusive proxy hooks.
    """

    KNOWN_HARNESSES = [
        {"name": "Ollama Service", "default_port": 11434, "protocol": "ollama_native"},
        {"name": "LM Studio Local Server", "default_port": 1234, "protocol": "openai_compatible"},
        {"name": "vLLM High-Throughput Engine", "default_port": 8000, "protocol": "openai_compatible"},
        {"name": "LocalAI Unified Endpoint", "default_port": 8080, "protocol": "openai_compatible"},
        {"name": "Text Generation WebUI (oobabooga)", "default_port": 5000, "protocol": "openai_compatible"},
        {"name": "Claude Desktop / Hermes Harness", "default_port": 3000, "protocol": "anthropic_mcp"}
    ]

    @staticmethod
    def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                return s.connect_ex((host, port)) == 0
        except Exception:
            return False

    def scan_active_harnesses(self) -> List[Dict[str, Any]]:
        """Scans local ports to discover active harnesses."""
        active = []
        for harness in self.KNOWN_HARNESSES:
            port = harness["default_port"]
            if self.is_port_open(port):
                active.append({
                    "name": harness["name"],
                    "port": port,
                    "status": "RUNNING_ACTIVE",
                    "protocol": harness["protocol"],
                    "hook_recommendation": f"Route traffic through HyperMem Proxy on Port 8765 -> Fallback to {port}"
                })
        return active

    def generate_authorization_request(self, detected_harness: Dict[str, Any]) -> str:
        return (
            f"[HyperMem Hook Authorization Request]\n"
            f"Detected active AI harness: {detected_harness['name']} on Port {detected_harness['port']}.\n"
            f"Would you like HyperMem to attach non-intrusive Synthuron memory & ISSI prompt caching? [Y/N]"
        )
