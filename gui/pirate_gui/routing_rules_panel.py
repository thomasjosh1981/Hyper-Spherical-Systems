"""
gui/pirate_gui/routing_rules_panel.py — Granular Point-and-Click Proxy Rules Panel
=====================================================================================

WYSIWYG Point-and-Click exclusion panel for:
  • Provider / Base URL (api.x.ai, api.openai.com, api.anthropic.com, 127.0.0.1:11434)
  • Hosted Models (grok-2, gpt-4o, claude-3-5-sonnet, deepseek-r1)
  • Applications / Harnesses (Cursor IDE, LangChain, Anthropic SDK, Continue)
  • Ports (11434, 1234, 8080, 5000, 11435)

Features:
  - Expandable/Collapsible Tree (+ / - symbols) with inline Action selectors
  - Color-coded status badges: 🟢 Compress  🟡 Bypass  🔴 Block  ⚪ Inherit
  - Multi-axis sorting:
      1. Group by Provider → Model → Application
      2. Group by Application → Provider → Model
      3. Group by Port → Application → Model
  - Instant Point-and-Click exclusion & inclusion toggling
  - Real-time search/filter box

Author: TwistedSoCal / Hyper-Spherical Systems
License: Proprietary — All Rights Reserved
"""

from __future__ import annotations

import sys
from pathlib import Path
from PySide6 import QtWidgets, QtCore, QtGui

# Safe import of RuleEngine
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from rule_engine import get_rule_engine, ACTION_COMPRESS, ACTION_BYPASS, ACTION_BLOCK, ACTION_INHERIT
except Exception:
    get_rule_engine = None
    ACTION_COMPRESS, ACTION_BYPASS, ACTION_BLOCK, ACTION_INHERIT = "compress", "bypass", "block", "inherit"


