from PIL import Image, ImageDraw, ImageFilter
import numpy as np

S    = 1000
BG   = (10, 14, 26)
TEAL = (0, 212, 170)

CY = 500  # baseline y

ECG = [
    (0,   CY),
    (320, CY),       # flat lead-in
    (390, CY - 12),  # tiny pre-notch up
    (420, CY + 22),  # Q dip
    (460, CY - 320), # R spike peak
    (500, CY + 30),  # S undershoot
    (530, CY),       # return to baseline
    (1000, CY),      # flat tail
]

def interp(pts, density=8000):
    out = []
    total_x = pts[-1][0] - pts[0][0]
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]; x1, y1 = pts[i + 1]
        n = max(3, int(density * abs(x1 - x0) / total_x))
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append((x0 + t*(x1-x0), y0 + t*(y1-y0)))
    out.append(pts[-1])
    return out

fine = interp(ECG)

canvas = Image.new("RGBA", (S, S), BG + (255,))

glow_layers = [
    (18, 18),
    (10, 45),
    (6,  90),
    (3, 200),
    (2, 255),
]

for width, alpha in glow_layers:
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(layer).line(fine, fill=TEAL + (alpha,), width=width, joint="curve")
    if width >= 6:
        layer = layer.filter(ImageFilter.GaussianBlur(width * 0.5))
    canvas = Image.alpha_composite(canvas, layer)

canvas.convert("RGB").save("logo_pulsemonitor_v3.png", "PNG", optimize=True)
print("Saved logo_pulsemonitor_v3.png")
