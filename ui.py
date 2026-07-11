from __future__ import annotations

import json
import ctypes
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import psutil

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDragEnterEvent, QDropEvent, QFont, QFontDatabase,
    QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QPolygonF, QRadialGradient, QShortcut, QVector3D, QMatrix4x4,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget, QProgressBar, QComboBox,
)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtOpenGL import (
    QOpenGLShaderProgram, QOpenGLShader, QOpenGLBuffer,
    QOpenGLVertexArrayObject, QOpenGLTexture
)

try:
    from OpenGL import GL
    _HAS_OPENGL = True
except Exception:
    _HAS_OPENGL = False

from config.settings import (
    DEFAULT_LIVE_VOICE,
    LIVE_VOICE_OPTIONS,
    get_live_voice_name,
    save_api_settings,
    set_live_voice_name,
)

from agent.ironman_catalog import (
    SuitDisplayMetadata,
    all_suit_metadata,
    is_arc_reactor_detail_request,
    parse_suit_request,
)
from agent.mesh_assets import MeshAsset, load_mesh_asset
from agent.gesture_camera import GestureCameraController
from actions.world_news import country_markers

# Import Enhanced Hologram
try:
    from agent.enhanced_hologram import EnhancedHologram3D
    _HAS_ENHANCED_HOLOGRAM = True
except Exception:
    _HAS_ENHANCED_HOLOGRAM = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

_DEFAULT_W, _DEFAULT_H = 980, 700
_MIN_W,     _MIN_H     = 820, 580
_LEFT_W  = 148
_RIGHT_W = 340

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


