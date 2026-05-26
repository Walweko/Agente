import os
import traceback
import requests as _requests
from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
from dotenv import load_dotenv
from core.mangadex import search_manga, get_chapters, get_chapter_pages, download_page_image
from core.ocr import extract_text_from_image, group_detections_into_bubbles
from core.translator import translate_batch
from core.image_processor import apply_translations_to_image, image_to_base64, get_image_dimensions

import pathlib
_env_path = pathlib.Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

# ── Diagnóstico de arranque ─────────────────────────────────────────────────
_key = os.getenv("NVIDIA_API_KEY", "")
print(f"[ENV] Buscando .env en: {_env_path}")
print(f"[ENV] .env existe: {_env_path.exists()}")
if not _key:
    print("[ENV] ⚠️  NVIDIA_API_KEY vacía — OCR usará datos de prueba")
elif _key.startswith("nvapi-XXXX"):
    print("[ENV] ⚠️  NVIDIA_API_KEY es el placeholder — ponla en .env")
else:
    print(f"[ENV] ✅  NVIDIA_API_KEY cargada: {_key[:12]}...")
# ────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)

_session = {
    "original_image_bytes": None,
    "bubbles": [],
}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/config", methods=["GET"])
def get_config():
    key = os.getenv("ANTHROPIC_API_KEY", "")
    ok  = bool(key and not key.startswith("sk-XXXX"))
    return jsonify({"anthropic_configured": ok, "demo_mode": not ok})

@app.route("/api/config", methods=["POST"])
def set_config():
    data = request.json or {}
    if data.get("anthropic_key"):
        os.environ["ANTHROPIC_API_KEY"] = data["anthropic_key"]
    return jsonify({"ok": True})

# ── proxy para imágenes de MangaDex ──────────────────────────────────
@app.route("/api/proxy-image")
def proxy_image():
    """
    Proxy transparente para imágenes de MangaDex.
    El browser carga /api/proxy-image?url=<url_mangadex>
    y el servidor hace la petición con el User-Agent correcto.
    """
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "url requerida"}), 400

    # Solo permitir dominios de MangaDex por seguridad
    allowed = (
        "uploads.mangadex.org",
        "cmdxd98gubfe6.cloudfront.net",
        "mangadex.network", 
        "mangadex.org",
    )
    from urllib.parse import urlparse
    host = urlparse(url).netloc
    if not any(host == a or host.endswith("." + a) for a in allowed):
        return jsonify({"error": "dominio no permitido"}), 403

    try:
        resp = _requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Referer":    "https://mangadex.org/",
                "Origin":     "https://mangadex.org",
            },
            timeout=30,
            stream=True,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/jpeg")
        return Response(resp.content, content_type=content_type)
    except Exception as e:
        return jsonify({"error": str(e)}), 502
# ────────────────────────────────────────────────────────────────────────────

@app.route("/api/manga/search")
def api_search_manga():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Parametro q requerido"}), 400
    try:
        return jsonify({"results": search_manga(query, limit=12)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/manga/<manga_id>/chapters")
def api_get_chapters(manga_id):
    try:
        chapters = get_chapters(manga_id, limit=30, offset=int(request.args.get("offset", 0)))
        return jsonify({"chapters": chapters})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chapter/<chapter_id>/pages")
def api_get_chapter_pages(chapter_id):
    try:
        pages = get_chapter_pages(chapter_id)
        return jsonify({"pages": pages, "total": len(pages)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/translate-page", methods=["POST"])
def api_translate_page():
    data     = request.json or {}
    page_url = data.get("page_url")
    if not page_url:
        return jsonify({"error": "page_url requerida"}), 400

    key = os.getenv("ANTHROPIC_API_KEY", "")

    try:
        image_bytes = download_page_image(page_url)
        img_w, img_h = get_image_dimensions(image_bytes)
        _session["original_image_bytes"] = image_bytes

        detections = extract_text_from_image(image_bytes, api_key=key)

        if not detections:
            return jsonify({
                "ok": True,
                "bubbles": [],
                "original_b64":   image_to_base64(image_bytes),
                "translated_b64": image_to_base64(image_bytes),
            })

        bubbles = group_detections_into_bubbles(detections, img_w, img_h)

        # Traducir
        try:
            translations = translate_batch([b["full_text"] for b in bubbles])
        except Exception as trans_err:
            print(f"[WARN] Traductor falló: {trans_err}. Usando textos originales.")
            translations = [b["full_text"] for b in bubbles]

        for i, bubble in enumerate(bubbles):
            bubble["translation"] = translations[i] if i < len(translations) else ""

        _session["bubbles"] = bubbles

        translated_bytes = apply_translations_to_image(image_bytes, bubbles)

        return jsonify({
            "ok": True,
            "bubbles": [
                {
                    "id":            i,
                    "original_text": b["full_text"],
                    "translation":   b["translation"],
                    "bbox":          b["bbox"],
                }
                for i, b in enumerate(bubbles)
            ],
            "original_b64":   image_to_base64(image_bytes),
            "translated_b64": image_to_base64(translated_bytes),
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/download-translated", methods=["POST"])
def api_download_translated():
    image_bytes = _session.get("original_image_bytes")
    if not image_bytes:
        return jsonify({"error": "No hay imagen en sesion"}), 400
    try:
        final_bytes = apply_translations_to_image(image_bytes, _session["bubbles"])
        return jsonify({"ok": True, "image_b64": image_to_base64(final_bytes)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port  = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    print(f"Servidor corriendo en http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)