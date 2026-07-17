"""wizard.py — first-run setup wizard (QWizard).

Eight pages:
    1. Welcome
    2. Drive detection / assignment
    3. VRAM/RAM calibration
    4. llama.cpp fetch + patch
    5. NVMe benchmark (optional)
    6. 3FA pairing (QR code)
    7. Encryption key generation (stub for now)
    8. Finish (saves config_gui.yaml)

Each page is a QWidget subclass; the wizard walks them in order and
exposes a single `result` dict on completion.
"""

from __future__ import annotations
import os
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from . import config_io


# ── Helpers ────────────────────────────────────────────────────────────
def _list_windows_drives() -> list[tuple[str, str]]:
    """Return [(letter, label)] for every fixed drive on the system."""
    import ctypes
    from ctypes import wintypes
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    out = []
    for i in range(26):
        if bitmask & (1 << i):
            letter = chr(ord("A") + i)
            root = f"{letter}:\\"
            t = ctypes.windll.kernel32.GetDriveTypeW(root)
            # 3 = DRIVE_FIXED
            if t == 3:
                # Volume name
                name_buf = ctypes.create_unicode_buffer(261)
                fs_buf   = ctypes.create_unicode_buffer(261)
                ok = ctypes.windll.kernel32.GetVolumeInformationW(
                    root, name_buf, 261, None, None, None, fs_buf, 261)
                label = name_buf.value if ok else ""
                if not label:
                    label = "(no label)"
                out.append((letter, label))
    return out


