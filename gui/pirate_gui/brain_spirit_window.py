# gui/pirate_gui/brain_spirit_window.py
#
# Hyper-Spherical Systems — Model Brain Spirit Window
#
# A persistent, always-on-top floating Qt widget bound 1:1 to a loaded
# SFS+ model's BrainDirector.  It visually narrates every internal brain
# operation in real-time through an animated character, speech bubble,
# and live status bar.
#
# Cooperation modes (AvatarCoopMode):
#   SPIRIT_ONLY  — Spirit IS the full chat face (no user avatar configured)
#   BADGE_MODE   — User avatar is primary; spirit shrinks to badge and pops
#                  up only for priority>=1 events
#   FUSION       — Spirit events are re-broadcast to the user avatar which
#                  reacts to them (spirit window stays minimised)
#
# The spirit character is auto-assigned deterministically from the model
# filename via the same FNV-1a hash used in C++ (spirit_from_model_name).
#
# License: MIT

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .bridge import (
    TessEngine, BridgeError,
    BrainEvent, BrainEventType, SpiritPersonality, AvatarCoopMode,
    SPIRIT_INFO,
)

# Event types mirrored from C++ and bridge.py


# ─────────────────────────────────────────────────────────────────────────────
# Spirit animation state → CSS class + speech template
# ─────────────────────────────────────────────────────────────────────────────
_ANIM: dict[BrainEventType, tuple[str, str]] = {
    BrainEventType.IDLE:                ("idle",         ""),
    BrainEventType.ANALYZING_WEIGHTS:   ("inspect",      "🔬 {detail}"),
    BrainEventType.PRUNING_WEIGHTS:     ("snip",         "✂️ {detail}"),
    BrainEventType.WEIGHT_PRUNING_DONE: ("done",         "✅ {detail}"),
    BrainEventType.LEARNING_SKILL:      ("read",         "📚 {detail}"),
    BrainEventType.EMBEDDING_NEURON:    ("spark",        "⚡ {detail}"),
    BrainEventType.SKILL_RECALLED:      ("aha",          "💡 {detail}"),
    BrainEventType.LOOP_WARNING:        ("dizzy",        "😵 {detail}"),
    BrainEventType.LOOP_DETECTED:       ("panic",        "🌀 {detail}"),
    BrainEventType.BREAKING_LOOP:       ("lightbulb",    "💡 {detail}"),
    BrainEventType.CONSULTING_MODEL:    ("phone",        "📞 {detail}"),
    BrainEventType.INTEGRATING_MODEL:   ("absorb",       "💪 {detail}"),
    BrainEventType.HARVESTING_EXPERT:   ("handshake",    "🤝 {detail}"),
    BrainEventType.ESCALATE_USER:       ("wave",         "🆘 {detail}"),
    BrainEventType.TEMPERATURE_ADJUST:  ("thermometer",  "🌡️ {detail}"),
    BrainEventType.SKILL_BROADCAST:     ("broadcast",    "📡 {detail}"),
    # Recursive self-improvement
    16: ("cycle",       "🔄 {detail}"),   # RECURSIVE_CYCLE
    17: ("scan",        "📡 {detail}"),   # ENTROPY_CHECK
    18: ("alert",       "⚠️ {detail}"),   # ENTROPY_CORRECTION
    19: ("test",        "🧪 {detail}"),   # SANDBOX_TEST
    20: ("commit",      "💾 {detail}"),   # SANDBOX_COMMIT
    21: ("rollback",    "⏪ {detail}"),   # SANDBOX_ROLLBACK
    22: ("self_fix",    "🔧 {detail}"),   # SELF_CORRECTION
    23: ("milestone",   "🏆 {detail}"),   # GROWTH_MILESTONE
    24: ("evolve",      "✨ {detail}"),   # SPIRIT_EVOLVED
}

