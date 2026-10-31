"""27 - Make one YouTube Short (9:16, ~60s) from the best fresh news story."""
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import media, render, script_gen, voice  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA, OUT, WORK = ROOT / "data", ROOT / "output", ROOT / "work"


def load(name, default):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def pick(items, produced):
    wanted = os.environ.get("NEWS_ID")
    if wanted:
        return next((i for i in items if i["id"] == wanted), None)
    ok = [i for i in items if i["id"] not in produced and i["status"] in ("confirmed", "official")]
    if not ok and os.environ.get("ALLOW_UNVERIFIED") == "1":
        ok = [i for i in items if i["id"] not in produced]
    return max(ok, key=lambda i: i["score"]) if ok else None


def main():
    for d in (OUT, WORK, DATA / "scripts"):
        d.mkdir(parents=True, exist_ok=True)
    news = load("news.json", {"items": []})
    produced = load("produced.json", [])
    item = pick(news["items"], produced)
    if not item:
        raise SystemExit("No suitable (confirmed/official, not yet produced) story. Stopping safely.")
    print(f"Story: {item['title']} [{item['status']}, score {item['score']}]")

    sc = script_gen.make_script(item)
    (DATA / "scripts" / f"{item['id']}.json").write_text(
        json.dumps({"news": item, **sc}, ensure_ascii=False, indent=2), encoding="utf-8")

    parts, used, total = [], set(), 0.0
    intro = WORK / "intro.mp4"
    render.card("27", "TECH NEWS  |  WORLD", 1.5, intro)
    parts.append(intro)
    for n, s in enumerate(sc["scenes"]):
        wav = WORK / f"voice_{n}.wav"
        voice.synth(s["narration"], wav)
        dur = voice.duration(wav) + 0.35
        clip = media.find_clip(s["search"], WORK / f"clip_{n}.mp4", used)
        seg = WORK / f"scene_{n}.mp4"
        render.scene(clip, wav, dur, s["narration"], seg, WORK, n)
        parts.append(seg)
        total += dur
        print(f"  scene {n}: {dur:.1f}s, footage={'yes' if clip else 'fallback'}")
    outro = WORK / "outro.mp4"
    render.card("27", "FOLLOW FOR DAILY TECH NEWS", 2.0, outro)
    parts.append(outro)

    final = OUT / f"short_{item['id']}.mp4"
    render.concat(parts, final, WORK)
    srcs = ", ".join(f"{l['source']}: {l['url']}" for l in item["source_links"])
    (OUT / f"short_{item['id']}.txt").write_text(
        f"{item['title']} | 27\n\nSources: {srcs}\n\n"
        "Note: visuals are illustrative stock footage, not footage of the event itself.\n"
        f"Script method: {sc['method']} | status: {item['status']}\n", encoding="utf-8")
    produced.append(item["id"])
    (DATA / "produced.json").write_text(json.dumps(produced), encoding="utf-8")
    (DATA / "last_run.json").write_text(json.dumps({
        "time": datetime.now(timezone.utc).isoformat(), "ok": True, "title": item["title"],
        "video": final.name, "seconds": round(total + 3.5, 1)}), encoding="utf-8")
    print(f"DONE: {final} (~{total + 3.5:.0f}s)")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        DATA.mkdir(exist_ok=True)
        (DATA / "last_run.json").write_text(json.dumps({
            "time": datetime.now(timezone.utc).isoformat(), "ok": False,
            "error": traceback.format_exc()[-800:]}), encoding="utf-8")
        raise
