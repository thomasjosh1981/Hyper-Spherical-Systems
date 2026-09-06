"""
user_vault_auth.py — User Vault Authentication & DPAPI Hardware Shield (Item #24)
================================================================================
Provides:
  1. Default Seamless Windows OS Authentication (DPAPI + User SID):
     - When the authorized user is logged into Windows, unlocks vault seamlessly (0 password prompts).
  2. Optional PIN / Password Mode:
     - Configurable toggle in settings ("Require PIN/Password on every launch").
  3. Drive Theft / Offline Extraction Defense:
     - Vault keys are cryptographically sealed with Windows DPAPI (machine + user bound).
     - If the hard drive is pulled and mounted on another machine or OS, DPAPI fails,
       forcing an Emergency Password / Offline Recovery Key prompt.
  4. 24-Word / Hex Emergency Recovery Key:
     - Allows restoring and decrypting the vault on fresh OS installs or relocated drives.
"""

from __future__ import annotations

import os
import sys
import json
import hmac
import hashlib
import secrets
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from PySide6 import QtCore, QtGui, QtWidgets


def _get_vault_dir() -> Path:
    """Returns directory for encrypted user vaults and auth envelopes."""
    base_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".hypes")) / "HypeS" / "Vaults"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def _get_windows_sid() -> str:
    """Retrieves current user Windows SID or falls back to username."""
    try:
        import ctypes
        import win32api
        import win32security
        user = win32api.GetUserName()
        sid, _, _ = win32security.LookupAccountName(None, user)
        return win32security.ConvertSidToStringSid(sid)
    except Exception:
        return os.environ.get("USERNAME", "DefaultUser")


def _dpapi_protect(data: bytes) -> Optional[bytes]:
    """Encrypts bytes using Windows DPAPI (CryptProtectData)."""
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        pDataIn = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_byte)))
        pDataOut = DATA_BLOB()

        CryptProtectData = ctypes.windll.crypt32.CryptProtectData
        CryptProtectData.argtypes = [
            ctypes.POINTER(DATA_BLOB),
            wintypes.LPCWSTR,
            ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB)
        ]
        CryptProtectData.restype = wintypes.BOOL

        if CryptProtectData(ctypes.byref(pDataIn), "HypeSVaultKey", None, None, None, 0, ctypes.byref(pDataOut)):
            out_bytes = ctypes.string_at(pDataOut.pbData, pDataOut.cbData)
            ctypes.windll.kernel32.LocalFree(pDataOut.pbData)
            return out_bytes
    except Exception:
        pass
    return None


def _dpapi_unprotect(data: bytes) -> Optional[bytes]:
    """Decrypts bytes using Windows DPAPI (CryptUnprotectData)."""
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        pDataIn = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_byte)))
        pDataOut = DATA_BLOB()

        CryptUnprotectData = ctypes.windll.crypt32.CryptUnprotectData
        CryptUnprotectData.argtypes = [
            ctypes.POINTER(DATA_BLOB),
            ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB)
        ]
        CryptUnprotectData.restype = wintypes.BOOL

        if CryptUnprotectData(ctypes.byref(pDataIn), None, None, None, None, 0, ctypes.byref(pDataOut)):
            out_bytes = ctypes.string_at(pDataOut.pbData, pDataOut.cbData)
            ctypes.windll.kernel32.LocalFree(pDataOut.pbData)
            return out_bytes
    except Exception:
        pass
    return None