class GranularRoutingRulesPanel(QtWidgets.QWidget):
    """
    Native PySide6 WYSIWYG Point-and-Click Granular Exclusion & Routing Panel.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.engine = get_rule_engine() if get_rule_engine else None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── HEADER BANNER ──────────────────────────────────────────────────
        hdr_box = QtWidgets.QGroupBox("🔀 Granular Proxy & Model Routing Rules (Point & Click)")
        hdr_lay = QtWidgets.QVBoxLayout(hdr_box)

        title_lbl = QtWidgets.QLabel(
            "Configure exact in/out compression & routing rules per Base URL, Model, or Application.\n"
            "Point-and-click to exclude specific models (e.g. bypass Grok for Cursor IDE while keeping Grok compressed for LangChain)."
        )
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 12px;")
        hdr_lay.addWidget(title_lbl)
        layout.addWidget(hdr_box)

        # ── CONTROL BAR: SORTING & SEARCH ──────────────────────────────────
        ctrl_bar = QtWidgets.QHBoxLayout()

        # Sort Mode Combo
        sort_lbl = QtWidgets.QLabel("Sort / Group View By:")
        sort_lbl.setStyleSheet("color: #8899aa; font-weight: bold; font-size: 11px;")
        self.combo_sort = QtWidgets.QComboBox()
        self.combo_sort.addItems([
            "Provider → Model → Application",
            "Application → Provider → Model",
            "Port → Application → Model"
        ])
        self.combo_sort.setStyleSheet("""
            QComboBox {
                background: #0f172a; color: #00ffcc; border: 1px solid rgba(0, 255, 204, 0.4);
                border-radius: 5px; padding: 4px 8px; font-size: 11px; font-weight: bold;
            }
            QComboBox QAbstractItemView { background: #0b1120; color: #00ffcc; }
        """)
        self.combo_sort.currentIndexChanged.connect(self.populate_tree)

        # Search / Filter Box
        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText("🔍 Filter rules by provider, model, app, or port...")
        self.search_box.setStyleSheet("""
            QLineEdit {
                background: #0f172a; color: #ffffff; border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 5px; padding: 4px 10px; font-size: 11px;
            }
        """)
        self.search_box.textChanged.connect(self.filter_tree)

        ctrl_bar.addWidget(sort_lbl)
        ctrl_bar.addWidget(self.combo_sort, 1)
        ctrl_bar.addSpacing(12)
        ctrl_bar.addWidget(self.search_box, 1)
        layout.addLayout(ctrl_bar)

        # ── HIERARCHICAL TREE WIDGET ───────────────────────────────────────
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Target Entity / Hierarchy", "Action", "Inbound Comp", "Outbound Comp"])
        self.tree.setColumnWidth(0, 360)
        self.tree.setColumnWidth(1, 140)
        self.tree.setColumnWidth(2, 110)
        self.tree.setColumnWidth(3, 110)
        self.tree.setAnimated(True)
        self.tree.setIndentation(20)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)

        self.tree.setStyleSheet("""
            QTreeWidget {
                background: #060a14; color: #e2e8f0;
                border: 1px solid rgba(0, 200, 255, 0.25); border-radius: 8px;
                font-family: 'Consolas', 'Segoe UI', monospace; font-size: 11px;
            }
            QTreeWidget::item { padding: 4px; border-bottom: 1px solid rgba(255, 255, 255, 0.04); }
            QTreeWidget::item:hover { background: rgba(0, 200, 255, 0.08); }
            QTreeWidget::item:selected { background: rgba(0, 200, 255, 0.20); color: #ffffff; }
            QHeaderView::section {
                background: #0f172a; color: #38bdf8; font-weight: bold; font-size: 11px;
                border: none; padding: 6px; border-bottom: 2px solid rgba(0, 200, 255, 0.4);
            }
        """)

        layout.addWidget(self.tree, 1)

        # ── BOTTOM ACTION BUTTONS ──────────────────────────────────────────
        btn_bar = QtWidgets.QHBoxLayout()

        btn_add = QtWidgets.QPushButton("➕ Add Custom Exclusion Rule")
        btn_add.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #b45309, stop:1 #7c3aed);
                color: #ffffff; border: none; border-radius: 6px; padding: 7px 14px;
                font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #d97706, stop:1 #9333ea); }
        """)
        btn_add.clicked.connect(self._add_rule_dialog)

        btn_expand = QtWidgets.QPushButton("📂 Expand All")
        btn_expand.clicked.connect(self.tree.expandAll)

        btn_collapse = QtWidgets.QPushButton("📁 Collapse All")
        btn_collapse.clicked.connect(self.tree.collapseAll)

        btn_reset = QtWidgets.QPushButton("↺ Reset Defaults")
        btn_reset.clicked.connect(self._reset_rules)

        btn_bar.addWidget(btn_add)
        btn_bar.addWidget(btn_expand)
        btn_bar.addWidget(btn_collapse)
        btn_bar.addStretch()
        btn_bar.addWidget(btn_reset)
        layout.addLayout(btn_bar)

        self.populate_tree()

    # ── TREE POPULATION ───────────────────────────────────────────────────
    def populate_tree(self) -> None:
        self.tree.clear()
        if not self.engine:
            return

        rules = self.engine.rules.get("providers", {})
        sort_mode = self.combo_sort.currentIndex()

        if sort_mode == 0:
            # Group by Provider → Model → Application
            for prov_name, prov_data in rules.items():
                prov_item = QtWidgets.QTreeWidgetItem(self.tree)
                prov_item.setText(0, f"🌐 {prov_name}")
                self._apply_action_badge(prov_item, prov_data.get("action", ACTION_COMPRESS))
                prov_item.setText(2, "✓ In" if prov_data.get("compress_inbound", True) else "✕ In")
                prov_item.setText(3, "✓ Out" if prov_data.get("compress_outbound", True) else "✕ Out")

                models = prov_data.get("models", {})
                for model_name, model_data in models.items():
                    m_item = QtWidgets.QTreeWidgetItem(prov_item)
                    m_item.setText(0, f"  🧠 Model: {model_name}")
                    self._apply_action_badge(m_item, model_data.get("action", ACTION_INHERIT))

                    apps = model_data.get("apps", {})
                    for app_name, app_data in apps.items():
                        a_item = QtWidgets.QTreeWidgetItem(m_item)
                        a_item.setText(0, f"    📱 App: {app_name}")
                        self._apply_action_badge(a_item, app_data.get("action", ACTION_INHERIT))

        elif sort_mode == 1:
            # Group by Application → Provider → Model
            app_map = {}
            for prov_name, prov_data in rules.items():
                for model_name, model_data in prov_data.get("models", {}).items():
                    for app_name, app_data in model_data.get("apps", {}).items():
                        app_map.setdefault(app_name, []).append((prov_name, model_name, app_data.get("action")))

            for app_name, entries in app_map.items():
                app_item = QtWidgets.QTreeWidgetItem(self.tree)
                app_item.setText(0, f"📱 App: {app_name}")
                self._apply_action_badge(app_item, ACTION_COMPRESS)
                for prov_name, model_name, act in entries:
                    p_item = QtWidgets.QTreeWidgetItem(app_item)
                    p_item.setText(0, f"  🌐 {prov_name} / {model_name}")
                    self._apply_action_badge(p_item, act or ACTION_INHERIT)

        elif sort_mode == 2:
            # Group by Port → Application → Model
            ports = [11434, 1234, 8080, 5001, 5000, 8081, 11435]
            for port in ports:
                p_item = QtWidgets.QTreeWidgetItem(self.tree)
                p_item.setText(0, f"🔌 Port :{port}")
                self._apply_action_badge(p_item, ACTION_COMPRESS)
                a_item = QtWidgets.QTreeWidgetItem(p_item)
                a_item.setText(0, f"  📱 All Applications")
                self._apply_action_badge(a_item, ACTION_INHERIT)

        self.tree.expandAll()

    def _apply_action_badge(self, item: QtWidgets.QTreeWidgetItem, action: str) -> None:
        if action == ACTION_COMPRESS:
            item.setText(1, "🟢 COMPRESS")
            item.setForeground(1, QtGui.QColor("#00ffcc"))
        elif action == ACTION_BYPASS:
            item.setText(1, "🟡 BYPASS")
            item.setForeground(1, QtGui.QColor("#fbbf24"))
        elif action == ACTION_BLOCK:
            item.setText(1, "🔴 BLOCK")
            item.setForeground(1, QtGui.QColor("#f87171"))
        else:
            item.setText(1, "⚪ INHERIT")
            item.setForeground(1, QtGui.QColor("#94a3b8"))

    def filter_tree(self, text: str) -> None:
        query = text.lower().strip()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            self._filter_item_recursive(item, query)

    def _filter_item_recursive(self, item: QtWidgets.QTreeWidgetItem, query: str) -> bool:
        match = query in item.text(0).lower() or query in item.text(1).lower()
        child_match = False
        for c in range(item.childCount()):
            if self._filter_item_recursive(item.child(c), query):
                child_match = True
        show = match or child_match
        item.setHidden(not show)
        return show

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self.tree.itemAt(pos)
        if not item:
            return

        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("QMenu { background: #0f172a; color: #ffffff; border: 1px solid rgba(0, 200, 255, 0.4); }")

        act_compress = menu.addAction("🟢 Set to COMPRESS (Apply CCTM)")
        act_bypass   = menu.addAction("🟡 Set to BYPASS (Exclude from Compression)")
        act_block    = menu.addAction("🔴 Set to BLOCK (Deny Access)")
        act_inherit  = menu.addAction("⚪ Set to INHERIT (Use Parent Rule)")

        selected = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if selected == act_compress:
            self._update_item_action(item, ACTION_COMPRESS)
        elif selected == act_bypass:
            self._update_item_action(item, ACTION_BYPASS)
        elif selected == act_block:
            self._update_item_action(item, ACTION_BLOCK)
        elif selected == act_inherit:
            self._update_item_action(item, ACTION_INHERIT)

    def _update_item_action(self, item: QtWidgets.QTreeWidgetItem, action: str) -> None:
        self._apply_action_badge(item, action)

        # Update engine rules based on node path
        parent = item.parent()
        if not parent:
            # Provider level
            prov = item.text(0).replace("🌐 ", "")
            if self.engine:
                self.engine.set_rule(prov, None, None, action)
        elif parent and not parent.parent():
            # Model level
            prov = parent.text(0).replace("🌐 ", "")
            model = item.text(0).replace("  🧠 Model: ", "")
            if self.engine:
                self.engine.set_rule(prov, model, None, action)
        elif parent and parent.parent():
            # App level
            prov = parent.parent().text(0).replace("🌐 ", "")
            model = parent.text(0).replace("  🧠 Model: ", "")
            app = item.text(0).replace("    📱 App: ", "")
            if self.engine:
                self.engine.set_rule(prov, model, app, action)

    def _add_rule_dialog(self) -> None:
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("➕ Add Custom Exclusion / Routing Rule")
        dlg.setMinimumWidth(440)
        lay = QtWidgets.QFormLayout(dlg)

        input_prov = QtWidgets.QLineEdit("api.x.ai (Grok)")
        input_model = QtWidgets.QLineEdit("grok-2")
        input_app = QtWidgets.QLineEdit("Cursor IDE")

        combo_act = QtWidgets.QComboBox()
        combo_act.addItems(["🟡 BYPASS (Exclude)", "🟢 COMPRESS", "🔴 BLOCK"])

        lay.addRow("Provider / Base URL:", input_prov)
        lay.addRow("Model Name:", input_model)
        lay.addRow("Application Name:", input_app)
        lay.addRow("Routing Action:", combo_act)

        btn = QtWidgets.QPushButton("⚡ Save Rule")
        btn.clicked.connect(dlg.accept)
        lay.addRow("", btn)

        if dlg.exec() == QtWidgets.QDialog.Accepted:
            action_map = {"🟡 BYPASS (Exclude)": ACTION_BYPASS, "🟢 COMPRESS": ACTION_COMPRESS, "🔴 BLOCK": ACTION_BLOCK}
            act = action_map.get(combo_act.currentText(), ACTION_BYPASS)
            if self.engine:
                self.engine.set_rule(input_prov.text(), input_model.text(), input_app.text(), act)
            self.populate_tree()

    def _reset_rules(self) -> None:
        if self.engine:
            self.engine.rules = json.loads(json.dumps(self.engine.load_rules()))
            self.engine.save_rules()
        self.populate_tree()