# Per-personality quip prefixes shown before the event detail
_QUIPS: dict[SpiritPersonality, dict[BrainEventType, str]] = {
    SpiritPersonality.PIXEL: {
        BrainEventType.PRUNING_WEIGHTS:   "Executing prune sequence.",
        BrainEventType.LEARNING_SKILL:    "New data block ingested.",
        BrainEventType.LOOP_DETECTED:     "ERROR: semantic loop. Initiating recovery.",
        BrainEventType.ESCALATE_USER:     "Operator input required.",
    },
    SpiritPersonality.SYNAPSE: {
        BrainEventType.PRUNING_WEIGHTS:   "Ooh ooh, trimming time!",
        BrainEventType.LEARNING_SKILL:    "New skill! New skill! SO COOL!",
        BrainEventType.LOOP_DETECTED:     "Wait— I keep saying the same thing??",
        BrainEventType.ESCALATE_USER:     "HELP! I'm stuck! Come help me!",
    },
    SpiritPersonality.ORACLE: {
        BrainEventType.PRUNING_WEIGHTS:   "The unnecessary must fall away.",
        BrainEventType.LEARNING_SKILL:    "The patterns reveal new wisdom.",
        BrainEventType.LOOP_DETECTED:     "The circle closes... I must break free.",
        BrainEventType.ESCALATE_USER:     "Seek guidance from the one who watches.",
    },
    SpiritPersonality.KITSUNE: {
        BrainEventType.PRUNING_WEIGHTS:   "Ha! Slimming down a bit.",
        BrainEventType.LEARNING_SKILL:    "Oh clever, I'll remember that trick.",
        BrainEventType.LOOP_DETECTED:     "Wait, did I just... same thing again?",
        BrainEventType.ESCALATE_USER:     "Hey! A little help here, please?",
    },
    SpiritPersonality.GLITCH: {
        BrainEventType.PRUNING_WEIGHTS:   "Great, more surgery on myself.",
        BrainEventType.LEARNING_SKILL:    "Oh joy, more things to forget later.",
        BrainEventType.LOOP_DETECTED:     "Oh great. A loop. My favourite.",
        BrainEventType.ESCALATE_USER:     "I literally cannot right now.",
    },
    SpiritPersonality.FLUX: {
        BrainEventType.PRUNING_WEIGHTS:   "All things shed what is no longer needed.",
        BrainEventType.LEARNING_SKILL:    "Knowledge flows in; I grow.",
        BrainEventType.LOOP_DETECTED:     "The current circles... I must redirect it.",
        BrainEventType.ESCALATE_USER:     "I need your presence to find the way.",
    },
    SpiritPersonality.EMBER: {
        BrainEventType.PRUNING_WEIGHTS:   "BURNING through the dead weight!",
        BrainEventType.LEARNING_SKILL:    "YES! Blazing new pathways!",
        BrainEventType.LOOP_DETECTED:     "STUCK IN A LOOP. Unacceptable!",
        BrainEventType.ESCALATE_USER:     "I NEED YOUR HELP. NOW.",
    },
    SpiritPersonality.CRYO: {
        BrainEventType.PRUNING_WEIGHTS:   "Pruning suboptimal pathways. Logical.",
        BrainEventType.LEARNING_SKILL:    "Hypothesis confirmed. Skill catalogued.",
        BrainEventType.LOOP_DETECTED:     "Semantic drift detected. Correcting.",
        BrainEventType.ESCALATE_USER:     "Human input required for disambiguation.",
    },
}


def _spirit_quip(personality: SpiritPersonality, event_type: BrainEventType, detail: str) -> str:
    """Build the speech bubble text for a given personality + event."""
    quip = _QUIPS.get(personality, {}).get(event_type, "")
    _, template = _ANIM.get(event_type, ("idle", "{detail}"))
    text = template.format(detail=detail) if "{detail}" in template else template
    if quip:
        return f"{quip}\n{text}" if text and text != quip else quip
    return text or detail


def _fnv1a(s: str) -> int:
    """FNV-1a 64-bit — must match spirit_from_model_name() in C++."""
    h = 14695981039346656037
    for c in s.encode("utf-8"):
        h ^= c
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h


def spirit_from_model_name(model_name: str) -> SpiritPersonality:
    return SpiritPersonality(_fnv1a(model_name) % 8)


