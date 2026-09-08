from PIL import Image, ImageDraw, ImageFilter
import numpy as np

S = 1000
BG    = (10,  14,  26)      # #0a0e1a  navy background
TEAL  = (0,  212, 170)      # #00D4AA  teal
WHITE = (220, 255, 248)     # near-white dot core

# ── Canvas ────────────────────────────────────────────────────────
canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))

# ── Layer helper ──────────────────────────────────────────────────
def new_layer():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))

def composite(base, layer):
    return Image.alpha_composite(base, layer)

# ══════════════════════════════════════════════════════════════════
# 1. BACKGROUND — rounded square
# ══════════════════════════════════════════════════════════════════
bg_layer = new_layer()
d = ImageDraw.Draw(bg_layer)
RADIUS   = 120          # corner radius
MARGIN   = 18           # inset from canvas edge
d.rounded_rectangle(
    [MARGIN, MARGIN, S - MARGIN, S - MARGIN],
    radius=RADIUS,
    fill=BG + (255,)
)
canvas = composite(canvas, bg_layer)

# ══════════════════════════════════════════════════════════════════
# 2. BORDER — teal rounded rectangle stroke (glow + crisp)
# ══════════════════════════════════════════════════════════════════
BORDER_INSET = 28

def draw_border(width, alpha):
    layer = new_layer()
    d = ImageDraw.Draw(layer)
    half = width // 2
    inset = BORDER_INSET + half
    d.rounded_rectangle(
        [inset, inset, S - inset, S - inset],
        radius=RADIUS - (BORDER_INSET - MARGIN),
        outline=TEAL + (alpha,),
        width=width
    )
    return layer

# outer glow
for w, a, blur in [(22, 40, 8), (14, 70, 5), (8, 120, 3)]:
    bl = draw_border(w, a)
    bl = bl.filter(ImageFilter.GaussianBlur(blur))
    canvas = composite(canvas, bl)

# crisp core stroke
canvas = composite(canvas, draw_border(6, 255))

# ══════════════════════════════════════════════════════════════════
# 3. ECG PATH — QRS complex
#    Baseline at y=540.  Coords tuned to match the original icon.
# ══════════════════════════════════════════════════════════════════
BL = 540    # baseline y
ECG = [
    (60,  BL),          # lead-in flat left edge
    (295, BL),          # flat to P-wave start
    (330, BL - 55),     # P-wave peak
    (365, BL),          # P-wave return to baseline
    (395, BL + 48),     # Q dip
    (440, BL - 330),    # R spike peak  ← glow dot here
    (480, BL + 88),     # S deep undershoot
    (518, BL),          # S return to baseline
    (555, BL - 65),     # T-wave peak
    (610, BL),          # T-wave end
    (940, BL),          # flat tail to right edge
]
PEAK = (440, BL - 330)

def interp(pts, density=6000):
    out = []
    total_x = pts[-1][0] - pts[0][0]
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]; x1, y1 = pts[i + 1]
        n = max(3, int(density * abs(x1 - x0) / total_x))
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append((x0 + t*(x1-x0), y0 + t*(y1-y0)))
    out.append(pts[-1])
    return out

fine_pts = interp(ECG)

# Glow layers for the ECG line
ecg_glow = [
    (30, 18),   # (width, alpha)  outermost haze
    (20, 40),
    (14, 70),
    (9,  110),
    (6,  180),
    (4,  255),  # crisp core
]

for width, alpha in ecg_glow:
    layer = new_layer()
    d = ImageDraw.Draw(layer)
    d.line(fine_pts, fill=TEAL + (alpha,), width=width, joint="curve")
    if width >= 6:
        layer = layer.filter(ImageFilter.GaussianBlur(radius=width * 0.55))
    canvas = composite(canvas, layer)

# ══════════════════════════════════════════════════════════════════
# 4. GLOW DOT at spike peak
# ══════════════════════════════════════════════════════════════════
px, py = PEAK

dot_layers = [
    (90,  28,  TEAL,  14),   # (radius, alpha, colour, blur)
    (62,  55,  TEAL,  10),
    (42,  90,  TEAL,   7),
    (28, 140,  TEAL,   4),
    (18, 200,  WHITE,  2),
    (10, 240,  WHITE,  1),
    ( 6, 255,  WHITE,  0),   # solid bright core
]

for radius, alpha, colour, blur in dot_layers:
    layer = new_layer()
    d = ImageDraw.Draw(layer)
    d.ellipse([px-radius, py-radius, px+radius, py+radius],
              fill=colour + (alpha,))
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    canvas = composite(canvas, layer)

# ══════════════════════════════════════════════════════════════════
# 5. Save
# ══════════════════════════════════════════════════════════════════
canvas.convert("RGB").save("logo_pulsemonitor_hd.png", "PNG", optimize=True)
print("Saved logo_pulsemonitor_hd.png")
