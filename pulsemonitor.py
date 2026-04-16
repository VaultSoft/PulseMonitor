#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  PulseMonitor v1.0  —  Professional PC Health Monitor        ║
║  Install: pip install PyQt6 psutil                           ║
║  Temps: nvidia-smi (GPU) + WMI ACPI thermal zones (CPU)     ║
║         No kernel drivers — AV-clean build                   ║
╚══════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations
import sys, os, time, platform, math, subprocess, threading, json
from datetime import datetime
from collections import deque
from typing import Optional, List, Dict
import urllib.request

import psutil
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QFrame,
    QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QSystemTrayIcon, QMenu, QSizePolicy, QAbstractItemView, QSpacerItem
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QSize, QPoint, QRect, QRectF,
    QPointF, QLineF, QPropertyAnimation, QVariantAnimation, QEasingCurve,
    pyqtProperty
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QIcon, QPixmap,
    QLinearGradient, QPainterPath, QAction, QCursor, QMouseEvent
)
# pyqtgraph removed — BigChart now uses pure QPainter (no multiprocessing dep)

# ─── App version + GitHub update source ───────────────────────────
APP_VERSION  = "1.0.0"
GITHUB_OWNER = "VaultSoft"
GITHUB_REPO  = "PulseMonitor"

# ─── Detect NVIDIA GPU via nvidia-smi (no GPUtil dependency) ─────
def _nvidia_smi_available() -> bool:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"],
            capture_output=True, timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return r.returncode == 0
    except Exception:
        return False

HAS_GPU: bool = _nvidia_smi_available()

# ─── Windows registry for startup apps ────────────────────────────
HAS_WINREG = False
if platform.system() == "Windows":
    try:
        import winreg as _winreg; HAS_WINREG = True
    except ImportError:
        pass


# ═══════════════════════════════════════════════════════════════════
# PALETTE
# ═══════════════════════════════════════════════════════════════════
C = {
    "bg0":   "#060A10",   # deepest bg
    "bg1":   "#0D1117",   # window bg
    "bg2":   "#131A23",   # card
    "bg3":   "#1B2535",   # card hover / selected
    "b0":    "#1C2B3A",   # border
    "b1":    "#263848",   # border bright
    "acc":   "#00D4AA",   # teal accent
    "acc2":  "#007A60",
    "blue":  "#4D9EFF",
    "purp":  "#9575FF",
    "t1":    "#E2EAF4",
    "t2":    "#7A90A8",
    "t3":    "#304050",
    "grn":   "#2ECC71",
    "amb":   "#F0A500",
    "red":   "#E74C3C",
    "cpu":   "#4D9EFF",
    "gpu":   "#9575FF",
    "ram":   "#00D4AA",
    "disk":  "#F0A500",
    "fan":   "#4D9EFF",
}

WARN_T  = 80    # °C
WARN_D  = 10    # % free
POLL_MS = 500   # ms — fast poll; slow items (drives/procs/fans) update every 4th tick
HIST    = 90    # history samples (~45 s at 500 ms)
ANIM_MS = int(POLL_MS * 0.84)  # animation duration — finishes just before next poll


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════
def pct_color(pct: float) -> str:
    if pct >= 90: return C["red"]
    if pct >= 65: return C["amb"]
    return C["grn"]

def temp_color(t: Optional[float]) -> str:
    if t is None: return C["t2"]
    if t >= 80: return C["red"]
    if t >= 65: return C["amb"]
    return C["grn"]

def fmt_uptime(s: float) -> str:
    s = int(s)
    d, s = divmod(s, 86400); h, s = divmod(s, 3600); m, _ = divmod(s, 60)
    return f"{d}d {h:02d}h {m:02d}m" if d else f"{h}h {m:02d}m" if h else f"{m}m"

def fmt_gb(gb: float) -> str:
    return f"{gb/1024:.1f} TB" if gb >= 1024 else f"{gb:.1f} GB" if gb >= 1 else f"{gb*1024:.0f} MB"

# ═══════════════════════════════════════════════════════════════════
# DATA MODEL
# ═══════════════════════════════════════════════════════════════════
class Metrics:
    def __init__(self):
        self.cpu_pct   = 0.0;    self.cpu_cores: List[float] = []
        self.cpu_freq  = 0.0;    self.cpu_temp: Optional[float] = None
        self.cpu_hist  = deque([0.0]*HIST, maxlen=HIST)

        self.ram_pct   = 0.0;    self.ram_used  = 0.0
        self.ram_total = 0.0;    self.ram_hist  = deque([0.0]*HIST, maxlen=HIST)

        self.gpu_name  = "";     self.gpu_pct   = 0.0
        self.gpu_temp: Optional[float] = None
        self.gpu_vram_u = 0.0;  self.gpu_vram_t = 0.0
        self.gpu_hist  = deque([0.0]*HIST, maxlen=HIST)

        self.drives:  List[Dict] = []
        self.procs:   List[Dict] = []
        self.fans:    Dict = {}
        self.startup: List[Dict] = []
        self.uptime   = 0.0

