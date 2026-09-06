# gui/pirate_gui/hypersphere_canvas.py
#
# Hyper-Spherical Systems — 4D Hyperspherical Animated Graphic Canvas v1.0
#
# Visual Features:
# 1. Central Hypersphere with internal & external bubbling sub-spheres
# 2. Vertex point rendering & inverted spinning vortexes (outside-in & inside-out)
# 3. High-contrast XOR color interference blending (Neon Cyan, Magenta, Gold, Deep Violet)
# 4. Smooth opacity pulsing & bleeding background effect (~5 sec boot sequence)
# 5. Data Unstacking Chipper Effect: Unstacks data blocks into glowing particles,
#    sucks them into swirling vortexes, and projects rings/blinking dots.
#
# Usage:
#   from hypersphere_canvas import HypersphereCanvas
#   canvas = HypersphereCanvas(parent)
#   canvas.start_animation()
#
# License: MIT

import math
import time
import random
from typing import List, Dict
from PySide6 import QtCore, QtGui, QtWidgets


class _SubSphere:
    def __init__(self, cx: float, cy: float):
        self.angle = random.uniform(0, math.pi * 2)
        self.orbit_radius = random.uniform(20, 90)
        self.radius = random.uniform(6, 22)
        self.speed = random.uniform(0.02, 0.06)
        self.color_phase = random.uniform(0, math.pi * 2)


class _DataParticle:
    def __init__(self, w: int, h: int):
        self.reset(w, h)

    def reset(self, w: int, h: int):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-2, 2)
        self.size = random.uniform(2, 6)
        self.alpha = random.uniform(100, 255)
        self.chipped = random.choice([True, False])


class HypersphereCanvas(QtWidgets.QWidget):
    """
    4D Hyperspherical animated graphic canvas for HypeS onboarding & startup.
    """

    def __init__(self, parent=None, width=400, height=250):
        super().__init__(parent)
        self.setMinimumSize(width, height)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self._time = 0.0
        self._pulse_alpha = 1.0
        self._vortex_angle = 0.0

        # Sub-spheres and unstacking particles
        self._sub_spheres: List[_SubSphere] = [_SubSphere(width/2, height/2) for _ in range(12)]
        self._particles: List[_DataParticle] = [_DataParticle(width, height) for _ in range(40)]

        # Timer ~60 fps
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._update_animation)
        self._timer.start()

    def start_animation(self):
        if not self._timer.isActive():
            self._timer.start()

    def stop_animation(self):
        self._timer.stop()

    def _update_animation(self):
        self._time += 0.03
        self._vortex_angle += 0.05
        self._pulse_alpha = 0.5 + 0.5 * math.sin(self._time * 1.5)

        # Update particles & sub-spheres
        w = max(1, self.width())
        h = max(1, self.height())
        cx, cy = w / 2, h / 2

        for p in self._particles:
            # Vortex pull towards center
            dx = cx - p.x
            dy = cy - p.y
            dist = math.sqrt(dx*dx + dy*dy) + 0.1
            p.vx += (dx / dist) * 0.15
            p.vy += (dy / dist) * 0.15
            p.x += p.vx
            p.y += p.vy
            if dist < 15:
                p.reset(w, h)

        for s in self._sub_spheres:
            s.angle += s.speed
            s.color_phase += 0.02

        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        radius = min(w, h) * 0.35

        # Background XOR glow radial gradient
        bg_grad = QtGui.QRadialGradient(cx, cy, radius * 1.8)
        bg_grad.setColorAt(0.0, QtGui.QColor(14, 165, 233, int(40 * self._pulse_alpha)))
        bg_grad.setColorAt(0.5, QtGui.QColor(168, 85, 247, int(25 * self._pulse_alpha)))
        bg_grad.setColorAt(1.0, QtGui.QColor(10, 10, 20, 0))
        p.setBrush(bg_grad)
        p.setPen(QtCore.Qt.NoPen)
        p.drawRect(self.rect())

        # 1. Outer Swirling Inverted Vortex Rings
        p.setCompositionMode(QtGui.QPainter.CompositionMode_Difference) # XOR interference
        p.setPen(QtGui.QPen(QtGui.QColor(0, 255, 204, 180), 1.5, QtCore.Qt.DashLine))

        for i in range(4):
            ring_r = radius * (0.4 + 0.2 * i) + math.sin(self._time + i) * 8
            p.drawEllipse(QtCore.QPointF(cx, cy), ring_r, ring_r * 0.6)

        # 2. Spinning Vertex Interverted Lines
        p.setPen(QtGui.QPen(QtGui.QColor(255, 0, 128, 140), 1.0))
        num_vertices = 10
        for i in range(num_vertices):
            a = self._vortex_angle + (i * math.pi * 2 / num_vertices)
            vx = cx + math.cos(a) * radius * 1.2
            vy = cy + math.sin(a) * radius * 1.2
            p.drawLine(QtCore.QPointF(cx, cy), QtCore.QPointF(vx, vy))

        # 3. Bubbling Sub-Spheres
        p.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
        for s in self._sub_spheres:
            sx = cx + math.cos(s.angle) * s.orbit_radius
            sy = cy + math.sin(s.angle * 1.3) * (s.orbit_radius * 0.6)

            sub_grad = QtGui.QRadialGradient(sx, sy, s.radius)
            r_c = int(128 + 127 * math.sin(s.color_phase))
            g_c = int(128 + 127 * math.cos(s.color_phase))
            b_c = 255
            sub_grad.setColorAt(0.0, QtGui.QColor(r_c, g_c, b_c, 220))
            sub_grad.setColorAt(1.0, QtGui.QColor(0, 200, 255, 20))
            p.setBrush(sub_grad)
            p.setPen(QtGui.QPen(QtGui.QColor(0, 255, 204, 160), 1))
            p.drawEllipse(QtCore.QPointF(sx, sy), s.radius, s.radius)

        # 4. Central Hypersphere Body
        main_grad = QtGui.QRadialGradient(cx, cy, radius)
        main_grad.setColorAt(0.0, QtGui.QColor(0, 255, 204, 230))
        main_grad.setColorAt(0.4, QtGui.QColor(56, 189, 248, 180))
        main_grad.setColorAt(0.8, QtGui.QColor(168, 85, 247, 120))
        main_grad.setColorAt(1.0, QtGui.QColor(10, 10, 20, 10))

        p.setBrush(main_grad)
        p.setPen(QtGui.QPen(QtGui.QColor(56, 189, 248, 240), 2))
        p.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)

        # 5. Data Unstacking Chipper Particles
        p.setPen(QtCore.Qt.NoPen)
        for part in self._particles:
            col = QtGui.QColor(255, 215, 0) if part.chipped else QtGui.QColor(0, 255, 204)
            col.setAlpha(int(part.alpha))
            p.setBrush(col)
            p.drawEllipse(QtCore.QPointF(part.x, part.y), part.size, part.size)

        p.end()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    win.setWindowTitle("4D Hyperspherical Animated Canvas")
    canvas = HypersphereCanvas(win, 600, 400)
    win.setCentralWidget(canvas)
    win.resize(600, 400)
    win.show()
    sys.exit(app.exec())