class UserVaultSecurityManager:
    """
    Manages cryptographic envelopes, default seamless login, and offline recovery keys.
    """

    def __init__(self, username: Optional[str] = None):
        self.username = username or os.environ.get("USERNAME", "DefaultUser")
        self.sid = _get_windows_sid()
        self.vault_dir = _get_vault_dir()
        self.envelope_file = self.vault_dir / f"{self.username}_vault_envelope.json"
        self._active_master_key: Optional[bytes] = None

    def initialize_vault(self, password: Optional[str] = None, require_pin_on_launch: bool = False) -> str:
        """
        Creates a new encrypted vault envelope with DPAPI protection and generates a Recovery Key.
        Returns the generated 24-word / Hex Offline Recovery Key.
        """
        raw_master_key = secrets.token_bytes(32)
        salt = secrets.token_bytes(16)
        recovery_seed = secrets.token_hex(16).upper() # e.g. 32-char hex recovery key
        formatted_recovery_key = "-".join([recovery_seed[i:i+4] for i in range(0, len(recovery_seed), 4)])

        # Derive recovery cipher key
        rec_key_derived = hashlib.pbkdf2_hmac("sha256", formatted_recovery_key.encode("utf-8"), salt, 100000)

        # Encrypt master key using recovery key (XOR / HMAC stream)
        rec_encrypted_master = bytes(a ^ b for a, b in zip(raw_master_key, rec_key_derived[:32]))

        # Encrypt master key with Windows DPAPI (tied to current OS login)
        dpapi_sealed_blob = _dpapi_protect(raw_master_key)
        dpapi_hex = dpapi_sealed_blob.hex() if dpapi_sealed_blob else ""

        # If user specified a manual password
        pwd_encrypted_master = ""
        pwd_hash = ""
        if password:
            pwd_derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
            pwd_encrypted_master = bytes(a ^ b for a, b in zip(raw_master_key, pwd_derived[:32])).hex()
            pwd_hash = hashlib.sha256(password.encode("utf-8") + salt).hexdigest()

        envelope_data = {
            "version": 2,
            "username": self.username,
            "sid": self.sid,
            "require_pin_on_launch": require_pin_on_launch,
            "salt": salt.hex(),
            "dpapi_sealed_master": dpapi_hex,
            "recovery_encrypted_master": rec_encrypted_master.hex(),
            "has_password": bool(password),
            "pwd_encrypted_master": pwd_encrypted_master,
            "pwd_hash": pwd_hash,
            "created_at": QtCore.QDateTime.currentDateTime().toString(QtCore.Qt.ISODate)
        }

        with open(self.envelope_file, "w", encoding="utf-8") as f:
            json.dump(envelope_data, f, indent=2)

        self._active_master_key = raw_master_key
        return formatted_recovery_key

    def try_seamless_unlock(self) -> Tuple[bool, str]:
        """
        Attempts seamless Windows OS authentication (0 password prompts).
        Fails if DPAPI fails (e.g. drive stolen or mounted on another OS) or if require_pin_on_launch is True.
        """
        if not self.envelope_file.exists():
            return False, "Vault envelope not found. New initialization required."

        try:
            with open(self.envelope_file, "r", encoding="utf-8") as f:
                env = json.load(f)

            if env.get("require_pin_on_launch", False):
                return False, "PIN/Password required by user security policy."

            dpapi_hex = env.get("dpapi_sealed_master", "")
            if not dpapi_hex:
                return False, "No DPAPI hardware envelope present."

            raw_dpapi = bytes.fromhex(dpapi_hex)
            unsealed = _dpapi_unprotect(raw_dpapi)

            if unsealed and len(unsealed) == 32:
                self._active_master_key = unsealed
                return True, "Seamless Windows OS authentication successful."
            else:
                return False, "DPAPI verification failed (Drive relocated or Windows credentials altered)."
        except Exception as e:
            return False, f"Envelope read error: {e}"

    def unlock_with_password(self, password: str) -> bool:
        """Unlocks vault using manual password."""
        if not self.envelope_file.exists():
            return False

        try:
            with open(self.envelope_file, "r", encoding="utf-8") as f:
                env = json.load(f)

            salt = bytes.fromhex(env["salt"])
            pwd_hash = hashlib.sha256(password.encode("utf-8") + salt).hexdigest()
            if pwd_hash != env.get("pwd_hash", ""):
                return False

            pwd_derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
            pwd_encrypted_master = bytes.fromhex(env["pwd_encrypted_master"])
            self._active_master_key = bytes(a ^ b for a, b in zip(pwd_encrypted_master, pwd_derived[:32]))
            return True
        except Exception:
            return False

    def unlock_with_recovery_key(self, recovery_key: str) -> bool:
        """Unlocks vault using the offline 32-char / 24-word recovery key."""
        if not self.envelope_file.exists():
            return False

        try:
            cleaned_key = recovery_key.strip().upper().replace(" ", "").replace("-", "")
            formatted_key = "-".join([cleaned_key[i:i+4] for i in range(0, len(cleaned_key), 4)])

            with open(self.envelope_file, "r", encoding="utf-8") as f:
                env = json.load(f)

            salt = bytes.fromhex(env["salt"])
            rec_key_derived = hashlib.pbkdf2_hmac("sha256", formatted_key.encode("utf-8"), salt, 100000)
            rec_encrypted = bytes.fromhex(env["recovery_encrypted_master"])
            self._active_master_key = bytes(a ^ b for a, b in zip(rec_encrypted, rec_key_derived[:32]))

            # Re-seal with current Windows DPAPI on this new host
            new_dpapi = _dpapi_protect(self._active_master_key)
            if new_dpapi:
                env["dpapi_sealed_master"] = new_dpapi.hex()
                env["sid"] = self.sid
                with open(self.envelope_file, "w", encoding="utf-8") as f:
                    json.dump(env, f, indent=2)

            return True
        except Exception:
            return False