# ═══════════════════════════════════════════════════════════════════
# MONITOR THREAD
# ═══════════════════════════════════════════════════════════════════
class MonitorThread(QThread):
    sig_data  = pyqtSignal(object)
    sig_alert = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self._go = True
        self.data = Metrics()
        self._alerted: set = set()
        self._slow_tick = 0          # increments each poll; slow ops run every 4th
        self._acpi_wmi  = None       # lazy WMI connection for ACPI thermal zones
        self.data.startup = self._read_startup()
        psutil.cpu_percent(interval=None, percpu=True)   # prime pump

    def run(self):
        time.sleep(0.5)
        while self._go:
            t0 = time.monotonic()
            self._poll()
            self.sig_data.emit(self.data)
            self._check_alerts()
            rest = POLL_MS/1000.0 - (time.monotonic()-t0)
            if rest > 0: time.sleep(rest)

    def stop(self):
        self._go = False; self.wait()

    # ── collect all metrics ───────────────────────────────────────
    def _poll(self):
        d = self.data
        self._slow_tick += 1

        # ── Fast path: CPU / RAM / GPU  (every 500 ms) ───────────
        d.cpu_pct   = psutil.cpu_percent(interval=None)
        d.cpu_cores = psutil.cpu_percent(interval=None, percpu=True)
        f = psutil.cpu_freq(); d.cpu_freq = f.current if f else 0.0
        d.cpu_temp  = self._cpu_temp()
        d.cpu_hist.append(d.cpu_pct)

        vm = psutil.virtual_memory()
        d.ram_pct = vm.percent; d.ram_used = vm.used/1e9; d.ram_total = vm.total/1e9
        d.ram_hist.append(d.ram_pct)

        self._poll_gpu(d)
        d.uptime = time.time() - psutil.boot_time()

        # ── Slow path: drives / processes / fans  (every ~2 s) ───
        if self._slow_tick % 4 == 1:   # offset by 1 so first call populates data
            drives = []
            for p in psutil.disk_partitions(all=False):
                try:
                    u = psutil.disk_usage(p.mountpoint)
                    drives.append({"dev":p.device,"mount":p.mountpoint,"fs":p.fstype,
                                   "total":u.total/1e9,"used":u.used/1e9,
                                   "free":u.free/1e9,"pct":u.percent})
                except Exception: pass
            d.drives = drives

            procs = []
            for p in psutil.process_iter(["pid","name","cpu_percent","memory_percent","status"]):
                try:
                    i = p.info
                    procs.append({"pid":i["pid"],"name":i["name"] or "—",
                                   "cpu":i["cpu_percent"] or 0.0,
                                   "mem":i["memory_percent"] or 0.0,
                                   "status":i["status"] or "—"})
                except (psutil.NoSuchProcess, psutil.AccessDenied): pass
            d.procs = sorted(procs, key=lambda x: x["cpu"], reverse=True)[:100]

            try:    d.fans = psutil.sensors_fans() or {}
            except: d.fans = {}

    def _cpu_temp(self) -> Optional[float]:
        # ── 1. Windows ACPI thermal zones (no kernel driver needed) ──
        #    root\wmi  MSAcpi_ThermalZoneTemperature
        #    CurrentTemperature is in tenths of Kelvin
        if platform.system() == "Windows":
            try:
                if self._acpi_wmi is None:
                    import wmi as _w
                    self._acpi_wmi = _w.WMI(namespace=r"root\wmi")
                zones = self._acpi_wmi.MSAcpi_ThermalZoneTemperature()
                if zones:
                    temps = [
                        (z.CurrentTemperature / 10.0) - 273.15
                        for z in zones
                        if z.CurrentTemperature and z.CurrentTemperature > 2731
                    ]
                    if temps:
                        return max(temps)
            except Exception:
                self._acpi_wmi = None   # reset on COM/WMI error; retry next poll

        # ── 2. psutil  (Linux / macOS; occasionally Windows) ─────────
        try:
            t = psutil.sensors_temperatures()
            if t:
                for k in ("coretemp","k10temp","cpu-thermal","Package id 0","Tdie","cpu_thermal"):
                    if k in t and t[k]: return t[k][0].current
                for v in t.values():
                    if v: return v[0].current
        except Exception: pass

        return None

    def _poll_gpu(self, d: Metrics):
        # nvidia-smi — silent subprocess, no terminal window
        try:
            r = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=name,temperature.gpu,utilization.gpu,"
                 "memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if r.returncode == 0:
                parts = [x.strip() for x in r.stdout.strip().split(",")]
                if len(parts) >= 5:
                    d.gpu_name   = parts[0]
                    d.gpu_temp   = float(parts[1])
                    d.gpu_pct    = float(parts[2])
                    d.gpu_vram_u = float(parts[3]) / 1024
                    d.gpu_vram_t = float(parts[4]) / 1024
                    d.gpu_hist.append(d.gpu_pct)
                    return
        except Exception: pass

        d.gpu_name = "Not detected"; d.gpu_pct = 0.0; d.gpu_temp = None
        d.gpu_hist.append(0.0)

    def _read_startup(self) -> List[Dict]:
        apps = []
        if not HAS_WINREG: return apps
        hives = [
            (_winreg.HKEY_CURRENT_USER,
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run","HKCU"),
            (_winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run","HKLM"),
            (_winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run","HKLM 32-bit"),
        ]
        for hive, path, label in hives:
            try:
                k = _winreg.OpenKey(hive, path); i = 0
                while True:
                    try:
                        n, v, _ = _winreg.EnumValue(k, i); i += 1
                        apps.append({"name":n,"path":v,"scope":label})
                    except OSError: break
                _winreg.CloseKey(k)
            except Exception: pass
        return apps

    def _check_alerts(self):
        d = self.data
        def once(key, title, msg):
            if key not in self._alerted:
                self._alerted.add(key); self.sig_alert.emit(title, msg)
        def clr(key): self._alerted.discard(key)

        if d.cpu_temp and d.cpu_temp >= WARN_T:
            once("ct","CPU Temperature Warning",
                 f"CPU is {d.cpu_temp:.0f}°C — above {WARN_T}°C threshold!")
        elif d.cpu_temp: clr("ct")

        if d.gpu_temp and d.gpu_temp >= WARN_T:
            once("gt","GPU Temperature Warning",
                 f"GPU is {d.gpu_temp:.0f}°C — above {WARN_T}°C threshold!")
        elif d.gpu_temp: clr("gt")

        for dr in d.drives:
            free = 100 - dr["pct"]; k = f"dk_{dr['mount']}"
            if free <= WARN_D:
                once(k,"Low Disk Space Warning",
                     f"{dr['mount']} has only {free:.0f}% free ({dr['free']:.1f} GB remaining)")
            else: clr(k)

# ═══════════════════════════════════════════════════════════════════
# PAINTER WIDGETS
# ═══════════════════════════════════════════════════════════════════
class Sparkline(QWidget):
    """Mini anti-aliased area chart."""
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._c = QColor(color)
        self._hist: deque = deque([0.0]*HIST, maxlen=HIST)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setMinimumSize(80, 38)

    def set_hist(self, hist: deque):
        self._hist = hist; self.update()

    def paintEvent(self, _):
        pts_data = list(self._hist)
        n = len(pts_data)
        if n < 2: return
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pad = 2

        def pt(i, v):
            x = pad + i*(w-2*pad)/(n-1)
            y = h - pad - (v/100.0)*(h-2*pad)
            return QPointF(x, y)

        points = [pt(i, v) for i, v in enumerate(pts_data)]

        # Gradient fill
        fill = QPainterPath()
        fill.moveTo(QPointF(points[0].x(), h))
        for pp in points: fill.lineTo(pp)
        fill.lineTo(QPointF(points[-1].x(), h))
        fill.closeSubpath()

        grad = QLinearGradient(0, 0, 0, h)
        c1 = QColor(self._c); c1.setAlpha(70)
        c2 = QColor(self._c); c2.setAlpha(0)
        grad.setColorAt(0, c1); grad.setColorAt(1, c2)
        p.setPen(Qt.PenStyle.NoPen); p.fillPath(fill, grad)

        # Line
        pen = QPen(self._c, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                   Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        line = QPainterPath(); line.moveTo(points[0])
        for pp in points[1:]: line.lineTo(pp)
        p.drawPath(line)
        p.end()


class ThinBar(QWidget):
    """Slim progress bar that animates smoothly to each new value."""
    def __init__(self, color: str, height: int = 4, parent=None):
        super().__init__(parent)
        self._color = color
        self._disp  = 0.0   # currently rendered value
        self.setFixedHeight(height)
        self._anim = QPropertyAnimation(self, b"fillPct", self)
        self._anim.setDuration(ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # Qt property the animation drives
    def _get_fill(self): return self._disp
    def _set_fill(self, v): self._disp = v; self.update()
    fillPct = pyqtProperty(float, fget=_get_fill, fset=_set_fill)

    def set_pct(self, pct: float):
        target = max(0.0, min(100.0, pct))
        self._anim.stop()
        self._anim.setStartValue(self._disp)
        self._anim.setEndValue(target)
        self._anim.start()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()); h = r.height(); rr = h / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C["b0"])); p.drawRoundedRect(r, rr, rr)
        fill_w = r.width() * self._disp / 100.0
        if fill_w > 0:
            fr = QRectF(0, 0, fill_w, h)
            p.setBrush(QColor(pct_color(self._disp)))
            p.drawRoundedRect(fr, rr, rr)
        p.end()


class CircleGauge(QWidget):
    """Circular arc gauge that sweeps smoothly to each new value."""
    def __init__(self, color: str, size: int = 100, parent=None):
        super().__init__(parent)
        self._color = color
        self._disp  = 0.0
        self.setFixedSize(size, size)
        self._anim = QPropertyAnimation(self, b"arcPct", self)
        self._anim.setDuration(ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_arc(self): return self._disp
    def _set_arc(self, v): self._disp = v; self.update()
    arcPct = pyqtProperty(float, fget=_get_arc, fset=_set_arc)

    def set_pct(self, pct: float):
        target = max(0.0, min(100.0, pct))
        self._anim.stop()
        self._anim.setStartValue(self._disp)
        self._anim.setEndValue(target)
        self._anim.start()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        m = 8
        rect = QRectF(m, m, w - 2*m, h - 2*m)
        clr = QColor(pct_color(self._disp))

        pen = QPen(QColor(C["b0"]), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
        p.setPen(pen); p.drawArc(rect, 0, 360 * 16)

        if self._disp > 0:
            pen.setColor(clr); pen.setWidth(7)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(rect, 90 * 16, int(-self._disp / 100.0 * 360 * 16))

        font = QFont(); font.setPointSize(w // 8); font.setBold(True)
        p.setFont(font); p.setPen(QPen(clr))
        p.drawText(rect.toRect(), Qt.AlignmentFlag.AlignCenter, f"{self._disp:.0f}%")
        p.end()


class AnimFloat(QLabel):
    """QLabel that smoothly counts to new numeric values via QVariantAnimation."""
    def __init__(self, fmt: str = "{:.1f}%", style: str = "", parent=None):
        super().__init__("—", parent)
        self._fmt = fmt
        self._val = 0.0
        if style:
            self.setStyleSheet(style)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._tick)

    def _tick(self, v):
        self._val = float(v)
        self.setText(self._fmt.format(self._val))

    def animate_to(self, value: float):
        self._anim.stop()
        self._anim.setStartValue(float(self._val))
        self._anim.setEndValue(float(value))
        self._anim.start()


class BigChart(QWidget):
    """Full-width anti-aliased line chart drawn with pure QPainter.
    Matches the previous pyqtgraph look: gradient fill, glow line, Y-axis labels.
    No pyqtgraph / multiprocessing dependency."""

    _Y_LABELS = [0, 25, 50, 75, 100]

    def __init__(self, color: str, ylabel: str = "%", parent=None):
        super().__init__(parent)
        self._color  = QColor(color)
        self._ylabel = ylabel
        self._hist: deque = deque([0.0] * HIST, maxlen=HIST)
        self.setMinimumSize(120, 80)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def update_hist(self, hist: deque):
        self._hist = hist
        self.update()

    def paintEvent(self, _):
        pts = list(self._hist)
        n   = len(pts)
        if n < 2:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # ── Margins: leave room for Y-axis labels on the left ────────
        lm, rm, tm, bm = 36, 8, 6, 22   # left, right, top, bottom

        chart_w = w - lm - rm
        chart_h = h - tm - bm

        # ── Background ───────────────────────────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C["bg2"]))
        p.drawRect(self.rect())

        # ── Horizontal grid lines + Y labels ─────────────────────────
        grid_pen = QPen(QColor(C["b0"]), 1, Qt.PenStyle.SolidLine)
        grid_pen.setColor(QColor(C["b0"]))
        lbl_font = QFont(); lbl_font.setPointSize(8)
        p.setFont(lbl_font)

        for yv in self._Y_LABELS:
            gy = tm + chart_h - int(yv / 100.0 * chart_h)
            p.setPen(grid_pen)
            p.drawLine(lm, gy, lm + chart_w, gy)
            p.setPen(QPen(QColor(C["t2"])))
            p.drawText(QRect(0, gy - 8, lm - 4, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       str(yv))

        # ── Y-axis label (rotated) ────────────────────────────────────
        p.save()
        p.setPen(QPen(QColor(C["t2"])))
        p.setFont(lbl_font)
        p.translate(10, tm + chart_h // 2)
        p.rotate(-90)
        p.drawText(QRect(-30, -8, 60, 16),
                   Qt.AlignmentFlag.AlignCenter, self._ylabel)
        p.restore()

        # ── Map data → pixel coordinates ─────────────────────────────
        def pt(i, v):
            x = lm + i * chart_w / (n - 1)
            y = tm + chart_h - v / 100.0 * chart_h
            return QPointF(x, y)

        points = [pt(i, v) for i, v in enumerate(pts)]

        # ── Gradient fill ────────────────────────────────────────────
        fill_path = QPainterPath()
        fill_path.moveTo(QPointF(points[0].x(), tm + chart_h))
        for pp in points:
            fill_path.lineTo(pp)
        fill_path.lineTo(QPointF(points[-1].x(), tm + chart_h))
        fill_path.closeSubpath()

        grad = QLinearGradient(0, tm, 0, tm + chart_h)
        top_c = QColor(self._color); top_c.setAlpha(45)
        bot_c = QColor(self._color); bot_c.setAlpha(0)
        grad.setColorAt(0, top_c); grad.setColorAt(1, bot_c)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(fill_path, grad)

        # ── Glow line (wide, faint) ───────────────────────────────────
        glow_c = QColor(self._color); glow_c.setAlpha(28)
        glow_pen = QPen(glow_c, 8, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(glow_pen)
        glow_path = QPainterPath(); glow_path.moveTo(points[0])
        for pp in points[1:]: glow_path.lineTo(pp)
        p.drawPath(glow_path)

        # ── Crisp main line ───────────────────────────────────────────
        line_pen = QPen(self._color, 2, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(line_pen)
        line_path = QPainterPath(); line_path.moveTo(points[0])
        for pp in points[1:]: line_path.lineTo(pp)
        p.drawPath(line_path)

        # ── Border ────────────────────────────────────────────────────
        p.setPen(QPen(QColor(C["b0"]), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(lm, tm, chart_w, chart_h)

        p.end()

# ═══════════════════════════════════════════════════════════════════
# CARD WIDGETS
# ═══════════════════════════════════════════════════════════════════
def _card_style() -> str:
    return f"""
        background-color: {C['bg2']};
        border: 1px solid {C['b0']};
        border-radius: 10px;
    """

def _card(parent=None) -> QFrame:
    f = QFrame(parent)
    f.setStyleSheet(f"QFrame {{ {_card_style()} }}")
    return f


class MetricCard(QFrame):
    """Dashboard summary card with sparkline and usage bar."""
    def __init__(self, title: str, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self.setStyleSheet(f"QFrame {{ {_card_style()} }}")
        self.setMinimumSize(200, 148)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(6)

        # Header
        hdr = QHBoxLayout(); hdr.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{color}; font-size:9px; background:transparent; border:none;")
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(f"color:{C['t2']}; font-size:10px; font-weight:600; letter-spacing:1.5px; background:transparent; border:none;")
        hdr.addWidget(dot); hdr.addWidget(lbl); hdr.addStretch()
        root.addLayout(hdr)

        # Value + sparkline
        mid = QHBoxLayout(); mid.setSpacing(8)
        vcol = QVBoxLayout(); vcol.setSpacing(1)
        val_style = (f"color:{C['t1']}; font-size:26px; font-weight:700;"
                     f" background:transparent; border:none;")
        self._val = AnimFloat("{:.1f}%", style=val_style)
        self._sub = QLabel("")
        self._sub.setStyleSheet(f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")
        vcol.addWidget(self._val); vcol.addWidget(self._sub); vcol.addStretch()
        self._spark = Sparkline(color)
        mid.addLayout(vcol, 2); mid.addWidget(self._spark, 3)
        root.addLayout(mid)

        # Thin bar
        self._bar = ThinBar(color, 4)
        root.addWidget(self._bar)

    def refresh(self, pct: float, sub: str, hist: deque):
        """pct — numeric percentage (animated); sub — plain text subtitle."""
        self._val.animate_to(pct)
        self._sub.setText(sub)
        self._bar.set_pct(pct)
        self._spark.set_hist(hist)


class CoreBar(QWidget):
    """Single CPU core usage row."""
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self); row.setContentsMargins(0,2,0,2); row.setSpacing(10)
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")
        self._lbl.setFixedWidth(54)
        self._bar = ThinBar(C["cpu"], 8)
        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setStyleSheet(f"color:{C['t1']}; font-size:11px; background:transparent; border:none;")
        self._pct_lbl.setFixedWidth(36)
        row.addWidget(self._lbl); row.addWidget(self._bar, 1); row.addWidget(self._pct_lbl)

    def refresh(self, pct: float):
        self._bar.set_pct(pct)
        c = pct_color(pct)
        self._pct_lbl.setText(f"{pct:.0f}%")
        self._pct_lbl.setStyleSheet(f"color:{c}; font-size:11px; background:transparent; border:none;")


class DriveCard(QFrame):
    """Storage drive card with visual usage bar."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QFrame {{ {_card_style()} }}")
        root = QVBoxLayout(self); root.setContentsMargins(16,14,16,14); root.setSpacing(8)

        # Header row
        top = QHBoxLayout()
        self._name = QLabel("—")
        self._name.setStyleSheet(f"color:{C['t1']}; font-size:14px; font-weight:600; background:transparent; border:none;")
        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setStyleSheet(f"color:{C['grn']}; font-size:20px; font-weight:700; background:transparent; border:none;")
        top.addWidget(self._name); top.addStretch(); top.addWidget(self._pct_lbl)
        root.addLayout(top)

        # Size row
        self._size_lbl = QLabel("0 GB / 0 GB")
        self._size_lbl.setStyleSheet(f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")
        root.addWidget(self._size_lbl)

        # Bar
        self._bar = ThinBar(C["disk"], 10)
        root.addWidget(self._bar)

        # Footer
        bot = QHBoxLayout()
        self._fs  = QLabel("NTFS")
        self._free = QLabel("Free: 0 GB")
        for w in (self._fs, self._free):
            w.setStyleSheet(f"color:{C['t3']}; font-size:10px; background:transparent; border:none;")
        bot.addWidget(self._fs); bot.addStretch(); bot.addWidget(self._free)
        root.addLayout(bot)

    def refresh(self, data: Dict):
        pct  = data["pct"]
        free = 100 - pct
        clr  = C["red"] if free < 10 else C["amb"] if free < 25 else C["grn"]
        self._name.setText(f"{data['mount']}  ·  {data['fs']}")
        self._pct_lbl.setText(f"{pct:.0f}%")
        self._pct_lbl.setStyleSheet(f"color:{clr}; font-size:20px; font-weight:700; background:transparent; border:none;")
        self._size_lbl.setText(f"Used: {fmt_gb(data['used'])}  /  Total: {fmt_gb(data['total'])}")
        self._bar.set_pct(pct)
        self._free.setText(f"Free: {fmt_gb(data['free'])}")
        self._fs.setText(data["fs"])


class FanCard(QFrame):
    """Fan speed display card."""
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self._name = name
        self.setStyleSheet(f"QFrame {{ {_card_style()} }}")
        self.setMinimumWidth(160)
        root = QVBoxLayout(self); root.setContentsMargins(16,14,16,14); root.setSpacing(6)

        dot_row = QHBoxLayout(); dot_row.setSpacing(6)
        dot = QLabel("●"); dot.setStyleSheet(f"color:{C['fan']}; font-size:9px; background:transparent; border:none;")
        lbl = QLabel("FAN"); lbl.setStyleSheet(f"color:{C['t2']}; font-size:10px; font-weight:600; letter-spacing:1.5px; background:transparent; border:none;")
        dot_row.addWidget(dot); dot_row.addWidget(lbl); dot_row.addStretch()
        root.addLayout(dot_row)

        self._rpm = QLabel("— RPM")
        self._rpm.setStyleSheet(f"color:{C['t1']}; font-size:22px; font-weight:700; background:transparent; border:none;")
        root.addWidget(self._rpm)

        self._name_lbl = QLabel(name)
        self._name_lbl.setStyleSheet(f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")
        self._name_lbl.setWordWrap(True)
        root.addWidget(self._name_lbl)

    def refresh(self, rpm: float):
        self._rpm.setText(f"{rpm:,.0f} RPM")
        c = C["amb"] if rpm > 3000 else C["grn"]
        self._rpm.setStyleSheet(f"color:{c}; font-size:22px; font-weight:700; background:transparent; border:none;")

# ═══════════════════════════════════════════════════════════════════
# SHARED TABLE STYLE
# ═══════════════════════════════════════════════════════════════════
def styled_table(cols: List[str], col_widths: List[int] = None) -> QTableWidget:
    t = QTableWidget(0, len(cols))
    t.setHorizontalHeaderLabels(cols)
    t.verticalHeader().setVisible(False)
    t.setShowGrid(False)
    t.setAlternatingRowColors(False)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    t.setSortingEnabled(False)
    hh = t.horizontalHeader()
    if col_widths:
        for i, w in enumerate(col_widths):
            if w == -1: hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:       t.setColumnWidth(i, w)
    else:
        hh.setStretchLastSection(True)
    t.setStyleSheet(f"""
        QTableWidget {{
            background: {C['bg2']};
            border: 1px solid {C['b0']};
            border-radius: 8px;
            color: {C['t1']};
            font-size: 12px;
            selection-background-color: {C['bg3']};
            outline: none;
        }}
        QTableWidget::item {{ padding: 5px 10px; border: none; }}
        QTableWidget::item:hover {{ background: {C['bg3']}; }}
        QHeaderView::section {{
            background: {C['bg1']};
            color: {C['t2']};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.2px;
            padding: 8px 10px;
            border: none;
            border-bottom: 1px solid {C['b0']};
        }}
        QScrollBar:vertical {{
            background: {C['bg1']}; width: 6px; border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: {C['b1']}; border-radius: 3px; min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {C['acc']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    """)
    return t

# ═══════════════════════════════════════════════════════════════════
# SECTION HEADER
# ═══════════════════════════════════════════════════════════════════
def section_header(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"""
        color: {C['t1']}; font-size: 18px; font-weight: 700;
        padding-bottom: 2px; background: transparent; border: none;
        border-bottom: 2px solid {C['acc']};
    """)
    return lbl

def section_sub(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")
    return lbl

# ═══════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════════════════════════════════
class DashboardPage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:transparent;")
        inner = QWidget()
        self.setWidget(inner)
        root = QVBoxLayout(inner); root.setContentsMargins(28,24,28,24); root.setSpacing(20)

        # Title
        root.addWidget(section_header("Dashboard"))
        root.addWidget(section_sub("Real-time system overview"))

        # Metric cards row
        cards_row = QHBoxLayout(); cards_row.setSpacing(14)
        self._cpu_card = MetricCard("CPU", C["cpu"])
        self._gpu_card = MetricCard("GPU", C["gpu"])
        self._ram_card = MetricCard("Memory", C["ram"])
        for card in (self._cpu_card, self._gpu_card, self._ram_card):
            cards_row.addWidget(card, 1)
        root.addLayout(cards_row)

        # Charts row
        charts_row = QHBoxLayout(); charts_row.setSpacing(14)
        for title, color, attr in (
            ("CPU Usage", C["cpu"], "_cpu_chart"),
            ("Memory Usage", C["ram"], "_ram_chart"),
        ):
            box = _card()
            bl  = QVBoxLayout(box); bl.setContentsMargins(14,12,14,12); bl.setSpacing(8)
            bl.addWidget(QLabel(title) if False else self._make_chart_label(title, color))
            chart = BigChart(color); chart.setMinimumHeight(120)
            setattr(self, attr, chart)
            bl.addWidget(chart)
            charts_row.addWidget(box, 1)
        root.addLayout(charts_row)

        # Drive summary
        root.addWidget(section_header("Drive Space"))
        self._drives_grid = QGridLayout(); self._drives_grid.setSpacing(12)
        self._drive_cards: List[DriveCard] = []
        root.addLayout(self._drives_grid)

        # Stats strip
        self._stats_bar = QFrame()
        self._stats_bar.setStyleSheet(f"QFrame {{ background:{C['bg2']}; border:1px solid {C['b0']}; border-radius:8px; }}")
        sb_layout = QHBoxLayout(self._stats_bar)
        sb_layout.setContentsMargins(20,10,20,10); sb_layout.setSpacing(0)
        self._stat_labels: Dict[str, QLabel] = {}
        for key in ("uptime","cpu_name","timestamp"):
            lbl = QLabel("—")
            lbl.setStyleSheet(f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")
            self._stat_labels[key] = lbl
            sb_layout.addWidget(lbl)
            if key != "timestamp":
                sep = QLabel("  ·  ")
                sep.setStyleSheet(f"color:{C['t3']}; background:transparent; border:none;")
                sb_layout.addWidget(sep)
        sb_layout.addStretch()
        root.addWidget(self._stats_bar)
        root.addStretch()

    @staticmethod
    def _make_chart_label(title: str, color: str) -> QLabel:
        lbl = QLabel(title)
        lbl.setStyleSheet(f"color:{C['t1']}; font-size:12px; font-weight:600; background:transparent; border:none;")
        return lbl

    def update(self, m: Metrics):
        # CPU card
        temp_str = f"{m.cpu_temp:.0f}°C  ·  " if m.cpu_temp else ""
        self._cpu_card.refresh(m.cpu_pct,
                               f"{temp_str}{m.cpu_freq:.0f} MHz",
                               m.cpu_hist)
        # GPU card
        g_temp = f"{m.gpu_temp:.0f}°C  ·  " if m.gpu_temp else ""
        g_vram = f"{m.gpu_vram_u:.1f}/{m.gpu_vram_t:.1f} GB VRAM" if m.gpu_vram_t else ""
        self._gpu_card.refresh(m.gpu_pct,
                               f"{g_temp}{g_vram}" or m.gpu_name,
                               m.gpu_hist)
        # RAM card
        self._ram_card.refresh(m.ram_pct,
                               f"{fmt_gb(m.ram_used)} / {fmt_gb(m.ram_total)}",
                               m.ram_hist)
        # Charts
        self._cpu_chart.update_hist(m.cpu_hist)
        self._ram_chart.update_hist(m.ram_hist)

        # Drives
        if len(m.drives) != len(self._drive_cards):
            # Rebuild drive cards
            for i in reversed(range(self._drives_grid.count())):
                w = self._drives_grid.itemAt(i).widget()
                if w: self._drives_grid.removeWidget(w); w.deleteLater()
            self._drive_cards.clear()
            cols = 3
            for idx, dr in enumerate(m.drives):
                dc = DriveCard()
                self._drive_cards.append(dc)
                self._drives_grid.addWidget(dc, idx//cols, idx%cols)
        for card, dr in zip(self._drive_cards, m.drives):
            card.refresh(dr)

        # Stats strip
        cpu_name = platform.processor() or platform.machine()
        cpu_short = cpu_name[:48] + "…" if len(cpu_name) > 50 else cpu_name
        self._stat_labels["uptime"].setText(f"Uptime: {fmt_uptime(m.uptime)}")
        self._stat_labels["cpu_name"].setText(cpu_short)
        self._stat_labels["timestamp"].setText(
            datetime.now().strftime("%d %b %Y  %H:%M:%S"))

# ═══════════════════════════════════════════════════════════════════
# PAGE: CPU
# ═══════════════════════════════════════════════════════════════════
class CpuPage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:transparent;")
        inner = QWidget(); self.setWidget(inner)
        root = QVBoxLayout(inner); root.setContentsMargins(28,24,28,24); root.setSpacing(18)

        root.addWidget(section_header("CPU"))
        root.addWidget(section_sub("Processor utilisation and thermal status"))

        # Stats cards
        stats_row = QHBoxLayout(); stats_row.setSpacing(12)
        for attr, title in (("_usage_card","Usage"),("_temp_card","Temperature"),
                            ("_freq_card","Frequency"),("_cores_card","Cores")):
            card = _card(); cl = QVBoxLayout(card); cl.setContentsMargins(16,14,16,14); cl.setSpacing(4)
            label = QLabel(title.upper())
            label.setStyleSheet(f"color:{C['t2']}; font-size:10px; font-weight:600; letter-spacing:1.2px; background:transparent; border:none;")
            val = QLabel("—")
            val.setStyleSheet(f"color:{C['t1']}; font-size:22px; font-weight:700; background:transparent; border:none;")
            cl.addWidget(label); cl.addWidget(val); cl.addStretch()
            setattr(self, attr, val)
            stats_row.addWidget(card, 1)
        root.addLayout(stats_row)

        # Large chart
        chart_card = _card()
        ccl = QVBoxLayout(chart_card); ccl.setContentsMargins(14,12,14,12); ccl.setSpacing(8)
        ccl.addWidget(QLabel("CPU Usage (%)") if False else self._chart_label())
        self._chart = BigChart(C["cpu"]); self._chart.setMinimumHeight(160)
        ccl.addWidget(self._chart)
        root.addWidget(chart_card)

        # Per-core bars
        core_card = _card()
        ccl2 = QVBoxLayout(core_card); ccl2.setContentsMargins(16,14,16,14); ccl2.setSpacing(4)
        hdr_lbl = QLabel("Per-Core Usage")
        hdr_lbl.setStyleSheet(f"color:{C['t1']}; font-size:13px; font-weight:600; background:transparent; border:none;")
        ccl2.addWidget(hdr_lbl)
        self._core_grid = QGridLayout(); self._core_grid.setSpacing(6)
        ccl2.addLayout(self._core_grid)
        root.addWidget(core_card)
        root.addStretch()
        self._core_bars: List[CoreBar] = []

    @staticmethod
    def _chart_label() -> QLabel:
        lbl = QLabel("CPU Usage History")
        lbl.setStyleSheet(f"color:{C['t1']}; font-size:12px; font-weight:600; background:transparent; border:none;")
        return lbl

    def _pct_style(self, val: str, color: str) -> str:
        return f"color:{color}; font-size:22px; font-weight:700; background:transparent; border:none;"

    def update(self, m: Metrics):
        self._usage_card.setText(f"{m.cpu_pct:.1f}%")
        self._usage_card.setStyleSheet(self._pct_style("", pct_color(m.cpu_pct)))

        if m.cpu_temp is not None:
            self._temp_card.setText(f"{m.cpu_temp:.0f} °C")
            self._temp_card.setStyleSheet(self._pct_style("", temp_color(m.cpu_temp)))
        else:
            # AMD CPUs need admin for LHM sensor access
            hint = "Run as Admin" if platform.system() == "Windows" else "N/A"
            self._temp_card.setText(hint)
            self._temp_card.setStyleSheet(self._pct_style("", C["t2"]))

        self._freq_card.setText(f"{m.cpu_freq:,.0f} MHz")
        self._freq_card.setStyleSheet(self._pct_style("", C["blue"]))
        self._cores_card.setText(str(len(m.cpu_cores)))
        self._cores_card.setStyleSheet(self._pct_style("", C["t1"]))

        self._chart.update_hist(m.cpu_hist)

        # Per-core bars – rebuild if core count changed
        if len(m.cpu_cores) != len(self._core_bars):
            for i in reversed(range(self._core_grid.count())):
                w = self._core_grid.itemAt(i).widget()
                if w: self._core_grid.removeWidget(w); w.deleteLater()
            self._core_bars.clear()
            cols = 2
            for idx, _ in enumerate(m.cpu_cores):
                cb = CoreBar(f"Core {idx}")
                self._core_bars.append(cb)
                self._core_grid.addWidget(cb, idx//cols, idx%cols)
        for bar, pct in zip(self._core_bars, m.cpu_cores):
            bar.refresh(pct)

# ═══════════════════════════════════════════════════════════════════
# PAGE: MEMORY
# ═══════════════════════════════════════════════════════════════════
class MemoryPage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:transparent;")
        inner = QWidget(); self.setWidget(inner)
        root = QVBoxLayout(inner); root.setContentsMargins(28,24,28,24); root.setSpacing(18)

        root.addWidget(section_header("Memory"))
        root.addWidget(section_sub("RAM utilisation over time"))

        # Stats cards
        row = QHBoxLayout(); row.setSpacing(12)
        for attr, title in (("_pct_lbl","Usage"),("_used_lbl","Used"),
                            ("_total_lbl","Total"),("_free_lbl","Available")):
            card = _card(); cl = QVBoxLayout(card); cl.setContentsMargins(16,14,16,14); cl.setSpacing(4)
            tl = QLabel(title.upper())
            tl.setStyleSheet(f"color:{C['t2']}; font-size:10px; font-weight:600; letter-spacing:1.2px; background:transparent; border:none;")
            vl = QLabel("—")
            vl.setStyleSheet(f"color:{C['t1']}; font-size:22px; font-weight:700; background:transparent; border:none;")
            cl.addWidget(tl); cl.addWidget(vl); cl.addStretch()
            setattr(self, attr, vl); row.addWidget(card, 1)
        root.addLayout(row)

        # Gauge + chart
        mid = QHBoxLayout(); mid.setSpacing(14)
        gauge_card = _card(); gl = QVBoxLayout(gauge_card)
        gl.setContentsMargins(20,16,20,16); gl.setSpacing(8)
        gl.addStretch()
        self._gauge = CircleGauge(C["ram"], 140)
        gauge_wrapper = QHBoxLayout(); gauge_wrapper.addStretch()
        gauge_wrapper.addWidget(self._gauge); gauge_wrapper.addStretch()
        gl.addLayout(gauge_wrapper); gl.addStretch()

        chart_card = _card(); ccl = QVBoxLayout(chart_card)
        ccl.setContentsMargins(14,12,14,12); ccl.setSpacing(8)
        lbl = QLabel("Memory Usage History")
        lbl.setStyleSheet(f"color:{C['t1']}; font-size:12px; font-weight:600; background:transparent; border:none;")
        ccl.addWidget(lbl)
        self._chart = BigChart(C["ram"]); self._chart.setMinimumHeight(160)
        ccl.addWidget(self._chart)

        mid.addWidget(gauge_card, 1); mid.addWidget(chart_card, 3)
        root.addLayout(mid)
        root.addStretch()

    def update(self, m: Metrics):
        clr = pct_color(m.ram_pct)
        self._pct_lbl.setText(f"{m.ram_pct:.1f}%")
        self._pct_lbl.setStyleSheet(f"color:{clr}; font-size:22px; font-weight:700; background:transparent; border:none;")
        self._used_lbl.setText(fmt_gb(m.ram_used))
        self._used_lbl.setStyleSheet(f"color:{C['t1']}; font-size:22px; font-weight:700; background:transparent; border:none;")
        self._total_lbl.setText(fmt_gb(m.ram_total))
        self._total_lbl.setStyleSheet(f"color:{C['t1']}; font-size:22px; font-weight:700; background:transparent; border:none;")
        free = m.ram_total - m.ram_used
        self._free_lbl.setText(fmt_gb(free))
        self._free_lbl.setStyleSheet(f"color:{C['t1']}; font-size:22px; font-weight:700; background:transparent; border:none;")
        self._gauge.set_pct(m.ram_pct)
        self._chart.update_hist(m.ram_hist)

# ═══════════════════════════════════════════════════════════════════
# PAGE: GPU
# ═══════════════════════════════════════════════════════════════════
class GpuPage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:transparent;")
        inner = QWidget(); self.setWidget(inner)
        root = QVBoxLayout(inner); root.setContentsMargins(28,24,28,24); root.setSpacing(18)

        root.addWidget(section_header("GPU"))

        self._gpu_name_lbl = section_sub("Detecting GPU…")
        root.addWidget(self._gpu_name_lbl)

        # Stats cards
        row = QHBoxLayout(); row.setSpacing(12)
        for attr, title in (("_load_lbl","Load"),("_temp_lbl","Temperature"),
                            ("_vram_lbl","VRAM Used"),("_vram_t_lbl","VRAM Total")):
            card = _card(); cl = QVBoxLayout(card); cl.setContentsMargins(16,14,16,14); cl.setSpacing(4)
            tl = QLabel(title.upper())
            tl.setStyleSheet(f"color:{C['t2']}; font-size:10px; font-weight:600; letter-spacing:1.2px; background:transparent; border:none;")
            vl = QLabel("—")
            vl.setStyleSheet(f"color:{C['t1']}; font-size:22px; font-weight:700; background:transparent; border:none;")
            cl.addWidget(tl); cl.addWidget(vl); cl.addStretch()
            setattr(self, attr, vl); row.addWidget(card, 1)
        root.addLayout(row)

        # Chart
        chart_card = _card(); ccl = QVBoxLayout(chart_card)
        ccl.setContentsMargins(14,12,14,12); ccl.setSpacing(8)
        lbl = QLabel("GPU Load History")
        lbl.setStyleSheet(f"color:{C['t1']}; font-size:12px; font-weight:600; background:transparent; border:none;")
        ccl.addWidget(lbl)
        self._chart = BigChart(C["gpu"]); self._chart.setMinimumHeight(160)
        ccl.addWidget(self._chart)
        root.addWidget(chart_card)

        if not HAS_GPU:
            notice = QLabel(
                "No NVIDIA GPU detected.\n"
                "GPU monitoring requires an NVIDIA card with nvidia-smi available.\n"
                "AMD / Intel GPU support via WMI can be added with the wmi package.")
            notice.setStyleSheet(f"""
                color:{C['t2']}; font-size:12px; background:{C['bg2']};
                border:1px solid {C['b0']}; border-radius:8px; padding:16px;
            """)
            notice.setWordWrap(True)
            root.addWidget(notice)

        root.addStretch()

    def update(self, m: Metrics):
        self._gpu_name_lbl.setText(m.gpu_name or "—")
        self._load_lbl.setText(f"{m.gpu_pct:.1f}%")
        self._load_lbl.setStyleSheet(f"color:{pct_color(m.gpu_pct)}; font-size:22px; font-weight:700; background:transparent; border:none;")
        if m.gpu_temp:
            self._temp_lbl.setText(f"{m.gpu_temp:.0f} °C")
            self._temp_lbl.setStyleSheet(f"color:{temp_color(m.gpu_temp)}; font-size:22px; font-weight:700; background:transparent; border:none;")
        else:
            self._temp_lbl.setText("N/A")
            self._temp_lbl.setStyleSheet(f"color:{C['t2']}; font-size:22px; font-weight:700; background:transparent; border:none;")
        self._vram_lbl.setText(fmt_gb(m.gpu_vram_u) if m.gpu_vram_u else "N/A")
        self._vram_lbl.setStyleSheet(f"color:{C['t1']}; font-size:22px; font-weight:700; background:transparent; border:none;")
        self._vram_t_lbl.setText(fmt_gb(m.gpu_vram_t) if m.gpu_vram_t else "N/A")
        self._vram_t_lbl.setStyleSheet(f"color:{C['t1']}; font-size:22px; font-weight:700; background:transparent; border:none;")
        self._chart.update_hist(m.gpu_hist)

# ═══════════════════════════════════════════════════════════════════
# PAGE: STORAGE
# ═══════════════════════════════════════════════════════════════════
class StoragePage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:transparent;")
        inner = QWidget(); self.setWidget(inner)
        root = QVBoxLayout(inner); root.setContentsMargins(28,24,28,24); root.setSpacing(18)

        root.addWidget(section_header("Storage"))
        root.addWidget(section_sub("Disk space and filesystem health"))

        self._grid = QGridLayout(); self._grid.setSpacing(14)
        root.addLayout(self._grid)
        root.addStretch()
        self._cards: List[DriveCard] = []
        self._prev_drives = None   # identity guard

    def update(self, m: Metrics):
        if m.drives is self._prev_drives:
            return
        self._prev_drives = m.drives
        if len(m.drives) != len(self._cards):
            for i in reversed(range(self._grid.count())):
                w = self._grid.itemAt(i).widget()
                if w: self._grid.removeWidget(w); w.deleteLater()
            self._cards.clear()
            cols = 2
            for idx, dr in enumerate(m.drives):
                dc = DriveCard()
                self._cards.append(dc)
                self._grid.addWidget(dc, idx//cols, idx%cols)
        for card, dr in zip(self._cards, m.drives):
            card.refresh(dr)

# ═══════════════════════════════════════════════════════════════════
# PAGE: PROCESSES
# ═══════════════════════════════════════════════════════════════════
class ProcessPage(QWidget):
    def __init__(self):
        super().__init__()
        self._prev_procs = None   # identity guard — skip redraw when list unchanged
        root = QVBoxLayout(self); root.setContentsMargins(28,24,28,24); root.setSpacing(14)

        root.addWidget(section_header("Processes"))
        root.addWidget(section_sub("Running processes sorted by CPU usage  (top 100)"))

        self._table = styled_table(
            ["PID","Process Name","CPU %","Memory %","Status"],
            [70, -1, 90, 100, 100]
        )
        self._table.setMinimumHeight(400)
        root.addWidget(self._table)

    def update(self, m: Metrics):
        if m.procs is self._prev_procs:
            return          # slow-tick data unchanged; skip expensive redraw
        self._prev_procs = m.procs
        self._table.setUpdatesEnabled(False)
        self._table.setRowCount(len(m.procs))
        for row, proc in enumerate(m.procs):
            items = [
                (str(proc["pid"]),      C["t2"],  False),
                (proc["name"],          C["t1"],  False),
                (f"{proc['cpu']:.1f}",  pct_color(proc["cpu"]) if proc["cpu"] > 0 else C["t2"], False),
                (f"{proc['mem']:.1f}",  C["t2"],  False),
                (proc["status"],        C["t2"],  False),
            ]
            for col, (text, color, bold) in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color))
                if bold:
                    f = item.font(); f.setBold(True); item.setFont(f)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter |
                    (Qt.AlignmentFlag.AlignRight if col in (0,2,3) else Qt.AlignmentFlag.AlignLeft))
                self._table.setItem(row, col, item)
            self._table.setRowHeight(row, 30)
        self._table.setUpdatesEnabled(True)

# ═══════════════════════════════════════════════════════════════════
# PAGE: STARTUP APPS
# ═══════════════════════════════════════════════════════════════════
class StartupPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self); root.setContentsMargins(28,24,28,24); root.setSpacing(14)

        root.addWidget(section_header("Startup Programs"))
        root.addWidget(section_sub("Applications registered to launch at Windows startup"))

        self._table = styled_table(
            ["Name","Registry Scope","Command / Path"],
            [200, 110, -1]
        )
        root.addWidget(self._table)

        if not HAS_WINREG:
            notice = QLabel("Windows registry access is unavailable on this platform.")
            notice.setStyleSheet(f"color:{C['t2']}; font-size:12px; padding:12px; background:transparent; border:none;")
            root.addWidget(notice)

    def update(self, m: Metrics):
        self._table.setUpdatesEnabled(False)
        self._table.setRowCount(len(m.startup))
        for row, app in enumerate(m.startup):
            for col, (text, color) in enumerate([
                (app["name"],  C["t1"]),
                (app["scope"], C["acc"]),
                (app["path"],  C["t2"]),
            ]):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self._table.setItem(row, col, item)
            self._table.setRowHeight(row, 30)
        self._table.setUpdatesEnabled(True)

# ═══════════════════════════════════════════════════════════════════
# PAGE: FANS
# ═══════════════════════════════════════════════════════════════════
class FansPage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:transparent;")
        inner = QWidget(); self.setWidget(inner)
        self._root = QVBoxLayout(inner); self._root.setContentsMargins(28,24,28,24); self._root.setSpacing(18)

        self._root.addWidget(section_header("Fan Speeds"))
        self._root.addWidget(section_sub("System fan RPM readings from hardware sensors"))

        self._cards_row = QHBoxLayout(); self._cards_row.setSpacing(12)
        self._root.addLayout(self._cards_row)
        self._fan_cards: Dict[str, FanCard] = {}

        self._no_fans = QLabel(
            "No fan sensors detected.\n\n"
            "Fan speed monitoring requires:\n"
            "  • Linux: lm-sensors (sudo sensors-detect)\n"
            "  • Windows: fan data via lm-sensors or third-party tools\n"
            "  • macOS: SMC sensors access")
        self._no_fans.setStyleSheet(f"""
            color:{C['t2']}; font-size:12px; background:{C['bg2']};
            border:1px solid {C['b0']}; border-radius:8px; padding:20px;
        """)
        self._no_fans.setWordWrap(True)
        self._root.addWidget(self._no_fans)
        self._root.addStretch()

    def update(self, m: Metrics):
        all_fans = {}
        for controller, fans in m.fans.items():
            for fan in fans:
                key = f"{controller} / {fan.label}"
                all_fans[key] = fan.current

        if not all_fans:
            self._no_fans.show(); return
        self._no_fans.hide()

        for key, rpm in all_fans.items():
            if key not in self._fan_cards:
                fc = FanCard(key)
                self._fan_cards[key] = fc
                self._cards_row.addWidget(fc)
            self._fan_cards[key].refresh(rpm)

# ═══════════════════════════════════════════════════════════════════
# TITLE BAR
# ═══════════════════════════════════════════════════════════════════
class TitleBar(QWidget):
    def __init__(self, parent: QMainWindow):
        super().__init__(parent)
        self._parent = parent
        self._drag_pos: Optional[QPoint] = None
        self.setFixedHeight(46)
        self.setStyleSheet(f"background:{C['bg0']}; border-bottom:1px solid {C['b0']};")

        row = QHBoxLayout(self); row.setContentsMargins(16, 0, 10, 0); row.setSpacing(0)

        # Pulse icon (drawn inline)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(self._make_logo(20))
        icon_lbl.setStyleSheet("background:transparent; border:none;")

        app_lbl = QLabel("PulseMonitor")
        app_lbl.setStyleSheet(f"""
            color:{C['t1']}; font-size:14px; font-weight:700;
            letter-spacing:0.5px; background:transparent; border:none;
            margin-left:8px;
        """)
        ver_lbl = QLabel("v1.2")
        ver_lbl.setStyleSheet(f"color:{C['t3']}; font-size:11px; margin-left:6px; background:transparent; border:none;")

        row.addWidget(icon_lbl); row.addWidget(app_lbl); row.addWidget(ver_lbl)
        row.addStretch()

        # Window controls
        for symbol, tip, slot, hover_clr in (
            ("─", "Minimise", parent.showMinimized, C["t2"]),
            ("□", "Maximise", self._toggle_max, C["t2"]),
            ("✕", "Close",    parent.close,         C["red"]),
        ):
            btn = QPushButton(symbol)
            btn.setFixedSize(36, 36)
            btn.setToolTip(tip)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{C['t2']};
                    border:none; font-size:14px; border-radius:6px;
                }}
                QPushButton:hover {{ background:{hover_clr}22; color:{hover_clr}; }}
            """)
            btn.clicked.connect(slot)
            row.addWidget(btn)

    @staticmethod
    def _make_logo(size: int) -> QPixmap:
        pm = QPixmap(size, size); pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(C["acc"]), 2, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        pts = [QPointF(1,size/2), QPointF(size*0.22,size/2),
               QPointF(size*0.35,size*0.15), QPointF(size*0.5,size*0.85),
               QPointF(size*0.65,size*0.3), QPointF(size*0.78,size/2),
               QPointF(size-1,size/2)]
        for i in range(len(pts)-1):
            p.drawLine(pts[i], pts[i+1])
        p.end(); return pm

    def _toggle_max(self):
        if self._parent.isMaximized(): self._parent.showNormal()
        else:                          self._parent.showMaximized()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self._parent.pos()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self._parent.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, _):
        self._toggle_max()

# ═══════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════
NAV_ITEMS = [
    ("⊞", "Dashboard"),
    ("⬡", "CPU"),
    ("▣", "Memory"),
    ("◈", "GPU"),
    ("▦", "Storage"),
    ("≡", "Processes"),
    ("⚡","Startup"),
    ("∿", "Fans"),
]

class SideNavBtn(QPushButton):
    def __init__(self, icon: str, label: str):
        super().__init__()
        self._icon  = icon
        self._label = label
        self._active = False
        self.setFixedHeight(48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("border:none; background:transparent;")

    def set_active(self, v: bool):
        self._active = v; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if self._active:
            p.fillRect(0, 0, w, h, QColor(C["bg3"]))
            # Left accent bar
            p.setBrush(QColor(C["acc"])); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(0, 10, 3, h-20, 1.5, 1.5)
        elif self.underMouse():
            p.fillRect(0, 0, w, h, QColor(C["bg2"]))

        # Icon
        icon_font = QFont(); icon_font.setPointSize(13)
        p.setFont(icon_font)
        c = QColor(C["acc"] if self._active else C["t2"])
        p.setPen(QPen(c))
        p.drawText(QRect(14, 0, 30, h), Qt.AlignmentFlag.AlignCenter, self._icon)

        # Label
        lbl_font = QFont(); lbl_font.setPointSize(10)
        if self._active: lbl_font.setWeight(QFont.Weight.DemiBold)
        p.setFont(lbl_font)
        p.setPen(QPen(QColor(C["t1"] if self._active else C["t2"])))
        p.drawText(QRect(50, 0, w-58, h), Qt.AlignmentFlag.AlignVCenter, self._label)
        p.end()


class Sidebar(QWidget):
    page_selected = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(190)
        self.setStyleSheet(f"background:{C['bg0']}; border-right:1px solid {C['b0']};")

        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 16); root.setSpacing(2)

        # App branding strip
        brand = QWidget()
        brand.setFixedHeight(56)
        brand.setStyleSheet(f"background:{C['bg0']}; border-bottom:1px solid {C['b0']};")
        bl = QHBoxLayout(brand); bl.setContentsMargins(16,0,16,0)
        brand_lbl = QLabel("PULSE")
        brand_lbl.setStyleSheet(f"color:{C['acc']}; font-size:15px; font-weight:800; letter-spacing:3px; background:transparent; border:none;")
        bl.addWidget(brand_lbl)
        root.addWidget(brand)
        root.addSpacing(8)

        # Nav buttons
        self._btns: List[SideNavBtn] = []
        for icon, label in NAV_ITEMS:
            btn = SideNavBtn(icon, label)
            idx = len(self._btns)
            btn.clicked.connect(lambda _, i=idx: self._select(i))
            self._btns.append(btn)
            root.addWidget(btn)

        root.addStretch()

        # Version at bottom
        ver = QLabel(f"v{APP_VERSION}  ·  {platform.system()}")
        ver.setStyleSheet(f"color:{C['t3']}; font-size:10px; padding:0 16px; background:transparent; border:none;")
        root.addWidget(ver)

        self._select(0)

    def _select(self, idx: int):
        for i, btn in enumerate(self._btns):
            btn.set_active(i == idx)
        self.page_selected.emit(idx)

# ═══════════════════════════════════════════════════════════════════
# SYSTEM TRAY ICON (drawn programmatically)
# ═══════════════════════════════════════════════════════════════════
def make_tray_icon() -> QIcon:
    pm = QPixmap(32, 32); pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Dark circle background
    p.setBrush(QColor(C["bg2"])); p.setPen(QPen(QColor(C["acc"]), 1.5))
    p.drawEllipse(1, 1, 30, 30)
    # ECG / pulse line
    pts = [QPointF(4,16), QPointF(7,16), QPointF(11,8),
           QPointF(16,24), QPointF(21,11), QPointF(25,16), QPointF(28,16)]
    pen = QPen(QColor(C["acc"]), 2, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    for i in range(len(pts)-1):
        p.drawLine(pts[i], pts[i+1])
    p.end()
    return QIcon(pm)

# ═══════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════
GLOBAL_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {C['bg1']};
    color: {C['t1']};
    font-family: "Segoe UI", "SF Pro Display", "Ubuntu", "Helvetica Neue", sans-serif;
    font-size: 13px;
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: {C['bg1']}; width: 6px; border-radius: 3px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {C['b1']}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {C['acc']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:0; }}
QScrollBar:horizontal {{
    background: {C['bg1']}; height: 6px; border-radius: 3px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {C['b1']}; border-radius: 3px; min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; border:0; }}
QToolTip {{
    background: {C['bg3']}; color: {C['t1']};
    border: 1px solid {C['b1']}; padding: 4px 8px; border-radius: 4px;
}}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PulseMonitor")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # ── Central layout ────────────────────────────────────────
        central = QWidget(); self.setCentralWidget(central)
        central.setStyleSheet(f"background:{C['bg1']};")
        vbox = QVBoxLayout(central); vbox.setContentsMargins(0,0,0,0); vbox.setSpacing(0)

        # Title bar
        self._titlebar = TitleBar(self)
        vbox.addWidget(self._titlebar)

        # Update banner (hidden until an update is found)
        self._update_banner: Optional[UpdateBanner] = None
        self._banner_slot = vbox   # stash layout reference for banner insertion

        # Body (sidebar + pages)
        body = QWidget()
        body.setStyleSheet(f"background:{C['bg1']};")
        hbox = QHBoxLayout(body); hbox.setContentsMargins(0,0,0,0); hbox.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.page_selected.connect(self._switch_page)
        hbox.addWidget(self._sidebar)

        # Page stack
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{C['bg1']};")
        hbox.addWidget(self._stack, 1)
        vbox.addWidget(body, 1)

        # Status bar (bottom strip)
        self._status = QLabel("Starting…")
        self._status.setFixedHeight(26)
        self._status.setStyleSheet(f"""
            background:{C['bg0']}; color:{C['t3']};
            font-size:11px; padding:0 16px;
            border-top: 1px solid {C['b0']};
        """)
        vbox.addWidget(self._status)

        # ── Pages ─────────────────────────────────────────────────
        self._pages = [
            DashboardPage(),
            CpuPage(),
            MemoryPage(),
            GpuPage(),
            StoragePage(),
            ProcessPage(),
            StartupPage(),
            FansPage(),
        ]
        for page in self._pages:
            self._stack.addWidget(page)

        # ── Monitor thread ────────────────────────────────────────
        self._monitor = MonitorThread()
        self._monitor.sig_data.connect(self._on_data)
        self._monitor.sig_alert.connect(self._on_alert)
        self._monitor.start()

        # ── Auto-updater (checks after 3 s so startup is snappy) ─
        QTimer.singleShot(3000, self._start_update_check)

        # ── System tray ───────────────────────────────────────────
        self._tray = QSystemTrayIcon(make_tray_icon(), self)
        self._tray.setToolTip("PulseMonitor — running in background")
        tray_menu = QMenu()
        tray_menu.setStyleSheet(f"""
            QMenu {{ background:{C['bg2']}; border:1px solid {C['b0']}; color:{C['t1']}; padding:4px; }}
            QMenu::item {{ padding:6px 20px; border-radius:4px; }}
            QMenu::item:selected {{ background:{C['bg3']}; }}
        """)
        show_act = QAction("Show PulseMonitor", self)
        show_act.triggered.connect(self._show_from_tray)
        quit_act = QAction("Quit", self)
        quit_act.triggered.connect(QApplication.quit)
        tray_menu.addAction(show_act)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_act)
        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    # ── Page switching ────────────────────────────────────────────
    def _switch_page(self, idx: int):
        self._stack.setCurrentIndex(idx)

    # ── Auto-updater ──────────────────────────────────────────────
    def _start_update_check(self):
        self._updater = UpdateChecker(self)
        self._updater.sig_update_available.connect(self._show_update_banner)
        self._updater.start()

    def _show_update_banner(self, version: str, url: str):
        if self._update_banner is not None:
            return  # already showing
        banner = UpdateBanner(version, url, self.centralWidget())
        banner.dismissed.connect(self._hide_update_banner)
        self._update_banner = banner
        # Insert banner just below the title bar (index 1)
        self._banner_slot.insertWidget(1, banner)

    def _hide_update_banner(self):
        if self._update_banner:
            self._update_banner.hide()
            self._banner_slot.removeWidget(self._update_banner)
            self._update_banner.deleteLater()
            self._update_banner = None

    # ── Receive metrics ───────────────────────────────────────────
    def _on_data(self, m: Metrics):
        idx = self._stack.currentIndex()
        page = self._pages[idx]
        if hasattr(page, "update"): page.update(m)

        # Always keep dashboard drives + status updated
        if idx != 0 and hasattr(self._pages[0], "update"):
            pass   # don't update off-screen pages to save CPU

        self._status.setText(
            f"  CPU {m.cpu_pct:.1f}%"
            f"  ·  RAM {m.ram_pct:.1f}%"
            f"  ·  Uptime {fmt_uptime(m.uptime)}"
            f"  ·  {datetime.now().strftime('%H:%M:%S')}"
        )

    # ── Tray notifications ────────────────────────────────────────
    def _on_alert(self, title: str, msg: str):
        if self._tray.isVisible() and QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.showMessage(title, msg, QSystemTrayIcon.MessageIcon.Warning, 6000)

    # ── Tray interaction ──────────────────────────────────────────
    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self):
        self.showNormal(); self.raise_(); self.activateWindow()

    # ── Minimise-to-tray on close ─────────────────────────────────
    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "PulseMonitor",
            "Monitoring continues in the background. Double-click the tray icon to restore.",
            QSystemTrayIcon.MessageIcon.Information, 3000
        )

    # ── Clean shutdown ────────────────────────────────────────────
    def quit_app(self):
        self._monitor.stop()
        QApplication.quit()

    # ── Resize grip (bottom-right) ────────────────────────────────
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            pos = e.position().toPoint()
            if pos.x() > self.width()-16 and pos.y() > self.height()-16:
                self._resizing = True
                self._resize_start = e.globalPosition().toPoint()
                self._start_size   = self.size()
            else:
                self._resizing = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        if hasattr(self,"_resizing") and self._resizing and e.buttons() == Qt.MouseButton.LeftButton:
            delta = e.globalPosition().toPoint() - self._resize_start
            self.resize(max(800, self._start_size.width()+delta.x()),
                        max(600, self._start_size.height()+delta.y()))
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._resizing = False
        super().mouseReleaseEvent(e)

# ═══════════════════════════════════════════════════════════════════
# AUTO-UPDATER
# ═══════════════════════════════════════════════════════════════════
class UpdateChecker(QThread):
    """Checks GitHub Releases for a newer version in the background."""
    sig_update_available = pyqtSignal(str, str)   # (new_version, download_url)

    def run(self):
        try:
            api = (f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
                   f"/releases/latest")
            req = urllib.request.Request(api, headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"PulseMonitor/{APP_VERSION}",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "").lstrip("v")
            if not tag:
                return
            if self._is_newer(tag, APP_VERSION):
                # Find the .exe asset, or fall back to the html_url
                url = data.get("html_url", "")
                for asset in data.get("assets", []):
                    if asset.get("name", "").lower().endswith(".exe"):
                        url = asset["browser_download_url"]
                        break
                self.sig_update_available.emit(tag, url)
        except Exception:
            pass  # network offline / rate-limited — silently skip

    @staticmethod
    def _is_newer(remote: str, local: str) -> bool:
        def parts(v):
            try:
                return tuple(int(x) for x in v.split("."))
            except Exception:
                return (0,)
        return parts(remote) > parts(local)


class UpdateBanner(QWidget):
    """Slim dismissible banner shown at the top of the window when an update is ready."""
    dismissed = pyqtSignal()

    def __init__(self, version: str, url: str, parent=None):
        super().__init__(parent)
        self._url = url
        self.setFixedHeight(38)
        self.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {C['acc2']}, stop:1 #004D3A);
            border-bottom: 1px solid {C['acc']};
        """)
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 0, 10, 0)
        row.setSpacing(10)

        icon = QLabel("↑")
        icon.setStyleSheet(f"color:{C['acc']}; font-size:14px; font-weight:800; background:transparent;")
        msg = QLabel(f"PulseMonitor {version} is available — ")
        msg.setStyleSheet(f"color:{C['t1']}; font-size:12px; background:transparent;")
        link = QPushButton("Download now")
        link.setStyleSheet(f"""
            QPushButton {{
                color:{C['acc']}; font-size:12px; font-weight:600;
                background:transparent; border:none; text-decoration:underline;
                padding:0;
            }}
            QPushButton:hover {{ color:{C['t1']}; }}
        """)
        link.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        link.clicked.connect(self._open_url)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                color:{C['t2']}; font-size:11px; background:transparent;
                border:none; border-radius:11px;
            }}
            QPushButton:hover {{ background:{C['bg3']}; color:{C['t1']}; }}
        """)
        close_btn.clicked.connect(self.dismissed.emit)

        row.addWidget(icon)
        row.addWidget(msg)
        row.addWidget(link)
        row.addStretch()
        row.addWidget(close_btn)

    def _open_url(self):
        import webbrowser
        webbrowser.open(self._url)


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════
def main():
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("PulseMonitor")
    app.setApplicationVersion(APP_VERSION)
    app.setStyleSheet(GLOBAL_STYLE)

    # Set app icon
    icon_pm = QPixmap(32, 32); icon_pm.fill(Qt.GlobalColor.transparent)
    ip = QPainter(icon_pm); ip.setRenderHint(QPainter.RenderHint.Antialiasing)
    ip.setBrush(QColor(C["bg2"])); ip.setPen(Qt.PenStyle.NoPen)
    ip.drawRoundedRect(0,0,32,32,6,6)
    ip.setPen(QPen(QColor(C["acc"]),2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
    for a, b in zip(
        [QPointF(3,16),QPointF(7,16),QPointF(11,7),QPointF(16,25),QPointF(21,10),QPointF(25,16)],
        [QPointF(7,16),QPointF(11,7),QPointF(16,25),QPointF(21,10),QPointF(25,16),QPointF(29,16)],
    ): ip.drawLine(a, b)
    ip.end()
    app.setWindowIcon(QIcon(icon_pm))

    win = MainWindow()
    # Quit action in tray also needs to stop monitor
    for action in win._tray.contextMenu().actions():
        if action.text() == "Quit":
            action.triggered.disconnect()
            action.triggered.connect(win.quit_app)

    win.show()

    # Window drop shadow on Windows 11
    if platform.system() == "Windows":
        try:
            import ctypes
            hwnd = int(win.winId())
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWM_WINDOW_CORNER_PREFERENCE_ROUND = 2
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(ctypes.c_int(DWM_WINDOW_CORNER_PREFERENCE_ROUND)),
                ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
