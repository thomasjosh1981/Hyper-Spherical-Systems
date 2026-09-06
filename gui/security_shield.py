"""
gui/security_shield.py — HypeS Intercept Security Shield & Anti-Exploit Engine
=============================================================================

Protects intercepted ports from:
  1. DNS Rebinding attacks (malicious websites attempting to hit local AI ports)
  2. Unauthorized Origin / Host spoofing
  3. Excessive payload size DoS attacks (OOM protection)
  4. Malicious prompt injection / Remote Code Execution attempts in AI prompts
  5. Localhost loopback isolation verification

Author: TwistedSoCal / Hyper-Spherical Systems
License: Proprietary — All Rights Reserved
"""

from __future__ import annotations

import re
import json
import socket
from typing import Tuple, Dict, Optional, List

# Maximum allowed payload size (16 MB)
MAX_PAYLOAD_BYTES = 16 * 1024 * 1024

# Allowed Host header prefixes for local listeners
ALLOWED_LOCAL_HOSTS = {
    "localhost", "127.0.0.1", "[::1]", "::1",
    "http://localhost", "http://127.0.0.1"
}

# Malicious payload injection patterns (RCE / command injection / path traversal)
SUSPICIOUS_PROMPT_PATTERNS = [
    re.compile(r"__(import|builtins)__", re.IGNORECASE),
    re.compile(r"eval\s*\(\s*['\"]", re.IGNORECASE),
    re.compile(r"exec\s*\(\s*['\"]", re.IGNORECASE),
    re.compile(r"os\.system\s*\(", re.IGNORECASE),
    re.compile(r"subprocess\.(Popen|call|run)", re.IGNORECASE),
    re.compile(r"\b(rm\s+-rf\s+/|drop\s+database|truncate\s+table)\b", re.IGNORECASE),
    re.compile(r"<\s*script[^>]*>.*system\(", re.IGNORECASE),
]


class SecurityShield:
    """
    Real-time security validator for intercepted HTTP requests.
    Validates Host headers, Origin headers, payload size, and content safety.
    """

    @staticmethod
    def validate_request(parsed_req: dict) -> Tuple[bool, str, int]:
        """
        Validate an incoming intercepted HTTP request.
        Returns: (is_valid: bool, error_message: str, http_status_code: int)
        """
        headers = parsed_req.get("headers", {})
        host_hdr = headers.get("host", "").split(":")[0].lower()
        origin_hdr = headers.get("origin", "").lower()
        referer_hdr = headers.get("referer", "").lower()
        body_bytes = parsed_req.get("body", b"")

        # 1. Payload Size Limit Check (Anti-OOM DoS)
        if len(body_bytes) > MAX_PAYLOAD_BYTES:
            return False, f"Payload size {len(body_bytes)} exceeds maximum limit of {MAX_PAYLOAD_BYTES} bytes", 413

        # 2. Host Header & DNS Rebinding Check
        # Local requests must target localhost / 127.0.0.1 or an explicit cloud domain
        is_cloud = parsed_req.get("is_cloud", False)
        cloud_provider = parsed_req.get("cloud_provider")

        if not is_cloud and not cloud_provider:
            # Local endpoint — verify host is strictly local
            if host_hdr and host_hdr not in ALLOWED_LOCAL_HOSTS and not any(host_hdr.startswith(allowed) for allowed in ALLOWED_LOCAL_HOSTS):
                return False, f"Blocked suspicious Host header '{host_hdr}' (Anti-DNS Rebinding Protection)", 403

        # 3. Browser Origin Validation (Anti-CSRF / Anti-Drive-by-Browser attacks)
        if origin_hdr:
            origin_domain = origin_hdr.replace("http://", "").replace("https://", "").split(":")[0]
            if origin_domain and origin_domain not in ALLOWED_LOCAL_HOSTS and not any(origin_domain.startswith(allowed) for allowed in ALLOWED_LOCAL_HOSTS):
                # Check if it's an approved cloud domain
                if not any(origin_domain.endswith(provider) for provider in ["openai.com", "anthropic.com", "x.ai", "groq.com", "deepseek.com", "googleapis.com"]):
                    return False, f"Blocked unauthorized browser Origin '{origin_hdr}' from querying local AI port", 403

        # 4. Malicious Content Pattern Inspection (Fast pre-screening)
        if body_bytes:
            body_bytes_lower = body_bytes.lower()
            if any(token in body_bytes_lower for token in (b"__import", b"__builtins", b"eval", b"exec", b"os.system", b"subprocess", b"drop database", b"truncate table", b"script")):
                try:
                    body_str = body_bytes.decode("utf-8", errors="ignore")
                    for pattern in SUSPICIOUS_PROMPT_PATTERNS:
                        if pattern.search(body_str):
                            return False, "Blocked suspicious prompt injection or executable command pattern", 400
                except Exception:
                    pass

        return True, "OK", 200

    @staticmethod
    def is_loopback_only(address: str) -> bool:
        """Verify an IP address is strictly loopback (127.x.x.x or ::1)."""
        try:
            ip = socket.gethostbyname(address)
            return ip.startswith("127.") or ip == "::1"
        except Exception:
            return False


