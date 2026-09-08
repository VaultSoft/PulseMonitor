from PIL import Image, ImageDraw, ImageFilter
import numpy as np

SIZE = 1000
BG   = (10, 14, 26)        # #0a0e1a
TEAL = (0, 212, 170)       # #00D4AA

img = Image.new("RGBA", (SIZE, SIZE), BG + (255,))

# ── ECG path points ───────────────────────────────────────────────
# Horizontal centre-line sits at 55% down so the spike has room above
CY   = int(SIZE * 0.55)
MID  = SIZE // 2

# Flat lead-in → small pre-notch → sharp spike → overshoot → flat tail
pts = [
    (0,       CY),
    (280,     CY),           # flat lead-in
    (340,     CY + 18),      # tiny downward notch (Q)
    (370,     CY - 10),      # back up to baseline (R foot)
    (400,     CY - 300),     # peak (R spike)
    (430,     CY + 60),      # undershoot (S)
    (460,     CY + 30),      # S tail
    (500,     CY),           # return to baseline
    (560,     CY - 40),      # T-wave hump
    (620,     CY),           # end of T
    (1000,    CY),           # flat tail
]

PEAK_PT = (400, CY - 300)   # where the glow dot sits

def interp_pts(points, steps=8000):
    """Linearly interpolate a polyline into many fine points."""
    out = []
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        n = max(2, int(steps * abs(x1 - x0) / SIZE))
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    out.append(points[-1])
    return out

fine = interp_pts(pts)

# ── Glow layers: draw line repeatedly at decreasing opacity/width ──
glow_layers = [
    (22, 30),   # (width, alpha)  outermost, faintest
    (14, 55),
    (9,  90),
    (5, 140),
    (3, 200),
    (2, 255),   # core line, fully opaque
]

for width, alpha in glow_layers:
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    colour = TEAL + (alpha,)
    d.line(fine, fill=colour, width=width, joint="curve")
    # gentle blur on wide layers for smooth falloff
    if width >= 5:
        layer = layer.filter(ImageFilter.GaussianBlur(radius=width * 0.6))
    img = Image.alpha_composite(img, layer)

# ── Glow dot at spike peak ─────────────────────────────────────────
px, py = PEAK_PT
dot_layers = [
    (55, 40),   # (radius, alpha)
    (36, 80),
    (22, 130),
    (13, 200),
    (7,  255),  # bright core
]

for radius, alpha in dot_layers:
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse(
        [px - radius, py - radius, px + radius, py + radius],
        fill=TEAL + (alpha,)
    )
    layer = layer.filter(ImageFilter.GaussianBlur(radius=radius * 0.5))
    img = Image.alpha_composite(img, layer)

# Solid bright dot centre on top
layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(layer)
d.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(220, 255, 248, 255))
img = Image.alpha_composite(img, layer)

# ── Save ──────────────────────────────────────────────────────────
out = img.convert("RGB")
out.save("logo_pulsemonitor.png", "PNG", optimize=True)
print("Saved logo_pulsemonitor.png")
