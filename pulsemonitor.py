#!/usr/bin/env python3
"""PulseMonitor v1.1.0 — Professional PC Health Monitor (VaultSoft)"""
from __future__ import annotations
import sys, os, time, platform, math, subprocess, threading, json, csv, sqlite3, weakref
from datetime import datetime, date
from collections import deque
from typing import Optional, List, Dict, Tuple
import urllib.request, traceback

import psutil
import queue as _queue
import copy as _copy
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QFrame,
    QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QSystemTrayIcon, QMenu, QSizePolicy, QAbstractItemView,
    QSpinBox, QCheckBox, QComboBox, QFileDialog, QButtonGroup,
    QMessageBox, QInputDialog,
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, QObject, pyqtSignal, QSize, QPoint, QRect, QRectF,
    QPointF, QAbstractNativeEventFilter, QUrl,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QIcon, QPixmap,
    QLinearGradient, QPainterPath, QAction, QCursor, QMouseEvent,
    QDesktopServices,
)

APP_VERSION  = "1.1.0"
GITHUB_OWNER = "VaultSoft"
GITHUB_REPO  = "PulseMonitor"

_IS_WIN = platform.system() == "Windows"

# ── Logo PNG (loaded from bundled _logo_b64.txt) ──────────────────
import base64 as _base64

_LOGO_PIXMAP: Optional[QPixmap] = None

def _load_logo_pixmap() -> QPixmap:
    """Load logo PNG from _logo_b64.txt beside the executable (or script)."""
    try:
        _base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        _b64_path = os.path.join(_base_dir, "_logo_b64.txt")
        if os.path.exists(_b64_path):
            with open(_b64_path, "r") as _f:
                _b64_data = _f.read().strip()
            _raw = _base64.b64decode(_b64_data)
            _pm = QPixmap()
            _pm.loadFromData(_raw)
            if not _pm.isNull():
                return _pm
    except Exception:
        pass
    _pm2 = QPixmap(64, 64); _pm2.fill(Qt.GlobalColor.transparent)
    return _pm2

def _get_logo(size: int) -> QPixmap:
    global _LOGO_PIXMAP
    if _LOGO_PIXMAP is None:
        _LOGO_PIXMAP = _load_logo_pixmap()
    if _LOGO_PIXMAP.isNull():
        return _LOGO_PIXMAP
    return _LOGO_PIXMAP.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)

# ── optional stdlib extras ─────────────────────────────────────────
HAS_WINSOUND = False
if _IS_WIN:
    try:
        import winsound as _winsound; HAS_WINSOUND = True
    except ImportError:
        pass

HAS_WINREG = False
if _IS_WIN:
    try:
        import winreg as _winreg; HAS_WINREG = True
    except ImportError:
        pass

# ══════════════════════════════════════════════════════════════════
# THEMES
# ══════════════════════════════════════════════════════════════════
_DARK = {
    "bg0":"#060A10","bg1":"#0D1117","bg2":"#131A23","bg3":"#1B2535",
    "b0":"#1C2B3A","b1":"#263848",
    "acc":"#00D4AA","acc2":"#007A60",
    "blue":"#4D9EFF","purp":"#9575FF",
    "t1":"#E2EAF4","t2":"#a0aec0","t3":"#617080","title":"#ffffff",
    "grn":"#2ECC71","amb":"#F0A500","red":"#E74C3C",
    "cpu":"#4D9EFF","gpu":"#9575FF","ram":"#00D4AA","disk":"#F0A500","fan":"#4D9EFF",
    "net_up":"#FF6B6B","net_dn":"#4ECDC4",
}
_LIGHT = {
    "bg0":"#E8EDF3","bg1":"#F4F6F9","bg2":"#FFFFFF","bg3":"#EBF0F7",
    "b0":"#CBD5E0","b1":"#A0AEC0",
    "acc":"#009977","acc2":"#006B55",
    "blue":"#2563EB","purp":"#7C3AED",
    "t1":"#0F1923","t2":"#374151","t3":"#A0AEC0","title":"#0a0e1a",
    "grn":"#16A34A","amb":"#D97706","red":"#DC2626",
    "cpu":"#2563EB","gpu":"#7C3AED","ram":"#009977","disk":"#D97706","fan":"#2563EB",
    "net_up":"#DC2626","net_dn":"#0891B2",
}

C: Dict[str, str] = {}   # populated by init_theme()

def init_theme(name: str):
    C.clear()
    C.update(_LIGHT if name == "light" else _DARK)

# ══════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════
class Config:
    _PATH = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "PulseMonitor", "config.json"
    )
    def __init__(self):
        # alerts
        self.warn_temp:     int   = 80
        self.warn_disk:     int   = 10
        self.warn_cpu_pct:  int   = 90
        self.warn_gpu_pct:  int   = 90
        self.warn_ram_pct:  int   = 90
        self.alert_sound:   str   = "beep"   # "none" | "beep"
        # performance
        self.poll_ms:       int   = 500
        # appearance
        self.theme:         str   = "dark"
        # overlay
        self.overlay_x:     int   = -1      # -1 = auto (top-right)
        self.overlay_y:     int   = -1
        self.overlay_opacity: float = 0.88
        # dashboard widget visibility (True = show)
        self.dash_cpu:      bool  = True
        self.dash_gpu:      bool  = True
        self.dash_ram:      bool  = True
        self.dash_charts:   bool  = True
        self.dash_drives:   bool  = True
        self._load()

    def _load(self):
        try:
            with open(self._PATH) as f:
                d = json.load(f)
            for k, default in vars(self).items():
                if k.startswith("_"): continue
                if k in d:
                    try:
                        setattr(self, k, type(default)(d[k]))
                    except Exception:
                        pass
        except Exception:
            pass

    def save(self):
        try:
            os.makedirs(os.path.dirname(self._PATH), exist_ok=True)
            data = {k: v for k, v in vars(self).items() if not k.startswith("_")}
            with open(self._PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

CFG = Config()
init_theme(CFG.theme)

# ══════════════════════════════════════════════════════════════════
# CONSTANTS / HELPERS
# ══════════════════════════════════════════════════════════════════
HIST    = 90
ANIM_MS = int(CFG.poll_ms * 0.84)
_CPU_PROC_NAME = platform.processor() or platform.machine()   # cached — never changes
HIST_DB_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "PulseMonitor", "history.db"
)

def pct_color(p: float) -> str:
    if p >= 90: return C["red"]
    if p >= 65: return C["amb"]
    return C["grn"]

def temp_color(t: Optional[float]) -> str:
    if t is None: return C["t2"]
    w = CFG.warn_temp
    if t >= w:          return C["red"]
    if t >= w * 0.8125: return C["amb"]
    return C["grn"]

def fmt_uptime(s: float) -> str:
    s = int(s); d, s = divmod(s, 86400); h, s = divmod(s, 3600); m, _ = divmod(s, 60)
    return f"{d}d {h:02d}h {m:02d}m" if d else f"{h}h {m:02d}m" if h else f"{m}m"

def fmt_gb(gb: float) -> str:
    if gb >= 1024: return f"{gb/1024:.1f} TB"
    if gb >= 1:    return f"{gb:.1f} GB"
    return f"{gb*1024:.0f} MB"

def fmt_bytes_rate(bps: float) -> str:
    if bps >= 1_000_000: return f"{bps/1_000_000:.1f} MB/s"
    if bps >= 1_000:     return f"{bps/1_000:.0f} KB/s"
    return f"{bps:.0f} B/s"

def fmt_bytes_total(b: float) -> str:
    if b >= 1_073_741_824: return f"{b/1_073_741_824:.2f} GB"
    if b >= 1_048_576:     return f"{b/1_048_576:.1f} MB"
    if b >= 1_024:         return f"{b/1_024:.0f} KB"
    return f"{b:.0f} B"

def _play_alert():
    if not HAS_WINSOUND or CFG.alert_sound == "none": return
    try: _winsound.Beep(1000, 180)
    except Exception: pass

