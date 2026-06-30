#!/usr/bin/env python3
"""Generate test images for vibecleaner development/testing.

Creates a variety of comic-style pages with speech bubbles, cloud text,
sound effects, and edge cases for testing detect/OCR/inpaint pipelines.
"""

from PIL import Image, ImageDraw, ImageFont
import os

OUTPUT_DIR = "test_samples"
WIDTH, HEIGHT = 1200, 1700  # Typical manga page aspect ratio


def ensure_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Helper: draw shapes
# ---------------------------------------------------------------------------

def _bubble_font(size=28):
    """Try to load a font that supports Korean/Japanese; fall back to default."""
    candidates = [
        r"C:\Windows\Fonts\malgun.ttf",       # Malgun Gothic (Korean)
        r"C:\Windows\Fonts\simhei.ttf",        # SimHei (Chinese)
        r"C:\Windows\Fonts\arial.ttf",         # Arial (English)
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_ellipse_bubble(draw, bbox, fill="white", outline="black", width=3):
    """Draw an ellipse speech bubble."""
    x0, y0, x1, y1 = bbox
    draw.ellipse([x0, y0, x1, y1], fill=fill, outline=outline, width=width)


def draw_cloud_bubble(draw, center_x, center_y, w, h, fill="white", outline="black", width=3):
    """Draw a puffy cloud-style speech bubble using overlapping circles."""
    r = min(w, h) // 4
    points = []
    # Top bumps
    for i in range(5):
        cx = center_x - w // 2 + r + i * (w - 2 * r) // 4
        cy = center_y - h // 4
        points.append((cx - r, cy - r, cx + r, cy + r))
    # Bottom bumps
    for i in range(5):
        cx = center_x - w // 2 + r + i * (w - 2 * r) // 4
        cy = center_y + h // 4
        points.append((cx - r, cy - r, cx + r, cy + r))
    # Side bumps
    draw.ellipse([center_x - w // 2 - r // 2, center_y - r,
                  center_x - w // 2 + r // 2, center_y + r], fill=fill)
    draw.ellipse([center_x + w // 2 - r // 2, center_y - r,
                  center_x + w // 2 + r // 2, center_y + r], fill=fill)
    # Main body
    draw.rounded_rectangle(
        [center_x - w // 2, center_y - h // 2,
         center_x + w // 2, center_y + h // 2],
        radius=r, fill=fill, outline=outline, width=width
    )
    # Top/bottom bumps
    for p in points:
        draw.ellipse(p, fill=fill, outline=outline, width=width)


def draw_rect_bubble(draw, bbox, fill="white", outline="black", width=3, radius=12):
    """Draw a rounded-rectangle speech/thought bubble."""
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius,
                           fill=fill, outline=outline, width=width)


def draw_text_multiline(draw, text, x, y, max_w, font, color="black", line_spacing=8):
    """Wrap and draw text within max_w."""
    lines = text.split("\n")
    cy = y
    for line in lines:
        draw.text((x, cy), line, font=font, fill=color)
        cy += font.getbbox(line)[-1] + line_spacing
    return cy


def draw_tail(draw, bubble_x1, bubble_y1, tail_x, tail_y, fill="white", outline="black", width=3):
    """Draw a small triangle tail from bubble to a point."""
    tail_w, tail_h = 30, 60
    pts = [
        (bubble_x1 - 15, bubble_y1),
        (bubble_x1 + 15, bubble_y1),
        (tail_x, tail_y),
    ]
    draw.polygon(pts, fill=fill, outline=outline)


# ---------------------------------------------------------------------------
# Sample 1: Basic — three ellipse bubbles with Korean text
# ---------------------------------------------------------------------------

def sample_basic_bubbles():
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    font = _bubble_font(30)

    bubbles = [
        ((200, 100, 600, 350), "안녕하세요!\n오늘 날씨가 좋네요."),
        ((150, 500, 550, 750), "이건 테스트용 말풍선이에요.\n텍스트 인식이 잘 될까요?"),
        ((300, 900, 700, 1150), "네, 잘 보입니다!\n감사합니다."),
    ]

    for (bbox, text) in bubbles:
        draw_ellipse_bubble(draw, bbox)
        draw_text_multiline(draw, text, bbox[0] + 40, bbox[1] + 40,
                            bbox[2] - bbox[0] - 80, font)

    img.save(os.path.join(OUTPUT_DIR, "01_basic_bubbles.png"))
    print("  [ok] 01_basic_bubbles.png")


# ---------------------------------------------------------------------------
# Sample 2: Cloud bubbles (angry/shouting style)
# ---------------------------------------------------------------------------

def sample_cloud_bubbles():
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    font = _bubble_font(26)

    clouds = [
        (400, 250, 500, 300, "화나면 이렇게\n말해요!"),
        (600, 700, 450, 280, "진짜 기절할 정도야!"),
        (350, 1100, 550, 320, "이건 긴 텍스트 테스트입니다.\n여러 줄에 걸쳐서 텍스트가 어떻게\n보이는지 확인해 봐요."),
    ]

    for (cx, cy, w, h, text) in clouds:
        draw_cloud_bubble(draw, cx, cy, w, h)
        draw_text_multiline(draw, text, cx - 100, cy - 20, 200, font)

    img.save(os.path.join(OUTPUT_DIR, "02_cloud_bubbles.png"))
    print("  [ok] 02_cloud_bubbles.png")


# ---------------------------------------------------------------------------
# Sample 3: Complex background with gradient + pattern
# ---------------------------------------------------------------------------

def sample_complex_bg():
    img = Image.new("RGB", (WIDTH, HEIGHT), "#f0ebe3")
    draw = ImageDraw.Draw(img)
    font = _bubble_font(28)

    # Draw some background elements (simulated manga panels)
    draw.rectangle([0, 0, WIDTH, HEIGHT // 2], fill="#e8e0d4", outline="#ccc", width=2)
    draw.rectangle([0, HEIGHT // 2, WIDTH, HEIGHT], fill="#ddd5c8", outline="#ccc", width=2)

    # Diagonal speed lines in background
    for i in range(0, WIDTH, 20):
        draw.line([(i, 0), (i + 200, HEIGHT)], fill="#d5cfc5", width=1)

    # Bubbles on top
    draw_ellipse_bubble(draw, (100, 80, 500, 330))
    draw_text_multiline(draw, "배경이 복잡한 페이지입니다.\n속도선이 그려져 있어요.",
                        140, 120, 320, font)

    draw_rect_bubble(draw, (150, 500, 650, 750))
    draw_text_multiline(draw, "패널 구분이 명확한지\n확인해 보세요.",
                        190, 540, 420, font)

    draw_ellipse_bubble(draw, (250, 900, 650, 1150))
    draw_text_multiline(draw, "아래쪽 패널도\n정상적으로 인식될까요?",
                        290, 940, 320, font)

    # Small thought bubble
    draw_ellipse_bubble(draw, (750, 1300, 1050, 1500))
    draw_text_multiline(draw, "음...", 830, 1340, 180, font)

    img.save(os.path.join(OUTPUT_DIR, "03_complex_bg.png"))
    print("  [ok] 03_complex_bg.png")


# ---------------------------------------------------------------------------
# Sample 4: Sound effects (large stylized text, no bubble)
# ---------------------------------------------------------------------------

def sample_sfx():
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    font_big = _bubble_font(80)
    font_med = _bubble_font(50)

    # SFX text directly on canvas (no bubble)
    draw.text((200, 150), "쾅!", font=font_big, fill="red")
    draw.text((350, 500), "바람바람", font=font_med, fill="#3366cc")
    draw.text((150, 900), "두두두두두", font=font_med, fill="#cc3333")

    # A normal bubble for context
    draw_ellipse_bubble(draw, (300, 1200, 700, 1450))
    font_small = _bubble_font(28)
    draw_text_multiline(draw, "효과음이 있는 페이지입니다.", 340, 1240, 320, font_small)

    img.save(os.path.join(OUTPUT_DIR, "04_sfx.png"))
    print("  [ok] 04_sfx.png")


# ---------------------------------------------------------------------------
# Sample 5: Edge case — blank page (no bubbles at all)
# ---------------------------------------------------------------------------

def sample_blank():
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    img.save(os.path.join(OUTPUT_DIR, "05_blank_page.png"))
    print("  [ok] 05_blank_page.png")


# ---------------------------------------------------------------------------
# Sample 6: Edge case — very small text
# ---------------------------------------------------------------------------

def sample_small_text():
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    font_tiny = _bubble_font(10)  # Very small

    draw_ellipse_bubble(draw, (100, 100, 500, 300))
    draw_text_multiline(draw, "이 텍스트는 매우 작아요.\n인식이 될까요?", 130, 140, 340, font_tiny)

    # Normal size for comparison
    font_normal = _bubble_font(28)
    draw_ellipse_bubble(draw, (100, 500, 500, 750))
    draw_text_multiline(draw, "이건 정상 크기입니다.", 130, 540, 340, font_normal)

    img.save(os.path.join(OUTPUT_DIR, "06_small_text.png"))
    print("  [ok] 06_small_text.png")


# ---------------------------------------------------------------------------
# Sample 7: Many bubbles (density test)
# ---------------------------------------------------------------------------

def sample_dense():
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    font = _bubble_font(22)

    positions = [
        (50, 50, 300, 200, "첫 번째"),
        (400, 50, 650, 200, "두 번째"),
        (700, 50, 950, 200, "세 번째"),
        (50, 250, 300, 400, "네 번째"),
        (400, 250, 650, 400, "다섯 번째"),
        (700, 250, 950, 400, "여섯 번째"),
        (50, 450, 300, 600, "일곱 번째"),
        (400, 450, 650, 600, "여덟 번째"),
        (700, 450, 950, 600, "아홉 번째"),
        (200, 700, 500, 900, "열 번째"),
        (600, 700, 900, 900, "열한 번째"),
        (100, 1000, 450, 1200, "열두 번째"),
    ]

    for (x0, y0, x1, y1, label) in positions:
        draw_ellipse_bubble(draw, (x0, y0, x1, y1))
        draw.text((x0 + 20, y0 + 30), label, font=font, fill="black")

    img.save(os.path.join(OUTPUT_DIR, "07_dense_bubbles.png"))
    print("  [ok] 07_dense_bubbles.png")


# ---------------------------------------------------------------------------
# Sample 8: Mixed languages (Korean + Japanese + English)
# ---------------------------------------------------------------------------

def sample_mixed_lang():
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    font = _bubble_font(28)

    bubbles = [
        (100, 100, 500, 350, "한국어 테스트입니다."),
        (100, 450, 500, 700, "日本語テストです。\nちゃんと認識されますか？"),
        (100, 800, 500, 1050, "English test.\nCan you read this?"),
        (100, 1150, 500, 1400, "혼합: Hello!\nこんにちは!\n안녕하세요!"),
    ]

    for (x0, y0, x1, y1, text) in bubbles:
        draw_ellipse_bubble(draw, (x0, y0, x1, y1))
        draw_text_multiline(draw, text, x0 + 30, y0 + 30, x1 - x0 - 60, font)

    img.save(os.path.join(OUTPUT_DIR, "08_mixed_languages.png"))
    print("  [ok] 08_mixed_languages.png")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ensure_dir()
    print("Generating test images...")
    sample_basic_bubbles()
    sample_cloud_bubbles()
    sample_complex_bg()
    sample_sfx()
    sample_blank()
    sample_small_text()
    sample_dense()
    sample_mixed_lang()
    print(f"\nDone! 8 samples saved to {os.path.abspath(OUTPUT_DIR)}/")
