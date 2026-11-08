"""Free research and image tools. No API keys needed.

WikipediaArticleTool  reads an English Wikipedia article and its reference links (a starting map, never a final source).
CommonsImageTool      finds public-domain or openly licensed images on Wikimedia Commons, downloads them,
                      and records the credit and license for every file in credits.csv.
"""
from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from typing import Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

UA = {"User-Agent": "RiddlesRealmsDocumentaryCrew/0.1 (https://riddlesandrealms.store)"}
WIKI = "https://en.wikipedia.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"
# Licenses we accept without asking. CC BY / CC BY-SA need the credit line, which credits.csv keeps.
OK_LICENSES = ("public domain", "pd", "cc0", "cc by", "cc-by", "no restrictions")


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


class ArticleInput(BaseModel):
    title: str = Field(..., description="Exact or close Wikipedia article title, e.g. 'Violet Jessop'")


class WikipediaArticleTool(BaseTool):
    name: str = "wikipedia_article"
    description: str = (
        "Read an English Wikipedia article as plain text, followed by the external reference URLs it cites. "
        "Use it to map a topic and find primary and reputable sources; cite those sources, not Wikipedia, wherever possible."
    )
    args_schema: Type[BaseModel] = ArticleInput

    def _run(self, title: str) -> str:
        s = requests.get(WIKI, params={"action": "query", "list": "search", "srsearch": title, "format": "json", "srlimit": 1}, headers=UA, timeout=30).json()
        hits = s.get("query", {}).get("search", [])
        if not hits:
            return f"No Wikipedia article found for '{title}'."
        page = hits[0]["title"]
        t = requests.get(WIKI, params={"action": "query", "prop": "extracts", "explaintext": 1, "titles": page, "format": "json"}, headers=UA, timeout=30).json()
        text = next(iter(t["query"]["pages"].values())).get("extract", "")
        r = requests.get(WIKI, params={"action": "query", "prop": "extlinks", "titles": page, "ellimit": 200, "format": "json"}, headers=UA, timeout=30).json()
        links = [l["*"] for l in next(iter(r["query"]["pages"].values())).get("extlinks", [])]
        return f"# {page}\nhttps://en.wikipedia.org/wiki/{page.replace(' ', '_')}\n\n{text[:24000]}\n\n## Reference links\n" + "\n".join(links[:120])


class ImageInput(BaseModel):
    query: str = Field(..., description="What to search for on Wikimedia Commons, e.g. 'RMS Olympic HMS Hawke collision 1911'")
    topic_slug: str = Field(..., description="Folder name for this topic, e.g. 'violet-jessop'")
    max_images: int = Field(4, description="How many images to download for this query (1 to 6)")


class CommonsImageTool(BaseTool):
    name: str = "commons_image_download"
    description: str = (
        "Search Wikimedia Commons and download openly licensed images (public domain, CC0, CC BY, CC BY-SA) "
        "into output/<topic_slug>/images, logging title, author, license, source page and description to credits.csv. "
        "Run it several times with different specific queries (the person, the place, the ship, the newspaper, the year). "
        "Returns what was saved, or why nothing was."
    )
    args_schema: Type[BaseModel] = ImageInput

    def _run(self, query: str, topic_slug: str, max_images: int = 4) -> str:
        max_images = max(1, min(int(max_images), 6))
        out = Path(os.getenv("OUTPUT_DIR", "output")) / topic_slug / "images"
        out.mkdir(parents=True, exist_ok=True)
        credits = out / "credits.csv"
        new = not credits.exists()
        params = {
            "action": "query", "format": "json", "generator": "search", "gsrsearch": query, "gsrnamespace": 6,
            "gsrlimit": 20, "prop": "imageinfo", "iiprop": "url|extmetadata|mime|size", "iiurlwidth": 1920,
        }
        data = requests.get(COMMONS, params=params, headers=UA, timeout=30).json()
        pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
        saved, skipped = [], []
        with credits.open("a", newline="") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["file", "title", "author", "license", "source_page", "description", "query"])
            for p in pages:
                if len(saved) >= max_images:
                    break
                info = (p.get("imageinfo") or [{}])[0]
                if info.get("mime") not in ("image/jpeg", "image/png", "image/tiff"):
                    continue
                if min(info.get("width", 0), info.get("height", 0)) < 400:
                    continue
                meta = info.get("extmetadata", {})
                lic = _clean(meta.get("LicenseShortName", {}).get("value", ""))
                if not any(k in lic.lower() for k in OK_LICENSES):
                    skipped.append(f"{p['title']} ({lic or 'no license'})")
                    continue
                url = info.get("thumburl") or info.get("url")
                ext = ".png" if info.get("mime") == "image/png" else ".jpg"
                n = len(list(out.glob("*.*"))) - (1 if credits.exists() else 0)
                fname = f"{n + 1:02d}{ext}"
                img = requests.get(url, headers=UA, timeout=60)
                if img.status_code != 200:
                    continue
                (out / fname).write_bytes(img.content)
                w.writerow([fname, p["title"], _clean(meta.get("Artist", {}).get("value", "")), lic,
                            info.get("descriptionurl", ""), _clean(meta.get("ImageDescription", {}).get("value", ""))[:300], query])
                saved.append(f"{fname}: {p['title']} [{lic}]")
        if not saved:
            return f"No usable openly licensed images for '{query}'. Skipped: {', '.join(skipped[:8]) or 'none found'}. Try a more specific or different query."
        return "Saved:\n" + "\n".join(saved)