# ══════════════════════════════════════════════════════════════════
# HISTORY DATABASE
# ══════════════════════════════════════════════════════════════════
class HistoryDB:
    """SQLite3 performance log. Thread-safe: single cached connection with lock."""
    def __init__(self):
        self._path = HIST_DB_PATH
        self._lock = threading.Lock()
        self._db: Optional[sqlite3.Connection] = None
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        if self._db is None:
            self._db = sqlite3.connect(self._path, timeout=5, check_same_thread=False)
        return self._db

    def _init_db(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with self._lock:
                con = self._conn()
                con.execute("""CREATE TABLE IF NOT EXISTS perf_log (
                    ts       INTEGER PRIMARY KEY,
                    cpu      REAL, gpu      REAL, ram      REAL,
                    cpu_temp REAL, gpu_temp REAL,
                    net_up   REAL, net_dn   REAL
                )""")
                con.execute("CREATE INDEX IF NOT EXISTS idx_ts ON perf_log(ts)")
                cutoff = int(time.time()) - 8 * 86400
                con.execute("DELETE FROM perf_log WHERE ts < ?", (cutoff,))
                con.commit()
        except Exception:
            self._db = None

    def insert(self, cpu, gpu, ram, cpu_temp, gpu_temp, net_up, net_dn):
        try:
            with self._lock:
                con = self._conn()
                con.execute(
                    "INSERT OR REPLACE INTO perf_log VALUES (?,?,?,?,?,?,?,?)",
                    (int(time.time()), cpu, gpu, ram,
                     cpu_temp or 0, gpu_temp or 0, net_up, net_dn)
                )
                con.commit()
        except Exception:
            self._db = None

    def query(self, since_ts: int, max_points: int = 120) -> List[Dict]:
        """Return up to max_points rows since since_ts, evenly sampled."""
        try:
            with self._lock:
                rows = self._conn().execute(
                    "SELECT ts,cpu,gpu,ram,cpu_temp,gpu_temp,net_up,net_dn "
                    "FROM perf_log WHERE ts >= ? ORDER BY ts",
                    (since_ts,)
                ).fetchall()
            if not rows: return []
            step = max(1, len(rows) // max_points)
            sampled = rows[::step]
            return [
                {"ts": r[0], "cpu": r[1], "gpu": r[2], "ram": r[3],
                 "cpu_temp": r[4], "gpu_temp": r[5], "net_up": r[6], "net_dn": r[7]}
                for r in sampled
            ]
        except Exception:
            self._db = None
            return []

HISTORY_DB = HistoryDB()

# ══════════════════════════════════════════════════════════════════
# DATA MODEL
# ══════════════════════════════════════════════════════════════════
class Metrics:
    def __init__(self):
        self.cpu_pct  = 0.0;  self.cpu_cores: List[float] = []
        self.cpu_freq = 0.0;  self.cpu_temp: Optional[float] = None
        self.cpu_hist = deque([0.0]*HIST, maxlen=HIST)

        self.ram_pct  = 0.0;  self.ram_used  = 0.0
        self.ram_total= 0.0;  self.ram_hist  = deque([0.0]*HIST, maxlen=HIST)

        self.gpu_name = "";   self.gpu_pct   = 0.0
        self.gpu_temp: Optional[float] = None
        self.gpu_vram_u = 0.0; self.gpu_vram_t = 0.0
        self.gpu_hist  = deque([0.0]*HIST, maxlen=HIST)
        self.gpu_vendor = "unknown"   # nvidia / amd / intel / unknown

        self.drives:  List[Dict] = []
        self.procs:   List[Dict] = []
        self.fans:    Dict = {}
        self.startup: List[Dict] = []
        self.uptime   = 0.0

        # network
        self.net_recv_rate = 0.0   # bytes/s
        self.net_sent_rate = 0.0
        self.net_recv_today = 0.0  # bytes since midnight
        self.net_sent_today = 0.0
        self.net_top_procs: List[Dict] = []
        self.net_recv_hist = deque([0.0]*HIST, maxlen=HIST)
        self.net_sent_hist = deque([0.0]*HIST, maxlen=HIST)

def _read_startup_apps() -> List[Dict]:
    apps = []
    if not HAS_WINREG: return apps
    hives = [
        (_winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "HKCU"),
        (_winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "HKLM"),
    ]
    for hive, path, label in hives:
        try:
            k = _winreg.OpenKey(hive, path); i = 0
            while True:
                try:
                    n, v, _ = _winreg.EnumValue(k, i); i += 1
                    apps.append({"name": n, "path": v, "scope": label})
                except OSError:
                    break
            _winreg.CloseKey(k)
        except Exception:
            pass
    return apps


# ══════════════════════════════════════════════════════════════════
# MONITOR THREAD
# ══════════════════════════════════════════════════════════════════
class MonitorThread(QThread):
    sig_tick  = pyqtSignal()           # zero-arg ping — avoids passing PyObject* through Qt cross-thread signal
    sig_alert = pyqtSignal(str, str)   # (title, message) — strings are safe cross-thread

    def __init__(self):
        super().__init__()
        self._go = True
        self.data = Metrics()
        self._snapshot: Optional[Metrics] = None   # GIL-atomic snapshot for main thread
        self._alert_q: _queue.Queue = _queue.Queue()  # alerts passed via Python queue
        self._alerted: set = set()
        self._slow_tick = 0
        # visibility flag — set by main thread (GIL-atomic bool write)
        self._window_visible = True
        # temperature WMI handles (lazy)
        self._acpi_wmi  = None
        self._lhm_wmi   = None
        self._ohm_wmi   = None
        # temperature cache — re-read WMI at most every 4 ticks (~2 s at 500 ms poll)
        self._cached_cpu_temp: Optional[float] = None
        self._temp_tick = 0
        # GPU state
        self._gpu_vendor  = "unknown"
        self._gpu_wmi     = None     # WMI connection for AMD/Intel perf counters
        self._gpu_wmi_err = False    # stop retrying if class missing
        self._gpu_tick    = 0        # throttle nvidia-smi to every other visible tick
        # network state
        self._prev_net_io  = None
        self._prev_net_t   = 0.0
        self._net_today_date = date.today()
        self._net_today_recv = 0.0
        self._net_today_sent = 0.0
        # active page index — set by main thread so heavy per-page queries can be skipped
        self._active_page = 0
        # startup (read once)
        self.data.startup = self._read_startup()
        psutil.cpu_percent(interval=None, percpu=True)   # prime pump
        # detect GPU vendor (nvidia-smi first, then WMI — but WMI must run on this thread;
        # we'll detect lazily on first poll inside run())
        self._gpu_vendor_detected = False

    def set_window_visible(self, visible: bool):
        """Called from main thread when window is shown/hidden to tray."""
        self._window_visible = visible

    def set_active_page(self, idx: int):
        """Called from main thread on page navigation to skip irrelevant heavy queries."""
        self._active_page = idx

    def run(self):
        time.sleep(0.5)
        while self._go:
            t0 = time.monotonic()
            try:
                self._poll()
            except Exception:
                try:
                    with open(_CRASH_LOG, "a", encoding="utf-8") as _f:
                        _f.write(f"\nMONITOR_THREAD_EXCEPTION  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        import traceback as _tb
                        _f.write(_tb.format_exc() + "\n")
                except Exception:
                    pass
            self._snapshot = _copy.copy(self.data)  # shallow copy; GIL-atomic assignment
            self._check_alerts()
            self.sig_tick.emit()  # no Python objects through Qt type system
            poll_ms = CFG.poll_ms if self._window_visible else max(CFG.poll_ms, 1000)
            rest = poll_ms / 1000.0 - (time.monotonic() - t0)
            if rest > 0:
                time.sleep(rest)

    def stop(self):
        self._go = False
        self.wait()

    # ── detect GPU vendor on worker thread ────────────────────────
    def _detect_gpu_vendor(self):
        if self._gpu_vendor_detected:
            return
        self._gpu_vendor_detected = True
        # 1. nvidia-smi
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"],
                capture_output=True, timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if r.returncode == 0:
                self._gpu_vendor = "nvidia"
                self.data.gpu_vendor = "nvidia"
                return
        except Exception:
            pass
        # 2. WMI Win32_VideoController
        if not _IS_WIN:
            return
        try:
            import wmi as _wmi
            w = _wmi.WMI()
            for vc in w.Win32_VideoController():
                name = (vc.Name or "").upper()
                if "NVIDIA" in name:
                    self._gpu_vendor = "nvidia"; break
                if "AMD" in name or "RADEON" in name or "ATI" in name:
                    self._gpu_vendor = "amd"
                    self.data.gpu_name = vc.Name or "AMD GPU"
                    break
                if "INTEL" in name:
                    self._gpu_vendor = "intel"
                    self.data.gpu_name = vc.Name or "Intel GPU"
                    break
            self.data.gpu_vendor = self._gpu_vendor
        except Exception:
            pass

    # ── main poll ─────────────────────────────────────────────────
    def _poll(self):
        d = self.data
        self._slow_tick += 1
        _hidden = not self._window_visible

        if not self._gpu_vendor_detected:
            self._detect_gpu_vendor()

        # fast path — always runs (cheap psutil calls, needed for alerts + history)
        d.cpu_pct   = psutil.cpu_percent(interval=None)
        d.cpu_cores = psutil.cpu_percent(interval=None, percpu=True)
        f = psutil.cpu_freq(); d.cpu_freq = f.current if f else 0.0
        d.cpu_temp  = self._cpu_temp_cached(_hidden)
        d.cpu_hist.append(d.cpu_pct)

        vm = psutil.virtual_memory()
        d.ram_pct   = vm.percent
        d.ram_used  = vm.used  / 1e9
        d.ram_total = vm.total / 1e9
        d.ram_hist.append(d.ram_pct)

        # GPU + network: skip subprocess/WMI when hidden (keep last value)
        if _hidden:
            d.gpu_hist.append(d.gpu_pct)
        else:
            self._poll_gpu(d)
        self._poll_network(d)
        d.uptime = time.time() - psutil.boot_time()

        # slow path — skip entirely when hidden
        if not _hidden and self._slow_tick % 4 == 1:
            # drives: refresh every 8 ticks (~4 s) — space changes slowly
            if self._slow_tick % 8 == 1:
                drives = []
                for p in psutil.disk_partitions(all=False):
                    try:
                        u = psutil.disk_usage(p.mountpoint)
                        drives.append({"dev": p.device, "mount": p.mountpoint,
                                       "fs": p.fstype,
                                       "total": u.total/1e9, "used": u.used/1e9,
                                       "free": u.free/1e9, "pct": u.percent})
                    except Exception:
                        pass
                d.drives = drives

            # process list — only when on the Process page (idx 5)
            if self._active_page == 5:
                procs = []
                for p in psutil.process_iter(["pid","name","cpu_percent","memory_percent","status"]):
                    try:
                        i = p.info
                        procs.append({"pid": i["pid"], "name": i["name"] or "—",
                                      "cpu": i["cpu_percent"] or 0.0,
                                      "mem": i["memory_percent"] or 0.0,
                                      "status": i["status"] or "—"})
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                d.procs = sorted(procs, key=lambda x: x["cpu"], reverse=True)[:100]

            try:    d.fans = psutil.sensors_fans() or {}
            except: d.fans = {}

            # per-process network connections — only when on Network page (idx 8)
            if self._active_page == 8:
                self._poll_net_procs(d)

    # ── CPU temperature ───────────────────────────────────────────
    def _cpu_temp(self) -> Optional[float]:
        if not _IS_WIN:
            try:
                t = psutil.sensors_temperatures()
                if t:
                    for k in ("coretemp","k10temp","cpu-thermal","Tdie","cpu_thermal"):
                        if k in t and t[k]: return t[k][0].current
                    for v in t.values():
                        if v: return v[0].current
            except Exception:
                pass
            return None

        # 1. LibreHardwareMonitor WMI service (if user runs LHM as service)
        temp = self._lhm_temp("cpu")
        if temp is not None: return temp

        # 2. OpenHardwareMonitor WMI (if OHM is running)
        temp = self._ohm_temp("cpu")
        if temp is not None: return temp

        # 3. ACPI thermal zones
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
                if temps: return max(temps)
        except Exception:
            self._acpi_wmi = None

        # 4. psutil (Linux/macOS fallback)
        try:
            t = psutil.sensors_temperatures()
            if t:
                for k in ("coretemp","k10temp","Package id 0","Tdie"):
                    if k in t and t[k]: return t[k][0].current
                for v in t.values():
                    if v: return v[0].current
        except Exception:
            pass
        return None

    def _cpu_temp_cached(self, hidden: bool) -> Optional[float]:
        """Return CPU temperature, querying at most every 4 ticks (~2 s); never when hidden."""
        self._temp_tick += 1
        if hidden or self._temp_tick % 4 != 1:
            return self._cached_cpu_temp
        self._cached_cpu_temp = self._cpu_temp()
        return self._cached_cpu_temp

    def _lhm_temp(self, kind: str) -> Optional[float]:
        """Query LibreHardwareMonitor WMI service for temperature."""
        try:
            if self._lhm_wmi is None:
                import wmi as _w
                self._lhm_wmi = _w.WMI(namespace=r"root\LibreHardwareMonitor")
            sensors = self._lhm_wmi.Sensor()
            best = None
            for s in sensors:
                if s.SensorType != "Temperature": continue
                name = (s.Name or "").lower()
                if kind == "cpu" and ("cpu" in name or "package" in name or "tdie" in name):
                    val = float(s.Value or 0)
                    if val > 0 and (best is None or val > best): best = val
                elif kind == "gpu" and "gpu" in name and "core" in name:
                    val = float(s.Value or 0)
                    if val > 0 and (best is None or val > best): best = val
            return best
        except Exception:
            self._lhm_wmi = None
            return None

    def _ohm_temp(self, kind: str) -> Optional[float]:
        """Query OpenHardwareMonitor WMI for temperature."""
        try:
            if self._ohm_wmi is None:
                import wmi as _w
                self._ohm_wmi = _w.WMI(namespace=r"root\OpenHardwareMonitor")
            sensors = self._ohm_wmi.Sensor()
            best = None
            for s in sensors:
                if s.SensorType != "Temperature": continue
                name = (s.Name or "").lower()
                if kind == "cpu" and "cpu" in name:
                    val = float(s.Value or 0)
                    if val > 0 and (best is None or val > best): best = val
                elif kind == "gpu" and "gpu" in name:
                    val = float(s.Value or 0)
                    if val > 0 and (best is None or val > best): best = val
            return best
        except Exception:
            self._ohm_wmi = None
            return None

    # ── GPU polling ───────────────────────────────────────────────
    def _poll_gpu(self, d: Metrics):
        if self._gpu_vendor == "nvidia":
            self._poll_gpu_nvidia(d)
        elif self._gpu_vendor in ("amd", "intel"):
            self._poll_gpu_wmi(d)
        else:
            d.gpu_hist.append(0.0)

    def _poll_gpu_nvidia(self, d: Metrics):
        self._gpu_tick += 1
        if self._gpu_tick % 2 == 0:
            # Skip nvidia-smi on even ticks — keeps cached values, halves subprocess cost
            d.gpu_hist.append(d.gpu_pct)
            return
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
        except Exception:
            pass
        d.gpu_pct = 0.0; d.gpu_temp = None
        d.gpu_hist.append(0.0)

    def _poll_gpu_wmi(self, d: Metrics):
        """AMD/Intel GPU via Windows GPU Performance Counters WMI class."""
        if self._gpu_wmi_err:
            d.gpu_hist.append(d.gpu_pct); return
        try:
            if self._gpu_wmi is None:
                import wmi as _w
                self._gpu_wmi = _w.WMI(namespace=r"root\cimv2")

            # utilization — sum 3D engine instances
            total_util = 0.0
            count = 0
            engines = self._gpu_wmi.query(
                "SELECT UtilizationPercentage FROM "
                "Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine"
            )
            for e in engines:
                util = float(e.UtilizationPercentage or 0)
                total_util = max(total_util, util)   # peak across engines
                count += 1
            if count > 0:
                d.gpu_pct = min(100.0, total_util)

            # dedicated VRAM used
            try:
                mem_rows = self._gpu_wmi.query(
                    "SELECT LocalMemoryUsage FROM "
                    "Win32_PerfFormattedData_GPUPerformanceCounters_GPULocalAdapterMemory"
                )
                if mem_rows:
                    d.gpu_vram_u = sum(float(m.LocalMemoryUsage or 0)
                                       for m in mem_rows) / 1_073_741_824
            except Exception:
                pass

            # temperature via LHM/OHM if available
            t = self._lhm_temp("gpu") or self._ohm_temp("gpu")
            d.gpu_temp = t

            d.gpu_hist.append(d.gpu_pct)
        except Exception:
            self._gpu_wmi = None
            # If the WMI class doesn't exist on this machine, stop trying
            self._gpu_wmi_err = True
            d.gpu_hist.append(d.gpu_pct)

    # ── Network polling ───────────────────────────────────────────
    def _poll_network(self, d: Metrics):
        try:
            now_io = psutil.net_io_counters()
            now_t  = time.monotonic()
            if self._prev_net_io is not None:
                dt = now_t - self._prev_net_t
                if dt > 0:
                    d.net_recv_rate = max(0.0, (now_io.bytes_recv - self._prev_net_io.bytes_recv) / dt)
                    d.net_sent_rate = max(0.0, (now_io.bytes_sent - self._prev_net_io.bytes_sent) / dt)
                    # daily totals
                    today = date.today()
                    if today != self._net_today_date:
                        self._net_today_date = today
                        self._net_today_recv = 0.0
                        self._net_today_sent = 0.0
                    self._net_today_recv += max(0, now_io.bytes_recv - self._prev_net_io.bytes_recv)
                    self._net_today_sent += max(0, now_io.bytes_sent - self._prev_net_io.bytes_sent)
                    d.net_recv_today = self._net_today_recv
                    d.net_sent_today = self._net_today_sent
            self._prev_net_io = now_io
            self._prev_net_t  = now_t
            # Normalize rate to 0–100 scale for sparkline (cap at 100 MB/s)
            d.net_recv_hist.append(min(100.0, d.net_recv_rate / 1_000_000))
            d.net_sent_hist.append(min(100.0, d.net_sent_rate / 1_000_000))
        except Exception:
            d.net_recv_hist.append(0.0)
            d.net_sent_hist.append(0.0)

    def _poll_net_procs(self, d: Metrics):
        try:
            conns = psutil.net_connections(kind="inet")
            pid_conns: Dict[int, int] = {}
            for c in conns:
                if c.pid and c.status in ("ESTABLISHED", "CLOSE_WAIT"):
                    pid_conns[c.pid] = pid_conns.get(c.pid, 0) + 1
            result = []
            for pid, cnt in sorted(pid_conns.items(), key=lambda x: -x[1])[:12]:
                try:
                    p = psutil.Process(pid)
                    result.append({"pid": pid, "name": p.name(), "conns": cnt})
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            d.net_top_procs = result
        except Exception:
            pass

    # ── Startup apps ──────────────────────────────────────────────
    def _read_startup(self) -> List[Dict]:
        return _read_startup_apps()

    # ── Alerts ────────────────────────────────────────────────────
    def _check_alerts(self):
        d = self.data
        def once(key, title, msg):
            if key not in self._alerted:
                self._alerted.add(key)
                self.sig_alert.emit(title, msg)
                _play_alert()
        def clr(key): self._alerted.discard(key)

        if d.cpu_temp and d.cpu_temp >= CFG.warn_temp:
            once("ct", "CPU Temp Warning", f"CPU {d.cpu_temp:.0f}°C exceeds {CFG.warn_temp}°C")
        elif d.cpu_temp: clr("ct")

        if d.gpu_temp and d.gpu_temp >= CFG.warn_temp:
            once("gt", "GPU Temp Warning", f"GPU {d.gpu_temp:.0f}°C exceeds {CFG.warn_temp}°C")
        elif d.gpu_temp: clr("gt")

        if d.cpu_pct >= CFG.warn_cpu_pct:
            once("cp", "High CPU Usage", f"CPU usage {d.cpu_pct:.0f}% exceeds {CFG.warn_cpu_pct}%")
        else: clr("cp")

        if d.gpu_pct >= CFG.warn_gpu_pct:
            once("gp", "High GPU Usage", f"GPU usage {d.gpu_pct:.0f}% exceeds {CFG.warn_gpu_pct}%")
        else: clr("gp")

        if d.ram_pct >= CFG.warn_ram_pct:
            once("rp", "High RAM Usage", f"RAM usage {d.ram_pct:.0f}% exceeds {CFG.warn_ram_pct}%")
        else: clr("rp")

        for dr in d.drives:
            free = 100 - dr["pct"]; k = f"dk_{dr['mount']}"
            if free <= CFG.warn_disk:
                once(k, "Low Disk Space", f"{dr['mount']} only {free:.0f}% free ({dr['free']:.1f} GB)")
            else: clr(k)



# ══════════════════════════════════════════════════════════════════
# ANIMATION HELPER  — shared 30fps driver, no per-widget QTimers
# ══════════════════════════════════════════════════════════════════
class _Tween:
    """Animation helper. Registers with _AnimDriver instead of owning a QTimer.
    Eliminates the main source of idle CPU: dozens of 60fps timers."""

    def __init__(self, callback, duration_ms: int, parent=None):
        self._cb   = callback
        self._dur  = max(1, duration_ms) / 1000.0
        self._start = 0.0; self._end = 0.0; self._t0 = 0.0
        self._running = False

    def animate(self, start: float, end: float):
        if abs(end - start) < 0.05:
            self._cb(end); return
        self._start = float(start); self._end = float(end)
        self._t0 = time.monotonic()
        if not self._running:
            self._running = True
            _AnimDriver.get().register(self)

    def stop(self):
        self._running = False

    def _step(self) -> bool:
        """Advance one frame. Returns True when complete."""
        if not self._running:
            return True
        t = min(1.0, (time.monotonic() - self._t0) / self._dur)
        eased = 1.0 - (1.0 - t) ** 3
        self._cb(self._start + (self._end - self._start) * eased)
        if t >= 1.0:
            self._running = False
            return True
        return False


class _AnimDriver(QObject):
    """Single 33ms QTimer that drives all active _Tween objects (~30fps).
    One timer instead of one-per-widget reduces idle CPU from ~80% to <5%."""
    _inst: Optional['_AnimDriver'] = None

    @classmethod
    def get(cls) -> '_AnimDriver':
        if cls._inst is None:
            cls._inst = _AnimDriver()
        return cls._inst

    def __init__(self):
        super().__init__()
        self._active: List[_Tween] = []
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def register(self, tween: _Tween):
        if tween not in self._active:
            self._active.append(tween)
        if not self._timer.isActive():
            self._timer.start()

    def _tick(self):
        still: List[_Tween] = []
        for t in self._active:
            try:
                done = t._step()
            except RuntimeError:
                done = True   # underlying C++ widget was deleted mid-animation
            if not done:
                still.append(t)
        self._active = still
        if not self._active:
            self._timer.stop()


# ══════════════════════════════════════════════════════════════════
# PAINTER WIDGETS
# ══════════════════════════════════════════════════════════════════
class Sparkline(QWidget):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._c = QColor(color)
        self._hist: deque = deque([0.0]*HIST, maxlen=HIST)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setMinimumSize(80, 38)

    def set_hist(self, hist: deque):
        self._hist = hist; self.update()

    def paintEvent(self, _):
        pts = list(self._hist); n = len(pts)
        if n < 2: return
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height(); pad = 2
        def pt(i, v):
            return QPointF(pad + i*(w-2*pad)/(n-1), h-pad-(v/100.0)*(h-2*pad))
        points = [pt(i, v) for i, v in enumerate(pts)]
        fill = QPainterPath()
        fill.moveTo(QPointF(points[0].x(), h))
        for pp in points: fill.lineTo(pp)
        fill.lineTo(QPointF(points[-1].x(), h)); fill.closeSubpath()
        grad = QLinearGradient(0, 0, 0, h)
        c1 = QColor(self._c); c1.setAlpha(70)
        c2 = QColor(self._c); c2.setAlpha(0)
        grad.setColorAt(0, c1); grad.setColorAt(1, c2)
        p.setPen(Qt.PenStyle.NoPen); p.fillPath(fill, grad)
        pen = QPen(self._c, 1.8, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen); line = QPainterPath(); line.moveTo(points[0])
        for pp in points[1:]: line.lineTo(pp)
        p.drawPath(line); p.end()


class ThinBar(QWidget):
    def __init__(self, color: str, height: int = 4, parent=None):
        super().__init__(parent)
        self._color = color; self._disp = 0.0
        self.setFixedHeight(height)
        self._tween = _Tween(self._on_tween, ANIM_MS, self)

    def _on_tween(self, v: float):
        self._disp = v; self.update()

    def set_pct(self, pct: float):
        self._tween.animate(self._disp, max(0.0, min(100.0, pct)))

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()); h = r.height(); rr = h/2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C["b0"])); p.drawRoundedRect(r, rr, rr)
        fw = r.width() * self._disp / 100.0
        if fw > 0:
            p.setBrush(QColor(pct_color(self._disp)))
            p.drawRoundedRect(QRectF(0, 0, fw, h), rr, rr)
        p.end()