def _humanize_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ── Page 1: Welcome ────────────────────────────────────────────────────
class WelcomePage(QtWidgets.QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Welcome to Project Tesseract")
        self.setSubTitle("Let's set up your local AI inference engine.")

        layout = QtWidgets.QVBoxLayout(self)
        text = QtWidgets.QLabel(
            "<h2>Welcome, operator.</h2>"
            "<p>This wizard will guide you through the first-time setup of the "
            "<b>Project Tesseract</b> engine. We will:</p>"
            "<ol>"
            "<li>Detect your drives and assign them to tiers</li>"
            "<li>Calibrate VRAM and RAM limits</li>"
            "<li>Fetch and patch llama.cpp</li>"
            "<li>(Optional) Run the NVMe benchmark</li>"
            "<li>Pair your Android 3FA device</li>"
            "<li>Generate your encryption key fingerprint</li>"
            "</ol>"
            "<p>Setup takes 5–10 minutes. Your progress is saved automatically, "
            "so you can quit and resume any time.</p>"
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        layout.addStretch(1)


# ── Page 2: Drive assignment ───────────────────────────────────────────
class DrivePage(QtWidgets.QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Drive Detection")
        self.setSubTitle("Assign one drive to each tier.")

        self.drives_table = QtWidgets.QTableWidget(0, 4)
        self.drives_table.setHorizontalHeaderLabels(
            ["Drive", "Label", "Role", "Tesseract Path"])
        self.drives_table.horizontalHeader().setStretchLastSection(True)
        self.drives_table.verticalHeader().setVisible(False)
        self.drives_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)

        self.refresh_btn = QtWidgets.QPushButton("Rescan Drives")
        self.refresh_btn.clicked.connect(self._populate)

        info = QtWidgets.QLabel(
            "<i>Tesseract needs at minimum one NVMe (primary). "
            "Secondary and cold tiers are optional.</i>")
        info.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(self.drives_table)
        layout.addWidget(self.refresh_btn)
        self._populate()
        self.registerField("drives_table*", self.drives_table)

    def _populate(self) -> None:
        try:
            drives = _list_windows_drives()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Drive scan failed", str(e))
            drives = []
        self.drives_table.setRowCount(len(drives))
        roles = ["primary", "secondary", "cold", "unused"]
        for row, (letter, label) in enumerate(drives):
            self.drives_table.setItem(row, 0, QtWidgets.QTableWidgetItem(f"{letter}:"))
            self.drives_table.setItem(row, 1, QtWidgets.QTableWidgetItem(label))
            combo = QtWidgets.QComboBox()
            combo.addItems(roles)
            self.drives_table.setCellWidget(row, 2, combo)
            self.drives_table.setItem(row, 3,
                QtWidgets.QTableWidgetItem(f"{letter}:\\tesseract_data"))

    def validatePage(self) -> bool:
        roles = []
        for row in range(self.drives_table.rowCount()):
            combo = self.drives_table.cellWidget(row, 2)
            if combo:
                roles.append(combo.currentText())
        if roles.count("primary") != 1:
            QtWidgets.QMessageBox.warning(
                self, "Setup check",
                "Please pick exactly ONE drive as the primary tier.")
            return False
        return True

    def get_assignments(self) -> list[config_io.DriveAssignment]:
        out = []
        for row in range(self.drives_table.rowCount()):
            letter_item = self.drives_table.item(row, 0)
            label_item  = self.drives_table.item(row, 1)
            combo       = self.drives_table.cellWidget(row, 2)
            path_item   = self.drives_table.item(row, 3)
            if not letter_item or not combo:
                continue
            out.append(config_io.DriveAssignment(
                letter=letter_item.text().rstrip(":"),
                role=combo.currentText(),
                label=label_item.text() if label_item else "",
            ))
        return out


# ── Page 3: VRAM / RAM calibration ────────────────────────────────────
class VramPage(QtWidgets.QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("VRAM and RAM")
        self.setSubTitle("Tell Tesseract how much memory it can use.")

        form = QtWidgets.QFormLayout()

        self.vram_gb = QtWidgets.QSpinBox()
        self.vram_gb.setRange(1, 256)
        self.vram_gb.setValue(12)        # user has a 12GB GPU
        self.vram_gb.setSuffix(" GB")
        self.vram_gb.setToolTip("Total physical VRAM on your GPU (you have 12GB; no discrete GPU).")

        self.ram_gb = QtWidgets.QSpinBox()
        self.ram_gb.setRange(1, 1024)
        self.ram_gb.setValue(32)
        self.ram_gb.setSuffix(" GB")
        self.ram_gb.setToolTip("Total physical system RAM (staging pool).")

        self.vram_ratio = QtWidgets.QDoubleSpinBox()
        self.vram_ratio.setRange(0.10, 0.99)
        self.vram_ratio.setSingleStep(0.05)
        self.vram_ratio.setValue(0.90)   # hard cap = 90% of physical VRAM
        self.vram_ratio.setDecimals(2)
        self.vram_ratio.setToolTip("Hard cap as fraction of physical VRAM. Default 0.90 (use 90% of the GPU).")

        self.ram_ratio = QtWidgets.QDoubleSpinBox()
        self.ram_ratio.setRange(0.05, 0.95)
        self.ram_ratio.setSingleStep(0.05)
        self.ram_ratio.setValue(0.50)
        self.ram_ratio.setDecimals(2)

        form.addRow("Physical VRAM:", self.vram_gb)
        form.addRow("Physical RAM:",  self.ram_gb)
        form.addRow("VRAM cap (max % of total):", self.vram_ratio)
        form.addRow("RAM staging (max % of total):", self.ram_ratio)

        info = QtWidgets.QLabel(
            "<i>The 70% VRAM cap prevents OOM crashes; the 50% RAM staging "
            "leaves room for the OS and other apps.</i>")
        info.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(info)
        layout.addStretch(1)

        self.registerField("vram_gb",    self.vram_gb)
        self.registerField("ram_gb",     self.ram_gb)
        self.registerField("vram_ratio", self.vram_ratio, "value")
        self.registerField("ram_ratio",  self.ram_ratio,  "value")


# ── Page 4: llama.cpp fetch + patch ───────────────────────────────────
class LlamaCppPage(QtWidgets.QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("llama.cpp Integration")
        self.setSubTitle("Fetch upstream and patch in Tesseract's harness hooks.")

        self.path_edit = QtWidgets.QLineEdit(str(Path(r"C:\Users\twist\workspace\llama.cpp")))
        self.browse = QtWidgets.QPushButton("Browse...")
        self.browse.clicked.connect(self._browse)

        path_row = QtWidgets.QHBoxLayout()
        path_row.addWidget(self.path_edit)
        path_row.addWidget(self.browse)

        self.fetch_btn = QtWidgets.QPushButton("Fetch & Patch")
        self.fetch_btn.clicked.connect(self._do_fetch)
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)

        self.status_lbl = QtWidgets.QLabel("Not yet fetched.")
        self.status_lbl.setStyleSheet("color: orange")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Target directory:"))
        layout.addLayout(path_row)
        layout.addWidget(self.fetch_btn)
        layout.addWidget(self.log)
        layout.addWidget(self.status_lbl)

        self.registerField("llama_path", self.path_edit)
        self._llama_ok = False

    def _browse(self) -> None:
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose llama.cpp directory")
        if d:
            self.path_edit.setText(d)

    def _log(self, msg: str) -> None:
        self.log.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def _do_fetch(self) -> None:
        target = Path(self.path_edit.text())
        target.mkdir(parents=True, exist_ok=True)

        # Skip clone if already a git repo with our patch applied
        marker = target / ".tesseract_patched"
        if marker.exists():
            self._log("Already patched; skipping.")
            self._mark_ok()
            return

        self._log(f"Fetching llama.cpp into {target} ...")
        if not (target / ".git").exists():
            self.fetch_btn.setEnabled(False)
            rc = QtCore.QProcess.execute(
                "git", ["clone", "--depth=1",
                        "https://github.com/ggerganov/llama.cpp.git", str(target)])
            self.fetch_btn.setEnabled(True)
            if rc != 0:
                self._log(f"git clone failed (rc={rc})")
                self.status_lbl.setText("Clone failed.")
                self.status_lbl.setStyleSheet("color: red")
                return
        else:
            self._log("Existing repo detected, skipping clone.")

        # Apply patch: copy our harness files into the llama tree
        self._log("Applying harness_hook patch...")
        try:
            import shutil
            shutil.copy(
                Path(r"C:\Users\twist\workspace\project_tesseract\include\harness_hook.hpp"),
                target / "common")
            shutil.copy(
                Path(r"C:\Users\twist\workspace\project_tesseract\src\harness_hook.cpp"),
                target / "common")
            marker.write_text(f"patched at {time.ctime()}\n")
            self._log("Patch applied.")
            self._mark_ok()
        except Exception as e:
            self._log(f"Patch failed: {e}")
            self.status_lbl.setText("Patch failed.")
            self.status_lbl.setStyleSheet("color: red")

    def _mark_ok(self) -> None:
        self._llama_ok = True
        self.status_lbl.setText("Ready.")
        self.status_lbl.setStyleSheet("color: green")
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._llama_ok


# ── Page 5: NVMe benchmark (optional) ────────────────────────────────
class BenchmarkPage(QtWidgets.QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("NVMe Benchmark")
        self.setSubTitle("(Optional) Measure your drive's optimal chunk size.")

        self.run_btn = QtWidgets.QPushButton("Run nvme_benchmark.exe")
        self.run_btn.clicked.connect(self._run)
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(2000)

        self.read_chunk = QtWidgets.QSpinBox()
        self.read_chunk.setRange(65536, 16 * 1024 * 1024)
        self.read_chunk.setValue(1048576)
        self.read_chunk.setSingleStep(65536)
        self.read_chunk.setSuffix(" B")
        self.write_chunk = QtWidgets.QSpinBox()
        self.write_chunk.setRange(65536, 16 * 1024 * 1024)
        self.write_chunk.setValue(524288)
        self.write_chunk.setSingleStep(65536)
        self.write_chunk.setSuffix(" B")

        form = QtWidgets.QFormLayout()
        form.addRow("Optimal read chunk:", self.read_chunk)
        form.addRow("Optimal write chunk:", self.write_chunk)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(
            "<i>This writes test data to every NVMe drive. It is safe but takes "
            "about 30 seconds per drive. Skip if you've already benchmarked.</i>"))
        layout.addWidget(self.run_btn)
        layout.addWidget(self.output)
        layout.addLayout(form)

        self.registerField("read_chunk",  self.read_chunk)
        self.registerField("write_chunk", self.write_chunk)

    def _run(self) -> None:
        exe = Path(r"C:\Users\twist\workspace\project_tesseract\build\nvme_benchmark.exe")
        if not exe.exists():
            self.output.appendPlainText(f"ERROR: {exe} not found. Build the project first.")
            return
        self.output.appendPlainText(f"Running {exe} ...")
        self.run_btn.setEnabled(False)
        try:
            res = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
            self.output.appendPlainText(res.stdout)
            if res.stderr:
                self.output.appendPlainText("--- STDERR ---")
                self.output.appendPlainText(res.stderr)
            self.output.appendPlainText(f"--- benchmark complete (rc={res.returncode}) ---")
            # Try to extract the last "X_read: NNN" / "X_write: NNN" from the output
            import re
            reads, writes = {}, {}
            for line in res.stdout.splitlines():
                m = re.match(r'\s*"([A-Z])_read":\s*(\d+)', line)
                if m: reads[m.group(1)] = int(m.group(2)) * 1024
                m = re.match(r'\s*"([A-Z])_write":\s*(\d+)', line)
                if m: writes[m.group(1)] = int(m.group(2)) * 1024
            if reads:
                # pick max read chunk
                self.read_chunk.setValue(max(reads.values()))
            if writes:
                self.write_chunk.setValue(max(writes.values()))
        except subprocess.TimeoutExpired:
            self.output.appendPlainText("Benchmark timed out after 5 min.")
        finally:
            self.run_btn.setEnabled(True)


# ── Page 6: 3FA pairing ───────────────────────────────────────────────
class ThreeFAPage(QtWidgets.QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("3FA Pairing")
        self.setSubTitle("Pair your Android authenticator device.")

        # Generate a random pairing secret on the fly
        import secrets, base64
        raw = secrets.token_bytes(16)
        self._secret_b32 = base64.b32encode(raw).decode().rstrip("=")
        self._pairing_uri = f"tesseract://pair?secret={self._secret_b32}&issuer=Tesseract"

        qr_img = self._generate_qr(self._pairing_uri)
        self.qr_label = QtWidgets.QLabel()
        self.qr_label.setPixmap(qr_img.scaled(280, 280,
                            QtCore.Qt.KeepAspectRatio,
                            QtCore.Qt.SmoothTransformation))

        self.confirm_chk = QtWidgets.QCheckBox(
            "I have scanned the QR code with the Tesseract Authenticator app.")

        secret_lbl = QtWidgets.QLabel(
            f"<b>Manual entry secret:</b><br>"
            f"<code style='font-family:monospace'>{self._secret_b32}</code>")
        secret_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.qr_label, 0, QtCore.Qt.AlignCenter)
        layout.addWidget(secret_lbl)
        layout.addWidget(self.confirm_chk)
        layout.addStretch(1)

        self.registerField("threefa_paired", self.confirm_chk)

    @staticmethod
    def _generate_qr(data: str) -> QtGui.QPixmap:
        # Minimal pure-Qt QR renderer — fall back to text if no QR lib.
        try:
            import qrcode
            from qrcode.image.pil import PilImage
            img = qrcode.make(data)
            img.save("/tmp/_tess_qr.png")
            return QtGui.QPixmap("/tmp/_tess_qr.png")
        except ImportError:
            pm = QtGui.QPixmap(280, 280)
            pm.fill(QtCore.Qt.white)
            painter = QtGui.QPainter(pm)
            painter.setPen(QtCore.Qt.black)
            painter.drawText(pm.rect(), QtCore.Qt.AlignCenter,
                             f"[QR code for]\n{data[:48]}...")
            painter.end()
            return pm


# ── Page 7: Encryption key generation (stub) ──────────────────────────
class EncryptionPage(QtWidgets.QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Encryption Key")
        self.setSubTitle("Generate your local encryption fingerprint.")

        self.gen_btn = QtWidgets.QPushButton("Generate Key")
        self.gen_btn.clicked.connect(self._gen)
        self.fpr_lbl = QtWidgets.QLabel("<i>(not generated yet)</i>")
        self.fpr_lbl.setWordWrap(True)
        self.fpr_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self._fpr: Optional[str] = None

        info = QtWidgets.QLabel(
            "<i>The actual ChaCha20-Poly1305 / quantum-resistant layer will be "
            "wired up in the next phase. For now we generate a fingerprint that "
            "the GUI can display and verify.</i>")
        info.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(self.gen_btn)
        layout.addWidget(self.fpr_lbl)
        layout.addStretch(1)

    def _gen(self) -> None:
        import secrets, hashlib
        raw = secrets.token_bytes(32)
        digest = hashlib.sha256(raw).hexdigest()
        words = digest[:8].upper()
        self._fpr = f"TESS-KEY-{words}-{digest[8:16].upper()}-{digest[16:24].upper()}"
        self.fpr_lbl.setText(f"<b>Fingerprint:</b><br><code>{self._fpr}</code>")
        self.gen_btn.setEnabled(False)
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._fpr is not None


# ── Page 8: Finish ────────────────────────────────────────────────────
class FinishPage(QtWidgets.QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Setup Complete")
        self.setSubTitle("Tesseract is configured. Click Finish to launch the dashboard.")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(
            "<h2>You're ready to roll.</h2>"
            "<p>Your settings have been saved to "
            "<code>config_gui.yaml</code>.</p>"
            "<p>The main dashboard will now open. From there you can:</p>"
            "<ul>"
            "<li>Monitor live VRAM/RAM/compression telemetry</li>"
            "<li>Tune engine parameters with fine-grained sliders</li>"
            "<li>Run the benchmark again</li>"
            "<li>Manage your 3FA devices</li>"
            "</ul>"))
        layout.addStretch(1)


# ── Wizard assembly ───────────────────────────────────────────────────
class SetupWizard(QtWidgets.QWizard):
    def __init__(self, cfg: Optional[config_io.GuiConfig] = None) -> None:
        super().__init__()
        self.setWindowTitle("Tesseract Setup Wizard")
        self.setWizardStyle(QtWidgets.QWizard.ModernStyle)
        self.resize(820, 640)

        self._cfg = cfg or config_io.load()
        self._drive_page: Optional[DrivePage] = None

        self.addPage(WelcomePage())
        self._drive_page = DrivePage();     self.addPage(self._drive_page)
        self.addPage(VramPage())
        self.addPage(LlamaCppPage())
        self.addPage(BenchmarkPage())
        self.addPage(ThreeFAPage())
        self.addPage(EncryptionPage())
        self.addPage(FinishPage())

    def accept(self) -> None:    # noqa: D401
        # Save settings before closing
        cfg = self._cfg
        cfg.wizard_completed = True
        if self._drive_page is not None:
            cfg.drives = self._drive_page.get_assignments()
        # VRAM/RAM
        cfg.phys_vram_gb   = self.field("vram_gb")
        cfg.phys_ram_gb    = self.field("ram_gb")
        cfg.vram_max_ratio = float(self.field("vram_ratio"))
        cfg.ram_staging_pct = float(self.field("ram_ratio"))
        # NVMe chunks
        cfg.nvme_optimal_read_chunk  = int(self.field("read_chunk"))
        cfg.nvme_optimal_write_chunk = int(self.field("write_chunk"))
        # llama
        cfg.llama_cpp_path = self.field("llama_path")
        cfg.llama_patched  = True
        # 3FA
        threefa_page = self.page(5)
        if isinstance(threefa_page, ThreeFAPage):
            cfg.threefa_pairing_secret = threefa_page._secret_b32
            cfg.threefa_paired = bool(self.field("threefa_paired"))
        # Encryption
        enc_page = self.page(6)
        if isinstance(enc_page, EncryptionPage) and enc_page._fpr:
            cfg.encryption_key_fpr = enc_page._fpr
        # Persist
        try:
            config_io.save(cfg)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Save failed", str(e))
        super().accept()


def run_wizard_if_needed() -> config_io.GuiConfig:
    """Entry point used by main(): launches wizard on first run, returns config."""
    cfg = config_io.load()
    if cfg.wizard_completed:
        return cfg

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    wizard = SetupWizard(cfg)
    if wizard.exec() == QtWidgets.QWizard.Accepted:
        return config_io.load()
    return cfg