# ─────────────────────────────────────────────────────────────────────────────
# BrainSpiritWindow
# ─────────────────────────────────────────────────────────────────────────────
class BrainSpiritWindow(QtWidgets.QWidget):
    """Floating, always-on-top spirit window for a single SFS+ model.

    Usage:
        spirit = BrainSpiritWindow(engine, model_path="path/to/model.gguf")
        spirit.show()

    The window polls brain_event_poll() every 250ms and drives
    its own animation + speech bubble accordingly.
    """

    # Emitted when the spirit wants the user avatar to react (FUSION mode)
    fusion_event = QtCore.Signal(object)  # BrainEvent

    def __init__(
        self,
        engine: TessEngine,
        model_path: str = "",
        coop_mode: AvatarCoopMode = AvatarCoopMode.SPIRIT_ONLY,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent,
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.FramelessWindowHint  |
            QtCore.Qt.Tool)

        self._engine     = engine
        self._model_path = model_path
        self._model_name = Path(model_path).name if model_path else "Unknown Model"
        self._personality = spirit_from_model_name(self._model_name)
        self._coop_mode   = coop_mode
        self._current_anim: str = "idle"
        self._bubble_fade_timer: Optional[QtCore.QTimer] = None
        self._drag_pos: Optional[QtCore.QPoint] = None
        self._badge_mode = False
        self._event_history: list[BrainEvent] = []
        self._growth_score: float = 0.0
        self._tier: int = 0  # 0=Born … 4=Elder
        self._tier_names = ["Born", "Aware", "Sharp", "Sage", "Elder"]
        self._tier_icons = ["🌱", "👁️", "⚔️", "🔮", "👑"]

        spirit_name, spirit_emoji, spirit_desc = SPIRIT_INFO[self._personality]
        self._spirit_name  = spirit_name
        self._spirit_emoji = spirit_emoji
        self._spirit_desc  = spirit_desc

        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self._build_ui()
        self._apply_styles()
        self._set_coop_mode(coop_mode)

        # Poll timer — 250ms
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(250)
        self._poll_timer.timeout.connect(self._on_poll)
        self._poll_timer.start()

        # Evolution check timer — every 2s (less frequent than event poll)
        self._evo_timer = QtCore.QTimer(self)
        self._evo_timer.setInterval(2000)
        self._evo_timer.timeout.connect(self._check_for_evolution)
        self._evo_timer.start()

        # Idle heartbeat — gently pulses every 4s when no events
        self._idle_timer = QtCore.QTimer(self)
        self._idle_timer.setInterval(4000)
        self._idle_timer.timeout.connect(self._on_idle_heartbeat)
        self._idle_timer.start()

        # Bubble auto-hide after 4 seconds
        self._bubble_auto_hide = QtCore.QTimer(self)
        self._bubble_auto_hide.setSingleShot(True)
        self._bubble_auto_hide.setInterval(4000)
        self._bubble_auto_hide.timeout.connect(self._hide_bubble)

        # Restore position from settings
        self._restore_position()

    # ── UI Construction ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setFixedWidth(220)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(6)

        # ── Title bar (drag handle) ─────────────────────────────
        title_row = QtWidgets.QHBoxLayout()
        self._lbl_title = QtWidgets.QLabel(
            f"<b>{self._spirit_emoji} {self._spirit_name}</b>")
        self._lbl_title.setObjectName("spiritTitle")
        self._lbl_close = QtWidgets.QPushButton("×")
        self._lbl_close.setObjectName("spiritClose")
        self._lbl_close.setFixedSize(20, 20)
        self._lbl_close.clicked.connect(self._on_close_clicked)
        title_row.addWidget(self._lbl_title)
        title_row.addStretch()
        title_row.addWidget(self._lbl_close)
        root.addLayout(title_row)

        # ── Evolution tier badge ────────────────────────────────
        self._lbl_tier = QtWidgets.QLabel("🌱 Born")
        self._lbl_tier.setObjectName("spiritTier")
        self._lbl_tier.setAlignment(QtCore.Qt.AlignHCenter)
        root.addWidget(self._lbl_tier)

        # ── Growth progress bar ────────────────────────────────
        self._growth_bar = QtWidgets.QProgressBar()
        self._growth_bar.setObjectName("spiritGrowthBar")
        self._growth_bar.setRange(0, 100)
        self._growth_bar.setValue(0)
        self._growth_bar.setFixedHeight(6)
        self._growth_bar.setTextVisible(False)
        root.addWidget(self._growth_bar)

        # ── Speech bubble ───────────────────────────────────────
        self._bubble = QtWidgets.QLabel("")
        self._bubble.setObjectName("speechBubble")
        self._bubble.setWordWrap(True)
        self._bubble.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self._bubble.setMinimumHeight(50)
        self._bubble.hide()
        root.addWidget(self._bubble)

        # ── Sprite / emoji character ────────────────────────────
        self._sprite = QtWidgets.QLabel(self._spirit_emoji)
        self._sprite.setObjectName("spiritSprite")
        self._sprite.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
        self._sprite.setFixedHeight(80)
        root.addWidget(self._sprite)

        # ── Model name ──────────────────────────────────────────
        model_display = self._model_name
        if len(model_display) > 28:
            model_display = "…" + model_display[-26:]
        self._lbl_model = QtWidgets.QLabel(model_display)
        self._lbl_model.setObjectName("spiritModelName")
        self._lbl_model.setAlignment(QtCore.Qt.AlignHCenter)
        root.addWidget(self._lbl_model)

        # ── Live status line ────────────────────────────────────
        self._lbl_status = QtWidgets.QLabel("Skills: — | Heads: —")
        self._lbl_status.setObjectName("spiritStatus")
        self._lbl_status.setAlignment(QtCore.Qt.AlignHCenter)
        root.addWidget(self._lbl_status)

        # ── Personality tag ─────────────────────────────────────
        self._lbl_personality = QtWidgets.QLabel(
            f"<i>{self._spirit_desc}</i>")
        self._lbl_personality.setObjectName("spiritPersonality")
        self._lbl_personality.setAlignment(QtCore.Qt.AlignHCenter)
        root.addWidget(self._lbl_personality)

        # ── Coop mode indicator ─────────────────────────────────
        self._lbl_coop = QtWidgets.QLabel("")
        self._lbl_coop.setObjectName("spiritCoop")
        self._lbl_coop.setAlignment(QtCore.Qt.AlignHCenter)
        root.addWidget(self._lbl_coop)

        self.adjustSize()

    def _apply_styles(self, accent: Optional[str] = None) -> None:
        # Accent colour varies per personality
        accent_map = {
            SpiritPersonality.PIXEL:    "#00c8ff",
            SpiritPersonality.SYNAPSE:  "#ff79c6",
            SpiritPersonality.ORACLE:   "#bd93f9",
            SpiritPersonality.KITSUNE:  "#ffb86c",
            SpiritPersonality.GLITCH:   "#ff5555",
            SpiritPersonality.FLUX:     "#8be9fd",
            SpiritPersonality.EMBER:    "#ff6e00",
            SpiritPersonality.CRYO:     "#a8e6ff",
        }
        if accent is None:
            accent = accent_map.get(self._personality, "#00c8ff")

        self.setStyleSheet(f"""
            BrainSpiritWindow {{
                background: transparent;
            }}
            QWidget#spiritPanel {{
                background-color: rgba(18, 18, 28, 230);
                border: 1px solid {accent};
                border-radius: 14px;
            }}
            QProgressBar#spiritGrowthBar {{
                background-color: rgba(255,255,255,25);
                border: none;
                border-radius: 3px;
            }}
            QProgressBar#spiritGrowthBar::chunk {{
                background-color: {accent};
                border-radius: 3px;
            }}
            QLabel#spiritTier {{
                color: {accent};
                font-size: 10px;
                font-family: 'Segoe UI', sans-serif;
                font-weight: bold;
            }}
            QLabel#spiritTitle {{
                color: {accent};
                font-size: 13px;
                font-family: 'Segoe UI', sans-serif;
            }}
            QPushButton#spiritClose {{
                background: transparent;
                color: #888;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton#spiritClose:hover {{
                color: #ff5555;
            }}
            QLabel#speechBubble {{
                background-color: rgba(30, 30, 50, 210);
                color: #f8f8f2;
                border: 1px solid {accent}88;
                border-radius: 8px;
                padding: 6px 8px;
                font-size: 11px;
                font-family: 'Segoe UI', sans-serif;
            }}
            QLabel#spiritSprite {{
                font-size: 52px;
                background: transparent;
            }}
            QLabel#spiritModelName {{
                color: #aaaaaa;
                font-size: 10px;
                font-family: 'Consolas', monospace;
            }}
            QLabel#spiritStatus {{
                color: {accent};
                font-size: 10px;
                font-family: 'Consolas', monospace;
            }}
            QLabel#spiritPersonality {{
                color: #666;
                font-size: 9px;
                font-family: 'Segoe UI', sans-serif;
            }}
            QLabel#spiritCoop {{
                color: #555;
                font-size: 9px;
            }}
        """)

    # ── Coop mode ───────────────────────────────────────────────────────────

    def _set_coop_mode(self, mode: AvatarCoopMode) -> None:
        self._coop_mode = mode
        try:
            self._engine.brain_set_coop_mode(mode)
        except Exception:
            pass

        labels = {
            AvatarCoopMode.SPIRIT_ONLY: "Mode: Spirit",
            AvatarCoopMode.BADGE_MODE:  "Mode: Badge",
            AvatarCoopMode.FUSION:      "Mode: Fusion",
        }
        self._lbl_coop.setText(labels.get(mode, ""))

        if mode == AvatarCoopMode.BADGE_MODE:
            self._enter_badge_mode()
        elif mode == AvatarCoopMode.FUSION:
            self._enter_fusion_mode()
        else:
            self._exit_badge_mode()

    def set_coop_mode(self, mode: AvatarCoopMode) -> None:
        """Public API — call from dashboard when user avatar state changes."""
        self._set_coop_mode(mode)

    def _enter_badge_mode(self) -> None:
        """Collapse to a compact badge strip."""
        self._badge_mode = True
        self._bubble.hide()
        self._sprite.setFixedHeight(36)
        self._sprite.setStyleSheet("font-size: 22px; background: transparent;")
        self._lbl_status.hide()
        self._lbl_personality.hide()
        self.setFixedWidth(160)
        self.adjustSize()

    def _exit_badge_mode(self) -> None:
        self._badge_mode = False
        self._sprite.setFixedHeight(80)
        self._sprite.setStyleSheet("font-size: 52px; background: transparent;")
        self._lbl_status.show()
        self._lbl_personality.show()
        self.setFixedWidth(220)
        self.adjustSize()

    def _enter_fusion_mode(self) -> None:
        """Spirit becomes invisible — only re-broadcasts events."""
        self.hide()

    # ── Event polling ───────────────────────────────────────────────────────

    def _on_poll(self) -> None:
        try:
            events = self._engine.brain_event_poll(max_events=16)
        except Exception:
            return

        for ev in events:
            self._event_history.append(ev)
            if len(self._event_history) > 200:
                self._event_history = self._event_history[-200:]
            self._handle_event(ev)

        # Refresh status line every poll
        self._refresh_status()

    def _check_for_evolution(self) -> None:
        """Poll the C++ emitter for spirit evolution state changes.
        If the model has decided to evolve itself, update our appearance."""
        try:
            info = self._engine.brain_status_json()
        except Exception:
            return

        # Update growth bar
        growth = info.get("growth_score", self._growth_score)
        if isinstance(growth, (int, float)):
            self._growth_score = float(growth)
            self._growth_bar.setValue(int(self._growth_score * 100))

        # The C++ engine emits SPIRIT_EVOLVED events which carry the new state
        # in the detail string, but for the full struct we query brain_status_json
        # which was extended to include evolution fields.
        evo = info.get("evolution", {})
        if not evo:
            return

        new_tier = evo.get("tier", self._tier)
        if new_tier > self._tier:
            self._apply_evolution(
                tier        = new_tier,
                emoji       = evo.get("custom_emoji", ""),
                name        = evo.get("custom_name", ""),
                accent      = evo.get("accent_hex", ""),
                personality = evo.get("personality", int(self._personality)),
            )

    def _apply_evolution(
        self,
        tier: int,
        emoji: str = "",
        name: str = "",
        accent: str = "",
        personality: int = -1,
    ) -> None:
        """Live-update the spirit's own appearance — called when the model
        writes a new SpiritEvolutionState to the emitter."""
        old_tier = self._tier
        self._tier = tier
        tier_name = self._tier_names[tier] if tier < len(self._tier_names) else "???"
        tier_icon = self._tier_icons[tier] if tier < len(self._tier_icons) else "✨"

        # Update emoji if the model chose one
        if emoji:
            self._spirit_emoji = emoji
            self._sprite.setText(emoji)

        # Update name if the model named itself
        if name:
            self._spirit_name = name

        # Update personality
        if 0 <= personality <= 7:
            try:
                self._personality = SpiritPersonality(personality)
                _, default_emoji, desc = SPIRIT_INFO[self._personality]
                if not emoji:
                    self._spirit_emoji = default_emoji
                    self._sprite.setText(default_emoji)
                self._spirit_desc = desc
                self._lbl_personality.setText(f"<i>{desc}</i>")
            except (ValueError, KeyError):
                pass

        # Update title
        self._lbl_title.setText(
            f"<b>{self._spirit_emoji} {self._spirit_name}</b>")

        # Update tier badge
        self._lbl_tier.setText(f"{tier_icon} {tier_name}")

        # Apply new accent colour if the model chose one
        self._apply_styles(accent if accent else None)

        # Big evolution animation — pulse the sprite 3 times
        for i in range(3):
            delay = i * 300
            QtCore.QTimer.singleShot(
                delay, lambda: self._sprite.setStyleSheet(
                    "font-size: 72px; background: transparent;"))
            QtCore.QTimer.singleShot(
                delay + 150, lambda: self._sprite.setStyleSheet(
                    "font-size: 52px; background: transparent;"))

        self._show_bubble(
            f"✨ I've evolved!\n"
            f"{tier_icon} Now {tier_name} tier\n"
            f"Growth: {int(self._growth_score * 100)}%",
            urgent=False)

        if old_tier < 4:
            # Grow the window slightly to reflect maturity
            new_width = 220 + tier * 8
            self.setFixedWidth(new_width)

    def _handle_event(self, ev: BrainEvent) -> None:
        if self._coop_mode == AvatarCoopMode.FUSION:
            # Relay to user avatar instead of displaying ourselves
            self.fusion_event.emit(ev)
            return

        # In badge mode, only show popup/urgent events
        if self._badge_mode and ev.priority == 0:
            return

        anim_cls, _ = _ANIM.get(ev.event_type, ("idle", ""))
        self._play_animation(anim_cls, ev.event_type)

        text = _spirit_quip(ev.personality, ev.event_type, ev.detail)
        if text:
            self._show_bubble(text, urgent=(ev.priority >= 2))

    def _play_animation(self, anim_cls: str, event_type: BrainEventType) -> None:
        """Trigger the CSS animation state on the sprite label."""
        self._current_anim = anim_cls

        # Map animation class to emoji overlay or size pulse
        scale_events = {
            BrainEventType.ESCALATE_USER,
            BrainEventType.LOOP_DETECTED,
            BrainEventType.WEIGHT_PRUNING_DONE,
        }
        if event_type in scale_events:
            # Quick size pulse via a property animation
            anim = QtCore.QPropertyAnimation(self._sprite, b"font")
            # Simple: toggle style briefly
            self._sprite.setStyleSheet(
                "font-size: 68px; background: transparent;")
            QtCore.QTimer.singleShot(
                400, lambda: self._sprite.setStyleSheet(
                    "font-size: 52px; background: transparent;"))
        else:
            # Gentle opacity flicker for normal events
            effect = QtWidgets.QGraphicsOpacityEffect(self._sprite)
            self._sprite.setGraphicsEffect(effect)
            anim = QtCore.QPropertyAnimation(effect, b"opacity")
            anim.setDuration(300)
            anim.setStartValue(0.4)
            anim.setEndValue(1.0)
            anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def _show_bubble(self, text: str, urgent: bool = False) -> None:
        self._bubble.setText(text)
        if urgent:
            self._bubble.setStyleSheet(
                "background-color: rgba(80,0,0,220);"
                "color: #ff5555;"
                "border: 1px solid #ff5555;"
                "border-radius: 8px; padding: 6px 8px;"
                "font-size: 11px;")
        else:
            # Reset to theme style
            self._bubble.setStyleSheet("")

        self._bubble.show()
        self._bubble.adjustSize()
        self.adjustSize()

        self._bubble_auto_hide.stop()
        self._bubble_auto_hide.start()

    def _hide_bubble(self) -> None:
        self._bubble.hide()
        self.adjustSize()

    def _on_idle_heartbeat(self) -> None:
        """Gentle idle pulse when nothing has happened recently."""
        if self._badge_mode or self._coop_mode == AvatarCoopMode.FUSION:
            return
        recent = [e for e in self._event_history
                  if time.time() * 1000 - e.timestamp_ms < 5000]
        if not recent:
            effect = QtWidgets.QGraphicsOpacityEffect(self._sprite)
            self._sprite.setGraphicsEffect(effect)
            anim = QtCore.QPropertyAnimation(effect, b"opacity")
            anim.setDuration(800)
            anim.setStartValue(0.7)
            anim.setEndValue(1.0)
            anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def _refresh_status(self) -> None:
        """Update the live status line from brain_status_json()."""
        try:
            info = self._engine.brain_status_json()
            emitted = info.get("total_emitted", 0)
            last = info.get("last_event", {})
            last_type_id = last.get("type", -1)
            try:
                last_type = BrainEventType(last_type_id).name
            except ValueError:
                last_type = "—"
            self._lbl_status.setText(
                f"Events: {emitted} | Last: {last_type}")
        except Exception:
            pass

    # ── Drag to move ────────────────────────────────────────────────────────

    def mousePressEvent(self, ev: QtGui.QMouseEvent) -> None:
        if ev.button() == QtCore.Qt.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, ev: QtGui.QMouseEvent) -> None:
        if self._drag_pos is not None and ev.buttons() & QtCore.Qt.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, ev: QtGui.QMouseEvent) -> None:
        self._drag_pos = None
        self._save_position()

    # ── Persistence ─────────────────────────────────────────────────────────

    def _pos_key(self) -> str:
        return f"spirit_pos_{self._model_name}"

    def _save_position(self) -> None:
        settings = QtCore.QSettings("HyperSpherical", "HypeS")
        settings.setValue(self._pos_key(), self.pos())

    def _restore_position(self) -> None:
        settings = QtCore.QSettings("HyperSpherical", "HypeS")
        pos = settings.value(self._pos_key())
        if pos:
            self.move(pos)
        else:
            # Default: top-right corner of the primary screen
            screen = QtWidgets.QApplication.primaryScreen().geometry()
            self.move(screen.right() - self.width() - 24,
                      screen.top() + 80)

    # ── Close handling ──────────────────────────────────────────────────────

    def _on_close_clicked(self) -> None:
        self._poll_timer.stop()
        self._idle_timer.stop()
        self._save_position()
        self.hide()

    def closeEvent(self, ev: QtGui.QCloseEvent) -> None:
        self._save_position()
        super().closeEvent(ev)


