#!/usr/bin/env python3
"""Benchmark edge_margin formulas across various crop sizes.

Compares:
  current: max(5, min_dim // 15)
  alt_log: max(4, min(20, int(min_dim ** 0.5 * 2.5)))
  alt_asym: directional-independent with clamped range

Outputs a visual comparison image showing the protected zone (black) vs
active inpaint zone (white) for each formula at representative sizes.
"""

from PIL import Image, ImageDraw, ImageFont
import os

# ── Formulas ────────────────────────────────────────────────────────────────

def current_formula(min_dim: int) -> int:
    return max(5, min_dim // 15)

def alt_log(min_dim: int) -> int:
    return max(4, min(20, int(min_dim ** 0.5 * 2.5)))

def alt_clamped(min_dim: int) -> int:
    """Linear with hard clamp: 5..15px regardless of size."""
    return max(5, min(15, min_dim // 20))

FORMULAS = [
    ("current\n(min//15)", current_formula),
    ("alt_log\n(sqrt scale)", alt_log),
    ("alt_clamped\n(5..15)", alt_clamped),
]

# ── Representative crop sizes (from actual bubble detections) ──────────────

SIZES = [
    (50, 50),      # tiny text bubble
    (80, 60),      # small rectangular
    (120, 100),    # medium
    (200, 150),    # typical speech bubble
    (300, 250),    # large
    (400, 400),    # very large
    (600, 500),    # extra large
]

# ── Render comparison ──────────────────────────────────────────────────────

CELL_W = 180
CELL_H = 140
PAD = 20
TITLE_H = 60
LABEL_H = 50
TOTAL_W = PAD * 2 + CELL_W * len(SIZES) + (CELL_W - 160)  # extra space
TOTAL_H = PAD * 2 + CELL_H * len(FORMULAS) + TITLE_H + LABEL_H

img = Image.new("RGB", (TOTAL_W, TOTAL_H), "#1a1a2e")
draw = ImageDraw.Draw(img)

try:
    font_title = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 16)
    font_label = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 12)
    font_small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 10)
except Exception:
    font_title = ImageFont.load_default()
    font_label = font_small = font_title

# Title
draw.text((PAD, 10), "Edge Margin Formula Comparison", fill="white", font=font_title)
draw.text((PAD, 30), "White = inpaint active zone  |  Black = protected edge zone", fill="#aaa", font=font_small)

for col, (cw, ch) in enumerate(SIZES):
    x = PAD + col * CELL_W + 10
    draw.text((x, 50), f"{cw}x{ch}", fill="#8888cc", font=font_small)

for row, (name, formula) in enumerate(FORMULAS):
    y_base = PAD + TITLE_H + row * CELL_H

    # Formula name label
    draw.text((4, y_base + 30), name, fill="#ffcc00", font=font_label)

    for col, (cw, ch) in enumerate(SIZES):
        x = PAD + col * CELL_W + 10
        y = y_base + 10

        min_dim = min(cw, ch)
        margin = formula(min_dim)

        # Scale up for visibility (4x)
        scale = 4
        sw = cw * scale
        sh = ch * scale
        sm = margin * scale

        # Draw background (active zone = white)
        draw.rectangle([x, y, x + sw, y + sh], fill="white")

        # Draw protected border (black inset)
        draw.rectangle([x, y, x + sw, y + sm], fill="black")  # top
        draw.rectangle([x, y + sh - sm, x + sw, y + sh], fill="black")  # bottom
        draw.rectangle([x, y, x + sm, y + sh], fill="black")  # left
        draw.rectangle([x + sw - sm, y, x + sw, y + sh], fill="black")  # right

        # Margin value
        margin_pct = (margin / min_dim * 100) if min_dim > 0 else 0
        draw.text((x + 4, y + sh + 2), f"{margin}px ({margin_pct:.1f}%)", fill="#ccc")

# ── Numerical table ─────────────────────────────────────────────────────────

print("=" * 70)
print(f"{'Crop':>10} | {'MinDim':>6} | {'Current':>8} | {'Alt_Log':>8} | {'Clamped':>8}")
print("-" * 70)
for cw, ch in SIZES:
    m = min(cw, ch)
    c = current_formula(m)
    l = alt_log(m)
    cl = alt_clamped(m)
    c_pct = c / m * 100
    l_pct = l / m * 100
    cl_pct = cl / m * 100
    print(f"  {cw}x{ch:>3}  | {m:>4}  | {c:>3}px ({c_pct:4.1f}%) | {l:>3}px ({l_pct:4.1f}%) | {cl:>3}px ({cl_pct:4.1f}%)")

print("=" * 70)
print()

# ── Analyze with actual test images ─────────────────────────────────────────

print("Analysis with test_samples/ images:")
print("-" * 70)

test_dir = "test_samples"
if os.path.exists(test_dir):
    for fname in sorted(os.listdir(test_dir)):
        if fname.endswith(".png"):
            fpath = os.path.join(test_dir, fname)
            try:
                ti = Image.open(fpath)
                tw, th = ti.size
                # Simulate: if a bubble occupies ~20% of page width
                bubble_w = int(tw * 0.2)
                bubble_h = int(th * 0.08)
                crop_min = min(bubble_w, bubble_h)
                margin_cur = current_formula(crop_min)
                margin_log = alt_log(crop_min)
                margin_clamp = alt_clamped(crop_min)
                print(f"  {fname:<30} page={tw}x{th}  "
                      f"est_bubble~{bubble_w}x{bubble_h}  "
                      f"margin: cur={margin_cur}px log={margin_log}px clamp={margin_clamp}px")
            except Exception:
                pass
else:
    print("  test_samples/ not found")

print()

# Save visualization
out_dir = "test_samples"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "_edge_margin_comparison.png")
img.save(out_path)
print(f"Visualization saved to: {out_path}")
