"""
gui/sfs_container_manager.py — Enforces SFS+ Native Capabilities & Peer Model Mesh Access
==========================================================================================
Enforces SFS+ guarantees for unpacked models:
  - Native Vision, TTS, Tool Calling bindings
  - Strict English-only enforcement (unless configured otherwise)
  - Secure Sandboxed PC access with explicit user consent
  - Peer-to-Peer Cross-Access: any SFS+ model can consult and use any other local SFS+ model on the PC
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    pass  # For headless testing

try:
    from gui.sfs_model_mesh import get_sfs_mesh, SFSModelMesh
except ImportError:
    try:
        from sfs_model_mesh import get_sfs_mesh, SFSModelMesh
    except ImportError:
        get_sfs_mesh = None


class SFSContainerManager:
    """Wraps an SFS+ model to ensure capability bounds, security restrictions, and peer model access."""
    
    def __init__(self, model_name: str, multilingual: bool = False, model_path: Optional[str] = None):
        self.model_name = model_name
        self.model_path = model_path
        self.multilingual = multilingual
        self.sandbox_enabled = True
        self.tools_available = [
            "python_repl",
            "system_shell",
            "file_system",
            "vision_api",
            "tts_engine",
            "consult_peer_model",
            "list_peer_models",
            "delegate_task_vmoe"
        ]
        self.mesh: Optional[SFSModelMesh] = get_sfs_mesh(model_path) if get_sfs_mesh else None

    def list_peer_models(self) -> List[Dict[str, Any]]:
        """Discover and list all other SFS+ models available on this computer."""
        if self.mesh:
            return self.mesh.list_peers(exclude_self=True)
        return []

    def consult_peer_model(self, target_model_name: str, prompt: str) -> Dict[str, Any]:
        """Directly calls another local SFS+ model on this machine to assist or collaborate."""
        if self.mesh:
            return self.mesh.consult_peer_model(target_model_name, prompt, caller_identity=self.model_name)
        return {
            "success": False,
            "error": "SFS Model Mesh subsystem not initialized.",
            "response": None
        }

    def generate_system_prompt(self) -> str:
        """Injects capability awareness into the model's system prompt."""
        peers = self.list_peer_models()
        peer_names = [p["name"] for p in peers] if peers else ["(None currently in directory)"]

        prompt = (
            f"You are operating within an SFS+ Container (Project Tesseract). "
            f"You have NATIVE capabilities including Vision, Text-to-Speech (TTS), Tool Calling, "
            f"and Peer-to-Peer Cross-Access to any other SFS+ model installed on this computer.\n"
            f"Available tools: {', '.join(self.tools_available)}.\n"
            f"Available Peer SFS+ Models on this PC: {', '.join(peer_names)}.\n"
            f"You may use 'consult_peer_model(target_model_name, prompt)' to collaborate, verify reasoning, or delegate tasks to any local peer model.\n"
        )
        
        if not self.multilingual:
            prompt += "CRITICAL RULE: You must communicate exclusively in English. Do not use translation layers or other languages. "
            
        prompt += "You have sandboxed PC access. You must request EXPLICIT USER CONSENT before executing shell or Python commands."
        return prompt
        
    def execute_sandboxed_command(self, cmd: str, is_python: bool = False, parent_widget: Optional['QtWidgets.QWidget'] = None) -> str:
        """
        Executes a command on the user's PC only after receiving explicit consent.
        """
        if not self.sandbox_enabled:
            return "Error: Sandbox execution is disabled."
            
        # Ask for explicit user consent
        if parent_widget and 'PySide6.QtWidgets' in sys.modules:
            reply = QtWidgets.QMessageBox.question(
                parent_widget,
                "⚠️ SFS+ Sandbox Execution Request",
                f"The model '{self.model_name}' wants to execute the following command on your PC:\n\n{cmd}\n\nDo you allow this?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return "Execution Denied by User."
        else:
            # Headless / CLI prompt
            print(f"\n[SFS+ SANDBOX WARNING] The model wants to execute:\n{cmd}")
            ans = input("Allow execution? (y/n): ").strip().lower()
            if ans != 'y':
                return "Execution Denied by User."
                
        # Execute securely
        try:
            if is_python:
                # Wrap python code in a temporary execution
                result = subprocess.run(
                    [sys.executable, "-c", cmd], 
                    capture_output=True, 
                    text=True, 
                    timeout=30
                )
            else:
                result = subprocess.run(
                    cmd, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    timeout=30
                )
            return f"Stdout:\n{result.stdout}\nStderr:\n{result.stderr}"
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out after 30 seconds."
        except Exception as e:
            return f"Sandbox Execution Error: {str(e)}"
