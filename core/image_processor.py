import io
import base64
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

def apply_translations_to_image(image_bytes, bubbles, font_path=None):
    img  = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    for bubble in bubbles:
        translation = bubble.get("translation", "").strip()
        if not translation:
            continue

        bbox = bubble["bbox"]
        pad  = int(min(w, h) * 0.01)
        x1   = max(0, int(bbox["left"]  * w) - pad)
        y1   = max(0, int(bbox["upper"] * h) - pad)
        x2   = min(w, int(bbox["right"] * w) + pad)
        y2   = min(h, int(bbox["lower"] * h) + pad)

        region   = img.crop((x1, y1, x2, y2))
        bg_color = _detect_bg(region)

        draw.rectangle([x1, y1, x2, y2], fill=bg_color)
        region_blur = img.crop((x1, y1, x2, y2)).filter(ImageFilter.GaussianBlur(radius=1))
        img.paste(region_blur, (x1, y1))

        draw = ImageDraw.Draw(img)
        _render_text(draw, translation, x1, y1, x2, y2, bg_color, font_path)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def image_to_base64(image_bytes):
    return base64.b64encode(image_bytes).decode("utf-8")


def get_image_dimensions(image_bytes):
    return Image.open(io.BytesIO(image_bytes)).size


def _detect_bg(region):
    arr  = np.array(region)
    mask = arr.mean(axis=2) > 180
    if mask.sum() > 50:
        bg = tuple(np.median(arr[mask], axis=0).astype(int))
        return (int(bg[0]), int(bg[1]), int(bg[2]))
    return (255, 255, 255)


def _render_text(draw, text, x1, y1, x2, y2, bg_color, font_path):
    box_w = x2 - x1
    box_h = y2 - y1
    if box_w < 10 or box_h < 10:
        return

    text_color = (0, 0, 0) if sum(bg_color) / 3 > 128 else (255, 255, 255)

    for font_size in range(min(box_h // 2, 22), 7, -1):
        try:
            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default(size=font_size)
        except Exception:
            font = ImageFont.load_default()

        chars_per_line = max(1, int(box_w / (font_size * 0.55)))
        lines          = textwrap.wrap(text, width=chars_per_line)
        line_height    = font_size + 2
        total_height   = line_height * len(lines)

        if total_height <= box_h:
            start_y = y1 + (box_h - total_height) // 2
            for i, line in enumerate(lines):
                try:
                    bbox_t = draw.textbbox((0, 0), line, font=font)
                    line_w = bbox_t[2] - bbox_t[0]
                except Exception:
                    line_w = len(line) * font_size * 0.55
                start_x = x1 + (box_w - line_w) // 2
                draw.text((start_x, start_y + i * line_height), line, fill=text_color, font=font)
            return

    try:
        font = ImageFont.load_default(size=8)
    except Exception:
        font = ImageFont.load_default()
    draw.text((x1 + 2, y1 + 2), text[:30], fill=text_color, font=font)
