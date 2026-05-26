import requests
from typing import Optional

MANGADEX_BASE = "https://api.mangadex.org"
MANGADEX_UPLOADS = "https://uploads.mangadex.org"

HEADERS = {
    "User-Agent": "MangaTranslatorApp/1.0 (educational project)"
}

def search_manga(query: str, limit: int = 12) -> list[dict]:
    """
    Busca mangas por título en inglés.
    Retorna lista de dicts con id, título, descripción, portada.
    """
    params = {
        "title": query,
        "limit": limit,
        "availableTranslatedLanguage[]": "en",
        "includes[]": ["cover_art", "author"],
        "contentRating[]": ["safe", "suggestive"],
        "order[relevance]": "desc"
    }

    resp = requests.get(f"{MANGADEX_BASE}/manga", params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("data", []):
        manga_id = item["id"]
        attrs = item.get("attributes", {})

        titles = attrs.get("title", {})
        title = titles.get("en") or next(iter(titles.values()), "Sin título")

        desc = attrs.get("description", {})
        description = desc.get("en", "")[:200] if desc else ""

        cover_url = _get_cover_url(manga_id, item.get("relationships", []))

        results.append({
            "id": manga_id,
            "title": title,
            "description": description,
            "cover_url": cover_url,
            "status": attrs.get("status", "unknown"),
            "year": attrs.get("year"),
        })

    return results

def get_chapters(manga_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
    params = {
        "manga": manga_id,
        "translatedLanguage[]": "en",
        "limit": limit,
        "offset": offset,
        "order[chapter]": "asc",
        "includes[]": ["scanlation_group"]
    }

    resp = requests.get(f"{MANGADEX_BASE}/chapter", params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    chapters = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        chapters.append({
            "id": item["id"],
            "chapter": attrs.get("chapter", "?"),
            "title": attrs.get("title") or f"Capítulo {attrs.get('chapter', '?')}",
            "pages": attrs.get("pages", 0),
            "publishAt": attrs.get("publishAt", ""),
        })

    return chapters

def get_chapter_pages(chapter_id: str) -> list[str]:
    resp = requests.get(
        f"{MANGADEX_BASE}/at-home/server/{chapter_id}",
        headers=HEADERS,
        timeout=15
    )
    resp.raise_for_status()
    data = resp.json()

    base_url = data["baseUrl"]
    chapter_hash = data["chapter"]["hash"]
    pages = data["chapter"]["data"]
    urls = [f"{base_url}/data/{chapter_hash}/{page}" for page in pages]
    return urls

def download_page_image(url: str) -> bytes:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.content

def _get_cover_url(manga_id: str, relationships: list) -> Optional[str]:
    for rel in relationships:
        if rel.get("type") == "cover_art":
            filename = rel.get("attributes", {}).get("fileName")
            if filename:
                return f"{MANGADEX_UPLOADS}/covers/{manga_id}/{filename}.256.jpg"
    return None
