import os
import traceback
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from core.mangadex import search_manga, get_chapters, get_chapter_pages, download_page_image
from core.ocr import extract_text_from_image, group_detections_into_bubbles
from core.translator import translate_batch
from core.image_processor import apply_translations_to_image, image_to_base64, get_image_dimensions

load_dotenv()
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
    key = os.getenv("NVIDIA_API_KEY", "")
    ok  = bool(key and not key.startswith("nvapi-XXXX"))
    return jsonify({"nvidia_configured": ok, "demo_mode": not ok})

@app.route("/api/config", methods=["POST"])
def set_config():
    data = request.json or {}
    if data.get("nvidia_key"):
        os.environ["NVIDIA_API_KEY"] = data["nvidia_key"]
    return jsonify({"ok": True})

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

    key = os.getenv("NVIDIA_API_KEY", "")

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

        bubbles      = group_detections_into_bubbles(detections, img_w, img_h)
        translations = translate_batch([b["full_text"] for b in bubbles], api_key=key)

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
