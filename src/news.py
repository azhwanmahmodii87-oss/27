"""27 - Stage 1: global tech news collector.

Fetches RSS/Atom feeds, drops old and duplicate stories, scores importance,
marks verification status, and writes data/news.json.
Uses only the Python standard library (no pip install needed).
"""
import difflib
import hashlib
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

# (name, url, weight 1-3, official company source?)
FEEDS = [
    ("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml", 3, False),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/", 3, False),
    ("The Verge", "https://www.theverge.com/rss/index.xml", 2, False),
    ("TechCrunch", "https://techcrunch.com/feed/", 2, False),
    ("Wired", "https://www.wired.com/feed/rss", 2, False),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", 2, False),
    ("NVIDIA Blog", "https://blogs.nvidia.com/feed/", 2, True),
    ("Google Blog", "https://blog.google/rss/", 2, True),
    ("Microsoft Blog", "https://blogs.microsoft.com/feed/", 2, True),
    ("OpenAI", "https://openai.com/news/rss.xml", 2, True),
]

MAX_AGE_HOURS = 48
KEYWORDS = [
    "ai", "artificial intelligence", "openai", "nvidia", "robot", "humanoid",
    "chip", "semiconductor", "quantum", "apple", "google", "microsoft", "meta",
    "space", "nasa", "spacex", "cyber", "hack", "breach", "launch", "unveil",
    "breakthrough", "model", "gpu", "self-driving", "autonomous",
]
STOP = set("the a an and or of to in on for with is are was by at from as it its "
           "this that new says say how why what will be has have".split())
OUT = Path(__file__).resolve().parent.parent / "data" / "news.json"


def local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def clean(text, limit=400):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def parse_date(value):
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_feed(xml_bytes):
    """Return a list of dicts: title, url, summary, published (datetime or None)."""
    root = ET.fromstring(xml_bytes)
    items = []
    for node in root.iter():
        if local(node.tag) not in ("item", "entry"):
            continue
        row = {"title": "", "url": "", "summary": "", "published": None}
        for child in node:
            name = local(child.tag)
            if name == "title":
                row["title"] = clean(child.text, 300)
            elif name == "link":
                row["url"] = (child.get("href") or child.text or "").strip() or row["url"]
            elif name in ("description", "summary", "content") and not row["summary"]:
                row["summary"] = clean(child.text)
            elif name in ("pubdate", "published", "updated", "date"):
                dt = parse_date(child.text)
                if dt and (row["published"] is None or name != "updated"):
                    row["published"] = dt
        if row["title"] and row["url"]:
            items.append(row)
    return items


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (27-news-bot)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def words(title):
    return {w for w in re.findall(r"[a-z0-9]+", title.lower()) if w not in STOP and len(w) > 2}


def similar(a, b):
    wa, wb = words(a["title"]), words(b["title"])
    if wa and wb:
        shared = len(wa & wb)
        if shared >= 3 and shared / len(wa | wb) >= 0.4:
            return True
    return difflib.SequenceMatcher(None, a["title"].lower(), b["title"].lower()).ratio() >= 0.75


def score(cluster, now):
    rep = cluster["rep"]
    raw = rep["weight"]
    raw += 2 * min(len(cluster["sources"]) - 1, 3)
    text = (rep["title"] + " " + rep["summary"]).lower()
    raw += min(sum(1 for k in KEYWORDS if re.search(r"\b" + re.escape(k) + r"\b", text)), 4)
    age_h = (now - rep["published"]).total_seconds() / 3600
    raw += 2 if age_h < 6 else 1 if age_h < 24 else 0
    return min(100, round(raw * 8))


def main():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_AGE_HOURS)
    collected, errors, ok_feeds = [], [], 0

    for name, url, weight, official in FEEDS:
        try:
            rows = parse_feed(fetch(url))
        except Exception as exc:  # one broken feed must not stop the rest
            errors.append(f"{name}: {exc}")
            print(f"[FAIL] {name}: {exc}")
            continue
        ok_feeds += 1
        kept = 0
        for r in rows:
            # Items without a date are skipped: we never pass unknown-age news as new.
            if r["published"] is None or r["published"] < cutoff or r["published"] > now + timedelta(hours=1):
                continue
            r.update(source=name, weight=weight, official=official)
            collected.append(r)
            kept += 1
        print(f"[OK]   {name}: {kept} recent items")

    collected.sort(key=lambda r: (-r["weight"], -r["published"].timestamp()))
    clusters = []
    for r in collected:
        for c in clusters:
            if similar(r, c["rep"]):
                if r["source"] not in c["sources"]:
                    c["sources"].append(r["source"])
                    c["links"].append({"source": r["source"], "url": r["url"]})
                break
        else:
            clusters.append({"rep": r, "sources": [r["source"]],
                             "links": [{"source": r["source"], "url": r["url"]}]})

    news = []
    for c in clusters:
        rep = c["rep"]
        if len(c["sources"]) >= 2:
            status = "confirmed"      # reported by 2+ independent sources
        elif rep["official"]:
            status = "official"       # announced by the company itself
        else:
            status = "unverified"     # single media source
        news.append({
            "id": hashlib.sha1(rep["title"].encode()).hexdigest()[:10],
            "title": rep["title"],
            "summary": rep["summary"],
            "source": rep["source"],
            "url": rep["url"],
            "published": rep["published"].isoformat(),
            "sources": c["sources"],
            "source_links": c["links"],
            "status": status,
            "score": score(c, now),
        })
    news.sort(key=lambda n: -n["score"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": now.isoformat(),
        "feeds_ok": ok_feeds,
        "feeds_total": len(FEEDS),
        "errors": errors,
        "count": len(news),
        "items": news,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(news)} stories to {OUT}")
    if ok_feeds == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