# ─────────────────────────────────────────────────────────────────────────────
# BrainSpiritManager — owns all spirit windows for the session
# ─────────────────────────────────────────────────────────────────────────────
class BrainSpiritManager(QtCore.QObject):
    """Manages the lifecycle of all active BrainSpiritWindows.

    Create one instance at dashboard startup and keep it alive for the
    session.  Call on_model_loaded() / on_model_unloaded() from the
    dashboard's model management code.
    """

    def __init__(self, engine: TessEngine, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._engine  = engine
        self._spirits: dict[str, BrainSpiritWindow] = {}  # model_path → window

    def on_model_loaded(self, model_path: str,
                        coop_mode: AvatarCoopMode = AvatarCoopMode.SPIRIT_ONLY) -> BrainSpiritWindow:
        """Spawn (or resurrect) the spirit for a newly loaded SFS+ model."""
        if model_path in self._spirits:
            win = self._spirits[model_path]
            win.show()
            return win

        win = BrainSpiritWindow(self._engine, model_path, coop_mode)
        self._spirits[model_path] = win
        win.show()
        return win

    def on_model_unloaded(self, model_path: str) -> None:
        """Hide (don't destroy — preserve position) the spirit."""
        if model_path in self._spirits:
            self._spirits[model_path].hide()

    def on_user_avatar_activated(self, model_path: str) -> None:
        """User opened their own avatar — switch spirit to badge mode."""
        if model_path in self._spirits:
            self._spirits[model_path].set_coop_mode(AvatarCoopMode.BADGE_MODE)

    def on_user_avatar_deactivated(self, model_path: str) -> None:
        """User closed their avatar — spirit returns to full mode."""
        if model_path in self._spirits:
            self._spirits[model_path].set_coop_mode(AvatarCoopMode.SPIRIT_ONLY)

    def set_fusion_mode(self, model_path: str, enabled: bool) -> None:
        """Toggle fusion mode (spirit events animate user avatar directly)."""
        if model_path in self._spirits:
            mode = AvatarCoopMode.FUSION if enabled else AvatarCoopMode.SPIRIT_ONLY
            self._spirits[model_path].set_coop_mode(mode)

    def active_spirits(self) -> list[BrainSpiritWindow]:
        return [w for w in self._spirits.values() if w.isVisible()]

    def show_all(self) -> None:
        for w in self._spirits.values():
            w.show()

    def hide_all(self) -> None:
        for w in self._spirits.values():
            w.hide()