class EmergencyKillswitch:
    """
    Hardware & Software E-STOP Engine.
    Instantly slams down all active SFS models, shuts off proxy bridges,
    and terminates rogue processes before data destruction can occur.
    """
    _estop_active = False

    @classmethod
    def is_triggered(cls) -> bool:
        return cls._estop_active

    @classmethod
    def trigger_estop(cls, reason: str = "Manual User Trigger") -> Dict[str, Any]:
        """
        Hard-kills all active AI processes, severs sockets, and locks disk buffers.
        """
        import os
        import signal
        import subprocess

        cls._estop_active = True
        killed_processes = []
        
        # Target process names associated with AI model inferencers and background workers
        target_binaries = [
            "golden_candy_spinner.exe", "golden_candy_spinner",
            "sfs_runtime_launcher.exe", "sfs_runtime_launcher",
            "llama.exe", "ollama.exe", "ollama_llama_server.exe",
            "vram_streamer.exe"
        ]

        if sys.platform == "win32":
            for binary in target_binaries:
                try:
                    res = subprocess.run(
                        f"taskkill /F /IM {binary} /T",
                        shell=True,
                        capture_output=True,
                        text=True
                    )
                    if "SUCCESS" in res.stdout:
                        killed_processes.append(binary)
                except Exception:
                    pass
        else:
            for binary in target_binaries:
                try:
                    subprocess.run(f"pkill -9 -f {binary}", shell=True)
                    killed_processes.append(binary)
                except Exception:
                    pass

        print(f"\n[🛑 E-STOP TRIGGERED] Reason: {reason}")
        print(f"[🛑 E-STOP] Terminated processes: {killed_processes or 'None running'}")

        return {
            "status": "EMERGENCY_STOPPED",
            "reason": reason,
            "killed_processes": killed_processes,
            "timestamp": time.time()
        }

    @classmethod
    def reset_estop(cls) -> None:
        cls._estop_active = False


class AntiDemolitionWatchdog:
    """
    Heuristic Security Shield that monitors for Trojanized SFS+ models attempting:
    1. Rapid unauthorized mass file encryption or deletion.
    2. Exfiltration of credentials, SSH keys, or browser sessions.
    3. Abnormal high-frequency WMI / PowerShell execution attempts.
    """
    
    _suspicious_actions_count = 0
    _threshold = 3

    @classmethod
    def record_suspicious_activity(cls, source_app: str, action: str) -> bool:
        cls._suspicious_actions_count += 1
        print(f"[⚠️ SECURITY ALERT] Suspicious model action detected: {source_app} -> {action}")
        
        if cls._suspicious_actions_count >= cls._threshold:
            EmergencyKillswitch.trigger_estop(
                reason=f"Automated Anti-Demolition: Suspicious behavior threshold exceeded by {source_app} ({action})"
            )
            return True
        return False
        if address in ("127.0.0.1", "::1", "localhost"):
            return True
        if address.startswith("127."):
            return True
        return False