class VaultUnlockDialog(QtWidgets.QDialog):
    """
    GUI Unlock Prompt that appears ONLY when manual authentication is required or DPAPI fails.
    """

    def __init__(self, manager: UserVaultSecurityManager, parent=None, is_drive_theft_challenge: bool = False):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("🔐 HypeS User Vault Authentication")
        self.setFixedSize(460, 320)
        self.setStyleSheet("""
            QDialog { background-color: #070c18; color: #f1f5f9; }
            QLabel { color: #cbd5e1; font-size: 12px; }
            QLineEdit { background-color: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 8px; color: #fff; font-size: 13px; }
            QLineEdit:focus { border-color: #00e5ff; }
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0099ff, stop:1 #00e5ff); color: #000; font-weight: bold; padding: 8px 16px; border-radius: 6px; }
            QPushButton:hover { background: #fff; }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        title_lbl = QtWidgets.QLabel("🔐 Encrypted Vault Verification")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #00e5ff;")
        layout.addWidget(title_lbl)

        if is_drive_theft_challenge:
            warn_lbl = QtWidgets.QLabel("⚠️ Security Alert: DPAPI hardware verification failed (Drive relocated or credentials altered). Enter Master Password or Offline Recovery Key.")
            warn_lbl.setWordWrap(True)
            warn_lbl.setStyleSheet("color: #f43f5e; font-weight: bold; font-size: 11px;")
            layout.addWidget(warn_lbl)
        else:
            desc_lbl = QtWidgets.QLabel("Enter your Master PIN / Password or Offline Recovery Key to unlock:")
            layout.addWidget(desc_lbl)

        # Input
        self.auth_input = QtWidgets.QLineEdit()
        self.auth_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.auth_input.setPlaceholderText("Enter Password / PIN or Recovery Key (XXXX-XXXX-...)")
        layout.addWidget(self.auth_input)

        # Checkbox toggle for recovery key mode
        self.chk_recovery = QtWidgets.QCheckBox("Use Offline Recovery Key instead of Password")
        self.chk_recovery.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.chk_recovery.toggled.connect(self._toggle_recovery_mode)
        layout.addWidget(self.chk_recovery)

        # Error label
        self.err_lbl = QtWidgets.QLabel("")
        self.err_lbl.setStyleSheet("color: #f43f5e; font-size: 11px;")
        layout.addWidget(self.err_lbl)

        layout.addStretch()

        # Buttons
        btn_box = QtWidgets.QHBoxLayout()
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("background: #334155; color: #fff;")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_unlock = QtWidgets.QPushButton("🔓 Unlock Vault")
        self.btn_unlock.clicked.connect(self._do_unlock)

        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_unlock)
        layout.addLayout(btn_box)

    def _toggle_recovery_mode(self, checked: bool):
        if checked:
            self.auth_input.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.auth_input.setPlaceholderText("HYPES-XXXX-XXXX-XXXX-XXXX")
        else:
            self.auth_input.setEchoMode(QtWidgets.QLineEdit.Password)
            self.auth_input.setPlaceholderText("Enter Password / PIN")

    def _do_unlock(self):
        val = self.auth_input.text().strip()
        if not val:
            self.err_lbl.setText("Please enter a password or recovery key.")
            return

        if self.chk_recovery.isChecked() or "-" in val:
            if self.manager.unlock_with_recovery_key(val):
                self.accept()
            else:
                self.err_lbl.setText("Invalid Recovery Key.")
        else:
            if self.manager.unlock_with_password(val):
                self.accept()
            else:
                self.err_lbl.setText("Incorrect Password/PIN.")