class C:
    BG        = "#030100"
    PANEL     = "#120906"
    PANEL2    = "#1b0e08"
    BORDER    = "#573315"
    BORDER_B  = "#a66a26"
    BORDER_A  = "#7b491d"
    PRI       = "#ffd18a"
    PRI_DIM   = "#b8742d"
    PRI_GHO   = "#271004"
    ACC       = "#ff8a1f"
    ACC2      = "#ffe08a"
    GREEN     = "#00ff88"
    GREEN_D   = "#00aa55"
    RED       = "#ff3355"
    MUTED_C   = "#aa3042"
    TEXT      = "#ffdca8"
    TEXT_DIM  = "#9b6b3a"
    TEXT_MED  = "#d4924a"
    WHITE     = "#fff3d6"
    DARK      = "#080301"
    BAR_BG    = "#241005"


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0   
        self.gpu  = -1.0  
        self.tmp  = -1.0  
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        gpu = self._get_gpu()
        tmp = self._get_temp()

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
                if vals:
                    return sum(vals) / len(vals)
        except Exception:
            pass
        if _OS == "Linux":
            try:
                r = subprocess.run(
                    ["rocm-smi", "--showuse", "--csv"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    for line in r.stdout.strip().split("\n"):
                        parts = line.split(",")
                        if len(parts) >= 2:
                            try:
                                return float(parts[1].strip().replace("%", ""))
                            except ValueError:
                                pass
            except Exception:
                pass
            try:
                r = subprocess.run(
                    ["intel_gpu_top", "-J", "-s", "500"],
                    capture_output=True, text=True, timeout=1
                )
                if r.returncode == 0 and "Render/3D" in r.stdout:
                    import re
                    m = re.search(r'"busy":\s*([\d.]+)', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["sudo", "-n", "powermetrics", "-n", "1", "-i", "500",
                     "--samplers", "gpu_power"],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0 and "GPU" in r.stdout:
                    import re
                    m = re.search(r'GPU\s+Active:\s+([\d.]+)%', r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass
        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            candidates = ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                          "cpu-thermal", "zenpower", "it8688"]
            for name in candidates:
                if name in temps:
                    entries = temps[name]
                    if entries:
                        return entries[0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass
        if _OS == "Darwin":
            try:
                r = subprocess.run(
                    ["osx-cpu-temp"], capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    import re
                    m = re.search(r"([\d.]+)", r.stdout)
                    if m:
                        return float(m.group(1))
            except Exception:
                pass
        if _OS == "Windows":
            try:
                r = subprocess.run(
                    ["powershell", "-Command",
                     "(Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi).CurrentTemperature"],
                    capture_output=True, text=True, timeout=3
                )
                if r.returncode == 0 and r.stdout.strip():
                    raw = float(r.stdout.strip().split("\n")[0])
                    return (raw / 10.0) - 273.15
            except Exception:
                pass
        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
            }


_metrics = _SysMetrics()


class HudCanvas(QWidget):
    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = time.time()
        self._scan       = 0.0
        self._scan2      = 180.0
        self._rings      = [0.0, 120.0, 240.0]
        self._pulses: list[float] = [0.0, 50.0, 100.0]
        self._blink      = True
        self._blink_tick = 0
        self._particles: list[list[float]] = []
        self._face_px: QPixmap | None = None
        self._load_face(face_path)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz  = min(img.size)
            img = img.resize((sz, sz), Image.LANCZOS)
            mk  = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz - 2, sz - 2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue())
            self._face_px = px
        except Exception:
            self._face_px = None

    def _step(self):
        self._tick += 1
        now = time.time()
        if now - self._last_t > (0.12 if self.speaking else 0.5):
            if self.speaking:
                self._tgt_scale = random.uniform(1.06, 1.14)
                self._tgt_halo  = random.uniform(145, 190)
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo  = random.uniform(15, 28)
            else:
                self._tgt_scale = random.uniform(1.001, 1.008)
                self._tgt_halo  = random.uniform(48, 68)
            self._last_t = now

        sp = 0.38 if self.speaking else 0.15
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp

        speeds = [1.3, -0.9, 2.0] if self.speaking else [0.55, -0.35, 0.9]
        for i, spd in enumerate(speeds):
            self._rings[i] = (self._rings[i] + spd) % 360

        self._scan  = (self._scan  + (3.0 if self.speaking else 1.3)) % 360
        self._scan2 = (self._scan2 + (-2.0 if self.speaking else -0.75)) % 360

        fw  = min(self.width(), self.height())
        lim = fw * 0.74
        spd = 4.2 if self.speaking else 2.0
        self._pulses = [r + spd for r in self._pulses if r + spd < lim]
        if len(self._pulses) < 3 and random.random() < (0.07 if self.speaking else 0.025):
            self._pulses.append(0.0)

        if self.speaking and random.random() < 0.28:
            cx, cy = self.width() / 2, self.height() / 2
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * 0.28
            self._particles.append([
                cx + math.cos(ang) * r_s, cy + math.sin(ang) * r_s,
                math.cos(ang) * random.uniform(0.9, 2.4),
                math.sin(ang) * random.uniform(0.9, 2.4) - 0.4, 1.0,
            ])
        self._particles = [
            [p[0]+p[2], p[1]+p[3], p[2]*0.97, p[3]*0.97, p[4]-0.028]
            for p in self._particles if p[4] > 0
        ]

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))

        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)

        # grid dots
        p.setPen(QPen(qcol(C.PRI_GHO), 1))
        for x in range(0, W, 48):
            for y in range(0, H, 48):
                p.drawPoint(x, y)

        r_face = fw * 0.31

        # halo glow
        for i in range(10):
            r   = r_face * (1.8 - i * 0.08)
            frc = 1.0 - i / 10
            a   = max(0, min(255, int(self._halo * 0.085 * frc)))
            col = qcol(C.MUTED_C if self.muted else C.PRI, a)
            p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # pulse rings
        for pr in self._pulses:
            a   = max(0, int(230 * (1.0 - pr / (fw * 0.74))))
            col = qcol(C.MUTED_C if self.muted else C.PRI, a)
            p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - pr, cy - pr, pr * 2, pr * 2))

        # spinning arc rings
        for idx, (r_frac, w_r, arc_l, gap) in enumerate(
            [(0.48, 3, 115, 78), (0.40, 2, 78, 55), (0.32, 1, 56, 40)]
        ):
            ring_r = fw * r_frac
            base   = self._rings[idx]
            a_val  = max(0, min(255, int(self._halo * (1.0 - idx * 0.18))))
            col    = qcol(C.MUTED_C if self.muted else C.PRI, a_val)
            p.setPen(QPen(col, w_r)); p.setBrush(Qt.BrushStyle.NoBrush)
            angle = base
            rect  = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
            while angle < base + 360:
                p.drawArc(rect, int(angle * 16), int(arc_l * 16))
                angle += arc_l + gap

        # scanners
        sr = fw * 0.50
        sa = min(255, int(self._halo * 1.5))
        ex = 75 if self.speaking else 44
        p.setPen(QPen(qcol(C.MUTED_C if self.muted else C.PRI, sa), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        srect = QRectF(cx - sr, cy - sr, sr * 2, sr * 2)
        p.drawArc(srect, int(self._scan * 16), int(ex * 16))
        p.setPen(QPen(qcol(C.ACC, sa // 2), 1.5))
        p.drawArc(srect, int(self._scan2 * 16), int(ex * 16))

        # tick marks
        t_out, t_in = fw * 0.497, fw * 0.474
        p.setPen(QPen(qcol(C.PRI, 140), 1))
        for deg in range(0, 360, 10):
            rad = math.radians(deg)
            inn = t_in if deg % 30 == 0 else t_in + 6
            p.drawLine(
                QPointF(cx + t_out * math.cos(rad), cy - t_out * math.sin(rad)),
                QPointF(cx + inn  * math.cos(rad), cy - inn  * math.sin(rad)),
            )

        # crosshair
        ch_r, gap_h = fw * 0.51, fw * 0.16
        p.setPen(QPen(qcol(C.PRI, int(self._halo * 0.5)), 1))
        p.drawLine(QPointF(cx - ch_r, cy), QPointF(cx - gap_h, cy))
        p.drawLine(QPointF(cx + gap_h, cy), QPointF(cx + ch_r, cy))
        p.drawLine(QPointF(cx, cy - ch_r), QPointF(cx, cy - gap_h))
        p.drawLine(QPointF(cx, cy + gap_h), QPointF(cx, cy + ch_r))

        # corner brackets
        bl = 24
        bc = qcol(C.PRI, 210)
        hl, hr = cx - fw // 2, cx + fw // 2
        ht, hb = cy - fw // 2, cy + fw // 2
        p.setPen(QPen(bc, 2))
        for bx, by, dx, dy in [(hl,ht,1,1),(hr,ht,-1,1),(hl,hb,1,-1),(hr,hb,-1,-1)]:
            p.drawLine(QPointF(bx, by), QPointF(bx + dx * bl, by))
            p.drawLine(QPointF(bx, by), QPointF(bx, by + dy * bl))

        # face
        if self._face_px:
            fsz    = int(fw * 0.62 * self._scale)
            scaled = self._face_px.scaled(
                fsz, fsz,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(int(cx - fsz / 2), int(cy - fsz / 2), scaled)
        else:
            orb_r = int(fw * 0.27 * self._scale)
            oc    = (200, 0, 50) if self.muted else (0, 60, 110)
            for i in range(8, 0, -1):
                r2  = int(orb_r * i / 8)
                frc = i / 8
                a   = max(0, min(255, int(self._halo * 1.1 * frc)))
                p.setBrush(QBrush(QColor(int(oc[0]*frc), int(oc[1]*frc), int(oc[2]*frc), a)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(cx - r2, cy - r2, r2 * 2, r2 * 2))
            p.setPen(QPen(qcol(C.PRI, min(255, int(self._halo * 2))), 1))
            p.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
            p.drawText(QRectF(cx - 80, cy - 14, 160, 28),
                       Qt.AlignmentFlag.AlignCenter, "J.A.R.V.I.S")

        # particles
        for pt in self._particles:
            a = max(0, min(255, int(pt[4] * 255)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(C.PRI, a)))
            p.drawEllipse(QPointF(pt[0], pt[1]), 2.5, 2.5)

        # status text
        sy = cy + fw * 0.40
        if self.muted:
            txt, col = "⊘  MUTED",     qcol(C.MUTED_C)
        elif self.speaking:
            txt, col = "●  SPEAKING",  qcol(C.ACC)
        elif self.state == "THINKING":
            sym = "◈" if self._blink else "◇"
            txt, col = f"{sym}  THINKING",   qcol(C.ACC2)
        elif self.state == "PROCESSING":
            sym = "▷" if self._blink else "▶"
            txt, col = f"{sym}  PROCESSING", qcol(C.ACC2)
        elif self.state == "LISTENING":
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  LISTENING",  qcol(C.GREEN)
        else:
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  {self.state}", qcol(C.PRI)

        p.setPen(QPen(col, 1))
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.drawText(QRectF(0, sy, W, 26), Qt.AlignmentFlag.AlignCenter, txt)

        # waveform
        wy = sy + 30
        N, bw = 36, 8
        wx0 = (W - N * bw) / 2
        for i in range(N):
            if self.muted:
                hgt, cl = 2, qcol(C.MUTED_C)
            elif self.speaking:
                hgt = random.randint(3, 20)
                cl  = qcol(C.PRI) if hgt > 12 else qcol(C.PRI_DIM)
            else:
                hgt = int(3 + 2 * math.sin(self._tick * 0.09 + i * 0.6))
                cl  = qcol(C.BORDER_B)
            p.fillRect(QRectF(wx0 + i * bw, wy + 20 - hgt, bw - 1, hgt), cl)


class Hologram3D(QOpenGLWidget):
    """Echtes 3D Hologramm mit OpenGL – rotierende Wireframe-Objekte + Epic Glow + Scanlines"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._angle_x = 0.0
        self._angle_y = 0.0
        self._angle_z = 0.0
        self._tick = 0
        self._speaking = False
        self._muted = False
        self._glow_intensity = 0.8  # Hologramm-Glow
        self._scanline_offset = 0.0  # Scanline-Animation

        self._vao = None
        self._vbo = None
        self._program = None
        self._vertex_count = 0

        # 200 Partikel im 3D-Raum
        self._particles = []
        for _ in range(200):
            theta = random.uniform(0, 2 * math.pi)
            phi = random.uniform(0, math.pi)
            r = random.uniform(0.5, 1.5)
            self._particles.append({
                'pos': [r * math.sin(phi) * math.cos(theta),
                        r * math.sin(phi) * math.sin(theta),
                        r * math.cos(phi)],
                'vel': [random.uniform(-0.002, 0.002) for _ in range(3)],
                'life': random.uniform(0.5, 1.0),
                'max_life': random.uniform(0.5, 1.0),
                'color': [random.uniform(0.0, 0.3), random.uniform(0.6, 1.0), random.uniform(0.8, 1.0)],
                'size': random.uniform(2.0, 5.0),
            })

        # Timer 60 FPS
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick_anim)
        self._tmr.start(16)

    def _tick_anim(self):
        self._tick += 1
        dt = 1.0 / 60.0
        speed = 1.8 if self._speaking else 0.5  # Schneller bei Sprechen
        self._angle_x += speed * dt
        self._angle_y += speed * 0.7 * dt
        self._angle_z += speed * 0.3 * dt

        # Glow pulst mit Audio
        self._glow_intensity = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(self._tick * 0.05))
        if self._speaking:
            self._glow_intensity *= 1.5

        # Scanline-Animation für holografischen Effekt
        self._scanline_offset = (self._scanline_offset + 0.3) % 100

        # Partikel updaten
        for p in self._particles:
            p['pos'][0] += p['vel'][0]
            p['pos'][1] += p['vel'][1]
            p['pos'][2] += p['vel'][2]
            p['life'] -= dt * 0.3
            if p['life'] <= 0:
                theta = random.uniform(0, 2 * math.pi)
                phi = random.uniform(0, math.pi)
                r = random.uniform(0.8, 1.8)
                p['pos'] = [r * math.sin(phi) * math.cos(theta),
                            r * math.sin(phi) * math.sin(theta),
                            r * math.cos(phi)]
                p['vel'] = [random.uniform(-0.002, 0.002) for _ in range(3)]
                p['life'] = p['max_life']
        self.update()

    def initializeGL(self):
        if not _HAS_OPENGL:
            return
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE)
        GL.glEnable(GL.GL_PROGRAM_POINT_SIZE)
        GL.glClearColor(0.0, 0.02, 0.04, 1.0)

        vs = QOpenGLShader(QOpenGLShader.ShaderTypeBit.Vertex)
        vs.compileSourceCode(b"""
        #version 330 core
        layout(location=0) in vec3 aPos;
        layout(location=1) in vec3 aCol;
        layout(location=2) in float aSize;
        out vec3 vCol;
        out float vAlpha;
        uniform mat4 uMVP;
        uniform float uTime;
        uniform bool uParticle;
        void main(){
            vec4 p = uMVP * vec4(aPos, 1.0);
            gl_Position = p;
            if(uParticle){
                float d = length(p.xyz);
                gl_PointSize = aSize * (80.0/max(d,0.5));
                vAlpha = 0.6+0.4*sin(uTime*2.0+length(aPos)*4.0);
            }else{
                gl_PointSize = 2.0;
                vAlpha = 0.5+0.5*sin(uTime*3.0+length(aPos)*6.0);
            }
            vCol = aCol;
        }
        """)
        fs = QOpenGLShader(QOpenGLShader.ShaderTypeBit.Fragment)
        fs.compileSourceCode(b"""
        #version 330 core
        in vec3 vCol;
        in float vAlpha;
        out vec4 fc;
        void main(){
            float d = length(gl_PointCoord-vec2(0.5));
            float a = smoothstep(0.5, 0.0, d) * vAlpha;
            fc = vec4(vCol, a*0.7);
        }
        """)
        self._program = QOpenGLShaderProgram()
        self._program.addShader(vs)
        self._program.addShader(fs)
        self._program.link()

        # Geometrie generieren
        verts = []
        # Wireframe-Würfel
        cube_edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
        cube_v = [(-1,-1,-1),(1,-1,-1),(1,-1,1),(-1,-1,1),
                  (-1,1,-1),(1,1,-1),(1,1,1),(-1,1,1)]
        for i,j in cube_edges:
            for idx in (i,j):
                x,y,z = cube_v[idx]
                verts.extend([x*0.5, y*0.5, z*0.5, 0.0, 0.8, 1.0, 2.0])
        # Wireframe-Sphäre (2 Ringe)
        for lat in range(0, 360, 15):
            a = math.radians(lat)
            x = 0.5*math.cos(a)
            y = 0.5*math.sin(a)
            for side in (-1, 1):
                verts.extend([x, y, side*0.3, 0.0, 1.0, 0.7, 2.0])
        for lon in range(0, 360, 15):
            a = math.radians(lon)
            x = 0.5*math.cos(a)
            z = 0.5*math.sin(a)
            for side in (-1, 1):
                verts.extend([x, side*0.3, z, 0.3, 0.9, 1.0, 2.0])
        # Partikel-Dummy (werden dynamisch)
        for _ in range(200):
            verts.extend([0,0,0, 0,1,0.5, 2.0])

        self._vertex_count = len(verts) // 7

        import array
        self._vao = QOpenGLVertexArrayObject()
        self._vao.create()
        self._vao.bind()
        self._vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self._vbo.create()
        self._vbo.bind()
        self._vbo.setUsagePattern(QOpenGLBuffer.UsagePattern.StaticDraw)
        arr = array.array('f', verts)
        self._vbo.allocate(arr.tobytes(), len(arr)*4)
        self._program.bind()
        self._program.enableAttributeArray(0)
        self._program.setAttributeBuffer(0, GL.GL_FLOAT, 0, 3, 7*4)
        self._program.enableAttributeArray(1)
        self._program.setAttributeBuffer(1, GL.GL_FLOAT, 3*4, 3, 7*4)
        self._program.enableAttributeArray(2)
        self._program.setAttributeBuffer(2, GL.GL_FLOAT, 6*4, 1, 7*4)
        self._vao.release()

    def resizeGL(self, w, h):
        if not _HAS_OPENGL:
            return
        GL.glViewport(0, 0, w, h)

    def paintGL(self):
        if not _HAS_OPENGL or not self._program:
            return
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        w, h = self.width(), self.height()
        aspect = w / h if h > 0 else 1.0
        proj = QMatrix4x4()
        proj.perspective(45.0, aspect, 0.1, 100.0)
        view = QMatrix4x4()
        view.lookAt(QVector3D(0, 0, 2.5), QVector3D(0, 0, 0), QVector3D(0, 1, 0))
        model = QMatrix4x4()
        model.rotate(self._angle_x * 57.3, 1, 0, 0)
        model.rotate(self._angle_y * 57.3, 0, 1, 0)
        model.rotate(self._angle_z * 57.3, 0, 0, 1)
        mvp = proj * view * model

        self._program.bind()
        self._program.setUniformValue("uMVP", mvp)
        self._program.setUniformValue("uTime", self._tick * 0.016)
        self._program.setUniformValue("uGlow", self._glow_intensity)
        self._program.setUniformValue("uParticle", False)
        self._vao.bind()
        
        # Wireframe mit Epic Glow
        GL.glDrawArrays(GL.GL_LINES, 0, 48)
        
        # Partikel mit Scanline-Overlay
        self._program.setUniformValue("uParticle", True)
        GL.glDrawArrays(GL.GL_POINTS, 48, 200)
        self._vao.release()
        self._program.release()
        
        # Post-Processing: Scanlines für holografischen Effekt
        self._draw_scanlines(w, h)

    def set_speaking(self, v: bool):
        self._speaking = v

    def set_muted(self, v: bool):
        self._muted = v

    def _draw_scanlines(self, w: int, h: int):
        """Zeichne holografische Scanlines über die Szene"""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        # Dünne Scanlines für Hologramm-Effekt
        line_spacing = 3
        for y in range(0, h, line_spacing):
            pos = int((y + self._scanline_offset) % h)
            # Alternating alpha für Flicker-Effekt
            alpha = 20 if (pos // line_spacing) % 2 == 0 else 5
            p.setPen(QPen(qcol("#00ff00", alpha), 1))
            p.drawLine(0, pos, w, pos)
        
        # Violette Chromatic Aberration oben/unten
        p.setPen(QPen(qcol("#ff00ff", 10), 2))
        p.drawLine(0, 0, w, 0)
        p.drawLine(0, h - 1, w, h - 1)
        p.end()


class MetricBar(QWidget):

    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0
        self._text  = "--"
        self.setFixedHeight(38)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct))
        self._text  = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        bar_h   = 4
        bar_y   = H - bar_h - 5
        bar_w   = W - 12
        bar_x   = 6
        fill_w  = int(bar_w * self._value / 100)

        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        if self._value > 85:
            bar_col = qcol(C.RED)
        elif self._value > 65:
            bar_col = qcol(C.ACC)
        else:
            bar_col = qcol(self._color)

        if fill_w > 0:
            p.setBrush(QBrush(bar_col))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)

        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(8, 5, 50, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 4, W - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)


class AetherOrbWidget(QWidget):
    """Warm energy-orb interface inspired by the user's video reference."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tick = 0
        self._speaking = False
        self._muted = False
        self._energy = 0.0
        self._inner_spin = 0.0
        self._paths = []
        for i in range(44):
            self._paths.append({
                "phase": random.uniform(0, math.tau),
                "tilt": random.uniform(-0.95, 0.95),
                "radius": random.uniform(0.52, 1.16),
                "speed": random.uniform(0.007, 0.022),
                "width": random.uniform(0.7, 3.2),
                "alpha": random.randint(55, 230),
            })
        self._sparks = [
            [random.random(), random.random(), random.uniform(0.4, 1.0)]
            for _ in range(150)
        ]
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(13)

    def set_speaking(self, v: bool):
        self._speaking = v

    def set_muted(self, v: bool):
        self._muted = v

    def _step(self):
        self._tick += 1
        target_energy = 1.0 if self._speaking else 0.18
        if self._muted:
            target_energy = 0.05
        self._energy += (target_energy - self._energy) * 0.09
        speed_boost = 1.0 + self._energy * 4.4
        self._inner_spin += 0.018 * speed_boost
        for p in self._paths:
            p["phase"] += p["speed"] * speed_boost
        if self._speaking and random.random() < 0.72:
            self._sparks.append([random.random(), random.random(), 1.0])
        drift = 0.0012 + self._energy * 0.004
        fade = 0.005 + self._energy * 0.004
        self._sparks = [[x, y - drift, max(0, a - fade)] for x, y, a in self._sparks if a > 0.02]
        while len(self._sparks) < 150:
            self._sparks.append([random.random(), random.random(), random.uniform(0.25, 0.9)])
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        span = min(W, H)

        bg = QRadialGradient(QPointF(cx, cy), span * 0.75)
        bg.setColorAt(0.0, qcol("#1b0902"))
        bg.setColorAt(0.38, qcol("#090301"))
        bg.setColorAt(1.0, qcol("#000000"))
        p.fillRect(self.rect(), QBrush(bg))

        pulse = 0.5 + 0.5 * math.sin(self._tick * (0.14 if self._speaking else 0.04))
        base_alpha = 60 if not self._muted else 24
        glow_alpha = int(base_alpha + pulse * (95 + self._energy * 95))
        glow = QRadialGradient(QPointF(cx, cy), span * (0.42 + self._energy * 0.1))
        glow.setColorAt(0.0, qcol("#fff2c4", min(230, glow_alpha + 45)))
        glow.setColorAt(0.25, qcol("#ff8a1f", glow_alpha))
        glow.setColorAt(0.62, qcol("#5b2105", int(60 + self._energy * 55)))
        glow.setColorAt(1.0, qcol("#000000", 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QRectF(cx - span * 0.42, cy - span * 0.42, span * 0.84, span * 0.84))

        core = QRadialGradient(QPointF(cx, cy), span * 0.18)
        core.setColorAt(0.0, qcol("#ffffff", 210 if self._speaking else 140))
        core.setColorAt(0.18, qcol("#ffd18a", 210))
        core.setColorAt(0.58, qcol("#ff7a16", 150))
        core.setColorAt(1.0, qcol("#120300", 0))
        p.setBrush(QBrush(core))
        p.drawEllipse(QRectF(cx - span * 0.18, cy - span * 0.18, span * 0.36, span * 0.36))

        for x, y, a in self._sparks:
            dx = (x - 0.5) * span * 0.95
            dy = (y - 0.5) * span * 0.95
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > span * 0.46:
                continue
            alpha = int(180 * a * (1.0 - dist / (span * 0.54)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol("#ffe5aa", alpha)))
            size = 1.0 + a * (2.0 + self._energy * 2.4)
            p.drawEllipse(QPointF(cx + dx, cy + dy), size, size)

        for idx, item in enumerate(self._paths):
            phase = item["phase"]
            tilt = item["tilt"]
            radius = span * (0.22 + self._energy * 0.035) * item["radius"]
            wobble = 0.20 + self._energy * 0.16 + 0.06 * math.sin(phase * 1.7 + idx)
            path = QPainterPath()
            steps = 58
            for step in range(steps):
                t = (step / (steps - 1)) * math.tau
                twist = t + phase
                r = radius * (1.0 + wobble * math.sin(t * 3.0 + phase))
                x = cx + math.cos(twist) * r
                y = cy + math.sin(twist) * r * (0.36 + abs(tilt) * 0.52)
                y += math.sin(twist * 1.7 + tilt * 4.0) * span * 0.025
                x += math.sin(twist * 0.9 + tilt) * span * 0.035
                if step == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            col = "#ff3355" if self._muted else ("#fff4cf" if idx % 5 == 0 else "#ffad3d")
            alpha = min(255, int(item["alpha"] * (1.0 + self._energy * 0.85)))
            width = item["width"] * (1.0 + self._energy * 0.45)
            p.setPen(QPen(qcol(col, alpha), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        p.setPen(QPen(qcol(C.PRI, 190), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for n, scale in enumerate((0.34, 0.46, 0.57)):
            phase = self._inner_spin * (1.0 + n * 0.4)
            rect = QRectF(cx - span * scale / 2, cy - span * scale / 2,
                          span * scale, span * scale)
            p.drawArc(rect, int(math.degrees(phase) * 16), int((190 + self._energy * 110) * 16))
            p.drawArc(rect, int((math.degrees(phase) + 210) * 16), int(70 * 16))

        p.setPen(QPen(qcol("#fff0bd", 130 + int(self._energy * 80)), 1))
        for scale in (0.42, 0.53):
            p.drawEllipse(QRectF(cx - span * scale / 2, cy - span * scale / 2,
                                 span * scale, span * scale))

        status_color = C.MUTED_C if self._muted else (C.ACC2 if self._speaking else C.PRI_DIM)
        status = "MUTED" if self._muted else ("VOICE ACTIVE" if self._speaking else "ONLINE")
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(status_color, 185), 1))
        p.drawText(QRectF(0, H - 42, W, 18), Qt.AlignmentFlag.AlignCenter, status)


class OriginalMeshOpenGLWidget(QOpenGLWidget):
    """GPU renderer for complete source meshes without visible triangle edges."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._asset = None
        self._program = None
        self._vbo = None
        self._ebo = None
        self._index_count = 0
        self._yaw = 0.0
        self._pitch = -8.0
        self._distance = 6.4
        self._dragging = False
        self._last_mouse = QPointF()
        self._pointer = QPointF()
        self._pointer_visible = False
        self._pointer_pressed = False
        self.setMouseTracking(True)

    def set_asset(self, asset: MeshAsset) -> None:
        self._asset = asset
        if self.isValid():
            self.makeCurrent()
            self._upload_asset()
            self.doneCurrent()
        self.update()

    def initializeGL(self) -> None:
        GL.glClearColor(0.01, 0.003, 0.0, 1.0)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)
        vertex_shader = """
            #version 330 core
            layout(location=0) in vec3 position;
            layout(location=1) in vec3 normal;
            layout(location=2) in vec4 color;
            uniform mat4 projection;
            uniform mat4 view;
            uniform mat4 model;
            out vec3 vNormal;
            out vec3 vPosition;
            out vec4 vColor;
            void main() {
                vec4 world = model * vec4(position, 1.0);
                vPosition = world.xyz;
                vNormal = normalize(mat3(model) * normal);
                vColor = color;
                gl_Position = projection * view * world;
            }
        """
        fragment_shader = """
            #version 330 core
            in vec3 vNormal;
            in vec3 vPosition;
            in vec4 vColor;
            out vec4 fragColor;
            void main() {
                vec3 n = normalize(vNormal);
                vec3 key = normalize(vec3(-0.45, 0.75, 0.65));
                vec3 fill = normalize(vec3(0.65, 0.15, 0.55));
                vec3 viewDir = normalize(vec3(0.0, 0.0, 6.0) - vPosition);
                float diffuse = max(dot(n, key), 0.0) * 0.78;
                float secondary = max(dot(n, fill), 0.0) * 0.25;
                float specular = pow(max(dot(reflect(-key, n), viewDir), 0.0), 52.0) * 0.72;
                float rim = pow(1.0 - max(dot(n, viewDir), 0.0), 2.5) * 0.18;
                vec3 base = pow(max(vColor.rgb, vec3(0.0)), vec3(2.2));
                vec3 lit = base * (0.30 + diffuse + secondary) + vec3(specular) + vec3(0.1, 0.55, 0.75) * rim;
                fragColor = vec4(pow(max(lit, vec3(0.0)), vec3(1.0 / 2.2)), 1.0);
            }
        """
        vertex = self._compile_shader(GL.GL_VERTEX_SHADER, vertex_shader)
        fragment = self._compile_shader(GL.GL_FRAGMENT_SHADER, fragment_shader)
        self._program = GL.glCreateProgram()
        GL.glAttachShader(self._program, vertex)
        GL.glAttachShader(self._program, fragment)
        GL.glLinkProgram(self._program)
        if not GL.glGetProgramiv(self._program, GL.GL_LINK_STATUS):
            raise RuntimeError(GL.glGetProgramInfoLog(self._program).decode("utf-8", "replace"))
        GL.glDeleteShader(vertex)
        GL.glDeleteShader(fragment)
        self._upload_asset()

    @staticmethod
    def _compile_shader(shader_type: int, source: str) -> int:
        shader = GL.glCreateShader(shader_type)
        GL.glShaderSource(shader, source)
        GL.glCompileShader(shader)
        if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
            raise RuntimeError(GL.glGetShaderInfoLog(shader).decode("utf-8", "replace"))
        return shader

    def _upload_asset(self) -> None:
        if self._asset is None or self._program is None:
            return
        vertices = np.asarray(self._asset.vertices, dtype=np.float32)
        faces = np.asarray(self._asset.faces, dtype=np.uint32)
        face_vertices = vertices[faces]
        face_normals = np.cross(
            face_vertices[:, 1] - face_vertices[:, 0],
            face_vertices[:, 2] - face_vertices[:, 0],
        )
        lengths = np.linalg.norm(face_normals, axis=1)
        valid = lengths > 1e-8
        face_normals[valid] /= lengths[valid, None]
        normals = np.zeros_like(vertices)
        color_sum = np.zeros((len(vertices), 4), dtype=np.float32)
        counts = np.zeros(len(vertices), dtype=np.float32)
        face_colors = self._asset.colors.astype(np.float32) / 255.0
        for corner in range(3):
            indices = faces[:, corner]
            np.add.at(normals, indices, face_normals)
            np.add.at(color_sum, indices, face_colors)
            np.add.at(counts, indices, 1.0)
        normal_lengths = np.linalg.norm(normals, axis=1)
        normal_valid = normal_lengths > 1e-8
        normals[normal_valid] /= normal_lengths[normal_valid, None]
        colors = color_sum / np.maximum(counts[:, None], 1.0)
        packed = np.ascontiguousarray(np.column_stack((vertices, normals, colors)), dtype=np.float32)
        indices = np.ascontiguousarray(faces.reshape(-1), dtype=np.uint32)
        if self._vbo:
            GL.glDeleteBuffers(1, [self._vbo])
        if self._ebo:
            GL.glDeleteBuffers(1, [self._ebo])
        self._vbo = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, packed.nbytes, packed, GL.GL_STATIC_DRAW)
        self._ebo = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL.GL_STATIC_DRAW)
        self._index_count = int(indices.size)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, 0)

    def paintGL(self) -> None:
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        if not self._program or not self._vbo or not self._index_count:
            return
        aspect = self.width() / max(self.height(), 1)
        projection = QMatrix4x4()
        projection.perspective(35.0, aspect, 0.05, 100.0)
        view = QMatrix4x4()
        view.translate(0.0, 0.0, -self._distance)
        model = QMatrix4x4()
        model.rotate(self._pitch, 1.0, 0.0, 0.0)
        model.rotate(self._yaw, 0.0, 1.0, 0.0)
        GL.glUseProgram(self._program)
        for name, matrix in (("projection", projection), ("view", view), ("model", model)):
            location = GL.glGetUniformLocation(self._program, name)
            values = np.asarray(matrix.data(), dtype=np.float32)
            GL.glUniformMatrix4fv(location, 1, False, values)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._vbo)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        stride = 10 * 4
        GL.glEnableVertexAttribArray(0)
        GL.glEnableVertexAttribArray(1)
        GL.glEnableVertexAttribArray(2)
        GL.glVertexAttribPointer(0, 3, GL.GL_FLOAT, False, stride, ctypes.c_void_p(0))
        GL.glVertexAttribPointer(1, 3, GL.GL_FLOAT, False, stride, ctypes.c_void_p(3 * 4))
        GL.glVertexAttribPointer(2, 4, GL.GL_FLOAT, False, stride, ctypes.c_void_p(6 * 4))
        GL.glDrawElements(GL.GL_TRIANGLES, self._index_count, GL.GL_UNSIGNED_INT, None)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, 0)
        GL.glUseProgram(0)

        if self._pointer_visible:
            painter = QPainter(self)
            color = QColor("#FFD18A" if self._pointer_pressed else "#70D6FF")
            painter.setPen(QPen(color, 1.5))
            center = self._pointer
            painter.drawEllipse(center, 10.0, 10.0)
            painter.drawLine(QPointF(center.x() - 17, center.y()), QPointF(center.x() + 17, center.y()))
            painter.drawLine(QPointF(center.x(), center.y() - 17), QPointF(center.x(), center.y() + 17))
            painter.end()

    def rotate_model(self, dx: float, dy: float) -> None:
        self._yaw += dx * 0.55
        self._pitch = max(-70.0, min(70.0, self._pitch + dy * 0.45))
        self.update()

    def zoom_model(self, delta: float) -> None:
        self._distance = max(2.4, min(10.0, self._distance - delta * 2.5))
        self.update()

    def set_hand_pointer(self, x: float, y: float, pressed: bool) -> None:
        self._pointer = QPointF(x * self.width(), y * self.height())
        self._pointer_visible = True
        self._pointer_pressed = pressed
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._last_mouse = event.position()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            delta = event.position() - self._last_mouse
            self.rotate_model(delta.x(), delta.y())
            self._last_mouse = event.position()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def wheelEvent(self, event) -> None:
        self.zoom_model(0.12 if event.angleDelta().y() > 0 else -0.12)


class ModelViewer3D(QWidget):
    """Interactive hologram viewer for imported and procedural 3-D assets."""

    country_selected = pyqtSignal(str, str)

    _ORIGINAL_MODEL_FILES = {
        "iron_man_downloaded": "iron_man.glb",
        "iron_man_mark_85": "iron_man_mark_85.glb",
        "iron_man_mark_85_rigged": "iron-man_mark_85__rigged.glb",
        "arc_reactor": "arc_reactor_assembled.glb",
        "bugatti_bolide": "bugatti_bolide.glb",
    }

    _MODEL_ALIASES = {
        "planet": ("erde", "planet", "mond", "mars", "jupiter", "sonne"),
        "atom": ("atom", "molekuel", "molekül", "molecule", "element"),
        "dna": ("dna", "gen", "genom", "helix"),
        "solar": ("sonnensystem", "solar", "galaxie", "universum", "weltall"),
        "vehicle": (
            "auto", "car", "wagen", "fahrzeug", "sportwagen", "supercar", "motor",
            "bugatti", "ferrari", "lamborghini", "porsche", "mercedes", "bmw", "audi",
            "flugzeug", "rakete",
        ),
        "house": ("haus", "house", "gebäude", "gebaeude", "building", "villa"),
    }

    _CONTINENT_OUTLINES = (
        ((72, -168), (58, -140), (50, -125), (30, -117), (17, -100), (10, -82),
         (25, -80), (45, -66), (58, -60), (72, -80), (72, -168)),
        ((12, -81), (5, -77), (-15, -75), (-35, -70), (-55, -67), (-52, -40),
         (-25, -35), (0, -50), (12, -65), (12, -81)),
        ((36, -10), (58, -10), (71, 20), (60, 60), (52, 100), (45, 145),
         (25, 122), (8, 105), (20, 78), (30, 45), (36, 25), (36, -10)),
        ((36, -17), (20, -18), (5, -8), (-35, 18), (-35, 38), (-10, 50),
         (12, 44), (32, 32), (36, -17)),
        ((-10, 112), (-22, 114), (-39, 145), (-29, 154), (-11, 142), (-10, 112)),
        ((60, -52), (76, -45), (82, -20), (70, -18), (60, -52)),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 340)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._subject = "Hologramm"
        self._kind = "generic"
        self._yaw = 0.0
        self._pitch = -0.22
        self._zoom = 1.0
        self._target_zoom = 1.0
        self._focused = False
        self._suit_metadata: SuitDisplayMetadata | None = None
        self._suit_mark: int | None = None
        self._mesh_asset_key = ""
        self._mesh_asset: MeshAsset | None = None
        self._detail_mode = False
        self._animation_state = "idle"
        self._exploded_progress = 0.0
        self._detail_phase = 0.0
        self._intro_progress = 1.0
        self._hovered_country = ""
        self._selected_country = ""
        self._country_hit_targets: list[tuple[str, str, QPointF, float]] = []
        self._suit_hit_targets: list[tuple[int, QRectF]] = []
        self._dragging = False
        self._last_mouse = QPointF()
        self._gesture_cursor = QPointF()
        self._gesture_cursor_visible = False
        self._gesture_cursor_pressed = False
        self._gesture_last_tick = 0
        self._gpu_view = None
        self._gpu_model_key = ""
        self._tick = 0
        self.setMouseTracking(True)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(16)

    @staticmethod
    def _clean_subject(subject: str) -> str:
        clean = " ".join((subject or "").split()).strip(" .,!?:;")
        return clean[:80] or "Hologramm"

    @classmethod
    def _kind_for(cls, subject: str) -> str:
        lowered = subject.lower()
        if any(term in lowered for term in (
            "welt-news", "welt news", "world news", "weltnachrichten",
            "laender-news", "länder-news", "nachrichten-globus", "news-globus",
        )):
            return "world_news"
        if is_arc_reactor_detail_request(subject):
            return "arc_reactor"
        if parse_suit_request(subject):
            return "iron_man_suit"
        iron_man_context = "iron man" in lowered or "ironman" in lowered
        collection_request = any(term in lowered for term in (
            "alle", "anzuege", "anzüge", "suits", "kollektion", "collection", "armory",
        ))
        if collection_request and (iron_man_context or "mark" in lowered):
            return "iron_man_catalog"
        if (iron_man_context
                and any(term in lowered for term in ("helm", "helmet"))):
            return "iron_man_helmet"
        if (iron_man_context
                and any(term in lowered for term in ("gauntlet", "handschuh", "repulsor"))):
            return "iron_man_repulsor"
        if (iron_man_context
                and any(term in lowered for term in ("ruestung", "rüstung", "anzug", "suit", "armor"))):
            return "iron_man_suit"
        if iron_man_context:
            return "iron_man_suit"
        if any(alias in lowered for alias in ("sonnensystem", "solar", "galaxie", "universum", "weltall")):
            return "solar"
        for kind, aliases in cls._MODEL_ALIASES.items():
            if any(alias in lowered for alias in aliases):
                return kind
        return "generic"

    def _select_subject(self, subject: str):
        self._subject = self._clean_subject(subject)
        self._suit_metadata = parse_suit_request(self._subject)
        self._suit_mark = self._suit_metadata.mark if self._suit_metadata else None
        self._kind = self._kind_for(self._subject)
        self._mesh_asset_key = self._mesh_key_for(self._kind, self._subject)
        self._mesh_asset = load_mesh_asset(self._mesh_asset_key) if self._mesh_asset_key else None
        if self._kind == "world_news":
            self._yaw = -1.45
            self._pitch = -0.12
            self._target_zoom = 1.0
        else:
            self._yaw = 0.52 if self._kind in ("vehicle", "house") else 0.08
            self._pitch = -0.20
        self._hovered_country = ""
        self._selected_country = ""

    @staticmethod
    def _mesh_key_for(kind: str, subject: str) -> str:
        lowered = subject.casefold()
        if kind == "planet" and any(term in lowered for term in ("erde", "earth")):
            return "earth"
        if kind == "house":
            return "house"
        if kind == "vehicle" and not any(term in lowered for term in ("flugzeug", "rakete")):
            if "bugatti" in lowered or "bolide" in lowered:
                return "bugatti_bolide"
            return "sports_car"
        if kind == "arc_reactor":
            return "arc_reactor"
        if kind in ("iron_man_suit", "iron_man_helmet"):
            metadata = parse_suit_request(subject)
            if metadata and metadata.mark == 85:
                if "rigged" in lowered:
                    return "iron_man_mark_85_rigged"
                return "iron_man_mark_85"
            return "iron_man_downloaded"
        return ""

    @staticmethod
    def _is_suit_mesh_key(key: str) -> bool:
        return key.startswith("iron_man")

    def _original_model_path(self) -> Path | None:
        filename = self._ORIGINAL_MODEL_FILES.get(self._mesh_asset_key)
        if not filename:
            return None
        path = BASE_DIR / "assets" / "models" / "original" / filename
        return path if path.is_file() else None

    def _sync_gpu_view(self) -> None:
        source = self._original_model_path()
        usable = (
            source is not None
            and self._mesh_asset is not None
            and _HAS_OPENGL
            and os.getenv("QT_QPA_PLATFORM", "").casefold() != "offscreen"
        )
        if not usable:
            if self._gpu_view is not None:
                self._gpu_view.hide()
            return
        if self._gpu_view is None:
            self._gpu_view = OriginalMeshOpenGLWidget(self)
            self._gpu_view.setGeometry(self.rect())
        if self._gpu_model_key != self._mesh_asset_key:
            self._gpu_view.set_asset(self._mesh_asset)
            self._gpu_model_key = self._mesh_asset_key
        self._gpu_view.setGeometry(self.rect())
        self._gpu_view.show()
        self._gpu_view.raise_()

    def show_model(self, subject: str):
        self._select_subject(subject)
        self._focused = False
        self._detail_mode = False
        self._animation_state = "idle"
        self._exploded_progress = 0.0
        self._intro_progress = 0.0
        if self._kind == "iron_man_helmet":
            self._target_zoom = 1.65
        elif self._kind == "iron_man_suit":
            self._target_zoom = 0.90
        elif self._kind == "vehicle":
            self._target_zoom = 1.28
        elif self._kind == "arc_reactor":
            self._target_zoom = 0.86
        else:
            self._target_zoom = 1.0
        self._sync_gpu_view()
        self.update()

    def focus_model(self, subject: str = ""):
        if subject and self._clean_subject(subject).lower() != self._subject.lower():
            self._select_subject(subject)
        self._focused = True
        self._target_zoom = 1.9
        self._sync_gpu_view()
        self.update()

    def show_detail(self, subject: str = ""):
        """Animate an exploded technical view for the current or requested model."""

        if subject:
            self._select_subject(subject)
        self._focused = True
        self._detail_mode = True
        self._animation_state = "exploding"
        self._exploded_progress = 0.0
        self._detail_phase = 0.0
        self._target_zoom = 0.78 if self._is_suit_mesh_key(self._mesh_asset_key) else 1.35
        self._sync_gpu_view()
        self.update()

    def resizeEvent(self, event):
        if self._gpu_view is not None:
            self._gpu_view.setGeometry(self.rect())
        super().resizeEvent(event)

    @property
    def subject(self) -> str:
        return self._subject

    def _step(self):
        self._tick += 1
        if self._kind == "world_news":
            if not self._hovered_country and not self._selected_country:
                self._yaw += 0.0022
            self._pitch += (-0.12 - self._pitch) * 0.025
        else:
            if self._dragging:
                rotation_speed = 0.0
            elif self._focused:
                rotation_speed = 0.0018 if self._detail_mode else 0.0035
            else:
                rotation_speed = 0.0048 if self._mesh_asset is not None else 0.007
            self._yaw += rotation_speed
            target_pitch = -0.20 + math.sin(self._tick * 0.006) * 0.065
            if not self._dragging:
                self._pitch += (target_pitch - self._pitch) * 0.06
        self._zoom += (self._target_zoom - self._zoom) * 0.055
        self._intro_progress = min(1.0, self._intro_progress + 0.032)
        if self._animation_state == "exploding":
            self._exploded_progress = min(1.0, self._exploded_progress + 0.018)
            if self._exploded_progress >= 1.0:
                self._animation_state = "exploded"
        self._detail_phase += 0.04 if self._detail_mode else 0.01
        if self._mesh_asset is not None:
            frame_stride = 4 if len(self._mesh_asset.render_faces) > 40_000 else 2
            if self._tick % frame_stride:
                return
        self.update()

    def _project(self, point: tuple[float, float, float], width: float, height: float) -> QPointF:
        x, y, z = self._rotate_point(point)
        intro_scale = 0.86 + 0.14 * self._ease_out(self._intro_progress)
        depth = max(1.2, 5.4 + z)
        scale = min(width, height) * 1.55 * self._zoom * intro_scale / depth
        return QPointF(width * 0.5 + x * scale, height * 0.52 - y * scale)

    def _rotate_point(self, point: tuple[float, float, float]) -> tuple[float, float, float]:
        x, y, z = point
        cy, sy = math.cos(self._yaw), math.sin(self._yaw)
        x, z = x * cy - z * sy, x * sy + z * cy
        cx, sx = math.cos(self._pitch), math.sin(self._pitch)
        y, z = y * cx - z * sx, y * sx + z * cx
        return x, y, z

    @staticmethod
    def _geo_point(latitude: float, longitude: float, radius: float = 1.0) -> tuple[float, float, float]:
        lat = math.radians(latitude)
        lon = math.radians(longitude)
        return (
            radius * math.cos(lat) * math.cos(lon),
            radius * math.sin(lat),
            radius * math.cos(lat) * math.sin(lon),
        )

    def _rotate_array(self, vertices: np.ndarray) -> np.ndarray:
        cy, sy = math.cos(self._yaw), math.sin(self._yaw)
        cx, sx = math.cos(self._pitch), math.sin(self._pitch)
        x = vertices[:, 0] * cy - vertices[:, 2] * sy
        z = vertices[:, 0] * sy + vertices[:, 2] * cy
        y = vertices[:, 1] * cx - z * sx
        z_rotated = vertices[:, 1] * sx + z * cx
        return np.column_stack((x, y, z_rotated)).astype(np.float32, copy=False)

    def _mesh_base_colors(self, asset: MeshAsset) -> np.ndarray:
        source_colors = asset.render_colors
        source_groups = asset.render_groups
        if self._mesh_asset_key == "arc_reactor":
            source = source_colors.copy()
            palette = np.asarray((
                (155, 54, 38, 255),
                (202, 112, 48, 255),
                (42, 48, 55, 255),
                (188, 246, 255, 255),
                (18, 23, 28, 255),
                (176, 184, 190, 255),
            ), dtype=np.float32)
            brightness = np.clip(source[:, :3].mean(axis=1) / 150.0, 0.62, 1.18)
            source[:, :3] = np.clip(
                palette[np.minimum(source_groups, 5), :3] * brightness[:, None],
                0,
                255,
            ).astype(np.uint8)
            return source
        if self._mesh_asset_key == "sports_car":
            colors = source_colors.copy()
            rgb = colors[:, :3]
            body_mask = (rgb[:, 1] > rgb[:, 0] * 1.12) & (rgb[:, 1] > rgb[:, 2] * 1.08)
            brand_colors = {
                "bugatti": (32, 92, 190),
                "ferrari": (205, 28, 32),
                "lamborghini": (225, 170, 24),
                "porsche": (175, 182, 190),
            }
            target = next(
                (color for brand, color in brand_colors.items() if brand in self._subject.casefold()),
                None,
            )
            if target and np.any(body_mask):
                brightness = np.clip(rgb[body_mask].mean(axis=1) / 108.0, 0.48, 1.25)
                colors[body_mask, :3] = np.clip(
                    np.asarray(target, dtype=np.float32)[None, :] * brightness[:, None],
                    0, 255,
                ).astype(np.uint8)
            return colors
        if self._mesh_asset_key != "iron_man_suit":
            return source_colors
        primary, accent, _ = self._suit_colours()
        if self._suit_mark == 39:
            primary = QColor("#E3E8E8")
            accent = QColor("#303A43")
        palette = np.asarray((
            primary.getRgb(),
            accent.getRgb(),
            (38, 44, 52, 255),
            (190, 247, 255, 255),
            (8, 13, 20, 255),
            (194, 192, 182, 255),
        ), dtype=np.uint8)
        return palette[np.minimum(source_groups, len(palette) - 1)]

    def _draw_mesh_model(self, painter: QPainter, width: float, height: float):
        asset = self._mesh_asset
        if asset is None:
            return

        vertices = asset.render_vertices
        is_suit_mesh = self._is_suit_mesh_key(self._mesh_asset_key)
        if self._mesh_asset_key == "iron_man_suit":
            profile = self._suit_metadata.profile if self._suit_metadata else "classic"
            profile_scale = {
                "prototype": (1.10, 0.98, 1.08),
                "stealth": (0.94, 1.03, 0.92),
                "heavy": (1.16, 1.02, 1.12),
                "orbital": (0.94, 1.07, 0.92),
                "nanotech": (0.96, 1.04, 0.90),
            }.get(profile, (1.0, 1.0, 1.0))
            vertices = vertices * np.asarray(profile_scale, dtype=np.float32)
        rotated = self._rotate_array(vertices)
        faces = asset.render_faces
        face_indices = np.arange(len(faces))
        if self._kind == "iron_man_helmet":
            face_indices = face_indices[asset.render_parts == 1]
            faces = faces[asset.render_parts == 1]
        triangles = rotated[faces].copy()

        if self._detail_mode and (is_suit_mesh or self._mesh_asset_key == "arc_reactor"):
            exploded = self._ease_out(self._exploded_progress) * 0.62
            if is_suit_mesh:
                directions = {
                    1: (0.0, 0.72, 0.06), 2: (0.0, 0.12, 0.40),
                    3: (-0.72, 0.08, 0.04), 4: (0.72, 0.08, 0.04),
                    5: (0.0, -0.28, 0.18), 6: (-0.34, -0.62, 0.04),
                    7: (0.34, -0.62, 0.04), 8: (0.0, 0.08, -0.72),
                }
            else:
                directions = {
                    1: (-0.65, 0.48, 0.20), 2: (0.0, 0.76, 0.32),
                    3: (0.65, 0.48, 0.20), 4: (-0.78, 0.0, 0.44),
                    5: (0.78, 0.0, 0.44), 6: (-0.48, -0.62, 0.24),
                    7: (0.48, -0.62, 0.24), 8: (0.0, 0.0, -0.82),
                }
            visible_parts = asset.render_parts[face_indices]
            for part, direction in directions.items():
                mask = visible_parts == part
                if not np.any(mask):
                    continue
                transformed_direction = self._rotate_array(
                    np.asarray((direction, (0.0, 0.0, 0.0)), dtype=np.float32)
                )[0]
                triangles[mask] += transformed_direction * exploded

        edge_a = triangles[:, 1] - triangles[:, 0]
        edge_b = triangles[:, 2] - triangles[:, 0]
        normals = np.cross(edge_a, edge_b)
        normal_length = np.linalg.norm(normals, axis=1)
        valid = normal_length > 1e-7
        normals[valid] /= normal_length[valid, None]

        # The source assets use counter-clockwise outward faces. The camera is
        # positioned on negative Z, so front-facing normals point toward -Z.
        if (
            (is_suit_mesh and self._mesh_asset_key != "iron_man_suit")
            or self._mesh_asset_key == "arc_reactor"
        ):
            visible = valid
        else:
            visible = valid & (normals[:, 2] < 0.10)
        triangles = triangles[visible]
        normals = normals[visible]
        source_indices = face_indices[visible]

        groups = asset.render_groups[source_indices]
        base_colors = self._mesh_base_colors(asset)[source_indices].astype(np.float32)
        key_light = np.asarray((-0.36, 0.58, -0.73), dtype=np.float32)
        key_light /= np.linalg.norm(key_light)
        fill_light = np.asarray((0.62, 0.14, -0.78), dtype=np.float32)
        fill_light /= np.linalg.norm(fill_light)
        diffuse = np.clip(normals @ key_light, 0.0, 1.0)
        fill = np.clip(normals @ fill_light, 0.0, 1.0)
        if self._mesh_asset_key == "earth":
            ambient, key_strength, fill_strength = 0.46, 0.78, 0.18
        elif is_suit_mesh and self._mesh_asset_key != "iron_man_suit":
            ambient, key_strength, fill_strength = 0.36, 0.76, 0.25
        else:
            ambient, key_strength, fill_strength = 0.24, 0.66, 0.18
        intensity = ambient + diffuse * key_strength + fill * fill_strength

        view = np.asarray((0.0, 0.0, -1.0), dtype=np.float32)
        half_vector = key_light + view
        half_vector /= np.linalg.norm(half_vector)
        highlight = np.clip(normals @ half_vector, 0.0, 1.0)
        material_power = np.take(
            np.asarray((42.0, 58.0, 88.0, 18.0, 34.0, 112.0), dtype=np.float32),
            np.minimum(groups, 5),
        )
        material_strength = np.take(
            np.asarray((48.0, 66.0, 82.0, 0.0, 18.0, 110.0), dtype=np.float32),
            np.minimum(groups, 5),
        )
        specular = np.power(highlight, material_power) * material_strength
        facing = np.clip(-normals[:, 2], 0.0, 1.0)
        rim_strength = 26.0 if is_suit_mesh or self._mesh_asset_key == "arc_reactor" else 10.0
        rim = np.power(1.0 - facing, 2.4) * rim_strength
        rgb = np.clip(base_colors[:, :3] * intensity[:, None] + specular[:, None] + rim[:, None], 0, 255)

        emissive = groups == 3
        if np.any(emissive):
            pulse = 0.82 + 0.18 * math.sin(self._detail_phase * 3.2)
            rgb[emissive] = np.clip(base_colors[emissive, :3] * (1.05 + pulse * 0.28), 0, 255)

        intro = 0.86 + 0.14 * self._ease_out(self._intro_progress)
        depth = np.maximum(1.2, 5.4 + triangles[:, :, 2])
        scale = min(width, height) * 1.55 * self._zoom * intro / depth
        screen_x = width * 0.5 + triangles[:, :, 0] * scale
        screen_y = height * 0.52 - triangles[:, :, 1] * scale
        order = np.argsort(triangles[:, :, 2].mean(axis=1))[::-1]

        center = self._project((0.0, 0.0, 0.0), width, height)
        aura = QRadialGradient(center, min(width, height) * 0.36 * self._zoom)
        aura.setColorAt(0.0, qcol("#2E9FB8", 34))
        aura.setColorAt(0.65, qcol("#0B5365", 14))
        aura.setColorAt(1.0, qcol("#000000", 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(aura))
        painter.drawEllipse(center, min(width, height) * 0.36, min(width, height) * 0.36)

        painter.setPen(Qt.PenStyle.NoPen)
        quantized_rgb = ((rgb.astype(np.uint16) // 8) * 8).clip(0, 255).astype(np.uint8)
        brush_cache: dict[tuple[int, int, int, int], QBrush] = {}
        for index in order:
            polygon = QPolygonF((
                QPointF(float(screen_x[index, 0]), float(screen_y[index, 0])),
                QPointF(float(screen_x[index, 1]), float(screen_y[index, 1])),
                QPointF(float(screen_x[index, 2]), float(screen_y[index, 2])),
            ))
            red, green, blue = quantized_rgb[index]
            alpha = 250 if groups[index] == 3 else 238
            brush_key = (int(red), int(green), int(blue), alpha)
            brush = brush_cache.get(brush_key)
            if brush is None:
                brush = QBrush(QColor(*brush_key))
                brush_cache[brush_key] = brush
            painter.setBrush(brush)
            painter.drawPolygon(polygon)

        if np.any(emissive):
            glow_indices = np.flatnonzero(emissive)
            stride = max(1, len(glow_indices) // 70)
            for index in glow_indices[::stride]:
                gx = float(screen_x[index].mean())
                gy = float(screen_y[index].mean())
                glow_radius = 10.0 if is_suit_mesh else 7.0
                glow = QRadialGradient(QPointF(gx, gy), glow_radius)
                glow.setColorAt(0.0, qcol("#BDFBFF", 130))
                glow.setColorAt(0.45, qcol("#56DFFF", 42))
                glow.setColorAt(1.0, qcol("#000000", 0))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(glow))
                painter.drawEllipse(QPointF(gx, gy), glow_radius, glow_radius)

        if self._detail_mode:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcol("#70D6FF", 62), 0.45))
            stride = max(1, len(order) // 120)
            for index in order[::stride]:
                painter.drawPolyline(QPolygonF((
                    QPointF(float(screen_x[index, 0]), float(screen_y[index, 0])),
                    QPointF(float(screen_x[index, 1]), float(screen_y[index, 1])),
                    QPointF(float(screen_x[index, 2]), float(screen_y[index, 2])),
                    QPointF(float(screen_x[index, 0]), float(screen_y[index, 0])),
                )))
        elif is_suit_mesh:
            seam_indices = np.flatnonzero(np.isin(groups, (4, 5)))
            seam_index_set = set(seam_indices.tolist())
            seam_order = [index for index in order if index in seam_index_set]
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(qcol("#07121C", 72), 0.38))
            stride = max(1, len(seam_order) // 80)
            for index in seam_order[::stride]:
                painter.drawPolyline(QPolygonF((
                    QPointF(float(screen_x[index, 0]), float(screen_y[index, 0])),
                    QPointF(float(screen_x[index, 1]), float(screen_y[index, 1])),
                    QPointF(float(screen_x[index, 2]), float(screen_y[index, 2])),
                    QPointF(float(screen_x[index, 0]), float(screen_y[index, 0])),
                )))

        painter.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        painter.setPen(QPen(qcol("#70D6FF", 175), 1))
        painter.drawText(
            QRectF(18, 38, width - 36, 18), Qt.AlignmentFlag.AlignLeft,
            f"SOURCE {len(asset.faces):,} TRI  //  DISPLAY LOD {len(asset.render_faces):,}  //  DRAG TO ROTATE",
        )

    def _draw_polyline(self, painter: QPainter, points, width: float, height: float,
                       color: QColor, pen_width: float = 1.0):
        poly = QPolygonF([self._project(point, width, height) for point in points])
        painter.setPen(QPen(color, pen_width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(poly)

    def _draw_planet(self, painter: QPainter, width: float, height: float, color: QColor):
        for lat in range(-60, 61, 20):
            radians = math.radians(lat)
            ring = [
                (math.cos(radians) * math.cos(math.radians(angle)), math.sin(radians),
                 math.cos(radians) * math.sin(math.radians(angle)))
                for angle in range(0, 361, 10)
            ]
            self._draw_polyline(painter, ring, width, height, color, 0.9)
        for lon in range(0, 180, 24):
            radians = math.radians(lon)
            arc = [
                (math.cos(math.radians(angle)) * math.cos(radians), math.sin(math.radians(angle)),
                 math.cos(math.radians(angle)) * math.sin(radians))
                for angle in range(-90, 91, 8)
            ]
            self._draw_polyline(painter, arc, width, height, color, 0.9)

    def _draw_surface_path(self, painter: QPainter, points, width: float, height: float,
                           color: QColor, pen_width: float = 1.0):
        """Draw only the camera-facing pieces of a path on a sphere."""

        painter.setPen(QPen(color, pen_width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        previous = None
        previous_visible = False
        for point in points:
            visible = self._rotate_point(point)[2] <= 0.08
            projected = self._project(point, width, height)
            if previous is not None and previous_visible and visible:
                painter.drawLine(previous, projected)
            previous = projected
            previous_visible = visible

    def _draw_world_news(self, painter: QPainter, width: float, height: float):
        center = self._project((0.0, 0.0, 0.0), width, height)
        intro = 0.86 + 0.14 * self._ease_out(self._intro_progress)
        radius = min(width, height) * 1.55 * self._zoom * intro / 5.4
        globe_fill = QRadialGradient(center - QPointF(radius * 0.22, radius * 0.28), radius * 1.28)
        globe_fill.setColorAt(0.0, qcol("#163343", 215))
        globe_fill.setColorAt(0.65, qcol("#07151D", 225))
        globe_fill.setColorAt(1.0, qcol("#010608", 245))
        painter.setPen(QPen(qcol("#70D6FF", 210), 1.6))
        painter.setBrush(QBrush(globe_fill))
        painter.drawEllipse(center, radius, radius)

        for latitude in range(-60, 61, 20):
            points = [self._geo_point(latitude, longitude, 1.006)
                      for longitude in range(-180, 181, 5)]
            self._draw_surface_path(painter, points, width, height, qcol("#3F91A8", 80), 0.7)
        for longitude in range(-180, 180, 20):
            points = [self._geo_point(latitude, longitude, 1.006)
                      for latitude in range(-90, 91, 4)]
            self._draw_surface_path(painter, points, width, height, qcol("#3F91A8", 72), 0.7)

        for outline in self._CONTINENT_OUTLINES:
            points = [self._geo_point(latitude, longitude, 1.018)
                      for latitude, longitude in outline]
            self._draw_surface_path(painter, points, width, height, qcol("#FFD18A", 185), 1.2)

        self._country_hit_targets = []
        visible_markers = []
        for country in country_markers():
            point = self._geo_point(country.latitude, country.longitude, 1.035)
            depth = self._rotate_point(point)[2]
            if depth <= 0.02:
                visible_markers.append((depth, country, self._project(point, width, height)))

        for _, country, position in sorted(visible_markers, key=lambda item: item[0], reverse=True):
            selected = country.code == self._selected_country
            hovered = country.code == self._hovered_country
            pulse = 1.0 + 0.18 * math.sin(self._detail_phase * 3.2)
            marker_radius = (7.0 if selected else 5.0 if hovered else 3.2) * pulse
            color = qcol("#FFF3D6", 245) if selected else qcol("#70D6FF", 235)
            painter.setPen(QPen(color, 1.2))
            painter.setBrush(QBrush(qcol("#FFAD3D", 210) if selected else qcol("#70D6FF", 150)))
            painter.drawEllipse(position, marker_radius, marker_radius)
            self._country_hit_targets.append((country.code, country.name, position, 15.0))

            if hovered or selected:
                label = f"{country.name.upper()}  [{country.code}]"
                label_rect = QRectF(position.x() + 10, position.y() - 19, 170, 18)
                painter.setPen(QPen(qcol("#FFF3D6", 235), 1))
                painter.setBrush(QBrush(qcol("#030100", 210)))
                painter.drawRoundedRect(label_rect, 3, 3)
                painter.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
                painter.drawText(label_rect.adjusted(6, 0, -4, 0),
                                 Qt.AlignmentFlag.AlignVCenter, label)

        painter.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        painter.setPen(QPen(qcol("#70D6FF", 200), 1))
        painter.drawText(QRectF(18, 38, width - 36, 18), Qt.AlignmentFlag.AlignLeft,
                         "LAND ANKLICKEN  //  AKTUELLE SCHLAGZEILEN")

    def _draw_atom(self, painter: QPainter, width: float, height: float, color: QColor):
        for tilt in (0.0, math.pi / 3, -math.pi / 3):
            orbit = []
            for angle in range(0, 361, 7):
                radians = math.radians(angle)
                orbit.append((
                    math.cos(radians), math.sin(radians) * math.cos(tilt) * 0.42,
                    math.sin(radians) * math.sin(tilt) * 0.85,
                ))
            self._draw_polyline(painter, orbit, width, height, color, 1.1)
        center = self._project((0, 0, 0), width, height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(qcol("#fff4cf", 240)))
        painter.drawEllipse(center, 12 * self._zoom, 12 * self._zoom)

    def _draw_dna(self, painter: QPainter, width: float, height: float, color: QColor):
        left, right = [], []
        for degree in range(-270, 271, 9):
            radians = math.radians(degree)
            y = degree / 270.0 * 1.35
            left.append((0.48 * math.cos(radians), y, 0.48 * math.sin(radians)))
            right.append((-0.48 * math.cos(radians), y, -0.48 * math.sin(radians)))
        self._draw_polyline(painter, left, width, height, color, 1.5)
        self._draw_polyline(painter, right, width, height, qcol("#ffd18a", 220), 1.5)
        for index in range(0, len(left), 7):
            self._draw_polyline(painter, (left[index], right[index]), width, height,
                                qcol("#ff8a1f", 150), 0.8)

    def _draw_solar(self, painter: QPainter, width: float, height: float, color: QColor):
        for radius in (0.45, 0.75, 1.05, 1.35):
            ring = [
                (radius * math.cos(math.radians(angle)), 0.0,
                 radius * math.sin(math.radians(angle)))
                for angle in range(0, 361, 8)
            ]
            self._draw_polyline(painter, ring, width, height, qcol("#ffd18a", 135), 0.8)
        center = self._project((0, 0, 0), width, height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(qcol("#fff3b0", 245)))
        painter.drawEllipse(center, 13 * self._zoom, 13 * self._zoom)
        for index, radius in enumerate((0.45, 0.75, 1.05, 1.35)):
            angle = self._yaw * (1.5 - index * 0.18) + index * 1.4
            point = (radius * math.cos(angle), 0.0, radius * math.sin(angle))
            pos = self._project(point, width, height)
            painter.setBrush(QBrush(color if index % 2 else qcol("#ff8a1f", 230)))
            painter.drawEllipse(pos, 4 + index * 1.5, 4 + index * 1.5)

    def _draw_vehicle(self, painter: QPainter, width: float, height: float, color: QColor):
        points = [
            (-1.05, -0.35, -0.45), (1.05, -0.35, -0.45), (1.05, -0.35, 0.45), (-1.05, -0.35, 0.45),
            (-0.70, 0.25, -0.45), (0.50, 0.25, -0.45), (0.50, 0.25, 0.45), (-0.70, 0.25, 0.45),
        ]
        edges = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
                 (0, 4), (1, 5), (2, 6), (3, 7))
        painter.setPen(QPen(color, 1.4))
        for a, b in edges:
            painter.drawLine(self._project(points[a], width, height), self._project(points[b], width, height))
        for x in (-0.65, 0.65):
            for z in (-0.5, 0.5):
                wheel = self._project((x, -0.45, z), width, height)
                painter.setBrush(QBrush(qcol("#120906", 230)))
                painter.drawEllipse(wheel, 10 * self._zoom, 10 * self._zoom)

    def _draw_generic(self, painter: QPainter, width: float, height: float, color: QColor):
        # Unknown subjects get a neutral analysis lattice instead of a misleading cube.
        for latitude in range(-60, 61, 20):
            points = [self._geo_point(latitude, longitude) for longitude in range(-180, 181, 8)]
            self._draw_polyline(painter, points, width, height, qcol("#FFD18A", 115), 0.8)
        for tilt in (0.0, math.pi / 3, -math.pi / 3):
            orbit = []
            for angle in range(0, 361, 7):
                radians = math.radians(angle)
                orbit.append((
                    1.28 * math.cos(radians),
                    1.28 * math.sin(radians) * math.cos(tilt),
                    1.28 * math.sin(radians) * math.sin(tilt),
                ))
            self._draw_polyline(painter, orbit, width, height, color, 1.0)
        for index in range(14):
            phase = self._detail_phase * (0.35 + index * 0.018) + index * 1.7
            point = (
                1.02 * math.cos(phase) * math.cos(index * 0.45),
                1.02 * math.sin(index * 0.45),
                1.02 * math.sin(phase) * math.cos(index * 0.45),
            )
            position = self._project(point, width, height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(qcol("#FFF3D6", 170)))
            painter.drawEllipse(position, 2.2, 2.2)

    @staticmethod
    def _ease_out(progress: float) -> float:
        progress = max(0.0, min(1.0, progress))
        return 1.0 - (1.0 - progress) ** 3

    def _draw_box(self, painter: QPainter, center: tuple[float, float, float],
                  size: tuple[float, float, float], width: float, height: float,
                  color: QColor, pen_width: float = 1.1):
        cx, cy, cz = center
        hx, hy, hz = (value * 0.5 for value in size)
        points = [
            (cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
            (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
            (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
            (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz),
        ]
        edges = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
                 (0, 4), (1, 5), (2, 6), (3, 7))
        painter.setPen(QPen(color, pen_width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for start, end in edges:
            painter.drawLine(
                self._project(points[start], width, height),
                self._project(points[end], width, height),
            )

    def _draw_armour_prism(self, painter: QPainter, outline, offset,
                           depth: float, width: float, height: float,
                           color: QColor, pen_width: float = 1.3):
        """Render one faceted armour plate from a front outline and shallow depth."""

        ox, oy, oz = offset
        front = [(x + ox, y + oy, oz - depth * 0.5) for x, y in outline]
        back = [(x + ox, y + oy, oz + depth * 0.5) for x, y in outline]
        front.append(front[0])
        back.append(back[0])
        self._draw_polyline(painter, front, width, height, color, pen_width)
        self._draw_polyline(painter, back, width, height, qcol(color.name(), 105), 0.75)
        painter.setPen(QPen(qcol(color.name(), 155), 0.75))
        for index in range(0, len(outline), max(1, len(outline) // 4)):
            painter.drawLine(
                self._project(front[index], width, height),
                self._project(back[index], width, height),
            )

    def _detail_label(self, painter: QPainter, text: str, point: tuple[float, float, float],
                      width: float, height: float, color: QColor):
        if not self._detail_mode:
            return
        pos = self._project(point, width, height)
        painter.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        painter.setPen(QPen(color, 205))
        painter.drawText(QRectF(pos.x() + 7, pos.y() - 16, 130, 16),
                         Qt.AlignmentFlag.AlignLeft, text)

    def _suit_colours(self) -> tuple[QColor, QColor, QColor]:
        profile = self._suit_metadata.profile if self._suit_metadata else "classic"
        primary_hex = self._suit_metadata.color if self._suit_metadata else "#D62839"
        accents = {
            "prototype": "#D5D8DC", "classic": "#F6BD60", "portable": "#FFD166",
            "stealth": "#86BBD8", "specialist": "#CDB4DB", "heavy": "#F4A261",
            "orbital": "#70D6FF", "modular": "#FFE066", "nanotech": "#FF8FA3",
            "final": "#FFD166",
        }
        return qcol(primary_hex, 245), qcol(accents.get(profile, "#FFD166"), 245), qcol("#FFF3D6", 225)

    def _draw_ironman_suit(self, painter: QPainter, width: float, height: float):
        primary, accent, core_color = self._suit_colours()
        profile = self._suit_metadata.profile if self._suit_metadata else "classic"
        scale = {
            "prototype": 1.10, "heavy": 1.32, "orbital": 0.94,
            "stealth": 0.92, "nanotech": 0.96, "final": 0.98,
        }.get(profile, 1.0)
        exploded = self._ease_out(self._exploded_progress) if self._detail_mode else 0.0

        helmet = ((-0.22, 1.62), (0.22, 1.62), (0.29, 1.43),
                  (0.20, 1.12), (0.0, 1.03), (-0.20, 1.12), (-0.29, 1.43))
        chest = ((-0.50, 0.98), (0.50, 0.98), (0.43, 0.33),
                 (0.25, 0.02), (-0.25, 0.02), (-0.43, 0.33))
        pelvis = ((-0.28, -0.04), (0.28, -0.04), (0.35, -0.27),
                  (0.20, -0.43), (-0.20, -0.43), (-0.35, -0.27))
        left_arm = ((-0.56, 0.89), (-0.82, 0.78), (-0.92, 0.10),
                    (-0.76, -0.18), (-0.62, -0.02), (-0.57, 0.45))
        right_arm = tuple((-x, y) for x, y in reversed(left_arm))
        left_leg = ((-0.34, -0.42), (-0.05, -0.42), (-0.11, -1.42),
                    (-0.36, -1.61), (-0.49, -1.35), (-0.48, -0.72))
        right_leg = tuple((-x, y) for x, y in reversed(left_leg))

        pieces = (
            ("HELMET", helmet, (0.0, 0.68, 0.12), accent, 0.34),
            ("CHEST PLATE", chest, (0.0, 0.12, 0.34), primary, 0.42),
            ("WAIST ARMOR", pelvis, (0.0, -0.28, 0.22), accent, 0.34),
            ("LEFT GAUNTLET", left_arm, (-0.54, 0.10, 0.12), primary, 0.28),
            ("RIGHT GAUNTLET", right_arm, (0.54, 0.10, 0.12), primary, 0.28),
            ("LEFT LEG", left_leg, (-0.30, -0.54, 0.10), primary, 0.34),
            ("RIGHT LEG", right_leg, (0.30, -0.54, 0.10), primary, 0.34),
        )
        for label, outline, direction, color, depth in pieces:
            scaled_outline = tuple((x * scale, y * scale) for x, y in outline)
            offset = tuple(direction[index] * exploded for index in range(3))
            self._draw_armour_prism(
                painter, scaled_outline, offset, depth * scale,
                width, height, color, 1.45,
            )
            anchor = (offset[0], max(y for _, y in scaled_outline) + offset[1], offset[2])
            self._detail_label(painter, label, anchor, width, height, color)

        # Faceplate eye slits and shoulder seams make the silhouette readable at a glance.
        eye_y = 1.38 * scale + 0.68 * exploded
        for x1, x2 in ((-0.18, -0.04), (0.04, 0.18)):
            self._draw_polyline(
                painter,
                ((x1 * scale, eye_y, -0.19), (x2 * scale, eye_y + 0.025, -0.19)),
                width, height, qcol("#CFFBFF", 245), 2.0,
            )

        core_point = (0.0, 0.51 + 0.10 * exploded, 0.29 + 0.62 * exploded)
        core = self._project(core_point, width, height)
        pulse = 8.0 + math.sin(self._detail_phase * 3.0) * 2.0
        painter.setPen(QPen(accent, 1.2))
        painter.setBrush(QBrush(qcol("#FFF9E6", 230)))
        painter.drawEllipse(core, pulse * self._zoom, pulse * self._zoom)
        self._detail_label(painter, "ARC CORE", core_point, width, height, core_color)

    def _draw_ironman_helmet(self, painter: QPainter, width: float, height: float):
        primary, accent, _ = self._suit_colours()
        outline = ((-0.64, 0.76), (0.64, 0.76), (0.82, 0.28), (0.62, -0.66),
                   (0.25, -0.94), (0.0, -1.04), (-0.25, -0.94), (-0.62, -0.66),
                   (-0.82, 0.28))
        self._draw_armour_prism(painter, outline, (0.0, 0.0, 0.0), 0.72,
                                width, height, primary, 1.7)
        faceplate = ((-0.48, 0.48), (0.48, 0.48), (0.56, 0.08), (0.34, -0.55),
                     (0.0, -0.78), (-0.34, -0.55), (-0.56, 0.08))
        self._draw_armour_prism(painter, faceplate, (0.0, 0.0, -0.39), 0.08,
                                width, height, accent, 1.35)
        for x1, x2 in ((-0.38, -0.07), (0.07, 0.38)):
            self._draw_polyline(painter, ((x1, 0.18, -0.46), (x2, 0.22, -0.46)),
                                width, height, qcol("#CFFBFF", 250), 2.4)

    def _draw_ironman_repulsor(self, painter: QPainter, width: float, height: float):
        primary, accent, core = self._suit_colours()
        for radius, color, line_width in (
            (1.10, primary, 1.6), (0.84, accent, 1.3), (0.58, core, 1.1),
        ):
            self._draw_reactor_ring(painter, (0.0, 0.0, 0.0), radius,
                                    width, height, color, line_width)
        for angle in range(0, 360, 30):
            radians = math.radians(angle + self._detail_phase * 18)
            self._draw_polyline(
                painter,
                ((0.34 * math.cos(radians), 0.34 * math.sin(radians), -0.02),
                 (0.98 * math.cos(radians), 0.98 * math.sin(radians), 0.02)),
                width, height, accent, 1.0,
            )
        center = self._project((0.0, 0.0, -0.05), width, height)
        pulse = 18 + 4 * math.sin(self._detail_phase * 3.0)
        painter.setPen(QPen(qcol("#E9FDFF", 245), 1.5))
        painter.setBrush(QBrush(qcol("#CFFBFF", 210)))
        painter.drawEllipse(center, pulse * self._zoom, pulse * self._zoom)

    def _draw_reactor_ring(self, painter: QPainter, center: tuple[float, float, float],
                           radius: float, width: float, height: float, color: QColor,
                           pen_width: float = 1.2):
        ring = [
            (center[0] + radius * math.cos(math.radians(angle)),
             center[1] + radius * math.sin(math.radians(angle)), center[2])
            for angle in range(0, 361, 7)
        ]
        self._draw_polyline(painter, ring, width, height, color, pen_width)

    def _draw_arc_reactor(self, painter: QPainter, width: float, height: float):
        primary, accent, core_color = self._suit_colours()
        exploded = self._ease_out(self._exploded_progress) if self._detail_mode else 0.0
        components = (
            ("OUTER CASING", (0.0, 0.0, -0.18), (0.0, 0.0, -0.92), 1.12, primary),
            ("CONTAINMENT RING", (0.0, 0.0, -0.06), (-0.72, 0.42, -0.30), 0.92, accent),
            ("COPPER COIL", (0.0, 0.0, 0.04), (0.75, 0.30, -0.04), 0.73, qcol("#E07A2F", 245)),
            ("ENERGY LATTICE", (0.0, 0.0, 0.16), (-0.56, -0.54, 0.32), 0.53, qcol("#6DD3FF", 245)),
            ("EMITTER LENS", (0.0, 0.0, 0.28), (0.42, -0.52, 0.76), 0.31, core_color),
        )
        for label, base, direction, radius, color in components:
            center = tuple(base[index] + direction[index] * exploded for index in range(3))
            self._draw_reactor_ring(painter, center, radius, width, height, color, 1.45)
            self._detail_label(painter, label, center, width, height, color)

        coil_center = (0.75 * exploded, 0.30 * exploded, 0.04 - 0.04 * exploded)
        coil = []
        for angle in range(0, 721, 8):
            radians = math.radians(angle)
            radius = 0.63 + 0.05 * math.sin(radians * 5)
            coil.append((
                coil_center[0] + radius * math.cos(radians),
                coil_center[1] + radius * math.sin(radians),
                coil_center[2] + 0.03 * math.sin(radians * 2),
            ))
        self._draw_polyline(painter, coil, width, height, qcol("#FFB35C", 230), 0.9)

        bolt_origin = (0.0, 0.0, -0.18 - 0.92 * exploded)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(qcol("#FFF3D6", 220)))
        for angle in range(0, 360, 30):
            radians = math.radians(angle)
            point = (
                bolt_origin[0] + 1.28 * math.cos(radians),
                bolt_origin[1] + 1.28 * math.sin(radians),
                bolt_origin[2],
            )
            pos = self._project(point, width, height)
            painter.drawEllipse(pos, 2.4 + exploded * 1.8, 2.4 + exploded * 1.8)

        lens_center = (0.42 * exploded, -0.52 * exploded, 0.28 + 0.76 * exploded)
        lens = self._project(lens_center, width, height)
        glow = 13.0 + math.sin(self._detail_phase * 3.0) * 3.0
        painter.setPen(QPen(qcol("#CFFBFF", 250), 1.4))
        painter.setBrush(QBrush(qcol("#E9FDFF", 235)))
        painter.drawEllipse(lens, glow * self._zoom, glow * self._zoom)

    def _draw_ironman_catalog(self, painter: QPainter, width: float, height: float):
        suits = all_suit_metadata()
        self._suit_hit_targets = []
        columns = 13 if width >= 760 else 10
        rows = math.ceil(len(suits) / columns)
        margin_x, margin_y = 22, 54
        card_width = (width - margin_x * 2) / columns
        card_height = min((height - margin_y - 48) / rows, card_width * 1.22)
        painter.setFont(QFont("Courier New", 6, QFont.Weight.Bold))
        for index, suit in enumerate(suits):
            row, col = divmod(index, columns)
            rect = QRectF(
                margin_x + col * card_width + 2,
                margin_y + row * card_height + 2,
                max(12, card_width - 4),
                max(14, card_height - 4),
            )
            color = qcol(suit.color, 215)
            painter.setPen(QPen(color, 0.85))
            painter.setBrush(QBrush(qcol("#120906", 175)))
            painter.drawRoundedRect(rect, 2, 2)
            self._suit_hit_targets.append((suit.mark, QRectF(rect)))
            head = QRectF(rect.center().x() - rect.width() * 0.13, rect.y() + rect.height() * 0.16,
                          rect.width() * 0.26, rect.height() * 0.24)
            torso = QRectF(rect.center().x() - rect.width() * 0.19, rect.y() + rect.height() * 0.43,
                           rect.width() * 0.38, rect.height() * 0.34)
            painter.setBrush(QBrush(qcol(suit.color, 115)))
            painter.drawRoundedRect(head, 1, 1)
            painter.drawRoundedRect(torso, 1, 1)
            painter.setPen(QPen(qcol("#FFF3D6", 190), 1))
            painter.drawText(QRectF(rect.x(), rect.bottom() - 11, rect.width(), 10),
                             Qt.AlignmentFlag.AlignCenter, str(suit.mark))
        painter.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        painter.setPen(QPen(qcol("#FFD18A", 220), 1))
        painter.drawText(QRectF(18, height - 30, width - 36, 18), Qt.AlignmentFlag.AlignCenter,
                         "IRON MAN ARMORY - MARK I TO MARK LXXXV  //  ANZUG ANKLICKEN")

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()

        background = QRadialGradient(QPointF(width * 0.5, height * 0.5), max(width, height) * 0.65)
        background.setColorAt(0.0, qcol("#281103"))
        background.setColorAt(0.55, qcol("#080301"))
        background.setColorAt(1.0, qcol("#000000"))
        painter.fillRect(self.rect(), QBrush(background))

        grid_color = qcol("#a66a26", 38)
        painter.setPen(QPen(grid_color, 0.7))
        grid_step = max(28, int(min(width, height) / 12))
        grid_offset = int((self._tick * 0.18) % grid_step)
        for x in range(-grid_step + grid_offset, width, grid_step):
            painter.drawLine(x, 0, x, height)
        for y in range(-grid_step + grid_offset, height, grid_step):
            painter.drawLine(0, y, width, y)

        model_color = qcol("#ffd18a", 235)
        if self._mesh_asset is not None:
            self._draw_mesh_model(painter, width, height)
        elif self._kind == "world_news":
            self._draw_world_news(painter, width, height)
        elif self._kind == "iron_man_suit":
            self._draw_ironman_suit(painter, width, height)
        elif self._kind == "iron_man_catalog":
            self._draw_ironman_catalog(painter, width, height)
        elif self._kind == "iron_man_helmet":
            self._draw_ironman_helmet(painter, width, height)
        elif self._kind == "iron_man_repulsor":
            self._draw_ironman_repulsor(painter, width, height)
        elif self._kind == "arc_reactor":
            self._draw_arc_reactor(painter, width, height)
        elif self._kind == "planet":
            self._draw_planet(painter, width, height, model_color)
        elif self._kind == "atom":
            self._draw_atom(painter, width, height, model_color)
        elif self._kind == "dna":
            self._draw_dna(painter, width, height, model_color)
        elif self._kind == "solar":
            self._draw_solar(painter, width, height, model_color)
        elif self._kind == "vehicle":
            self._draw_vehicle(painter, width, height, model_color)
        elif self._kind == "house":
            self._draw_generic(painter, width, height, model_color)
        else:
            self._draw_generic(painter, width, height, model_color)

        self._draw_gesture_cursor(painter)
        painter.setPen(QPen(qcol("#fff3d6", 205), 1))
        painter.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        painter.drawText(QRectF(18, 14, width - 36, 22), Qt.AlignmentFlag.AlignLeft,
                         self._subject.upper())
        if self._kind == "world_news":
            state = (
                f"WORLD INTEL // {self._selected_country} SELECTED"
                if self._selected_country else "WORLD INTEL // SELECT COUNTRY"
            )
        elif self._animation_state == "exploding":
            state = f"EXPLODING {int(self._exploded_progress * 100):02d}%"
        elif self._animation_state == "exploded":
            state = "EXPLODED VIEW"
        else:
            state = "FOCUS LOCK" if self._focused else "3-D HOLOGRAM"
        painter.setPen(QPen(qcol("#ffad3d", 180), 1))
        painter.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(18, height - 34, width - 36, 18), Qt.AlignmentFlag.AlignLeft, state)
        painter.drawText(QRectF(18, height - 34, width - 36, 18), Qt.AlignmentFlag.AlignRight,
                         f"ZOOM {self._zoom:.1f}x")

    def _country_at(self, position: QPointF) -> tuple[str, str] | None:
        nearest = None
        nearest_distance = float("inf")
        for code, name, marker, hit_radius in self._country_hit_targets:
            distance = math.hypot(position.x() - marker.x(), position.y() - marker.y())
            if distance <= hit_radius and distance < nearest_distance:
                nearest = (code, name)
                nearest_distance = distance
        return nearest

    def mouseMoveEvent(self, event):
        if self._dragging and self._mesh_asset is not None:
            delta = event.position() - self._last_mouse
            self._yaw += delta.x() * 0.009
            self._pitch = max(-1.15, min(1.15, self._pitch + delta.y() * 0.007))
            self._last_mouse = event.position()
            self.update()
        elif self._kind == "world_news":
            country = self._country_at(event.position())
            hovered = country[0] if country else ""
            if hovered != self._hovered_country:
                self._hovered_country = hovered
                self.setCursor(
                    Qt.CursorShape.PointingHandCursor if country
                    else Qt.CursorShape.ArrowCursor
                )
                self.update()
        elif self._kind == "iron_man_catalog":
            over_card = any(rect.contains(event.position()) for _, rect in self._suit_hit_targets)
            self.setCursor(
                Qt.CursorShape.PointingHandCursor if over_card
                else Qt.CursorShape.ArrowCursor
            )
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered_country = ""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._kind == "world_news":
            country = self._country_at(event.position())
            if country:
                self._selected_country = country[0]
                self.country_selected.emit(*country)
                self.update()
                event.accept()
                return
        if event.button() == Qt.MouseButton.LeftButton and self._kind == "iron_man_catalog":
            for mark, rect in self._suit_hit_targets:
                if rect.contains(event.position()):
                    self.show_model(f"Iron Man Mark {mark}")
                    event.accept()
                    return
        if event.button() == Qt.MouseButton.LeftButton and self._mesh_asset is not None:
            self._dragging = True
            self._last_mouse = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if self._kind == "world_news" or self._mesh_asset is not None:
            direction = 1 if event.angleDelta().y() > 0 else -1
            max_zoom = 2.4 if self._mesh_asset is not None else 1.65
            self._target_zoom = max(0.68, min(max_zoom, self._target_zoom + direction * 0.12))
            event.accept()
            return
        super().wheelEvent(event)

    def gesture_zoom(self, delta: float) -> None:
        """Apply a camera-derived zoom delta without exposing camera frames."""

        if self._kind == "world_news" or self._mesh_asset is not None:
            max_zoom = 2.4 if self._mesh_asset is not None else 1.65
            self._target_zoom = max(0.68, min(max_zoom, self._target_zoom + float(delta)))
            if self._gpu_view is not None and self._gpu_view.isVisible():
                self._gpu_view.zoom_model(float(delta))
            self.update()

    def gesture_pointer(self, action: str, x: float, y: float) -> None:
        """Map local hand landmarks to model mouse movement, click, and drag."""

        position = QPointF(
            max(0.0, min(1.0, float(x))) * self.width(),
            max(0.0, min(1.0, float(y))) * self.height(),
        )
        self._gesture_cursor = position
        self._gesture_cursor_visible = True
        self._gesture_last_tick = self._tick
        if self._gpu_view is not None and self._gpu_view.isVisible():
            self._gpu_view.set_hand_pointer(float(x), float(y), action == "press")

        if action == "press":
            self._gesture_cursor_pressed = True
            if self._kind == "world_news":
                country = self._country_at(position)
                if country:
                    self._selected_country = country[0]
                    self.country_selected.emit(*country)
            elif self._kind == "iron_man_catalog":
                for mark, rect in self._suit_hit_targets:
                    if rect.contains(position):
                        self.show_model(f"Iron Man Mark {mark}")
                        break
            elif self._mesh_asset is not None:
                self._dragging = True
                self._last_mouse = position
        elif action == "release":
            self._gesture_cursor_pressed = False
            self._dragging = False
        elif action == "move":
            if self._dragging and self._mesh_asset is not None:
                delta = position - self._last_mouse
                self._yaw += delta.x() * 0.009
                self._pitch = max(-1.15, min(1.15, self._pitch + delta.y() * 0.007))
                if self._gpu_view is not None and self._gpu_view.isVisible():
                    self._gpu_view.rotate_model(float(delta.x()), float(delta.y()))
                self._last_mouse = position
            elif self._kind == "world_news":
                country = self._country_at(position)
                self._hovered_country = country[0] if country else ""
        self.update()

    def _draw_gesture_cursor(self, painter: QPainter) -> None:
        if not self._gesture_cursor_visible or self._tick - self._gesture_last_tick > 90:
            return
        center = self._gesture_cursor
        radius = 10.0 + 2.0 * math.sin(self._tick * 0.18)
        color = qcol("#FFD18A", 245) if self._gesture_cursor_pressed else qcol("#70D6FF", 225)
        painter.setBrush(QBrush(qcol("#70D6FF", 28)))
        painter.setPen(QPen(color, 1.4))
        painter.drawEllipse(center, radius, radius)
        painter.drawLine(QPointF(center.x() - radius - 6, center.y()), QPointF(center.x() - 4, center.y()))
        painter.drawLine(QPointF(center.x() + 4, center.y()), QPointF(center.x() + radius + 6, center.y()))
        painter.drawLine(QPointF(center.x(), center.y() - radius - 6), QPointF(center.x(), center.y() - 4))
        painter.drawLine(QPointF(center.x(), center.y() + 4), QPointF(center.x(), center.y() + radius + 6))


class ModelStage(QWidget):
    """Fullscreen presentation stage: model large, JARVIS remains in the corner."""

    close_requested = pyqtSignal()
    country_selected = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {C.BG}; border: 1px solid {C.BORDER_B};")
        self._subject = "Hologramm"

        root = QHBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        model_col = QVBoxLayout()
        model_col.setSpacing(8)
        self.viewer = ModelViewer3D(self)
        self.viewer.country_selected.connect(self._country_clicked)
        model_col.addWidget(self.viewer, stretch=1)
        self._status = QLabel("ANALYSEBEREIT - SAGEN SIE 'FOKUSSIERE ...'", self)
        self._status.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._status.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        model_col.addWidget(self._status)
        root.addLayout(model_col, stretch=1)

        corner = QFrame(self)
        corner.setFixedWidth(190)
        corner.setStyleSheet(f"background: {C.DARK}; border: 1px solid {C.BORDER};")
        corner_col = QVBoxLayout(corner)
        corner_col.setContentsMargins(10, 12, 10, 12)
        corner_col.setSpacing(8)

        label = QLabel("JARVIS", corner)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        corner_col.addWidget(label)

        self._corner_orb = AetherOrbWidget(corner)
        self._corner_orb.setMinimumSize(150, 150)
        self._corner_orb.setMaximumSize(170, 170)
        corner_col.addWidget(self._corner_orb, alignment=Qt.AlignmentFlag.AlignCenter)

        self._topic = QLabel(corner)
        self._topic.setWordWrap(True)
        self._topic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._topic.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._topic.setStyleSheet(f"color: {C.TEXT}; background: transparent; border: none;")
        corner_col.addWidget(self._topic)
        corner_col.addStretch()

        close_btn = QPushButton("ZURUECK", corner)
        close_btn.setFixedHeight(30)
        close_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; }}
            QPushButton:hover {{ color: {C.PRI}; border: 1px solid {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.close_requested.emit)
        corner_col.addWidget(close_btn)
        root.addWidget(corner)

        self.show_subject("Hologramm")

    def show_subject(self, subject: str):
        self._subject = ModelViewer3D._clean_subject(subject)
        self.viewer.show_model(self._subject)
        self._topic.setText(f"ANZEIGE\n{self._subject.upper()}")
        self._status.setText("ANALYSEBEREIT - SAGEN SIE 'FOKUSSIERE ...'")

    def focus_subject(self, subject: str = ""):
        self.viewer.focus_model(subject)
        self._subject = self.viewer.subject
        self._topic.setText(f"FOKUS\n{self._subject.upper()}")
        self._status.setText("FOKUS AKTIV - JARVIS BEREITET DIE ERKLAERUNG VOR")

    def detail_subject(self, subject: str = ""):
        self.viewer.show_detail(subject)
        self._subject = self.viewer.subject
        self._topic.setText(f"DETAIL\n{self._subject.upper()}")
        self._status.setText("EXPLOSIONSANSICHT AKTIV - BAUTEILE WERDEN ZERLEGT")

    def _country_clicked(self, code: str, name: str):
        self._topic.setText(f"WORLD INTEL\n{name.upper()} [{code}]")
        self._status.setText(f"LADE AKTUELLE MELDUNGEN FUER {name.upper()} ...")
        self.country_selected.emit(code, name)

    def set_news_status(self, status: str):
        self._status.setText(status.upper())

    def set_gesture_status(self, active: bool):
        if active:
            self._status.setText("GESTEN AKTIV - ZEIGEN | PINCH-KLICK/DRAG | V-GESTE-ZOOM")
        elif self.isVisible():
            self._status.setText("ANALYSEBEREIT - SAGEN SIE 'FOKUSSIERE ...'")

    def set_speaking(self, value: bool):
        self._corner_orb.set_speaking(value)

    def set_muted(self, value: bool):
        self._corner_orb.set_muted(value)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 9))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C.PANEL};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 6px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: {C.BG};
                width: 8px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B};
                border-radius: 4px;
                min-height: 20px;
            }}
        """)
        self._queue: list[str] = []
        self._typing  = False
        self._text    = ""
        self._pos     = 0
        self._tag     = "sys"
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        self._text   = self._queue.pop(0)
        self._pos    = 0
        tl = self._text.lower()
        if   tl.startswith("you:"):    self._tag = "you"
        elif tl.startswith("jarvis:"): self._tag = "ai"
        elif tl.startswith("file:"):   self._tag = "file"
        elif "err" in tl:              self._tag = "err"
        else:                          self._tag = "sys"
        self._tmr.start(6)

    def _step(self):
        if self._pos < len(self._text):
            ch  = self._text[self._pos]
            cur = self.textCursor()
            fmt = cur.charFormat()
            col = {
                "you":  qcol(C.WHITE),
                "ai":   qcol(C.PRI),
                "err":  qcol(C.RED),
                "file": qcol(C.GREEN),
                "sys":  qcol(C.ACC2),
            }.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(ch, fmt)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self._pos += 1
        else:
            self._tmr.stop()
            cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)


_FILE_ICONS = {
    "image":   ("🖼", "#00d4ff"), "video":   ("🎬", "#ff6b00"),
    "audio":   ("🎵", "#cc44ff"), "pdf":     ("📄", "#ff4444"),
    "word":    ("📝", "#4488ff"), "excel":   ("📊", "#44bb44"),
    "code":    ("💻", "#ffcc00"), "archive": ("📦", "#ff8844"),
    "pptx":    ("📊", "#ff6622"), "text":    ("📃", "#aaaaaa"),
    "data":    ("🔧", "#88ddff"), "unknown": ("📎", "#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file: str | None = None
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for JARVIS", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol("#001a24" if z._drag_over else ("#001218" if z._hovering else C.PANEL))
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   border_col = qcol(C.GREEN, 200)
        elif z._drag_over:    border_col = qcol(C.PRI, 230)
        elif z._hovering:     border_col = qcol(C.BORDER_B, 200)
        else:                 border_col = qcol(C.BORDER, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "Drop file here  or  Click to Browse")
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol("#1a4a5a"), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "Images · Video · Audio · PDF · Docs · Code · Data")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Courier New", 20))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⬇")
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Release to load")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if _OS == "Windows" else QFont("Arial", 22))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  ·  {size_str}")

        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol("#1e5c6a"), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✕")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
        else:
            z.mousePressEvent(e)


class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", font_size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED", 13, True))
        layout.addWidget(_lbl("Configure J.A.R.V.I.S. before first boot.", 9, color=C.PRI_DIM))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY", 8, color=C.TEXT_DIM,
                              align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Courier New", 10))
        self._key_input.setFixedHeight(32)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        layout.addWidget(self._key_input)
        layout.addSpacing(12)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color=C.TEXT_DIM,
                              align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=C.ACC2,
                              align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(12)

        init_btn = QPushButton("▸  INITIALISE SYSTEMS")
        init_btn.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO}; border: 1px solid {C.PRI};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows":(C.PRI,"#001a22"),"mac":(C.ACC2,"#1a1400"),"linux":(C.GREEN,"#001a0d")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: none; border-radius: 3px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #000d12; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 3px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {C.RED}; }}"
            )
            return
        self.done.emit(key, self._sel_os)


class SettingsOverlay(QWidget):
    voice_changed = pyqtSignal(str)
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._overlay_size = (500, 320)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SettingsOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignLeft):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setWordWrap(True)
            w.setFont(QFont("Courier New", font_size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("EINSTELLUNGEN", 13, True, align=Qt.AlignmentFlag.AlignCenter))
        layout.addWidget(_lbl("LIVE VOICE", 8, True, C.TEXT_DIM))

        self._voice_combo = QComboBox()
        self._voice_combo.setFont(QFont("Courier New", 9))
        self._voice_combo.setFixedHeight(34)
        self._voice_combo.setStyleSheet(f"""
            QComboBox {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px;
            }}
            QComboBox:hover {{ border: 1px solid {C.BORDER_B}; }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox QAbstractItemView {{
                background: #000d12; color: {C.TEXT};
                selection-background-color: {C.PRI_GHO};
                border: 1px solid {C.BORDER_B};
            }}
        """)
        current_voice = get_live_voice_name()
        current_index = 0
        for index, (voice, tone) in enumerate(LIVE_VOICE_OPTIONS):
            self._voice_combo.addItem(f"{voice} - {tone}", voice)
            if voice == current_voice:
                current_index = index
        self._voice_combo.setCurrentIndex(current_index)
        layout.addWidget(self._voice_combo)

        self._hint = _lbl(
            "Die Stimme wird in config/api_keys.json gespeichert und beim naechsten Live-Reconnect genutzt.",
            8,
            False,
            C.TEXT_MED,
        )
        layout.addWidget(self._hint)
        layout.addStretch()

        row = QHBoxLayout()
        row.setSpacing(8)

        cancel_btn = QPushButton("SCHLIESSEN")
        cancel_btn.setFixedHeight(32)
        cancel_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.PRI}; border: 1px solid {C.BORDER_B}; }}
        """)
        cancel_btn.clicked.connect(self.close_requested.emit)
        row.addWidget(cancel_btn)

        save_btn = QPushButton("VOICE SPEICHERN")
        save_btn.setFixedHeight(32)
        save_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        save_btn.clicked.connect(self._save)
        row.addWidget(save_btn)
        layout.addLayout(row)

    def _save(self):
        voice = self._voice_combo.currentData() or DEFAULT_LIVE_VOICE
        try:
            set_live_voice_name(voice)
        except Exception:
            self._hint.setText("Voice konnte nicht gespeichert werden.")
            self._hint.setStyleSheet(f"color: {C.RED}; background: transparent;")
            return
        self._hint.setText(f"Gespeichert: {voice}. Neustart/Reconnect nutzt diese Stimme.")
        self._hint.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        self.voice_changed.emit(voice)


class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)
    _uimode_sig = pyqtSignal(str)
    _show_sig = pyqtSignal()
    _model_sig = pyqtSignal(str, str)
    _news_status_sig = pyqtSignal(str)
    _gesture_zoom_sig = pyqtSignal(float)
    _gesture_pointer_sig = pyqtSignal(str, float, float)
    _gesture_status_sig = pyqtSignal(str)

    def __init__(self, face_path: str, use_3d: bool = True):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S — MARK XXXIX")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command  = None
        self.on_voice_changed = None
        self.on_country_selected = None
        self._muted           = False
        self._current_file: str | None = None
        self.use_3d = use_3d and _HAS_OPENGL

        central = QWidget()
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._header = self._build_header()
        root.addWidget(self._header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._left_panel = self._build_left_panel()
        body.addWidget(self._left_panel, stretch=0)

        if self.use_3d:
            # 3D Hologramm als zentrales Widget (Enhanced wenn verfügbar)
            if _HAS_ENHANCED_HOLOGRAM:
                print("[MainWindow] ✨ Using ENHANCED Hologram 3D")
                self.hologram = AetherOrbWidget()
            else:
                print("[MainWindow] Using Aether Orb Interface")
                self.hologram = AetherOrbWidget()
            
            self.hologram.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            body.addWidget(self.hologram, stretch=5)

            # 2D HUD rechts daneben
            self.hud = HudCanvas(face_path)
            self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            body.addWidget(self.hud, stretch=2)
        else:
            # Fallback: nur 2D HUD
            self.hud = HudCanvas(face_path)
            self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            body.addWidget(self.hud, stretch=5)

        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel, stretch=0)

        root.addLayout(body, stretch=1)
        self._footer = self._build_footer()
        root.addWidget(self._footer)

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        self._log_sig.connect(self._log.append_log)
        self._state_sig.connect(self._apply_state)
        self._uimode_sig.connect(self._apply_ui_mode)
        self._show_sig.connect(self._show_self)
        self._model_sig.connect(self._control_model)
        self._news_status_sig.connect(self._set_news_status)
        self._gesture_zoom_sig.connect(self._apply_gesture_zoom)
        self._gesture_pointer_sig.connect(self._apply_gesture_pointer)
        self._gesture_status_sig.connect(self._handle_gesture_status)

        # Start im Minimal-Modus: NUR JARVIS — kein Datum, keine Uhr, keine Panels
        self._ui_mode = "dashboard"
        self._apply_ui_mode("minimal")

        self._overlay: QWidget | None = None
        self._model_stage: ModelStage | None = None
        self._gesture_camera = GestureCameraController()
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)
        sc_mode = QShortcut(QKeySequence("F2"), self)
        sc_mode.activated.connect(lambda: self._apply_ui_mode("toggle"))

    def _apply_ui_mode(self, mode: str):
        """
        'minimal'   → NUR JARVIS: keine Uhr, kein Datum, keine Panels — nur das Gesicht.
        'dashboard' → 3D-Modell + alle Informationen (Monitor, Log, Upload, Eingabe).
        'toggle'    → umschalten.
        """
        if mode == "toggle":
            mode = "dashboard" if self._ui_mode == "minimal" else "minimal"
        if mode not in ("minimal", "dashboard") or mode == self._ui_mode:
            return
        self._ui_mode = mode
        minimal = (mode == "minimal")

        for w in (self._header, self._footer, self._left_panel, self._right_panel):
            w.setVisible(not minimal)
        if hasattr(self, "hologram"):
            self.hologram.setVisible(True)
        self.hud.setVisible(not minimal)

        if minimal:
            self.centralWidget().setStyleSheet(f"background: {C.BG};")
        try:
            self._log.append_log(f"SYS: UI-Modus → {mode.upper()}")
        except Exception:
            pass

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _show_self(self):
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def _center_overlay(self, overlay: QWidget):
        ow, oh = getattr(overlay, "_overlay_size", (460, 390))
        cw = self.centralWidget()
        overlay.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._overlay and self._overlay.isVisible():
            self._center_overlay(self._overlay)
        if self._model_stage and self._model_stage.isVisible():
            self._model_stage.setGeometry(self.centralWidget().rect())

    def _hide_model_stage(self):
        self._gesture_camera.stop()
        if self._model_stage:
            self._model_stage.hide()
            self._log.append_log("SYS: 3-D presentation closed.")

    def _apply_gesture_zoom(self, delta: float):
        if self._model_stage and self._model_stage.isVisible():
            self._model_stage.viewer.gesture_zoom(delta)

    def _apply_gesture_pointer(self, action: str, x: float, y: float):
        if self._model_stage and self._model_stage.isVisible():
            self._model_stage.viewer.gesture_pointer(action, x, y)

    def _handle_gesture_status(self, status: str):
        if self._model_stage:
            self._model_stage.set_gesture_status(status == "active")
        messages = {
            "active": "SYS: Gestenkamera aktiv (lokal, ohne Bildanzeige).",
            "camera_unavailable": "SYS: Gestenkamera konnte die konfigurierte Kamera nicht oeffnen.",
            "camera_lost": "SYS: Gestenkamera hat die Kameraverbindung verloren.",
            "model_missing": "SYS: MediaPipe-Handmodell fehlt.",
        }
        if status in messages:
            self._log.append_log(messages[status])
        elif status.startswith("error:"):
            self._log.append_log(f"SYS: Gestenkamera-Fehler: {status.split(':', 1)[1]}")

    def _country_selected(self, code: str, name: str):
        self._log.append_log(f"SYS: World Intel selected: {name} [{code}]")
        if self.on_country_selected:
            threading.Thread(
                target=self.on_country_selected,
                args=(code,),
                daemon=True,
            ).start()

    def _set_news_status(self, status: str):
        if self._model_stage:
            self._model_stage.set_news_status(status)

    def _control_model(self, action: str, subject: str = ""):
        """Run on the Qt thread through _model_sig; tools may call it from workers."""
        action = (action or "show").strip().lower()
        if action in ("hide", "close", "off"):
            self._hide_model_stage()
            return

        if action not in ("show", "focus", "detail"):
            self._log.append_log(f"SYS: Unknown model action: {action}")
            return

        if self._model_stage is None:
            self._model_stage = ModelStage(self.centralWidget())
            self._model_stage.close_requested.connect(self._hide_model_stage)
            self._model_stage.country_selected.connect(self._country_selected)

        stage = self._model_stage
        stage.setGeometry(self.centralWidget().rect())
        stage.set_muted(self._muted)
        stage.set_speaking(self.hud.speaking)

        if action == "show":
            stage.show_subject(subject)
            log_action = "3-D model displayed"
        elif action == "focus":
            if not stage.isVisible():
                stage.show_subject(subject or "Hologramm")
            stage.focus_subject(subject)
            log_action = "3-D model focused"
        else:
            stage.detail_subject(subject)
            log_action = "3-D detail animation started"

        stage.show()
        stage.raise_()
        stage.setFocus()
        self._gesture_camera.start(
            self._gesture_zoom_sig.emit,
            self._gesture_status_sig.emit,
            self._gesture_pointer_sig.emit,
        )
        self._log.append_log(f"SYS: {log_action}: {stage.viewer.subject}")

    def closeEvent(self, event):
        self._gesture_camera.stop()
        super().closeEvent(event)

    def _update_metrics(self):
        snap = _metrics.snapshot()

        cpu = snap["cpu"]
        self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")

        mem = snap["mem"]
        self._bar_mem.set_value(mem, f"{mem:.0f}%")

        net = snap["net"]
        if net < 1.0:
            net_str = f"{net*1024:.0f}KB/s"
        else:
            net_str = f"{net:.1f}MB/s"
        net_pct = min(100, net * 10)
        self._bar_net.set_value(net_pct, net_str)

        gpu = snap["gpu"]
        if gpu >= 0:
            self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
        else:
            self._bar_gpu.set_value(0, "N/A")

        tmp = snap["tmp"]
        if tmp >= 0:
            tmp_pct = min(100, (tmp / 100) * 100)
            self._bar_tmp.set_value(tmp_pct, f"{tmp:.0f}°C")
        else:
            self._bar_tmp.set_value(0, "N/A")

        try:
            boot_t  = psutil.boot_time()
            elapsed = time.time() - boot_t
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            self._uptime_lbl.setText(f"UP  {h:02d}:{m:02d}")
        except Exception:
            self._uptime_lbl.setText("UP  --:--")

        try:
            proc_count = len(psutil.pids())
            self._proc_lbl.setText(f"PROC  {proc_count}")
        except Exception:
            self._proc_lbl.setText("PROC  --")

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(54)
        w.setStyleSheet(f"background: {C.DARK}; border-bottom: 1px solid {C.BORDER_B};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 0, 16, 0)

        def _badge(txt, color=C.TEXT_MED):
            l = QLabel(txt)
            l.setFont(QFont("Courier New", 8))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_badge("MARK XXXIX", C.PRI_DIM))
        lay.addStretch()

        mid = QVBoxLayout(); mid.setSpacing(1)
        title = QLabel("J.A.R.V.I.S")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Courier New", 17, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        mid.addWidget(title)
        sub = QLabel("Just A Rather Very Intelligent System")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont("Courier New", 7))
        sub.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        mid.addWidget(sub)
        lay.addLayout(mid)
        lay.addStretch()

        right_col = QVBoxLayout(); right_col.setSpacing(2)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Courier New", 7))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        lay.addLayout(right_col)
        return w

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_LEFT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-right: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(6)

        hdr = QLabel("◈ SYS MONITOR")
        hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; "
                          f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;")
        lay.addWidget(hdr)
        lay.addSpacing(2)

        self._bar_cpu = MetricBar("CPU", C.PRI)
        self._bar_mem = MetricBar("MEM", C.ACC2)
        self._bar_net = MetricBar("NET", C.GREEN)
        self._bar_gpu = MetricBar("GPU", C.ACC)
        self._bar_tmp = MetricBar("TMP", "#ff6688")

        for bar in [self._bar_cpu, self._bar_mem, self._bar_net,
                    self._bar_gpu, self._bar_tmp]:
            lay.addWidget(bar)

        lay.addSpacing(4)

        info_panel = QWidget()
        info_panel.setStyleSheet(
            f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;"
        )
        ip_lay = QVBoxLayout(info_panel)
        ip_lay.setContentsMargins(6, 5, 6, 5)
        ip_lay.setSpacing(3)

        self._uptime_lbl = QLabel("UP  --:--")
        self._uptime_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._uptime_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        ip_lay.addWidget(self._uptime_lbl)

        self._proc_lbl = QLabel("PROC  --")
        self._proc_lbl.setFont(QFont("Courier New", 8))
        self._proc_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        ip_lay.addWidget(self._proc_lbl)

        os_name = {"Windows": "WIN", "Darwin": "macOS", "Linux": "LINUX"}.get(_OS, _OS.upper())
        os_lbl = QLabel(f"OS  {os_name}")
        os_lbl.setFont(QFont("Courier New", 8))
        os_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
        ip_lay.addWidget(os_lbl)

        lay.addWidget(info_panel)
        lay.addStretch()

        for txt, col in [
            ("PLAYWRIGHT\nREADY",        C.GREEN),
            ("AMAZON CART\nARMED",       C.PRI),
            ("TRADINGVIEW\n20 MIN IDLE", C.ACC2),
            ("LIVE TRADE\nLOCKED",       C.TEXT_DIM),
        ]:
            lbl = QLabel(txt)
            lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {col}; background: {C.PANEL2};"
                f"border: 1px solid {C.BORDER_A}; border-radius: 3px; padding: 4px;"
            )
            lay.addWidget(lbl)

        return w

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-left: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        def _sec(txt):
            l = QLabel(f"▸ {txt}")
            l.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            return l

        lay.addWidget(_sec("ACTIVITY LOG"))
        self._log = LogWidget()
        lay.addWidget(self._log, stretch=1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        lay.addWidget(_sec("FILE UPLOAD"))
        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        self._file_hint = QLabel("No file loaded — drop or click above to upload")
        self._file_hint.setFont(QFont("Courier New", 7))
        self._file_hint.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._file_hint.setWordWrap(True)
        lay.addWidget(self._file_hint)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_sec("COMMAND INPUT"))
        lay.addLayout(self._build_input_row())

        self._mute_btn = QPushButton("🎙  MICROPHONE ACTIVE")
        self._mute_btn.setFixedHeight(30)
        self._mute_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        lay.addWidget(self._mute_btn)

        self._settings_btn = QPushButton()
        self._settings_btn.setFixedHeight(28)
        self._settings_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.clicked.connect(self._show_settings)
        self._style_settings_btn()
        lay.addWidget(self._settings_btn)

        fs_btn = QPushButton("⛶  FULLSCREEN  [F11]")
        fs_btn.setFixedHeight(26)
        fs_btn.setFont(QFont("Courier New", 7))
        fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fs_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{
                color: {C.PRI}; border: 1px solid {C.BORDER_B};
            }}
        """)
        fs_btn.clicked.connect(self._toggle_fullscreen)
        lay.addWidget(fs_btn)

        return w

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(5)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command or question…")
        self._input.setFont(QFont("Courier New", 9))
        self._input.setFixedHeight(30)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d14; color: {C.WHITE};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 3px 7px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input)

        send = QPushButton("▸")
        send.setFixedSize(30, 30)
        send.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        send.clicked.connect(self._send)
        row.addWidget(send)
        return row

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(22)
        w.setStyleSheet(f"background: {C.DARK}; border-top: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w); lay.setContentsMargins(14, 0, 14, 0)

        def _fl(txt, color=C.TEXT_MED):
            l = QLabel(txt); l.setFont(QFont("Courier New", 7))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_fl("[F2] Ansicht  ·  SETTINGS: Voice  ·  [F4] Mute  ·  [F11] Fullscreen"))
        lay.addStretch()
        lay.addWidget(_fl("FatihMakes Industries  ·  MARK XXXIX  ·  CLASSIFIED"))
        lay.addStretch()
        lay.addWidget(_fl("© FATIHMAKES", C.PRI_DIM))
        return w

    def _on_file_selected(self, path: str):
        self._current_file = path
        p    = Path(path)
        cat  = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        self._file_hint.setText(f"{icon}  {p.name}  ·  {size}  ·  Tell JARVIS what to do with it")
        self._log.append_log(f"FILE: {p.name} ({size}) loaded")
        if self.on_text_command:
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.')} | size={size} | "
                f"Briefly tell the user you can see the file '{p.name}' "
                f"({size}) has been uploaded and ask what they'd like to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def _toggle_mute(self):
        self._muted = not self._muted
        self.hud.muted = self._muted
        if hasattr(self, 'hologram'):
            self.hologram.set_muted(self._muted)
        if self._model_stage:
            self._model_stage.set_muted(self._muted)
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText("🔇  MICROPHONE MUTED")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.MUTED_C}; color: #000;
                    border: 1px solid {C.MUTED_C}; border-radius: 3px;
                }}
            """)
        else:
            self._mute_btn.setText("🎙  MICROPHONE ACTIVE")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.GREEN};
                    border: 1px solid {C.GREEN_D}; border-radius: 3px;
                }}
                QPushButton:hover {{
                    background: #001f10;
                }}
            """)

    def _style_settings_btn(self):
        voice = get_live_voice_name()
        self._settings_btn.setText(f"SETTINGS  VOICE: {voice.upper()}")
        self._settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{
                color: {C.PRI}; border: 1px solid {C.BORDER_B};
            }}
        """)

    def _close_overlay(self):
        if self._overlay:
            self._overlay.hide()
            self._overlay = None

    def _show_settings(self):
        self._close_overlay()
        ov = SettingsOverlay(self.centralWidget())
        self._center_overlay(ov)
        ov.close_requested.connect(self._close_overlay)
        ov.voice_changed.connect(self._on_voice_changed)
        ov.show()
        self._overlay = ov

    def _on_voice_changed(self, voice: str):
        self._style_settings_btn()
        if self.on_voice_changed:
            threading.Thread(target=self.on_voice_changed, args=(voice,), daemon=True).start()
        else:
            self._log.append_log(f"SYS: Voice set to {voice}. Reconnect/restart applies it.")

    def _send(self):
        txt = self._input.text().strip()
        if not txt: return
        self._input.clear()
        self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _apply_state(self, state: str):
        self.hud.state    = state
        self.hud.speaking = (state == "SPEAKING")
        if hasattr(self, 'hologram'):
            self.hologram.set_speaking(state == "SPEAKING")
        if self._model_stage:
            self._model_stage.set_speaking(state == "SPEAKING")

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception:
            return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        self._center_overlay(ov)
        ov.done.connect(self._on_setup_done)
        ov.show()
        self._overlay = ov

    def _on_setup_done(self, key: str, os_name: str):
        save_api_settings({
            "gemini_api_key": key,
            "os_system": os_name,
            "live_voice_name": get_live_voice_name(),
        })
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        self._log.append_log(f"SYS: Initialised. OS={os_name.upper()}. JARVIS online.")


class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class JarvisUI:
    def __init__(self, face_path: str, size=None, use_3d: bool = True):
        if QApplication.instance() is None:
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path, use_3d=use_3d)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    @property
    def on_voice_changed(self):
        return self._win.on_voice_changed

    @on_voice_changed.setter
    def on_voice_changed(self, cb):
        self._win.on_voice_changed = cb

    @property
    def on_country_selected(self):
        return self._win.on_country_selected

    @on_country_selected.setter
    def on_country_selected(self, cb):
        self._win.on_country_selected = cb

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def set_ui_mode(self, mode: str):
        """'minimal' = nur JARVIS | 'dashboard' = 3D-Modell + alle Infos | 'toggle'"""
        self._win._uimode_sig.emit(mode)

    def control_model(self, action: str, subject: str = ""):
        """Thread-safe control for the full-screen 3-D presentation stage."""
        self._win._model_sig.emit(action, subject)

    def set_news_status(self, status: str):
        self._win._news_status_sig.emit(status)

    def show_self(self):
        self._win._show_sig.emit()

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if self._win._apply_state:
            self._win._apply_state("LISTENING")
