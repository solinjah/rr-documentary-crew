"""Free Wikipedia and Wikimedia Commons helpers. No API keys needed."""
from __future__ import annotations

import csv
import re
from pathlib import Path

import requests

UA = {"User-Agent": "RiddlesRealmsDocumentaryCrew/0.2 (https://riddlesandrealms.store)"}
WIKI = "https://en.wikipedia.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"
OK_LICENSES = ("public domain", "pd", "cc0", "cc by", "cc-by", "no restrictions")


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def wikipedia_article(title: str) -> str:
    s = requests.get(WIKI, params={"action": "query", "list": "search", "srsearch": title, "format": "json", "srlimit": 1}, headers=UA, timeout=30).json()
    hits = s.get("query", {}).get("search", [])
    if not hits:
        return f"No Wikipedia article found for '{title}'."
    page = hits[0]["title"]
    t = requests.get(WIKI, params={"action": "query", "prop": "extracts", "explaintext": 1, "titles": page, "format": "json"}, headers=UA, timeout=30).json()
    text = next(iter(t["query"]["pages"].values())).get("extract", "")
    r = requests.get(WIKI, params={"action": "query", "prop": "extlinks", "titles": page, "ellimit": 200, "format": "json"}, headers=UA, timeout=30).json()
    links = [l["*"] for l in next(iter(r["query"]["pages"].values())).get("extlinks", [])]
    return f"# {page}\nhttps://en.wikipedia.org/wiki/{page.replace(' ', '_')}\n\n{text[:12000]}\n\n## Reference links\n" + "\n".join(links[:60])


def download_images(query: str, folder: Path, per_query: int = 2, seen: set | None = None) -> list[str]:
    """Download up to per_query openly licensed images for one query. Logs every file to credits.csv."""
    seen = seen if seen is not None else set()
    folder.mkdir(parents=True, exist_ok=True)
    credits = folder / "credits.csv"
    new = not credits.exists()
    params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": query, "gsrnamespace": 6,
              "gsrlimit": 15, "prop": "imageinfo", "iiprop": "url|extmetadata|mime|size", "iiurlwidth": 1920}
    try:
        data = requests.get(COMMONS, params=params, headers=UA, timeout=30).json()
    except Exception as e:  # network trouble: skip this query, keep going
        return [f"(search failed for '{query}': {e})"]
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    saved = []
    with credits.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["file", "title", "author", "license", "source_page", "description", "query"])
        for p in pages:
            if len(saved) >= per_query:
                break
            if p["title"] in seen:
                continue
            info = (p.get("imageinfo") or [{}])[0]
            if info.get("mime") not in ("image/jpeg", "image/png", "image/tiff"):
                continue
            if min(info.get("width", 0), info.get("height", 0)) < 400:
                continue
            meta = info.get("extmetadata", {})
            lic = _clean(meta.get("LicenseShortName", {}).get("value", ""))
            if not any(k in lic.lower() for k in OK_LICENSES):
                continue
            url = info.get("thumburl") or info.get("url")
            try:
                img = requests.get(url, headers=UA, timeout=60)
            except Exception:
                continue
            if img.status_code != 200:
                continue
            n = len([f for f in folder.iterdir() if f.suffix.lower() in (".jpg", ".png")]) + 1
            fname = f"{n:02d}{'.png' if info.get('mime') == 'image/png' else '.jpg'}"
            (folder / fname).write_bytes(img.content)
            seen.add(p["title"])
            w.writerow([fname, p["title"], _clean(meta.get("Artist", {}).get("value", "")), lic,
                        info.get("descriptionurl", ""), _clean(meta.get("ImageDescription", {}).get("value", ""))[:300], query])
            saved.append(f"{fname}: {p['title']} [{lic}]")
    return saved
