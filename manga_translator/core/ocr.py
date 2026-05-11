import base64
import json
import os
import re
import requests

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL_ID       = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"

SYSTEM_PROMPT = """You are a manga OCR assistant.
Extract ALL text from the manga image and return ONLY a valid JSON array. Nothing else.

Format:
[{"text": "bubble text", "left": 0.05, "upper": 0.10, "right": 0.45, "lower": 0.25}]

- left/upper/right/lower: normalized coordinates 0.0 to 1.0, origin at top-left
- Join multi-line bubbles with a space
- Include speech bubbles, thought bubbles, narration boxes, sound effects
- Return [] if no text found
- NO explanation, NO markdown, ONLY the JSON array"""

USER_PROMPT = "Extract all text bubbles. Return ONLY the JSON array."


def _detect_format(image_bytes):
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return "png"
    if image_bytes[:3] == b'\xff\xd8\xff':
        return "jpeg"
    if image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        return "webp"
    return "png"


def _clean_and_parse(raw):
    text = raw.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    start = text.find('[')
    if start == -1:
        return []

    depth = in_str = escape = False
    depth = 0
    end = -1
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end == -1:
        return []

    text = text[start:end]
    text = re.sub(r',\s*\[[0-9.,\s]+\]', '', text)

    def sanitize(m):
        inner = m.group(1)
        inner = inner.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        inner = re.sub(r'  +', ' ', inner).strip()
        return f'"{inner}"'
    text = re.sub(r'"((?:[^"\\]|\\.)*)"', sanitize, text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return []

def extract_text_from_image(image_bytes, api_key):
    api_key = api_key or os.getenv("NVIDIA_API_KEY", "")

    if not api_key or api_key.startswith("nvapi-XXXX"):
        return _mock_response()

    fmt      = _detect_format(image_bytes)
    b64      = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/{fmt};base64,{b64}"

    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text",      "text": USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }
        ],
        "max_tokens": 4096,
        "temperature": 0.1,
        "chat_template_kwargs": {"enable_thinking": False}
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept":        "application/json",
        "Content-Type":  "application/json"
    }

    resp = requests.post(NVIDIA_API_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()

    raw  = resp.json()["choices"][0]["message"]["content"]
    data = _clean_and_parse(raw)
    return _build_result(data)

def _build_result(items):
    def clamp(v, d=0.0):
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return d

    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        txt = str(item.get("text", "")).strip()
        if not txt:
            continue

        left  = clamp(item.get("left",  0.0))
        upper = clamp(item.get("upper", 0.0))
        right = clamp(item.get("right", 1.0))
        lower = clamp(item.get("lower", 1.0))

        if right <= left:
            right = min(1.0, left + 0.15)
        if lower <= upper:
            lower = min(1.0, upper + 0.08)

        result.append({
            "text":       txt,
            "confidence": 0.95,
            "bbox":       {"left": left, "upper": upper, "right": right, "lower": lower}
        })
    return result

def group_detections_into_bubbles(detections, img_width, img_height, gap_threshold=0.03):
    return [
        {"texts": [d["text"]], "full_text": d["text"], "bbox": d["bbox"], "confidence": 0.95}
        for d in detections
    ]

def _mock_response():
    return [
        {"text": "I can't believe this!", "confidence": 0.95,
         "bbox": {"left": 0.05, "upper": 0.05, "right": 0.45, "lower": 0.18}},
        {"text": "We have to stop him!", "confidence": 0.95,
         "bbox": {"left": 0.55, "upper": 0.10, "right": 0.95, "lower": 0.25}},
    ]
