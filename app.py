import os
import json
import time
import hashlib
from datetime import datetime, timezone
from typing import List, Dict
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, Response
from feedgen.feed import FeedGenerator

# ---- Config (tweak as needed) ----
BLOG_LIST_URL = os.getenv(
    "BLOG_LIST_URL",
    "https://teamtopologies.com/news-blogs-newsletters?category=Blog",
)
BASE_URL = "https://teamtopologies.com/"
USER_AGENT = os.getenv(
    "USER_AGENT", "MinifluxFeedGen/1.0 (+https://miniflux.lan)")
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "20"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "900"))  # seconds (15 min)
TIMEOUT = float(os.getenv("TIMEOUT", "15.0"))
CACHE_FILE = os.getenv("CACHE_FILE", "/data/cache.json")

app = FastAPI()


def _now() -> float:
    return time.time()


def _load_cache() -> Dict:
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(data: Dict) -> None:
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, CACHE_FILE)


def _get_client() -> httpx.Client:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en",
    }
    return httpx.Client(headers=headers, timeout=TIMEOUT, follow_redirects=True)


def _absolutize(href: str) -> str:
    return href if bool(urlparse(href).netloc) else urljoin(BASE_URL, href)


def _parse_posts_from_list(html: str) -> List[str]:
    """
    Heuristics to collect post links from the listing page.
    We look for anchors under sections that resemble post listings.
    """
    soup = BeautifulSoup(html, "html.parser")
    links = set()

    # 1) Obvious article cards
    for a in soup.select("a[href]"):
        href = a.get("href")
        if not href:
            continue
        # Only keep site-internal links under "news-blogs-newsletters"
        if "news-blogs-newsletters" in href:
            links.add(_absolutize(href))

    # De-duplicate while keeping order
    ordered = []
    seen = set()
    for u in links:
        if u not in seen:
            ordered.append(u)
            seen.add(u)
    # Keep most recent first (listing already tends to be newest-first)
    return ordered[: MAX_ITEMS * 2]  # fetch a few extra to filter later


def _extract_text(soup: BeautifulSoup, selectors: List[str]) -> str | None:
    for sel in selectors:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    return None


def _extract_meta(soup: BeautifulSoup, names: List[str]) -> str | None:
    for n in names:
        # property or name-based meta (og:title, article:published_time, etc.)
        tag = soup.find("meta", attrs={"property": n}) or soup.find(
            "meta", attrs={"name": n})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def _parse_date(candidate: str | None) -> datetime | None:
    if not candidate:
        return None
    # Try common ISO formats
    try:
        dt = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    # Fallback: try a few common patterns (very light)
    fmts = [
        "%Y-%m-%d",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(candidate, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def _fetch_post(client: httpx.Client, url: str) -> Dict | None:
    r = client.get(url)
    if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    title = (
        _extract_meta(soup, ["og:title", "twitter:title"])
        or _extract_text(soup, ["h1", "header h1", "article h1"])
    )
    desc = _extract_meta(soup, ["og:description", "description"])
    date_raw = _extract_meta(
        soup, ["article:published_time", "og:updated_time", "date"])
    # Also try visible date elements
    if not date_raw:
        date_raw = _extract_text(
            soup, ["time[datetime]", "time", ".post-date", ".ArticleDate"])

    published = _parse_date(date_raw)
    item = {
        "id": hashlib.sha256(url.encode()).hexdigest(),
        "url": url,
        "title": title or "Untitled",
        "summary": desc or "",
        "published": (published or datetime.utcnow().replace(tzinfo=timezone.utc)).isoformat(),
    }
    return item


def _build_feed(items: List[Dict]) -> bytes:
    fg = FeedGenerator()
    fg.load_extension("podcast")  # harmless; keeps namespaces friendly
    fg.title("Team Topologies — Blog (Unofficial RSS)")
    fg.link(href=BLOG_LIST_URL, rel="alternate")
    fg.link(href="https://miniflux.lan/feed.xml", rel="self")
    fg.description("Unofficial RSS feed generated by a local scraper.")
    fg.language("en")

    # Sort newest-first
    items = sorted(items, key=lambda i: i["published"], reverse=True)[
        :MAX_ITEMS]
    for it in items:
        fe = fg.add_entry()
        fe.id(it["id"])
        fe.title(it["title"])
        fe.link(href=it["url"])
        if it.get("summary"):
            fe.description(it["summary"])
        fe.published(it["published"])

    return fg.rss_str(pretty=True)


def _refresh() -> bytes:
    client = _get_client()
    # Fetch listing
    r = client.get(BLOG_LIST_URL)
    r.raise_for_status()
    links = _parse_posts_from_list(r.text)

    items: List[Dict] = []
    for u in links:
        try:
            item = _fetch_post(client, u)
            if item:
                items.append(item)
        except Exception:
            continue

    return _build_feed(items)


@app.get("/feed.xml")
def feed():
    cache = _load_cache()
    if cache and (fresh := cache.get("ts")) and _now() - fresh < CACHE_TTL:
        return Response(content=cache.get("rss", "").encode("utf-8"), media_type="application/rss+xml")

    try:
        rss = _refresh()
        _save_cache(
            {"ts": _now(), "rss": rss.decode("utf-8", errors="ignore")})
        return Response(content=rss, media_type="application/rss+xml")
    except Exception as e:
        # Serve stale cache if available
        cache = _load_cache()
        if cache.get("rss"):
            return Response(content=cache["rss"].encode("utf-8"), media_type="application/rss+xml")
        # Else minimal empty feed
        fg = FeedGenerator()
        fg.title("Team Topologies — Blog (Unofficial RSS)")
        fg.link(href=BLOG_LIST_URL, rel="alternate")
        return Response(content=fg.rss_str(pretty=True), media_type="application/rss+xml")


@app.get("/")
def index():
    return {"ok": True}
