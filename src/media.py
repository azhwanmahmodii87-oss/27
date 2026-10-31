"""27 - Licensed stock footage from Pexels (free API key). Falls back to None."""
import json
import os
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (27-news-bot)"}


def find_clip(query, dest, used_ids):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    try:
        qs = urllib.parse.urlencode({"query": query, "orientation": "portrait", "per_page": 10})
        req = urllib.request.Request("https://api.pexels.com/videos/search?" + qs,
                                     headers={**UA, "Authorization": key})
        with urllib.request.urlopen(req, timeout=30) as resp:
            videos = json.load(resp).get("videos", [])
        for v in videos:
            if v["id"] in used_ids:
                continue
            files = [f for f in v.get("video_files", [])
                     if f.get("file_type") == "video/mp4" and (f.get("height") or 0) >= 1280]
            if not files:
                continue
            best = min(files, key=lambda f: f["height"])
            req = urllib.request.Request(best["link"], headers=UA)
            with urllib.request.urlopen(req, timeout=90) as resp, open(dest, "wb") as out:
                out.write(resp.read())
            used_ids.add(v["id"])
            return dest
    except Exception as exc:
        print(f"[WARN] footage search failed for '{query}': {exc}")
    return None