class CircleGauge(QWidget):
    def __init__(self, color: str, size: int = 100, parent=None):
        super().__init__(parent)
        self._color = color; self._disp = 0.0
        self.setFixedSize(size, size)
        self._tween = _Tween(self._on_tween, ANIM_MS, self)

    def _on_tween(self, v: float):
        self._disp = v; self.update()

    def set_pct(self, pct: float):
        self._tween.animate(self._disp, max(0.0, min(100.0, pct)))

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height(); m = 8
        rect = QRectF(m, m, w-2*m, h-2*m)
        clr = QColor(pct_color(self._disp))
        pen = QPen(QColor(C["b0"]), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
        p.setPen(pen); p.drawArc(rect, 0, 360*16)
        if self._disp > 0:
            pen.setColor(clr); pen.setWidth(7)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen)
            p.drawArc(rect, 90*16, int(-self._disp/100.0*360*16))
        font = QFont(); font.setPointSize(w//8); font.setBold(True)
        p.setFont(font); p.setPen(QPen(clr))
        p.drawText(rect.toRect(), Qt.AlignmentFlag.AlignCenter, f"{self._disp:.0f}%")
        p.end()


class AnimFloat(QLabel):
    def __init__(self, fmt: str = "{:.1f}%", style: str = "", parent=None):
        super().__init__("—", parent)
        self._fmt = fmt; self._val = 0.0
        if style: self.setStyleSheet(style)
        self._tween = _Tween(self._on_tween, ANIM_MS, self)

    def _on_tween(self, v: float):
        self._val = v
        self.setText(self._fmt.format(v))

    def animate_to(self, value: float):
        self._tween.animate(self._val, float(value))


class BigChart(QWidget):
    _Y_LABELS = [0, 25, 50, 75, 100]

    def __init__(self, color: str, ylabel: str = "%", parent=None):
        super().__init__(parent)
        self._color = QColor(color); self._ylabel = ylabel
        self._hist: deque = deque([0.0]*HIST, maxlen=HIST)
        self.setMinimumSize(120, 80)

    def update_hist(self, hist: deque):
        self._hist = hist; self.update()

    def paintEvent(self, _):
        pts = list(self._hist); n = len(pts)
        if n < 2: return
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        lm, rm, tm, bm = 36, 8, 6, 22
        cw, ch = w-lm-rm, h-tm-bm
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(C["bg2"])); p.drawRect(self.rect())
        grid_pen = QPen(QColor(C["b0"]), 1)
        lbl_font = QFont(); lbl_font.setPointSize(8); p.setFont(lbl_font)
        for yv in self._Y_LABELS:
            gy = tm+ch-int(yv/100.0*ch)
            p.setPen(grid_pen); p.drawLine(lm, gy, lm+cw, gy)
            p.setPen(QPen(QColor(C["t2"])))
            p.drawText(QRect(0, gy-8, lm-4, 16),
                       Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter, str(yv))
        p.save(); p.setPen(QPen(QColor(C["t2"]))); p.setFont(lbl_font)
        p.translate(10, tm+ch//2); p.rotate(-90)
        p.drawText(QRect(-30, -8, 60, 16), Qt.AlignmentFlag.AlignCenter, self._ylabel)
        p.restore()
        def pt(i, v):
            return QPointF(lm + i*cw/(n-1), tm+ch - v/100.0*ch)
        points = [pt(i, v) for i, v in enumerate(pts)]
        fill = QPainterPath(); fill.moveTo(QPointF(points[0].x(), tm+ch))
        for pp in points: fill.lineTo(pp)
        fill.lineTo(QPointF(points[-1].x(), tm+ch)); fill.closeSubpath()
        grad = QLinearGradient(0, tm, 0, tm+ch)
        tc = QColor(self._color); tc.setAlpha(45)
        bc = QColor(self._color); bc.setAlpha(0)
        grad.setColorAt(0, tc); grad.setColorAt(1, bc)
        p.setPen(Qt.PenStyle.NoPen); p.fillPath(fill, grad)
        glow_c = QColor(self._color); glow_c.setAlpha(28)
        p.setPen(QPen(glow_c, 8, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        gp = QPainterPath(); gp.moveTo(points[0])
        for pp in points[1:]: gp.lineTo(pp)
        p.drawPath(gp)
        p.setPen(QPen(self._color, 2, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        lp = QPainterPath(); lp.moveTo(points[0])
        for pp in points[1:]: lp.lineTo(pp)
        p.drawPath(lp)
        p.setPen(QPen(QColor(C["b0"]), 1)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(lm, tm, cw, ch); p.end()


# ══════════════════════════════════════════════════════════════════
# CARD / SHARED WIDGETS
# ══════════════════════════════════════════════════════════════════
def _card_style() -> str:
    return f"background-color:{C['bg2']}; border:1px solid {C['b0']}; border-radius:10px;"

def _card(parent=None) -> QFrame:
    f = QFrame(parent)
    f.setObjectName("card")
    return f


class MetricCard(QFrame):
    def __init__(self, title: str, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self.setObjectName("card")
        self.setMinimumSize(200, 148)
        root = QVBoxLayout(self); root.setContentsMargins(16,14,16,14); root.setSpacing(6)
        hdr = QHBoxLayout(); hdr.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{color}; font-size:9px; background:transparent; border:none;")
        self._title_lbl = QLabel(title.upper())
        self._title_lbl.setStyleSheet(f"color:{C['t2']}; font-size:10px; font-weight:600;"
                          f" letter-spacing:1.5px; background:transparent; border:none;")
        hdr.addWidget(dot); hdr.addWidget(self._title_lbl); hdr.addStretch()
        root.addLayout(hdr)
        mid = QHBoxLayout(); mid.setSpacing(8)
        vcol = QVBoxLayout(); vcol.setSpacing(1)
        self._val = AnimFloat("{:.1f}%", style=(
            f"color:{C['t1']}; font-size:26px; font-weight:700;"
            f" background:transparent; border:none;"))
        self._sub = QLabel("")
        self._sub.setStyleSheet(f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")
        vcol.addWidget(self._val); vcol.addWidget(self._sub); vcol.addStretch()
        self._spark = Sparkline(color)
        mid.addLayout(vcol, 2); mid.addWidget(self._spark, 3)
        root.addLayout(mid)
        self._bar = ThinBar(color, 4)
        root.addWidget(self._bar)

    def refresh(self, pct: float, sub: str, hist: deque):
        self._val.animate_to(pct); self._sub.setText(sub)
        self._bar.set_pct(pct); self._spark.set_hist(hist)

    def refresh_theme(self):
        self._title_lbl.setStyleSheet(
            f"color:{C['t2']}; font-size:10px; font-weight:600;"
            f" letter-spacing:1.5px; background:transparent; border:none;")
        self._val.setStyleSheet(
            f"color:{C['t1']}; font-size:26px; font-weight:700;"
            f" background:transparent; border:none;")
        self._sub.setStyleSheet(
            f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")


class CoreBar(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self); row.setContentsMargins(0,2,0,2); row.setSpacing(10)
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")
        self._lbl.setFixedWidth(54)
        self._bar = ThinBar(C["cpu"], 8)
        self._pct = QLabel("0%")
        self._pct.setStyleSheet(f"color:{C['t1']}; font-size:11px; background:transparent; border:none;")
        self._pct.setFixedWidth(36)
        row.addWidget(self._lbl); row.addWidget(self._bar, 1); row.addWidget(self._pct)

    def refresh(self, pct: float):
        self._bar.set_pct(pct); c = pct_color(pct)
        self._pct.setText(f"{pct:.0f}%")
        self._pct.setStyleSheet(f"color:{c}; font-size:11px; background:transparent; border:none;")


class DriveCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        root = QVBoxLayout(self); root.setContentsMargins(16,14,16,14); root.setSpacing(8)
        top = QHBoxLayout()
        self._name = QLabel("—")
        self._name.setStyleSheet(f"color:{C['t1']}; font-size:14px; font-weight:600; background:transparent; border:none;")
        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setStyleSheet(f"color:{C['grn']}; font-size:20px; font-weight:700; background:transparent; border:none;")
        top.addWidget(self._name); top.addStretch(); top.addWidget(self._pct_lbl)
        root.addLayout(top)
        self._size_lbl = QLabel("0 GB / 0 GB")
        self._size_lbl.setStyleSheet(f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")
        root.addWidget(self._size_lbl)
        self._bar = ThinBar(C["disk"], 10); root.addWidget(self._bar)
        bot = QHBoxLayout()
        self._fs = QLabel("NTFS"); self._free = QLabel("Free: 0 GB")
        for w2 in (self._fs, self._free):
            w2.setStyleSheet(f"color:{C['t3']}; font-size:10px; background:transparent; border:none;")
        bot.addWidget(self._fs); bot.addStretch(); bot.addWidget(self._free)
        root.addLayout(bot)

    def refresh(self, d: Dict):
        pct = d["pct"]; free = 100 - pct
        clr = C["red"] if free < 10 else C["amb"] if free < 25 else C["grn"]
        self._name.setText(f"{d['mount']}  ·  {d['fs']}")
        self._pct_lbl.setText(f"{pct:.0f}%")
        self._pct_lbl.setStyleSheet(f"color:{clr}; font-size:20px; font-weight:700; background:transparent; border:none;")
        self._size_lbl.setText(f"Used: {fmt_gb(d['used'])}  /  Total: {fmt_gb(d['total'])}")
        self._bar.set_pct(pct); self._free.setText(f"Free: {fmt_gb(d['free'])}")
        self._fs.setText(d["fs"])

    def refresh_theme(self):
        self._name.setStyleSheet(f"color:{C['t1']}; font-size:14px; font-weight:600; background:transparent; border:none;")
        self._size_lbl.setStyleSheet(f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")
        for w2 in (self._fs, self._free):
            w2.setStyleSheet(f"color:{C['t3']}; font-size:10px; background:transparent; border:none;")


class FanCard(QFrame):
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
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
        nl = QLabel(name); nl.setStyleSheet(f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")
        nl.setWordWrap(True); root.addWidget(nl)

    def refresh(self, rpm: float):
        self._rpm.setText(f"{rpm:,.0f} RPM")
        c = C["amb"] if rpm > 3000 else C["grn"]
        self._rpm.setStyleSheet(f"color:{c}; font-size:22px; font-weight:700; background:transparent; border:none;")


# ══════════════════════════════════════════════════════════════════
# SHARED TABLE / SECTION HELPERS
# ══════════════════════════════════════════════════════════════════
class DarkTable(QTableWidget):
    """QTableWidget with theme-aware styling that updates when the theme changes."""
    _instances: List[weakref.ref] = []

    @classmethod
    def _make_qss(cls) -> str:
        return (
            f"QTableWidget {{ background:{C['bg2']}; color:{C['t1']}; border:1px solid {C['b0']};"
            f" border-radius:8px; font-size:12px; gridline-color:{C['b0']}; outline:none;"
            f" selection-background-color:{C['bg3']}; selection-color:{C['t1']}; }}"
            f"QTableWidget::item {{ background:{C['bg2']}; color:{C['t1']}; padding:5px 10px; border:none; }}"
            f"QTableWidget::item:hover {{ background:{C['bg3']}; }}"
            f"QTableWidget::item:selected {{ background:{C['bg3']}; color:{C['t1']}; }}"
            f"QHeaderView {{ background:{C['bg1']}; border:none; }}"
            f"QHeaderView::section {{ background:{C['bg1']}; color:{C['t2']}; font-size:10px;"
            f" font-weight:700; letter-spacing:1.2px; padding:8px 10px; border:none;"
            f" border-bottom:1px solid {C['b0']}; }}"
            f"QScrollBar:vertical {{ background:{C['bg1']}; width:6px; border-radius:3px; }}"
            f"QScrollBar::handle:vertical {{ background:{C['b1']}; border-radius:3px; min-height:20px; }}"
            f"QScrollBar::handle:vertical:hover {{ background:{C['acc']}; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}"
        )

    @classmethod
    def refresh_all(cls):
        alive = []
        for ref in cls._instances:
            t = ref()
            if t is not None:
                t._apply_qss()
                alive.append(ref)
        cls._instances = alive

    def _apply_qss(self):
        self.setStyleSheet(self._make_qss())
        self.viewport().setStyleSheet(f"background:{C['bg2']}; color:{C['t1']};")

    def __init__(self, rows: int = 0, cols: int = 0, parent=None):
        super().__init__(rows, cols, parent)
        DarkTable._instances.append(weakref.ref(self))
        self._apply_qss()


def styled_table(cols: List[str], col_widths: List[int] = None) -> DarkTable:
    t = DarkTable(0, len(cols))
    t.setHorizontalHeaderLabels(cols)
    t.verticalHeader().setVisible(False)
    t.setShowGrid(False); t.setAlternatingRowColors(False)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    hh = t.horizontalHeader()
    if col_widths:
        for i, w2 in enumerate(col_widths):
            if w2 == -1: hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:         t.setColumnWidth(i, w2)
    else:
        hh.setStretchLastSection(True)
    return t


def section_header(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("sectionHeader")
    lbl.setStyleSheet(f"font-size:18px; font-weight:700;"
                      f" padding-bottom:2px; background:transparent; border:none;"
                      f" border-bottom:2px solid {C['acc']};")
    return lbl


def section_sub(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("sectionSub")
    lbl.setStyleSheet("font-size:11px; background:transparent; border:none;")
    return lbl


def _stat_card(title: str, attr_name: str, owner) -> QFrame:
    card = _card(); cl = QVBoxLayout(card); cl.setContentsMargins(16,14,16,14); cl.setSpacing(4)
    tl = QLabel(title.upper())
    tl.setStyleSheet(f"color:{C['t2']}; font-size:10px; font-weight:600; letter-spacing:1.2px; background:transparent; border:none;")
    vl = QLabel("—")
    vl.setStyleSheet(f"color:{C['t1']}; font-size:22px; font-weight:700; background:transparent; border:none;")
    cl.addWidget(tl); cl.addWidget(vl); cl.addStretch()
    setattr(owner, attr_name, vl)
    return card


# ══════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════
class DashboardPage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:transparent;")
        inner = QWidget(); self.setWidget(inner)
        self._root = QVBoxLayout(inner)
        self._root.setContentsMargins(28,24,28,24); self._root.setSpacing(20)
        self._root.addWidget(section_header("Dashboard"))
        self._root.addWidget(section_sub("Real-time system overview"))

        # metric cards
        self._cards_row = QHBoxLayout(); self._cards_row.setSpacing(14)
        self._cpu_card  = MetricCard("CPU",    C["cpu"])
        self._gpu_card  = MetricCard("GPU",    C["gpu"])
        self._ram_card  = MetricCard("Memory", C["ram"])
        for card in (self._cpu_card, self._gpu_card, self._ram_card):
            self._cards_row.addWidget(card, 1)
        self._cards_widget = QWidget(); self._cards_widget.setStyleSheet("background:transparent;")
        self._cards_widget.setLayout(self._cards_row)
        self._root.addWidget(self._cards_widget)

        # charts
        self._charts_widget = QWidget(); self._charts_widget.setStyleSheet("background:transparent;")
        charts_row = QHBoxLayout(self._charts_widget); charts_row.setSpacing(14)
        for title, color, attr in (("CPU Usage", C["cpu"], "_cpu_chart"),
                                    ("Memory Usage", C["ram"], "_ram_chart")):
            box = _card(); bl = QVBoxLayout(box); bl.setContentsMargins(14,12,14,12); bl.setSpacing(8)
            lbl2 = QLabel(title); lbl2.setObjectName("chartTitle")
            bl.addWidget(lbl2)
            chart = BigChart(color); chart.setMinimumHeight(120)
            setattr(self, attr, chart); bl.addWidget(chart)
            charts_row.addWidget(box, 1)
        self._root.addWidget(self._charts_widget)

        # drives
        self._drives_hdr = section_header("Drive Space")
        self._root.addWidget(self._drives_hdr)
        self._drives_container = QWidget(); self._drives_container.setStyleSheet("background:transparent;")
        self._drives_grid = QGridLayout(self._drives_container); self._drives_grid.setSpacing(12)
        self._drive_cards: List[DriveCard] = []
        self._root.addWidget(self._drives_container)

        # status strip
        self._stats_bar = QFrame()
        self._stats_bar.setObjectName("card")
        sb = QHBoxLayout(self._stats_bar); sb.setContentsMargins(20,10,20,10); sb.setSpacing(0)
        self._stat_labels: Dict[str, QLabel] = {}
        for key in ("uptime", "cpu_name", "timestamp"):
            lbl3 = QLabel("—")
            lbl3.setStyleSheet(f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")
            self._stat_labels[key] = lbl3; sb.addWidget(lbl3)
            if key != "timestamp":
                sep = QLabel("  ·  ")
                sep.setStyleSheet(f"color:{C['t3']}; background:transparent; border:none;")
                sb.addWidget(sep)
        sb.addStretch()
        self._root.addWidget(self._stats_bar)
        self._root.addStretch()

    def apply_visibility(self):
        self._cards_widget.setVisible(bool(CFG.dash_cpu or CFG.dash_gpu or CFG.dash_ram))
        self._cpu_card.setVisible(bool(CFG.dash_cpu))
        self._gpu_card.setVisible(bool(CFG.dash_gpu))
        self._ram_card.setVisible(bool(CFG.dash_ram))
        self._charts_widget.setVisible(bool(CFG.dash_charts))
        self._drives_hdr.setVisible(bool(CFG.dash_drives))
        self._drives_container.setVisible(bool(CFG.dash_drives))
        inner = self.widget()
        if inner:
            inner.adjustSize()
            inner.updateGeometry()

    def update(self, m: Metrics):
        self.apply_visibility()
        temp_str = f"{m.cpu_temp:.0f}°C  ·  " if m.cpu_temp else ""
        self._cpu_card.refresh(m.cpu_pct, f"{temp_str}{m.cpu_freq:.0f} MHz", m.cpu_hist)
        g_temp = f"{m.gpu_temp:.0f}°C  ·  " if m.gpu_temp else ""
        g_vram = f"{m.gpu_vram_u:.1f}/{m.gpu_vram_t:.1f} GB VRAM" if m.gpu_vram_t else ""
        self._gpu_card.refresh(m.gpu_pct, f"{g_temp}{g_vram}" or m.gpu_name, m.gpu_hist)
        self._ram_card.refresh(m.ram_pct, f"{fmt_gb(m.ram_used)} / {fmt_gb(m.ram_total)}", m.ram_hist)
        self._cpu_chart.update_hist(m.cpu_hist)
        self._ram_chart.update_hist(m.ram_hist)
        if len(m.drives) != len(self._drive_cards):
            for i in reversed(range(self._drives_grid.count())):
                w2 = self._drives_grid.itemAt(i).widget()
                if w2: self._drives_grid.removeWidget(w2); w2.deleteLater()
            self._drive_cards.clear()
            for idx, dr in enumerate(m.drives):
                dc = DriveCard(); self._drive_cards.append(dc)
                self._drives_grid.addWidget(dc, idx//3, idx%3)
        for card, dr in zip(self._drive_cards, m.drives):
            card.refresh(dr)
        cpu_short = _CPU_PROC_NAME[:48]+"…" if len(_CPU_PROC_NAME) > 50 else _CPU_PROC_NAME
        self._stat_labels["uptime"].setText(f"Uptime: {fmt_uptime(m.uptime)}")
        self._stat_labels["cpu_name"].setText(cpu_short)
        self._stat_labels["timestamp"].setText(datetime.now().strftime("%d %b %Y  %H:%M:%S"))

    def refresh_theme(self):
        for card in (self._cpu_card, self._gpu_card, self._ram_card):
            card.refresh_theme()
        for dc in self._drive_cards:
            dc.refresh_theme()
        for lbl in self._stat_labels.values():
            lbl.setStyleSheet(f"color:{C['t2']}; font-size:11px; background:transparent; border:none;")


# ══════════════════════════════════════════════════════════════════
# PAGE: CPU
# ══════════════════════════════════════════════════════════════════
class CpuPage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:transparent;")
        inner = QWidget(); self.setWidget(inner)
        root = QVBoxLayout(inner); root.setContentsMargins(28,24,28,24); root.setSpacing(18)
        root.addWidget(section_header("CPU"))
        root.addWidget(section_sub("Processor utilisation and thermal status"))
        stats_row = QHBoxLayout(); stats_row.setSpacing(12)
        for attr, title in (("_usage_card","Usage"),("_temp_card","Temperature"),
                            ("_freq_card","Frequency"),("_cores_card","Cores")):
            card = _stat_card(title, attr, self)
            if attr == "_temp_card": self._temp_card_frame = card
            stats_row.addWidget(card, 1)
        root.addLayout(stats_row)
        chart_card = _card(); ccl = QVBoxLayout(chart_card); ccl.setContentsMargins(14,12,14,12); ccl.setSpacing(8)
        lbl2 = QLabel("CPU Usage History"); lbl2.setObjectName("chartTitle")
        ccl.addWidget(lbl2)
        self._chart = BigChart(C["cpu"]); self._chart.setMinimumHeight(160); ccl.addWidget(self._chart)
        root.addWidget(chart_card)
        core_card = _card(); ccl2 = QVBoxLayout(core_card); ccl2.setContentsMargins(16,14,16,14); ccl2.setSpacing(4)
        hl = QLabel("Per-Core Usage"); hl.setObjectName("chartTitle")
        ccl2.addWidget(hl)
        self._core_grid = QGridLayout(); self._core_grid.setSpacing(6); ccl2.addLayout(self._core_grid)
        root.addWidget(core_card); root.addStretch()
        self._core_bars: List[CoreBar] = []

    def _vs(self, color): return f"color:{color}; font-size:22px; font-weight:700; background:transparent; border:none;"

    def update(self, m: Metrics):
        self._usage_card.setText(f"{m.cpu_pct:.1f}%")
        self._usage_card.setStyleSheet(self._vs(pct_color(m.cpu_pct)))
        if m.cpu_temp is not None:
            self._temp_card.setText(f"{m.cpu_temp:.0f} °C")
            self._temp_card.setStyleSheet(self._vs(temp_color(m.cpu_temp)))
            self._temp_card.setToolTip(""); self._temp_card_frame.setToolTip("")
        else:
            self._temp_card.setText("ⓘ  Unavailable")
            self._temp_card.setStyleSheet(f"color:{C['t2']}; font-size:13px; font-weight:600; background:transparent; border:none;")
            tip = ("CPU temperature unavailable.\n\nTo enable: install LibreHardwareMonitor "
                   "and run it as a service, or run PulseMonitor as Administrator.")
            self._temp_card.setToolTip(tip); self._temp_card_frame.setToolTip(tip)
        self._freq_card.setText(f"{m.cpu_freq:,.0f} MHz")
        self._freq_card.setStyleSheet(self._vs(C["blue"]))
        self._cores_card.setText(str(len(m.cpu_cores)))
        self._cores_card.setStyleSheet(self._vs(C["t1"]))
        self._chart.update_hist(m.cpu_hist)
        if len(m.cpu_cores) != len(self._core_bars):
            for i in reversed(range(self._core_grid.count())):
                w2 = self._core_grid.itemAt(i).widget()
                if w2: self._core_grid.removeWidget(w2); w2.deleteLater()
            self._core_bars.clear()
            for idx, _ in enumerate(m.cpu_cores):
                cb = CoreBar(f"Core {idx}"); self._core_bars.append(cb)
                self._core_grid.addWidget(cb, idx//2, idx%2)
        for bar, pct in zip(self._core_bars, m.cpu_cores):
            bar.refresh(pct)


# ══════════════════════════════════════════════════════════════════
# PAGE: MEMORY
# ══════════════════════════════════════════════════════════════════
class MemoryPage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:transparent;")
        inner = QWidget(); self.setWidget(inner)
        root = QVBoxLayout(inner); root.setContentsMargins(28,24,28,24); root.setSpacing(18)
        root.addWidget(section_header("Memory"))
        root.addWidget(section_sub("RAM utilisation over time"))
        row = QHBoxLayout(); row.setSpacing(12)
        for attr, title in (("_pct_lbl","Usage"),("_used_lbl","Used"),
                            ("_total_lbl","Total"),("_free_lbl","Available")):
            row.addWidget(_stat_card(title, attr, self), 1)
        root.addLayout(row)
        mid = QHBoxLayout(); mid.setSpacing(14)
        gauge_card = _card(); gl = QVBoxLayout(gauge_card); gl.setContentsMargins(20,16,20,16); gl.setSpacing(8)
        gl.addStretch()
        self._gauge = CircleGauge(C["ram"], 140)
        gw = QHBoxLayout(); gw.addStretch(); gw.addWidget(self._gauge); gw.addStretch()
        gl.addLayout(gw); gl.addStretch()
        chart_card = _card(); ccl = QVBoxLayout(chart_card); ccl.setContentsMargins(14,12,14,12); ccl.setSpacing(8)
        lbl2 = QLabel("Memory Usage History"); lbl2.setObjectName("chartTitle")
        ccl.addWidget(lbl2)
        self._chart = BigChart(C["ram"]); self._chart.setMinimumHeight(160); ccl.addWidget(self._chart)
        mid.addWidget(gauge_card, 1); mid.addWidget(chart_card, 3)
        root.addLayout(mid); root.addStretch()

    def update(self, m: Metrics):
        clr = pct_color(m.ram_pct)
        vs = "font-size:22px; font-weight:700; background:transparent; border:none;"
        self._pct_lbl.setText(f"{m.ram_pct:.1f}%"); self._pct_lbl.setStyleSheet(f"color:{clr}; {vs}")
        self._used_lbl.setText(fmt_gb(m.ram_used)); self._used_lbl.setStyleSheet(f"color:{C['t1']}; {vs}")
        self._total_lbl.setText(fmt_gb(m.ram_total)); self._total_lbl.setStyleSheet(f"color:{C['t1']}; {vs}")
        free = m.ram_total - m.ram_used
        self._free_lbl.setText(fmt_gb(free)); self._free_lbl.setStyleSheet(f"color:{C['t1']}; {vs}")
        self._gauge.set_pct(m.ram_pct); self._chart.update_hist(m.ram_hist)


# ══════════════════════════════════════════════════════════════════
# PAGE: GPU
# ══════════════════════════════════════════════════════════════════
class GpuPage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:transparent;")
        inner = QWidget(); self.setWidget(inner)
        root = QVBoxLayout(inner); root.setContentsMargins(28,24,28,24); root.setSpacing(18)
        root.addWidget(section_header("GPU"))
        self._gpu_name_lbl = section_sub("Detecting GPU…"); root.addWidget(self._gpu_name_lbl)
        self._vendor_lbl = QLabel("")
        self._vendor_lbl.setStyleSheet(f"color:{C['acc']}; font-size:11px; background:transparent; border:none;")
        root.addWidget(self._vendor_lbl)
        row = QHBoxLayout(); row.setSpacing(12)
        for attr, title in (("_load_lbl","Load"),("_temp_lbl","Temperature"),
                            ("_vram_lbl","VRAM Used"),("_vram_t_lbl","VRAM Total")):
            row.addWidget(_stat_card(title, attr, self), 1)
        root.addLayout(row)
        chart_card = _card(); ccl = QVBoxLayout(chart_card); ccl.setContentsMargins(14,12,14,12); ccl.setSpacing(8)
        lbl2 = QLabel("GPU Load History"); lbl2.setObjectName("chartTitle")
        ccl.addWidget(lbl2)
        self._chart = BigChart(C["gpu"]); self._chart.setMinimumHeight(160); ccl.addWidget(self._chart)
        root.addWidget(chart_card)
        self._notice = QLabel("")
        self._notice.setStyleSheet(f"color:{C['t2']}; font-size:12px; background:{C['bg2']};"
                                    f" border:1px solid {C['b0']}; border-radius:8px; padding:16px;")
        self._notice.setWordWrap(True); root.addWidget(self._notice)
        root.addStretch()

    def _vs(self, color): return f"color:{color}; font-size:22px; font-weight:700; background:transparent; border:none;"

    def update(self, m: Metrics):
        self._gpu_name_lbl.setText(m.gpu_name or "—")
        vendor_map = {"nvidia": "NVIDIA (nvidia-smi)", "amd": "AMD (WMI Perf Counters)",
                      "intel": "Intel (WMI Perf Counters)", "unknown": "No GPU detected"}
        self._vendor_lbl.setText(vendor_map.get(m.gpu_vendor, ""))
        self._load_lbl.setText(f"{m.gpu_pct:.1f}%"); self._load_lbl.setStyleSheet(self._vs(pct_color(m.gpu_pct)))
        if m.gpu_temp:
            self._temp_lbl.setText(f"{m.gpu_temp:.0f} °C"); self._temp_lbl.setStyleSheet(self._vs(temp_color(m.gpu_temp)))
        else:
            self._temp_lbl.setText("N/A"); self._temp_lbl.setStyleSheet(self._vs(C["t2"]))
        self._vram_lbl.setText(fmt_gb(m.gpu_vram_u) if m.gpu_vram_u else "N/A")
        self._vram_lbl.setStyleSheet(self._vs(C["t1"]))
        self._vram_t_lbl.setText(fmt_gb(m.gpu_vram_t) if m.gpu_vram_t else "N/A")
        self._vram_t_lbl.setStyleSheet(self._vs(C["t1"]))
        self._chart.update_hist(m.gpu_hist)
        if m.gpu_vendor == "unknown":
            self._notice.setText("No GPU detected. NVIDIA, AMD Radeon, and Intel graphics are supported.")
            self._notice.show()
        elif m.gpu_vendor in ("amd", "intel") and m.gpu_temp is None:
            self._notice.setText(
                f"Temperature monitoring for {m.gpu_vendor.upper()} GPUs requires LibreHardwareMonitor "
                "running as a service. Install LHM and enable its WMI provider to see GPU temperatures.")
            self._notice.show()
        else:
            self._notice.hide()


# ══════════════════════════════════════════════════════════════════
# PAGE: STORAGE
# ══════════════════════════════════════════════════════════════════
class StoragePage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:transparent;")
        inner = QWidget(); self.setWidget(inner)
        root = QVBoxLayout(inner); root.setContentsMargins(28,24,28,24); root.setSpacing(18)
        root.addWidget(section_header("Storage"))
        root.addWidget(section_sub("Disk space and filesystem health"))
        self._grid = QGridLayout(); self._grid.setSpacing(14); root.addLayout(self._grid)
        root.addStretch()
        self._cards: List[DriveCard] = []; self._prev = None

    def update(self, m: Metrics):
        if m.drives is self._prev: return
        self._prev = m.drives
        if len(m.drives) != len(self._cards):
            for i in reversed(range(self._grid.count())):
                w2 = self._grid.itemAt(i).widget()
                if w2: self._grid.removeWidget(w2); w2.deleteLater()
            self._cards.clear()
            for idx, dr in enumerate(m.drives):
                dc = DriveCard(); self._cards.append(dc)
                self._grid.addWidget(dc, idx//2, idx%2)
        for card, dr in zip(self._cards, m.drives):
            card.refresh(dr)

    def refresh_theme(self):
        for dc in self._cards:
            dc.refresh_theme()


_CRITICAL_PROCS = frozenset({
    "svchost.exe", "lsass.exe", "winlogon.exe", "csrss.exe",
    "smss.exe", "wininit.exe", "services.exe", "system", "registry",
})

# ══════════════════════════════════════════════════════════════════
# PAGE: PROCESSES
# ══════════════════════════════════════════════════════════════════
class ProcessPage(QWidget):
    def __init__(self):
        super().__init__()
        self._prev = None
        root = QVBoxLayout(self); root.setContentsMargins(28,24,28,24); root.setSpacing(14)
        root.addWidget(section_header("Processes"))
        root.addWidget(section_sub("Running processes sorted by CPU usage  (top 100)"))
        self._table = styled_table(["PID","Process Name","CPU %","Memory %","Status"],
                                   [70,-1,90,100,100])
        self._table.setMinimumHeight(400); root.addWidget(self._table)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)

    def _on_context_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0: return
        pid_item  = self._table.item(row, 0)
        name_item = self._table.item(row, 1)
        if not pid_item or not name_item: return
        pid  = int(pid_item.text())
        name = name_item.text()
        menu = QMenu(self._table)
        end_action = menu.addAction("End Task")
        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == end_action:
            if name.lower() in _CRITICAL_PROCS:
                reply = QMessageBox.warning(
                    self, "End Task",
                    f"Warning: Ending system processes may cause instability or data loss.\n\n"
                    f"Are you sure you want to end \"{name}\"?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
            else:
                reply = QMessageBox.question(
                    self, "End Task",
                    f"End \"{name}\"?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    psutil.Process(pid).kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    QMessageBox.warning(self, "Error",
                        f"Could not end \"{name}\":\n{e}")

    def update(self, m: Metrics):
        if m.procs is self._prev: return
        self._prev = m.procs
        self._table.setUpdatesEnabled(False)
        old_count = self._table.rowCount()
        new_count = len(m.procs)
        self._table.setRowCount(new_count)
        for row, proc in enumerate(m.procs):
            items_data = [
                (str(proc["pid"]),      C["t2"],
                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                (proc["name"],          C["t1"],
                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                (f"{proc['cpu']:.1f}",  pct_color(proc["cpu"]) if proc["cpu"] > 0 else C["t2"],
                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                (f"{proc['mem']:.1f}",  C["t2"],
                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                (proc["status"],        C["t2"],
                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            ]
            for col, (text, color, align) in enumerate(items_data):
                item = self._table.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    self._table.setItem(row, col, item)
                if item.text() != text:
                    item.setText(text)
                new_color = QColor(color)
                if item.foreground().color() != new_color:
                    item.setForeground(new_color)
                item.setTextAlignment(align)
            if row >= old_count:
                self._table.setRowHeight(row, 30)
        self._table.setUpdatesEnabled(True)


# ══════════════════════════════════════════════════════════════════
# PAGE: STARTUP
# ══════════════════════════════════════════════════════════════════
class StartupPage(QWidget):
    def __init__(self):
        super().__init__()
        self._apps: List[Dict] = []
        root = QVBoxLayout(self); root.setContentsMargins(28,24,28,24); root.setSpacing(14)
        root.addWidget(section_header("Startup Programs"))
        root.addWidget(section_sub("Applications registered to launch at Windows startup"))
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        btn_row.addStretch()
        self._add_btn = QPushButton("＋  Add to Startup")
        self._add_btn.setFixedHeight(32)
        self._add_btn.setStyleSheet(
            f"QPushButton {{ background:{C['acc']}; color:#000; border:none; border-radius:6px;"
            f" font-size:12px; font-weight:600; padding:0 16px; }}"
            f"QPushButton:hover {{ background:{C['acc2']}; color:#fff; }}")
        self._add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(self._add_btn)
        root.addLayout(btn_row)
        self._table = styled_table(["Name","Registry Scope","Command / Path"],[200,110,-1])
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        root.addWidget(self._table)

    def update(self, m: Metrics):
        self._apps = list(m.startup)
        self._fill_table(self._apps)

    def _fill_table(self, apps: List[Dict]):
        self._table.setUpdatesEnabled(False)
        self._table.setRowCount(len(apps))
        for row, app in enumerate(apps):
            for col, (text, color) in enumerate([
                (app["name"],  C["t1"]),(app["scope"], C["acc"]),(app["path"],C["t2"])]):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft)
                self._table.setItem(row, col, item)
            self._table.setRowHeight(row, 30)
        self._table.setUpdatesEnabled(True)

    def _refresh(self):
        self._apps = _read_startup_apps()
        self._fill_table(self._apps)

    def _on_context_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._apps): return
        app = self._apps[row]
        menu = QMenu(self._table)
        remove_action = menu.addAction("Remove from Startup")
        if app["scope"] == "HKLM":
            remove_action.setEnabled(False)
            remove_action.setText("Remove from Startup  (requires admin)")
        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == remove_action:
            reply = QMessageBox.question(
                self, "Remove from Startup",
                f"Remove \"{app['name']}\" from startup?\nThis will delete the registry entry.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    k = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                                        0, _winreg.KEY_SET_VALUE)
                    _winreg.DeleteValue(k, app["name"])
                    _winreg.CloseKey(k)
                    self._refresh()
                    QMessageBox.information(
                        self, "Registry Entry Removed",
                        f"Registry entry removed.\n\n"
                        f"Note: This app may still launch via Windows Task Scheduler or a "
                        f"system service. Check Task Scheduler (taskschd.msc) if it continues "
                        f"to start automatically.",
                    )
                except OSError as e:
                    if getattr(e, "winerror", None) == 2:
                        self._refresh()
                        QMessageBox.information(self, "Already Removed",
                            f"Entry already removed successfully.")
                    else:
                        QMessageBox.warning(self, "Error", f"Could not remove entry:\n{e}")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not remove entry:\n{e}")

    def _on_add(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Application", "", "Executables (*.exe);;All Files (*)")
        if not path: return
        stem = os.path.splitext(os.path.basename(path))[0]
        name, ok = QInputDialog.getText(self, "Add to Startup", "Startup entry name:", text=stem)
        if not ok or not name.strip(): return
        name = name.strip()
        try:
            k = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                                0, _winreg.KEY_SET_VALUE)
            _winreg.SetValueEx(k, name, 0, _winreg.REG_SZ, path)
            _winreg.CloseKey(k)
            self._refresh()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not add startup entry:\n{e}")


# ══════════════════════════════════════════════════════════════════
# PAGE: FANS
# ══════════════════════════════════════════════════════════════════
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
        self._no_fans = QLabel("No fan sensors detected.\n\nFan speed monitoring requires lm-sensors (Linux) or hardware driver support (Windows).")
        self._no_fans.setStyleSheet(f"color:{C['t2']}; font-size:12px; background:{C['bg2']}; border:1px solid {C['b0']}; border-radius:8px; padding:20px;")
        self._no_fans.setWordWrap(True); self._root.addWidget(self._no_fans); self._root.addStretch()

    def update(self, m: Metrics):
        all_fans = {}
        for controller, fans in m.fans.items():
            for fan in fans:
                all_fans[f"{controller}/{fan.label}"] = fan.current
        if not all_fans:
            self._no_fans.show(); return
        self._no_fans.hide()
        for key, rpm in all_fans.items():
            if key not in self._fan_cards:
                fc = FanCard(key); self._fan_cards[key] = fc
                self._cards_row.addWidget(fc)
            self._fan_cards[key].refresh(rpm)


# ══════════════════════════════════════════════════════════════════
# PAGE: NETWORK
# ══════════════════════════════════════════════════════════════════
class NetworkPage(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:transparent;")
        inner = QWidget(); self.setWidget(inner)
        root = QVBoxLayout(inner); root.setContentsMargins(28,24,28,24); root.setSpacing(18)
        root.addWidget(section_header("Network"))
        root.addWidget(section_sub("Real-time bandwidth and active connections"))

        # speed cards
        speed_row = QHBoxLayout(); speed_row.setSpacing(14)
        for attr, title, color in (("_dn_card","Download",C["net_dn"]),("_up_card","Upload",C["net_up"])):
            card = _card(); cl = QVBoxLayout(card); cl.setContentsMargins(20,16,20,16); cl.setSpacing(6)
            dot_row = QHBoxLayout()
            dot = QLabel("●"); dot.setStyleSheet(f"color:{color}; font-size:9px; background:transparent; border:none;")
            tl = QLabel(title.upper()); tl.setStyleSheet(f"color:{C['t2']}; font-size:10px; font-weight:600; letter-spacing:1.5px; background:transparent; border:none;")
            dot_row.addWidget(dot); dot_row.addWidget(tl); dot_row.addStretch()
            cl.addLayout(dot_row)
            val = QLabel("0 B/s"); val.setStyleSheet(f"color:{C['t1']}; font-size:28px; font-weight:700; background:transparent; border:none;")
            spark = Sparkline(color)
            mid_row = QHBoxLayout(); mid_row.setSpacing(8)
            mid_row.addWidget(val, 1); mid_row.addWidget(spark, 1)
            cl.addLayout(mid_row)
            setattr(self, attr, val); setattr(self, attr+"_spark", spark)
            speed_row.addWidget(card, 1)
        root.addLayout(speed_row)

        # today totals
        totals_card = _card(); tl2 = QHBoxLayout(totals_card); tl2.setContentsMargins(20,14,20,14); tl2.setSpacing(40)
        for attr2, label2 in (("_today_dn","Downloaded today"),("_today_up","Uploaded today")):
            col = QVBoxLayout(); col.setSpacing(2)
            lbl2 = QLabel(label2.upper()); lbl2.setStyleSheet(f"color:{C['t2']}; font-size:10px; font-weight:600; letter-spacing:1.2px; background:transparent; border:none;")
            val2 = QLabel("0 B"); val2.setStyleSheet(f"color:{C['t1']}; font-size:18px; font-weight:700; background:transparent; border:none;")
            col.addWidget(lbl2); col.addWidget(val2)
            setattr(self, attr2, val2); tl2.addLayout(col)
        tl2.addStretch()
        root.addWidget(totals_card)

        # active connections chart
        chart_card = _card(); ccl = QVBoxLayout(chart_card); ccl.setContentsMargins(14,12,14,12); ccl.setSpacing(8)
        lbl3 = QLabel("Bandwidth History  (MB/s scale, capped at 100 MB/s)"); lbl3.setObjectName("chartTitle")
        ccl.addWidget(lbl3)
        charts_row2 = QHBoxLayout(); charts_row2.setSpacing(10)
        self._dn_chart = BigChart(C["net_dn"], "MB/s"); self._dn_chart.setMinimumHeight(120)
        self._up_chart = BigChart(C["net_up"], "MB/s"); self._up_chart.setMinimumHeight(120)
        charts_row2.addWidget(self._dn_chart, 1); charts_row2.addWidget(self._up_chart, 1)
        ccl.addLayout(charts_row2); root.addWidget(chart_card)

        # apps using internet
        root.addWidget(section_header("Active Connections"))
        root.addWidget(section_sub("Processes with established internet connections"))
        self._net_table = styled_table(["PID","Process","Active Connections"],[80,300,-1])
        self._net_table.setMinimumHeight(260); root.addWidget(self._net_table)
        root.addStretch()

    def update(self, m: Metrics):
        self._dn_card.setText(fmt_bytes_rate(m.net_recv_rate))
        self._up_card.setText(fmt_bytes_rate(m.net_sent_rate))
        self._dn_card_spark.set_hist(m.net_recv_hist)
        self._up_card_spark.set_hist(m.net_sent_hist)
        self._today_dn.setText(fmt_bytes_total(m.net_recv_today))
        self._today_up.setText(fmt_bytes_total(m.net_sent_today))
        self._dn_chart.update_hist(m.net_recv_hist)
        self._up_chart.update_hist(m.net_sent_hist)
        self._net_table.setUpdatesEnabled(False)
        self._net_table.setRowCount(len(m.net_top_procs))
        for row, proc in enumerate(m.net_top_procs):
            for col, (text, color) in enumerate([
                (str(proc["pid"]),    C["t2"]),
                (proc["name"],        C["t1"]),
                (str(proc["conns"]),  C["acc"]),
            ]):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter |
                    (Qt.AlignmentFlag.AlignLeft if col == 1 else Qt.AlignmentFlag.AlignRight))
                self._net_table.setItem(row, col, item)
            self._net_table.setRowHeight(row, 30)
        self._net_table.setUpdatesEnabled(True)

    def refresh_theme(self):
        self._dn_card.setStyleSheet(f"color:{C['t1']}; font-size:28px; font-weight:700; background:transparent; border:none;")
        self._up_card.setStyleSheet(f"color:{C['t1']}; font-size:28px; font-weight:700; background:transparent; border:none;")
        self._today_dn.setStyleSheet(f"color:{C['t1']}; font-size:18px; font-weight:700; background:transparent; border:none;")
        self._today_up.setStyleSheet(f"color:{C['t1']}; font-size:18px; font-weight:700; background:transparent; border:none;")


# ══════════════════════════════════════════════════════════════════
# PAGE: HISTORY
# ══════════════════════════════════════════════════════════════════
class HistoryChart(QWidget):
    """History chart with proper time-axis: x-position proportional to timestamp."""
    def __init__(self, color: str, label: str, parent=None):
        super().__init__(parent)
        self._color = QColor(color); self._label = label
        self._points: List[Tuple[float, float]] = []  # (ts, value)
        self._range_seconds: int = 3600
        self.setMinimumSize(120, 100)

    def set_data(self, points: List[Tuple[float, float]], range_seconds: int):
        self._points = points; self._range_seconds = range_seconds; self.update()

    def paintEvent(self, _):
        pts = self._points; n = len(pts)
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        lm, rm, tm, bm = 36, 10, 6, 22
        cw, ch = w-lm-rm, h-tm-bm
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(C["bg2"])); p.drawRect(self.rect())
        grid_pen = QPen(QColor(C["b0"]), 1)
        lbl_font = QFont(); lbl_font.setPointSize(8); p.setFont(lbl_font)
        for yv in [0,25,50,75,100]:
            gy = tm+ch-int(yv/100.0*ch)
            p.setPen(grid_pen); p.drawLine(lm, gy, lm+cw, gy)
            p.setPen(QPen(QColor(C["t2"])))
            p.drawText(QRect(0, gy-8, lm-4, 16),
                       Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter, str(yv))
        p.save(); p.setPen(QPen(QColor(C["t2"]))); p.setFont(lbl_font)
        p.translate(10, tm+ch//2); p.rotate(-90)
        p.drawText(QRect(-30, -8, 60, 16), Qt.AlignmentFlag.AlignCenter, self._label)
        p.restore()
        # x-axis time labels
        now = time.time(); since = now - self._range_seconds
        rs = self._range_seconds
        if rs >= 86400:
            start_lbl = f"{rs//3600}h ago"
        elif rs >= 3600:
            start_lbl = f"{rs//60}m ago"
        else:
            start_lbl = f"{rs//60}m ago"
        p.setPen(QPen(QColor(C["t2"]))); p.setFont(lbl_font)
        p.drawText(QRect(lm, tm+ch+2, 60, bm-4), Qt.AlignmentFlag.AlignLeft, start_lbl)
        p.drawText(QRect(lm+cw-30, tm+ch+2, 34, bm-4), Qt.AlignmentFlag.AlignRight, "Now")
        if n < 2:
            p.setPen(QPen(QColor(C["b0"]), 1)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(lm, tm, cw, ch); p.end(); return
        def pt(ts, v):
            x_frac = max(0.0, min(1.0, (ts - since) / self._range_seconds))
            return QPointF(lm + x_frac * cw, tm + ch - max(0, min(100, v)) / 100.0 * ch)
        points = [pt(ts, v) for ts, v in pts]
        fill = QPainterPath(); fill.moveTo(QPointF(points[0].x(), tm+ch))
        for pp in points: fill.lineTo(pp)
        fill.lineTo(QPointF(points[-1].x(), tm+ch)); fill.closeSubpath()
        grad = QLinearGradient(0, tm, 0, tm+ch)
        tc = QColor(self._color); tc.setAlpha(50)
        bc = QColor(self._color); bc.setAlpha(0)
        grad.setColorAt(0, tc); grad.setColorAt(1, bc)
        p.setPen(Qt.PenStyle.NoPen); p.fillPath(fill, grad)
        p.setPen(QPen(self._color, 2, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        lp = QPainterPath(); lp.moveTo(points[0])
        for pp in points[1:]: lp.lineTo(pp)
        p.drawPath(lp)
        p.setPen(QPen(QColor(C["b0"]), 1)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(lm, tm, cw, ch); p.end()


class HistoryPage(QScrollArea):
    _RANGES = [("1 Hour", 3600), ("24 Hours", 86400), ("7 Days", 604800)]

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:transparent;")
        inner = QWidget(); self.setWidget(inner)
        root = QVBoxLayout(inner); root.setContentsMargins(28,24,28,24); root.setSpacing(18)
        root.addWidget(section_header("Performance History"))
        root.addWidget(section_sub("Historical performance logged every 60 seconds"))

        # range selector
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        self._range_btns: List[QPushButton] = []
        self._selected_range = 3600
        btn_style_active = (f"QPushButton {{ background:{C['acc']}; color:#000; border:none;"
                            f" border-radius:6px; padding:6px 18px; font-size:12px; font-weight:700; }}")
        btn_style_idle   = (f"QPushButton {{ background:{C['bg2']}; color:{C['t2']}; border:1px solid {C['b0']};"
                            f" border-radius:6px; padding:6px 18px; font-size:12px; }}"
                            f"QPushButton:hover {{ background:{C['bg3']}; color:{C['t1']}; }}")
        for label, seconds in self._RANGES:
            btn = QPushButton(label); btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(btn_style_active if seconds == 3600 else btn_style_idle)
            btn.clicked.connect(lambda _, s=seconds: self._set_range(s))
            self._range_btns.append(btn); btn_row.addWidget(btn)
        btn_row.addStretch(); root.addLayout(btn_row)

        # charts
        for attr, label, color in (("_cpu_hchart","CPU %",C["cpu"]),("_gpu_hchart","GPU %",C["gpu"]),("_ram_hchart","RAM %",C["ram"])):
            card = _card(); cl = QVBoxLayout(card); cl.setContentsMargins(14,12,14,12); cl.setSpacing(6)
            lbl2 = QLabel(label); lbl2.setObjectName("chartTitle")
            cl.addWidget(lbl2)
            chart = HistoryChart(color, label[:3]); chart.setMinimumHeight(110)
            setattr(self, attr, chart); cl.addWidget(chart); root.addWidget(card)

        self._no_data_lbl = QLabel("No history data yet. Data is logged every 60 seconds.")
        self._no_data_lbl.setStyleSheet(f"color:{C['t2']}; font-size:13px; background:transparent; border:none; padding:12px;")
        root.addWidget(self._no_data_lbl)
        root.addStretch()

        self._btn_styles = (btn_style_active, btn_style_idle)

    def _set_range(self, seconds: int):
        self._selected_range = seconds
        active, idle = self._btn_styles
        for btn, (_, s) in zip(self._range_btns, self._RANGES):
            btn.setStyleSheet(active if s == seconds else idle)
        self.refresh()

    def refresh(self):
        since = int(time.time()) - self._selected_range
        rows = HISTORY_DB.query(since, max_points=120)
        empty: List[Tuple[float, float]] = []
        if not rows:
            self._no_data_lbl.show()
            self._cpu_hchart.set_data(empty, self._selected_range)
            self._gpu_hchart.set_data(empty, self._selected_range)
            self._ram_hchart.set_data(empty, self._selected_range)
            return
        self._no_data_lbl.hide()
        cpu_pts = [(r["ts"], r["cpu"]) for r in rows]
        gpu_pts = [(r["ts"], r["gpu"]) for r in rows]
        ram_pts = [(r["ts"], r["ram"]) for r in rows]
        self._cpu_hchart.set_data(cpu_pts, self._selected_range)
        self._gpu_hchart.set_data(gpu_pts, self._selected_range)
        self._ram_hchart.set_data(ram_pts, self._selected_range)

    def update(self, m: Metrics):
        # called on every data tick but we refresh from DB only every N seconds
        pass

    def showEvent(self, e):
        super().showEvent(e); self.refresh()


# ══════════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ══════════════════════════════════════════════════════════════════
def _spin_style() -> str:
    return f"""
QSpinBox {{
    background:{C['bg2']}; color:{C['t1']}; border:1px solid {C['b0']};
    border-radius:6px; padding:5px 8px; font-size:13px; min-width:90px;
}}
QSpinBox:focus {{ border-color:{C['acc']}; }}
QSpinBox::up-button, QSpinBox::down-button {{ background:{C['bg3']}; border:none; width:22px; border-radius:4px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background:{C['b1']}; }}
QSpinBox::up-arrow, QSpinBox::down-arrow {{ image:none; width:0; }}
"""

def _combo_style() -> str:
    return f"""
QComboBox {{
    background:{C['bg2']}; color:{C['t1']}; border:1px solid {C['b0']};
    border-radius:6px; padding:5px 10px; font-size:13px; min-width:120px;
}}
QComboBox:focus {{ border-color:{C['acc']}; }}
QComboBox::drop-down {{ border:none; width:24px; }}
QComboBox QAbstractItemView {{
    background:{C['bg2']}; color:{C['t1']}; border:1px solid {C['b0']};
    selection-background-color:{C['bg3']};
}}
"""

def _check_style() -> str:
    return f"""
QCheckBox {{ color:{C['t1']}; font-size:13px; background:transparent; spacing:8px; }}
QCheckBox::indicator {{ width:18px; height:18px; border:2px solid {C['b1']}; border-radius:4px; background:{C['bg2']}; }}
QCheckBox::indicator:checked {{ background:{C['acc']}; border-color:{C['acc']}; }}
"""

def _settings_section(title: str) -> QLabel:
    lbl = QLabel(title)
    lbl.setStyleSheet(f"color:{C['acc']}; font-size:11px; font-weight:700; letter-spacing:1.5px;"
                      f" padding:0; background:transparent; border-bottom:1px solid {C['b0']}; margin-bottom:2px;")
    return lbl

def _settings_row(label: str, hint: str, control: QWidget) -> QFrame:
    w = _card()
    row = QHBoxLayout(w); row.setContentsMargins(16,12,16,12); row.setSpacing(12)
    left = QVBoxLayout(); left.setSpacing(2)
    # No explicit color — inherits from global QWidget rule, so theme changes auto-update
    lbl = QLabel(label); lbl.setStyleSheet("font-size:13px; background:transparent; border:none;")
    hl  = QLabel(hint);  hl.setStyleSheet("font-size:11px; background:transparent; border:none; opacity:0.75;")
    left.addWidget(lbl); left.addWidget(hl)
    row.addLayout(left, 1); row.addWidget(control)
    return w


class SettingsPage(QWidget):
    theme_changed = pyqtSignal()
    dash_visibility_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        scroll = QScrollArea(self); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        QVBoxLayout(self).addWidget(scroll); self.layout().setContentsMargins(0,0,0,0)
        inner = QWidget(); scroll.setWidget(inner)
        root = QVBoxLayout(inner); root.setContentsMargins(32,28,32,28); root.setSpacing(16)

        title = QLabel("Settings"); title.setStyleSheet("font-size:22px; font-weight:700; background:transparent; border:none;")
        root.addWidget(title)

        # ── Alert thresholds ─────────────────────────────────────
        root.addWidget(_settings_section("ALERT THRESHOLDS"))

        self._temp_spin = QSpinBox(); self._temp_spin.setRange(40,110); self._temp_spin.setSingleStep(5)
        self._temp_spin.setValue(CFG.warn_temp); self._temp_spin.setSuffix(" °C"); self._temp_spin.setStyleSheet(_spin_style())

        self._cpu_pct_spin = QSpinBox(); self._cpu_pct_spin.setRange(50,100); self._cpu_pct_spin.setSingleStep(5)
        self._cpu_pct_spin.setValue(CFG.warn_cpu_pct); self._cpu_pct_spin.setSuffix(" %"); self._cpu_pct_spin.setStyleSheet(_spin_style())

        self._gpu_pct_spin = QSpinBox(); self._gpu_pct_spin.setRange(50,100); self._gpu_pct_spin.setSingleStep(5)
        self._gpu_pct_spin.setValue(CFG.warn_gpu_pct); self._gpu_pct_spin.setSuffix(" %"); self._gpu_pct_spin.setStyleSheet(_spin_style())

        self._ram_pct_spin = QSpinBox(); self._ram_pct_spin.setRange(50,100); self._ram_pct_spin.setSingleStep(5)
        self._ram_pct_spin.setValue(CFG.warn_ram_pct); self._ram_pct_spin.setSuffix(" %"); self._ram_pct_spin.setStyleSheet(_spin_style())

        self._disk_spin = QSpinBox(); self._disk_spin.setRange(1,50); self._disk_spin.setSingleStep(1)
        self._disk_spin.setValue(CFG.warn_disk); self._disk_spin.setSuffix(" %"); self._disk_spin.setStyleSheet(_spin_style())

        self._sound_combo = QComboBox(); self._sound_combo.setStyleSheet(_combo_style())
        self._sound_combo.addItems(["None", "Beep"])
        self._sound_combo.setCurrentIndex(0 if CFG.alert_sound == "none" else 1)

        root.addWidget(_settings_row("CPU / GPU Temperature Alert",
            "Warn when CPU or GPU exceeds this temperature.", self._temp_spin))
        root.addWidget(_settings_row("CPU Usage Alert",
            "Warn when CPU usage exceeds this percentage.", self._cpu_pct_spin))
        root.addWidget(_settings_row("GPU Usage Alert",
            "Warn when GPU usage exceeds this percentage.", self._gpu_pct_spin))
        root.addWidget(_settings_row("RAM Usage Alert",
            "Warn when RAM usage exceeds this percentage.", self._ram_pct_spin))
        root.addWidget(_settings_row("Low Disk Space Alert",
            "Warn when free disk space falls below this percentage.", self._disk_spin))
        root.addWidget(_settings_row("Alert Sound",
            "Play a sound when an alert is triggered.", self._sound_combo))

        # ── Performance ───────────────────────────────────────────
        root.addWidget(_settings_section("PERFORMANCE"))
        self._poll_spin = QSpinBox(); self._poll_spin.setRange(250,5000); self._poll_spin.setSingleStep(250)
        self._poll_spin.setValue(CFG.poll_ms); self._poll_spin.setSuffix(" ms"); self._poll_spin.setStyleSheet(_spin_style())
        root.addWidget(_settings_row("Poll Refresh Rate",
            "How often PulseMonitor reads hardware metrics. Lower = more responsive, higher CPU use.",
            self._poll_spin))

        # ── Appearance ────────────────────────────────────────────
        root.addWidget(_settings_section("APPEARANCE"))
        self._theme_combo = QComboBox(); self._theme_combo.setStyleSheet(_combo_style())
        self._theme_combo.addItems(["Dark", "Light"])
        self._theme_combo.setCurrentIndex(0 if CFG.theme == "dark" else 1)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_combo_changed)
        root.addWidget(_settings_row("Theme",
            "Switch between dark and light mode. Applies immediately.",
            self._theme_combo))

        # ── Overlay ───────────────────────────────────────────────
        root.addWidget(_settings_section("MINI OVERLAY"))
        self._opacity_spin = QSpinBox(); self._opacity_spin.setRange(30,100); self._opacity_spin.setSingleStep(5)
        self._opacity_spin.setValue(int(CFG.overlay_opacity * 100)); self._opacity_spin.setSuffix(" %")
        self._opacity_spin.setStyleSheet(_spin_style())
        root.addWidget(_settings_row("Overlay Opacity",
            "Transparency of the mini overlay widget (Ctrl+Shift+M to toggle).",
            self._opacity_spin))

        # ── Dashboard ─────────────────────────────────────────────
        root.addWidget(_settings_section("DASHBOARD WIDGETS"))
        dash_card = _card()
        dash_layout = QVBoxLayout(dash_card); dash_layout.setContentsMargins(16,12,16,12); dash_layout.setSpacing(8)
        self._dash_checks: Dict[str, QCheckBox] = {}
        for key, label in [("dash_cpu","CPU Card"),("dash_gpu","GPU Card"),("dash_ram","RAM Card"),
                            ("dash_charts","Usage Charts"),("dash_drives","Drive Space")]:
            cb = QCheckBox(label); cb.setStyleSheet(_check_style())
            cb.setChecked(bool(getattr(CFG, key)))
            cb.toggled.connect(lambda checked, k=key: self._on_dash_check_changed(k, checked))
            self._dash_checks[key] = cb; dash_layout.addWidget(cb)
        root.addWidget(dash_card)

        # ── Export ────────────────────────────────────────────────
        root.addWidget(_settings_section("DATA EXPORT"))
        export_row = QHBoxLayout(); export_row.setSpacing(12)
        self._export_btn = QPushButton("Export Current Stats to CSV")
        self._export_btn.setFixedHeight(38)
        self._export_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._export_btn.setStyleSheet(f"""
            QPushButton {{ background:{C['bg2']}; color:{C['acc']}; font-size:13px; font-weight:600;
                           border:1px solid {C['b1']}; border-radius:8px; padding:0 24px; }}
            QPushButton:hover {{ background:{C['bg3']}; border-color:{C['acc']}; }}
        """)
        self._export_btn.clicked.connect(self._export_csv)
        self._export_lbl = QLabel(""); self._export_lbl.setStyleSheet(f"color:{C['acc']}; font-size:12px; background:transparent;")
        export_row.addWidget(self._export_btn); export_row.addWidget(self._export_lbl); export_row.addStretch()
        root.addLayout(export_row)

        # ── Save ──────────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(12)
        self._save_btn = QPushButton("Save Settings"); self._save_btn.setFixedHeight(38)
        self._save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._save_btn.setStyleSheet(f"""
            QPushButton {{ background:{C['acc']}; color:#000; font-size:13px;
                           font-weight:700; border-radius:8px; border:none; padding:0 24px; }}
            QPushButton:hover {{ background:#00F0C0; }}
            QPushButton:pressed {{ background:{C['acc2']}; color:{C['t1']}; }}
        """)
        self._save_btn.clicked.connect(self._save)
        self._saved_lbl = QLabel(""); self._saved_lbl.setStyleSheet(f"color:{C['acc']}; font-size:12px; background:transparent;")
        btn_row.addWidget(self._save_btn); btn_row.addWidget(self._saved_lbl); btn_row.addStretch()
        root.addLayout(btn_row)
        root.addStretch()

        # store current metrics for export
        self._current_metrics: Optional[Metrics] = None

    def set_metrics(self, m: Metrics):
        self._current_metrics = m

    def _save(self):
        CFG.warn_temp     = self._temp_spin.value()
        CFG.warn_cpu_pct  = self._cpu_pct_spin.value()
        CFG.warn_gpu_pct  = self._gpu_pct_spin.value()
        CFG.warn_ram_pct  = self._ram_pct_spin.value()
        CFG.warn_disk     = self._disk_spin.value()
        CFG.alert_sound   = "none" if self._sound_combo.currentIndex() == 0 else "beep"
        CFG.poll_ms       = self._poll_spin.value()
        CFG.theme         = "dark" if self._theme_combo.currentIndex() == 0 else "light"
        CFG.overlay_opacity = self._opacity_spin.value() / 100.0
        for key, cb in self._dash_checks.items():
            setattr(CFG, key, cb.isChecked())
        CFG.save()
        init_theme(CFG.theme)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(_global_style())
        self._refresh_theme_styles()
        self.theme_changed.emit()
        self.dash_visibility_changed.emit()
        self._saved_lbl.setText("Saved ✓")
        QTimer.singleShot(2500, lambda: self._saved_lbl.setText(""))

    def _on_theme_combo_changed(self, index: int):
        new_theme = "dark" if index == 0 else "light"
        if new_theme == CFG.theme:
            return
        CFG.theme = new_theme
        init_theme(CFG.theme)
        app_inst = QApplication.instance()
        if app_inst:
            app_inst.setStyleSheet(_global_style())
        self._refresh_theme_styles()
        self.theme_changed.emit()

    def _on_dash_check_changed(self, key: str, checked: bool):
        setattr(CFG, key, checked)
        self.dash_visibility_changed.emit()

    def _refresh_theme_styles(self):
        spin = _spin_style(); combo = _combo_style(); check = _check_style()
        for w in (self._temp_spin, self._cpu_pct_spin, self._gpu_pct_spin,
                  self._ram_pct_spin, self._disk_spin, self._poll_spin, self._opacity_spin):
            w.setStyleSheet(spin)
        self._sound_combo.setStyleSheet(combo)
        self._theme_combo.setStyleSheet(combo)
        for cb in self._dash_checks.values():
            cb.setStyleSheet(check)

    def _export_csv(self):
        m = self._current_metrics
        if m is None:
            self._export_lbl.setText("No data yet — wait a moment and try again.")
            QTimer.singleShot(3000, lambda: self._export_lbl.setText(""))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Stats", f"pulsemonitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)")
        if not path: return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                w.writerow([])
                w.writerow(["Metric", "Value"])
                w.writerow(["CPU Usage %", f"{m.cpu_pct:.1f}"])
                w.writerow(["CPU Temp °C", f"{m.cpu_temp:.0f}" if m.cpu_temp else "N/A"])
                w.writerow(["CPU Freq MHz", f"{m.cpu_freq:.0f}"])
                w.writerow(["GPU Name", m.gpu_name])
                w.writerow(["GPU Usage %", f"{m.gpu_pct:.1f}"])
                w.writerow(["GPU Temp °C", f"{m.gpu_temp:.0f}" if m.gpu_temp else "N/A"])
                w.writerow(["GPU VRAM Used GB", f"{m.gpu_vram_u:.2f}"])
                w.writerow(["GPU VRAM Total GB", f"{m.gpu_vram_t:.2f}"])
                w.writerow(["RAM Usage %", f"{m.ram_pct:.1f}"])
                w.writerow(["RAM Used GB", f"{m.ram_used:.2f}"])
                w.writerow(["RAM Total GB", f"{m.ram_total:.2f}"])
                w.writerow(["Net Download B/s", f"{m.net_recv_rate:.0f}"])
                w.writerow(["Net Upload B/s", f"{m.net_sent_rate:.0f}"])
                w.writerow(["Net Recv Today B", f"{m.net_recv_today:.0f}"])
                w.writerow(["Net Sent Today B", f"{m.net_sent_today:.0f}"])
                w.writerow(["Uptime s", f"{m.uptime:.0f}"])
                w.writerow([])
                w.writerow(["Drive", "Total GB", "Used GB", "Free GB", "Used %"])
                for dr in m.drives:
                    w.writerow([dr["mount"], f"{dr['total']:.1f}", f"{dr['used']:.1f}",
                                f"{dr['free']:.1f}", f"{dr['pct']:.0f}"])
                w.writerow([])
                w.writerow(["Core", "Usage %"])
                for i, pct in enumerate(m.cpu_cores):
                    w.writerow([f"Core {i}", f"{pct:.1f}"])
            self._export_lbl.setText(f"Exported ✓")
            QTimer.singleShot(3000, lambda: self._export_lbl.setText(""))
        except Exception as ex:
            self._export_lbl.setText(f"Error: {ex}")
            QTimer.singleShot(4000, lambda: self._export_lbl.setText(""))

    def update(self, m: Metrics):
        self.set_metrics(m)


# ══════════════════════════════════════════════════════════════════
# PAGE: ABOUT
# ══════════════════════════════════════════════════════════════════
class _LogoWidget(QWidget):
    def __init__(self, size=64, parent=None):
        super().__init__(parent); self._sz = size; self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        s = self._sz; r = s // 6
        p.setBrush(QColor("#0D1117")); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, s, s, r, r)
        pm = _get_logo(self._sz)
        if not pm.isNull():
            p.drawPixmap(0, 0, self._sz, self._sz, pm)
        else:
            # fallback: draw programmatic ECG
            s = self._sz; r = s//6
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setBrush(QColor(C["bg2"])); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(0, 0, s, s, r, r)
            mid = s*0.54; lh = s*0.30; mg = s*0.10; lw = s*0.80
            raw = [(0.04,0),(0.22,0),(0.30,-0.10),(0.36,0),(0.44,-0.42),
                   (0.50,0.30),(0.56,-0.10),(0.62,0),(0.78,-0.06),(0.96,0)]
            pts = [QPointF(mg+x*lw, mid+y*lh) for x, y in raw]
            pen = QPen(QColor(C["acc"]), max(1, s//28),
                       Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            for i in range(len(pts)-1): p.drawLine(pts[i], pts[i+1])
        p.end()


class AboutPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addStretch(1)
        col = QVBoxLayout(); col.setSpacing(0); col.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        logo = _LogoWidget(80); col.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)
        col.addSpacing(18)
        self._name_lbl = QLabel("PulseMonitor")
        self._name_lbl.setStyleSheet(f"color:{C['title']}; font-size:32px; font-weight:800; letter-spacing:1px; background:transparent;")
        self._name_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter); col.addWidget(self._name_lbl)
        col.addSpacing(6)
        ver_lbl = QLabel(f"v{APP_VERSION}  ·  Professional PC Health Monitor")
        ver_lbl.setStyleSheet(f"color:{C['acc']}; font-size:13px; font-weight:600; background:transparent;")
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter); col.addWidget(ver_lbl)
        col.addSpacing(4)
        pub_lbl = QLabel("by VaultSoft"); pub_lbl.setStyleSheet(f"color:{C['t2']}; font-size:12px; background:transparent;")
        pub_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter); col.addWidget(pub_lbl)
        col.addSpacing(28)
        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine); div.setFixedWidth(360)
        div.setStyleSheet(f"color:{C['b1']}; background:{C['b1']}; border:none; max-height:1px;")
        col.addWidget(div, 0, Qt.AlignmentFlag.AlignHCenter); col.addSpacing(24)
        desc = QLabel(
            "PulseMonitor gives you a real-time view of your PC's health —\n"
            "CPU, GPU, memory, storage, network, temperatures and more.\n"
            "Lightweight, AV-clean, and built for Windows 10 and 11.")
        desc.setStyleSheet(f"color:{C['t2']}; font-size:13px; background:transparent; padding:0 20px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignHCenter); desc.setWordWrap(True); desc.setFixedWidth(440)
        col.addWidget(desc, 0, Qt.AlignmentFlag.AlignHCenter); col.addSpacing(28)
        gh_btn = QPushButton("⬡  github.com/VaultSoft/PulseMonitor")
        gh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); gh_btn.setFixedHeight(40)
        gh_btn.setStyleSheet(f"""
            QPushButton {{ background:{C['bg2']}; color:{C['acc']}; border:1px solid {C['b1']};
                           border-radius:8px; font-size:13px; font-weight:600; padding:0 24px; }}
            QPushButton:hover {{ background:{C['bg3']}; border-color:{C['acc']}; }}
        """)
        gh_btn.clicked.connect(lambda: __import__("webbrowser").open("https://github.com/VaultSoft/PulseMonitor"))
        col.addWidget(gh_btn, 0, Qt.AlignmentFlag.AlignHCenter); col.addSpacing(12)
        kofi_btn = QPushButton("☕  Support on Ko-fi")
        kofi_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)); kofi_btn.setFixedHeight(40)
        kofi_btn.setStyleSheet("""
            QPushButton { background:#FF5E5B; color:#fff; border:none;
                          border-radius:8px; font-size:13px; font-weight:700; padding:0 24px; }
            QPushButton:hover { background:#FF7875; }
            QPushButton:pressed { background:#E54542; }
        """)
        kofi_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://ko-fi.com/vaultsoft")))
        col.addWidget(kofi_btn, 0, Qt.AlignmentFlag.AlignHCenter); col.addSpacing(32)
        copy_lbl = QLabel(f"© {datetime.now().year} VaultSoft. Released under the MIT Licence.")
        copy_lbl.setStyleSheet(f"color:{C['t3']}; font-size:11px; background:transparent;")
        copy_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter); col.addWidget(copy_lbl)
        root.addLayout(col); root.addStretch(1)

    def refresh_theme(self):
        self._name_lbl.setStyleSheet(
            f"color:{C['title']}; font-size:32px; font-weight:800; letter-spacing:1px; background:transparent;")


# ══════════════════════════════════════════════════════════════════
# MINI OVERLAY
# ══════════════════════════════════════════════════════════════════
class MiniOverlay(QWidget):
    """Always-on-top transparent widget showing CPU/GPU/RAM."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(CFG.overlay_opacity)
        self._drag_pos: Optional[QPoint] = None
        self._cpu = 0.0; self._gpu = 0.0; self._ram = 0.0
        self._cpu_t: Optional[float] = None; self._gpu_t: Optional[float] = None
        self.setFixedSize(160, 96)
        self._restore_pos()

    def _restore_pos(self):
        if CFG.overlay_x >= 0 and CFG.overlay_y >= 0:
            self.move(CFG.overlay_x, CFG.overlay_y)
        else:
            from PyQt6.QtWidgets import QApplication as _App
            screen = _App.primaryScreen().geometry()
            self.move(screen.right() - self.width() - 20, screen.top() + 40)

    def update_metrics(self, m: Metrics):
        self._cpu = m.cpu_pct; self._gpu = m.gpu_pct; self._ram = m.ram_pct
        self._cpu_t = m.cpu_temp; self._gpu_t = m.gpu_temp
        self.setWindowOpacity(CFG.overlay_opacity)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # background pill
        p.setBrush(QColor(20, 28, 40, 220))
        p.setPen(QPen(QColor(C["b1"]), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, w-1, h-1), 12, 12)
        # simple rows: label  VALUE%  (temp optional)
        font_lbl = QFont("Segoe UI", 9); font_lbl.setBold(True)
        font_val = QFont("Segoe UI", 11); font_val.setBold(True)
        rows = [
            ("CPU", self._cpu, C["cpu"],
             f"{self._cpu:.0f}%" + (f"  {self._cpu_t:.0f}°" if self._cpu_t else "")),
            ("GPU", self._gpu, C["gpu"],
             f"{self._gpu:.0f}%" + (f"  {self._gpu_t:.0f}°" if self._gpu_t else "")),
            ("RAM", self._ram, C["ram"], f"{self._ram:.0f}%"),
        ]
        row_h = h // 3
        lm = 12
        for i, (label, pct, color, val_text) in enumerate(rows):
            y = i * row_h
            p.setFont(font_lbl); p.setPen(QPen(QColor(color)))
            p.drawText(QRect(lm, y, 36, row_h), Qt.AlignmentFlag.AlignVCenter, label)
            p.setFont(font_val); p.setPen(QPen(QColor(pct_color(pct))))
            p.drawText(QRect(50, y, w - 62, row_h),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, val_text)
        p.end()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _):
        self._drag_pos = None
        CFG.overlay_x = self.x(); CFG.overlay_y = self.y(); CFG.save()

    def mouseDoubleClickEvent(self, _):
        self.hide()

    def closeEvent(self, e):
        e.ignore(); self.hide()


# ══════════════════════════════════════════════════════════════════
# NAVIGATION
# ══════════════════════════════════════════════════════════════════
NAV_ITEMS = [
    ("⊞", "Dashboard"),
    ("⬡", "CPU"),
    ("▣", "Memory"),
    ("◈", "GPU"),
    ("▦", "Storage"),
    ("≡", "Processes"),
    ("⚡","Startup"),
    ("∿", "Fans"),
    ("⇅", "Network"),
    ("◷", "History"),
    ("⚙", "Settings"),
    ("ℹ", "About"),
]


class SideNavBtn(QPushButton):
    def __init__(self, icon: str, label: str):
        super().__init__()
        self._icon = icon; self._label = label; self._active = False
        self.setFixedHeight(44); self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True); self.setStyleSheet("border:none; background:transparent;")

    def set_active(self, v: bool):
        self._active = v; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if self._active:
            p.fillRect(0, 0, w, h, QColor(C["bg3"]))
            p.setBrush(QColor(C["acc"])); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(0, 10, 3, h-20, 1.5, 1.5)
        elif self.underMouse():
            p.fillRect(0, 0, w, h, QColor(C["bg2"]))
        icon_font = QFont(); icon_font.setPointSize(12); p.setFont(icon_font)
        c = QColor(C["acc"] if self._active else C["t2"])
        p.setPen(QPen(c))
        p.drawText(QRect(12, 0, 28, h), Qt.AlignmentFlag.AlignCenter, self._icon)
        lbl_font = QFont(); lbl_font.setPointSize(9)
        if self._active: lbl_font.setWeight(QFont.Weight.DemiBold)
        p.setFont(lbl_font)
        p.setPen(QPen(QColor(C["t1"] if self._active else C["t2"])))
        p.drawText(QRect(46, 0, w-54, h), Qt.AlignmentFlag.AlignVCenter, self._label)
        p.end()


class Sidebar(QWidget):
    page_selected = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(178)
        self.setStyleSheet(f"background:{C['bg0']}; border-right:1px solid {C['b0']};")
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,12); root.setSpacing(1)
        self._brand = QWidget(); self._brand.setFixedHeight(52)
        self._brand.setStyleSheet(f"background:{C['bg0']}; border-bottom:1px solid {C['b0']};")
        bl = QHBoxLayout(self._brand); bl.setContentsMargins(14,0,14,0)
        self._brand_lbl = QLabel("PULSE")
        self._brand_lbl.setStyleSheet(f"color:{C['title']}; font-size:14px; font-weight:900; letter-spacing:3px; background:transparent; border:none;")
        bl.addWidget(self._brand_lbl); root.addWidget(self._brand); root.addSpacing(6)
        self._btns: List[SideNavBtn] = []
        for icon, label in NAV_ITEMS:
            btn = SideNavBtn(icon, label)
            idx = len(self._btns)
            btn.clicked.connect(lambda _, i=idx: self._select(i))
            self._btns.append(btn); root.addWidget(btn)
        root.addStretch()
        self._ver_lbl = QLabel(f"v{APP_VERSION}")
        self._ver_lbl.setStyleSheet(f"color:{C['t3']}; font-size:10px; padding:0 14px; background:transparent; border:none;")
        root.addWidget(self._ver_lbl)
        self._select(0)

    def refresh_theme(self):
        self.setStyleSheet(f"background:{C['bg0']}; border-right:1px solid {C['b0']};")
        self._brand.setStyleSheet(f"background:{C['bg0']}; border-bottom:1px solid {C['b0']};")
        self._brand_lbl.setStyleSheet(
            f"color:{C['title']}; font-size:14px; font-weight:900; letter-spacing:3px; background:transparent; border:none;")
        self._ver_lbl.setStyleSheet(
            f"color:{C['t3']}; font-size:10px; padding:0 14px; background:transparent; border:none;")
        for btn in self._btns:
            btn.update()

    def _select(self, idx: int):
        for i, btn in enumerate(self._btns): btn.set_active(i == idx)
        self.page_selected.emit(idx)


# ══════════════════════════════════════════════════════════════════
# TITLE BAR
# ══════════════════════════════════════════════════════════════════
class TitleBar(QWidget):
    overlay_toggled = pyqtSignal()

    def __init__(self, parent: QMainWindow):
        super().__init__(parent)
        self._parent = parent; self._drag_pos: Optional[QPoint] = None
        self.setFixedHeight(46)
        self.setStyleSheet(f"background:{C['bg0']}; border-bottom:1px solid {C['b0']};")
        row = QHBoxLayout(self); row.setContentsMargins(16,0,10,0); row.setSpacing(0)
        self._icon_lbl = QLabel(); self._icon_lbl.setPixmap(_get_logo(22))
        self._icon_lbl.setStyleSheet("background:transparent; border:none;")
        self._app_lbl = QLabel("PulseMonitor")
        self._app_lbl.setStyleSheet(f"color:{C['t1']}; font-size:14px; font-weight:700; letter-spacing:0.5px; background:transparent; border:none; margin-left:8px;")
        self._ver_lbl = QLabel(f"v{APP_VERSION}")
        self._ver_lbl.setStyleSheet(f"color:{C['t3']}; font-size:11px; margin-left:6px; background:transparent; border:none;")
        row.addWidget(self._icon_lbl); row.addWidget(self._app_lbl); row.addWidget(self._ver_lbl)
        row.addStretch()
        overlay_btn = QPushButton("⊡")
        overlay_btn.setFixedSize(36, 36); overlay_btn.setToolTip("Toggle Mini Overlay  (Ctrl+Shift+M)")
        overlay_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{C['acc']}; border:none; font-size:14px; border-radius:6px; }}
            QPushButton:hover {{ background:{C['acc']}22; }}
        """)
        overlay_btn.clicked.connect(self.overlay_toggled.emit)
        row.addWidget(overlay_btn)
        self._win_btns: List[QPushButton] = []
        for symbol, tip, slot, hover_clr in (
            ("─","Minimise", parent.showMinimized, C["t2"]),
            ("□","Maximise", self._toggle_max,     C["t2"]),
            ("✕","Close",    parent.close,          C["red"]),
        ):
            btn = QPushButton(symbol); btn.setFixedSize(36,36); btn.setToolTip(tip)
            btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{C['t2']}; border:none; font-size:14px; border-radius:6px; }}
                QPushButton:hover {{ background:{hover_clr}22; color:{hover_clr}; }}
            """)
            btn.clicked.connect(slot); row.addWidget(btn); self._win_btns.append(btn)

    def refresh_theme(self):
        self.setStyleSheet(f"background:{C['bg0']}; border-bottom:1px solid {C['b0']};")
        self._app_lbl.setStyleSheet(
            f"color:{C['t1']}; font-size:14px; font-weight:700; letter-spacing:0.5px;"
            f" background:transparent; border:none; margin-left:8px;")
        self._ver_lbl.setStyleSheet(
            f"color:{C['t3']}; font-size:11px; margin-left:6px; background:transparent; border:none;")

    def _toggle_max(self):
        if self._parent.isMaximized(): self._parent.showNormal()
        else:                          self._parent.showMaximized()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            if _IS_WIN:
                import ctypes
                hwnd = int(self._parent.winId())
                ctypes.windll.user32.ReleaseCapture()
                # WM_NCLBUTTONDOWN, HTCAPTION=2 — hands drag entirely to Windows
                ctypes.windll.user32.SendMessageW(hwnd, 0x00A1, 2, 0)
            else:
                self._drag_pos = e.globalPosition().toPoint() - self._parent.pos()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self._parent.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, _): self._toggle_max()


# ══════════════════════════════════════════════════════════════════
# TRAY ICON
# ══════════════════════════════════════════════════════════════════
def make_tray_icon() -> QIcon:
    pm = _get_logo(32)
    if not pm.isNull():
        return QIcon(pm)
    # fallback ECG icon
    pm2 = QPixmap(32,32); pm2.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm2); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(C["bg2"])); p.setPen(QPen(QColor(C["acc"]),1.5))
    p.drawEllipse(1,1,30,30)
    pts = [QPointF(4,16),QPointF(7,16),QPointF(11,8),QPointF(16,24),QPointF(21,11),QPointF(25,16),QPointF(28,16)]
    pen = QPen(QColor(C["acc"]),2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    for i in range(len(pts)-1): p.drawLine(pts[i],pts[i+1])
    p.end(); return QIcon(pm2)


# ══════════════════════════════════════════════════════════════════
# GLOBAL STYLE
# ══════════════════════════════════════════════════════════════════
def _global_style() -> str:
    return f"""
QMainWindow, QWidget {{
    background-color:{C['bg1']}; color:{C['t1']};
    font-family:"Segoe UI","SF Pro Display","Ubuntu",sans-serif; font-size:13px;
}}
QFrame#card {{
    background-color:{C['bg2']}; border:1px solid {C['b0']}; border-radius:10px;
}}
QLabel#sectionHeader {{
    color:{C['title']};
}}
QLabel#sectionSub {{
    color:{C['t2']};
}}
QLabel#chartTitle {{
    color:{C['t1']}; font-size:12px; font-weight:600; background:transparent; border:none;
}}
QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{ background:{C['bg1']}; width:6px; border-radius:3px; margin:0; }}
QScrollBar::handle:vertical {{ background:{C['b1']}; border-radius:3px; min-height:20px; }}
QScrollBar::handle:vertical:hover {{ background:{C['acc']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; border:0; }}
QScrollBar:horizontal {{ background:{C['bg1']}; height:6px; border-radius:3px; margin:0; }}
QScrollBar::handle:horizontal {{ background:{C['b1']}; border-radius:3px; min-width:20px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; border:0; }}
QToolTip {{ background:{C['bg3']}; color:{C['t1']}; border:1px solid {C['b1']}; padding:4px 8px; border-radius:4px; }}
QTableWidget, QTableView {{
    background-color:{C['bg2']}; color:{C['t1']};
    selection-background-color:{C['bg3']}; selection-color:{C['t1']};
    gridline-color:{C['b0']}; border:1px solid {C['b0']}; border-radius:8px; outline:none;
}}
QTableWidget::item, QTableView::item {{
    background-color:transparent; color:{C['t1']}; padding:5px 10px; border:none;
}}
QTableWidget::item:hover, QTableView::item:hover {{
    background-color:{C['bg3']};
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background-color:{C['bg3']}; color:{C['t1']};
}}
QHeaderView {{ background-color:{C['bg1']}; border:none; }}
QHeaderView::section {{
    background-color:{C['bg1']}; color:{C['t2']};
    font-size:10px; font-weight:700; letter-spacing:1.2px;
    padding:8px 10px; border:none; border-bottom:1px solid {C['b0']};
}}
"""


# ══════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ══════════════════════════════════════════════════════════════════
_WM_HOTKEY   = 0x0312
_HOTKEY_ID   = 7331
_MOD_CTRL    = 0x0002
_MOD_SHIFT   = 0x0004
_VK_M        = 0x4D


class _HotkeyFilter(QAbstractNativeEventFilter):
    """App-level native event filter for WM_HOTKEY — avoids overriding nativeEvent
    on the main window, which deadlocks during HWND creation on non-frameless windows."""
    def __init__(self, callback):
        super().__init__()
        self._cb = callback

    def nativeEventFilter(self, event_type, message):
        try:
            import ctypes, ctypes.wintypes as wt
            msg = ctypes.cast(int(message), ctypes.POINTER(wt.MSG)).contents
            if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                self._cb()
                return True, 0
        except Exception:
            pass
        return False, 0


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PulseMonitor")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._central = QWidget(); self.setCentralWidget(self._central)
        self._central.setStyleSheet(f"background:{C['bg1']};")
        vbox = QVBoxLayout(self._central); vbox.setContentsMargins(0,0,0,0); vbox.setSpacing(0)

        self._titlebar = TitleBar(self)
        self._titlebar.overlay_toggled.connect(self._toggle_overlay)
        vbox.addWidget(self._titlebar)

        self._update_banner = None
        self._banner_slot   = vbox

        self._body = QWidget(); self._body.setStyleSheet(f"background:{C['bg1']};")
        hbox = QHBoxLayout(self._body); hbox.setContentsMargins(0,0,0,0); hbox.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.page_selected.connect(self._switch_page)
        hbox.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{C['bg1']};")
        hbox.addWidget(self._stack, 1)
        vbox.addWidget(self._body, 1)

        self._status = QLabel("Starting…")
        self._status.setFixedHeight(26)
        self._status.setStyleSheet(f"background:{C['bg0']}; color:{C['t3']}; font-size:11px;"
                                    f" padding:0 16px; border-top:1px solid {C['b0']};")
        vbox.addWidget(self._status)

        # pages
        self._settings_page = SettingsPage()
        self._history_page  = HistoryPage()
        self._pages = [
            DashboardPage(),
            CpuPage(),
            MemoryPage(),
            GpuPage(),
            StoragePage(),
            ProcessPage(),
            StartupPage(),
            FansPage(),
            NetworkPage(),
            self._history_page,
            self._settings_page,
            AboutPage(),
        ]
        for page in self._pages:
            self._stack.addWidget(page)

        # connect settings signals
        self._settings_page.theme_changed.connect(self._on_theme_changed)
        self._dashboard_page = self._pages[0]
        self._storage_page   = self._pages[4]
        self._network_page   = self._pages[8]
        self._about_page     = self._pages[11]
        self._settings_page.dash_visibility_changed.connect(self._dashboard_page.apply_visibility)
        # apply saved visibility state immediately on startup
        self._dashboard_page.apply_visibility()

        # monitor
        self._tick_busy = False
        self._page_errors: Dict[int, int] = {}   # page_idx → consecutive error count
        self._monitor = MonitorThread()
        self._monitor.sig_tick.connect(self._on_tick)
        self._monitor.sig_alert.connect(self._on_alert)
        self._monitor.start()

        # history logging timer (every 60 s)
        self._last_metrics: Optional[Metrics] = None
        self._hist_timer = QTimer(self)
        self._hist_timer.timeout.connect(self._log_history)
        self._hist_timer.start(60_000)

        # auto-updater
        QTimer.singleShot(3000, self._start_update_check)

        # system tray
        self._tray = QSystemTrayIcon(make_tray_icon(), self)
        self._tray.setToolTip("PulseMonitor — running in background")
        tray_menu = QMenu()
        tray_menu.setStyleSheet(f"""
            QMenu {{ background:{C['bg2']}; border:1px solid {C['b0']}; color:{C['t1']}; padding:4px; }}
            QMenu::item {{ padding:6px 20px; border-radius:4px; }}
            QMenu::item:selected {{ background:{C['bg3']}; }}
        """)
        show_act = QAction("Show PulseMonitor", self); show_act.triggered.connect(self._show_from_tray)
        overlay_act = QAction("Toggle Overlay  (Ctrl+Shift+M)", self); overlay_act.triggered.connect(self._toggle_overlay)
        quit_act  = QAction("Quit", self); quit_act.triggered.connect(self.quit_app)
        tray_menu.addAction(show_act); tray_menu.addAction(overlay_act)
        tray_menu.addSeparator(); tray_menu.addAction(quit_act)
        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

        # mini overlay
        self._overlay = MiniOverlay()

        # global hotkey (Ctrl+Shift+M) via RegisterHotKey + app-level event filter
        self._hotkey_registered = False
        self._hotkey_filter = None
        if _IS_WIN:
            QTimer.singleShot(500, self._register_hotkey)

        self._resizing = False

    # ── hotkey ────────────────────────────────────────────────────
    def _register_hotkey(self):
        try:
            import ctypes
            hwnd = int(self.winId())
            ok = ctypes.windll.user32.RegisterHotKey(hwnd, _HOTKEY_ID, _MOD_CTRL | _MOD_SHIFT, _VK_M)
            if ok:
                self._hotkey_registered = True
                self._hotkey_filter = _HotkeyFilter(self._toggle_overlay)
                QApplication.instance().installNativeEventFilter(self._hotkey_filter)
        except Exception:
            pass

    # ── overlay ───────────────────────────────────────────────────
    def _toggle_overlay(self):
        if self._overlay.isVisible():
            self._overlay.hide()
        else:
            if self._last_metrics:
                self._overlay.update_metrics(self._last_metrics)
            self._overlay.show()

    # ── page switching ────────────────────────────────────────────
    def _switch_page(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self._monitor.set_active_page(idx)
        if idx == 0:
            self._dashboard_page.apply_visibility()
        elif idx == self._pages.index(self._history_page):
            self._history_page.refresh()

    # ── auto-updater ──────────────────────────────────────────────
    def _start_update_check(self):
        self._updater = UpdateChecker(self)
        self._updater.sig_update_available.connect(self._show_update_banner)
        self._updater.start()

    def _show_update_banner(self, version: str, url: str):
        if self._update_banner is not None: return
        banner = UpdateBanner(version, url, self.centralWidget())
        banner.dismissed.connect(self._hide_update_banner)
        self._update_banner = banner
        self._banner_slot.insertWidget(1, banner)

    def _hide_update_banner(self):
        if self._update_banner:
            self._update_banner.hide()
            self._banner_slot.removeWidget(self._update_banner)
            self._update_banner.deleteLater()
            self._update_banner = None

    # ── theme change ──────────────────────────────────────────────
    def _on_theme_changed(self):
        self._central.setStyleSheet(f"background:{C['bg1']};")
        self._body.setStyleSheet(f"background:{C['bg1']};")
        self._stack.setStyleSheet(f"background:{C['bg1']};")
        self._status.setStyleSheet(
            f"background:{C['bg0']}; color:{C['t3']}; font-size:11px;"
            f" padding:0 16px; border-top:1px solid {C['b0']};")
        self._titlebar.refresh_theme()
        self._sidebar.refresh_theme()
        self._dashboard_page.refresh_theme()
        self._storage_page.refresh_theme()
        self._network_page.refresh_theme()
        self._about_page.refresh_theme()
        DarkTable.refresh_all()

    # ── data ──────────────────────────────────────────────────────
    def _on_tick(self):
        if self._tick_busy:
            return
        self._tick_busy = True
        try:
            if getattr(self._titlebar, '_drag_pos', None) is not None:
                return
            m = self._monitor._snapshot
            if m is None:
                return
            self._last_metrics = m
            idx = self._stack.currentIndex()
            page = self._pages[idx]
            # Class-dict lookup calls the Python-defined update(m) without
            # triggering PyQt6's C++ QWidget.update() overload.
            _fn = type(page).__dict__.get("update")
            if _fn:
                err_count = self._page_errors.get(idx, 0)
                if err_count < 5:
                    try:
                        _fn(page, m)
                        if err_count:
                            self._page_errors[idx] = 0   # recovered
                    except Exception:
                        self._page_errors[idx] = err_count + 1
                        _write_crash(*sys.exc_info())
                        if err_count + 1 == 5:
                            self._status.setText(
                                f"  ⚠ Page error — switch to another page to recover")
            if self._overlay.isVisible():
                try:
                    self._overlay.update_metrics(m)
                except Exception:
                    pass
            if not self._page_errors.get(idx, 0) >= 5:
                self._status.setText(
                    f"  CPU {m.cpu_pct:.1f}%"
                    f"  ·  GPU {m.gpu_pct:.1f}%"
                    f"  ·  RAM {m.ram_pct:.1f}%"
                    f"  ·  ↓{fmt_bytes_rate(m.net_recv_rate)}  ↑{fmt_bytes_rate(m.net_sent_rate)}"
                    f"  ·  {datetime.now().strftime('%H:%M:%S')}"
                )
        except Exception:
            _write_crash(*sys.exc_info())
        finally:
            self._tick_busy = False

    def _log_history(self):
        m = self._last_metrics
        if m is None: return
        HISTORY_DB.insert(m.cpu_pct, m.gpu_pct, m.ram_pct,
                          m.cpu_temp, m.gpu_temp,
                          m.net_sent_rate, m.net_recv_rate)

    def _on_alert(self, title: str, msg: str):
        if self._tray.isVisible() and QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.showMessage(title, msg, QSystemTrayIcon.MessageIcon.Warning, 6000)

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self):
        self.showNormal(); self.raise_(); self.activateWindow()

    def showEvent(self, event):
        super().showEvent(event)
        self._monitor.set_window_visible(True)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._monitor.set_window_visible(False)

    def closeEvent(self, event):
        event.ignore(); self.hide()
        self._tray.showMessage("PulseMonitor",
            "Monitoring continues in the background. Double-click the tray icon to restore.",
            QSystemTrayIcon.MessageIcon.Information, 3000)

    def quit_app(self):
        try:
            with open(_CRASH_LOG, "a", encoding="utf-8") as _f:
                import traceback as _tb
                _f.write(f"\nQUIT  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                _f.write("".join(_tb.format_stack()) + "\n")
        except Exception:
            pass
        if _IS_WIN and self._hotkey_registered:
            try:
                import ctypes
                ctypes.windll.user32.UnregisterHotKey(int(self.winId()), _HOTKEY_ID)
                if self._hotkey_filter:
                    QApplication.instance().removeNativeEventFilter(self._hotkey_filter)
            except Exception: pass
        self._monitor.stop()
        self._hist_timer.stop()
        QApplication.quit()

    # ── resize grip ───────────────────────────────────────────────
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            pos = e.position().toPoint()
            self._resizing = pos.x() > self.width()-16 and pos.y() > self.height()-16
            if self._resizing:
                self._resize_start = e.globalPosition().toPoint()
                self._start_size   = self.size()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._resizing and e.buttons() == Qt.MouseButton.LeftButton:
            delta = e.globalPosition().toPoint() - self._resize_start
            self.resize(max(800, self._start_size.width()+delta.x()),
                        max(600, self._start_size.height()+delta.y()))
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._resizing = False; super().mouseReleaseEvent(e)


# ══════════════════════════════════════════════════════════════════
# AUTO-UPDATER
# ══════════════════════════════════════════════════════════════════
class UpdateChecker(QThread):
    sig_update_available = pyqtSignal(str, str)

    def run(self):
        try:
            api = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(api, headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"PulseMonitor/{APP_VERSION}",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name","").lstrip("v")
            if tag and self._is_newer(tag, APP_VERSION):
                self.sig_update_available.emit(tag, "https://vaultsoft.gumroad.com/l/PulseMonitor")
        except Exception:
            pass

    @staticmethod
    def _is_newer(remote: str, local: str) -> bool:
        def parts(v):
            try: return tuple(int(x) for x in v.split("."))
            except: return (0,)
        return parts(remote) > parts(local)


class UpdateBanner(QWidget):
    dismissed = pyqtSignal()

    def __init__(self, version: str, url: str, parent=None):
        super().__init__(parent)
        self._url = url; self.setFixedHeight(38)
        self.setStyleSheet(f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                           f"stop:0 {C['acc2']},stop:1 #004D3A); border-bottom:1px solid {C['acc']};")
        row = QHBoxLayout(self); row.setContentsMargins(14,0,10,0); row.setSpacing(10)
        icon = QLabel("↑"); icon.setStyleSheet(f"color:{C['acc']}; font-size:14px; font-weight:800; background:transparent;")
        msg = QLabel(f"PulseMonitor {version} is available — ")
        msg.setStyleSheet(f"color:{C['t1']}; font-size:12px; background:transparent;")
        link = QPushButton("Download now")
        link.setStyleSheet(f"QPushButton {{ color:{C['acc']}; font-size:12px; font-weight:600; background:transparent; border:none; text-decoration:underline; padding:0; }} QPushButton:hover {{ color:{C['t1']}; }}")
        link.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        link.clicked.connect(lambda: __import__("webbrowser").open(self._url))
        close_btn = QPushButton("✕"); close_btn.setFixedSize(22,22)
        close_btn.setStyleSheet(f"QPushButton {{ color:{C['t2']}; font-size:11px; background:transparent; border:none; border-radius:11px; }} QPushButton:hover {{ background:{C['bg3']}; color:{C['t1']}; }}")
        close_btn.clicked.connect(self.dismissed.emit)
        row.addWidget(icon); row.addWidget(msg); row.addWidget(link)
        row.addStretch(); row.addWidget(close_btn)


# ══════════════════════════════════════════════════════════════════
# CRASH LOGGER
# ══════════════════════════════════════════════════════════════════
_APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PulseMonitor")
os.makedirs(_APP_DATA_DIR, exist_ok=True)
_CRASH_LOG = os.path.join(_APP_DATA_DIR, "crash.log")

def _write_crash(exc_type, exc_value, exc_tb):
    try:
        with open(_CRASH_LOG, "a", encoding="utf-8") as f:
            f.write("\n" + "="*70 + "\n")
            f.write(f"CRASH  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" + "="*70 + "\n")
            f.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)) + "\n")
    except Exception: pass

def _qt_message_handler(mode, context, message):
    from PyQt6.QtCore import QtMsgType
    if mode in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
        try:
            with open(_CRASH_LOG, "a", encoding="utf-8") as f:
                f.write(f"\nQT {mode.name}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"  {context.file}:{context.line}  {message}\n")
        except Exception: pass


# ══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════
def main():
    sys.excepthook = _write_crash
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("PulseMonitor")
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")
    app.setStyleSheet(_global_style())
    from PyQt6.QtCore import qInstallMessageHandler
    qInstallMessageHandler(_qt_message_handler)
    def _slot_hook(et, ev, etb):
        _write_crash(et, ev, etb); sys.__excepthook__(et, ev, etb)
    sys.excepthook = _slot_hook

    # app icon from logo PNG
    _logo_pm = _get_logo(64)
    app.setWindowIcon(QIcon(_logo_pm) if not _logo_pm.isNull() else QIcon())

    try:
        with open(_CRASH_LOG, "a", encoding="utf-8") as _f:
            _f.write(f"\nSTARTUP  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  v{APP_VERSION}\n")
    except Exception:
        pass

    try:
        win = MainWindow()
    except Exception:
        _write_crash(*sys.exc_info()); raise

    # wire quit action
    for action in win._tray.contextMenu().actions():
        if action.text() == "Quit":
            try: action.triggered.disconnect()
            except Exception: pass
            action.triggered.connect(win.quit_app)

    # centre on primary screen
    screen_geo = app.primaryScreen().availableGeometry()
    win.move(screen_geo.center() - win.rect().center())
    win.show()
    win.raise_()
    win.activateWindow()

    # DWM rounded corners (Windows 11)
    if _IS_WIN:
        try:
            import ctypes
            hwnd = int(win.winId())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int))
        except Exception: pass

    try:
        sys.exit(app.exec())
    except SystemExit:
        raise
    except Exception:
        _write_crash(*sys.exc_info()); raise


if __name__ == "__main__":
    main()
