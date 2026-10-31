"""27 - English script writer.

Default: template script built ONLY from the facts in the news item (no invention).
Optional: free LLM via GitHub Models (set USE_LLM=1); falls back to the template on any error.
"""
import json
import os
import re
import urllib.request

MODEL = "openai/gpt-4.1-mini"

TOPICS = [
    (("ai", "openai", "model", "chatbot", "artificial"), "artificial intelligence data center"),
    (("robot", "humanoid"), "robot technology"),
    (("chip", "semiconductor", "gpu", "nvidia", "processor"), "computer chip circuit"),
    (("space", "nasa", "spacex", "rocket", "satellite"), "space rocket launch"),
    (("cyber", "hack", "breach", "security", "ransomware"), "cyber security code"),
    (("car", "tesla", "self-driving", "autonomous", "ev"), "electric car technology"),
    (("phone", "iphone", "android", "apple", "samsung"), "smartphone technology"),
]


def topic_query(text):
    words = set(re.findall(r"[a-z0-9\-]+", text.lower()))
    for keys, query in TOPICS:
        if words & set(keys):
            return query
    return "futuristic technology"


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 25]


def template_script(item):
    title = item["title"].rstrip(".")
    query = topic_query(item["title"] + " " + item.get("summary", ""))
    scenes = [{"narration": f"Tech news you need to know. {title}.", "search": query}]
    for s in sentences(item.get("summary", ""))[:3]:
        scenes.append({"narration": s, "search": query})
    srcs = item.get("sources") or [item["source"]]
    line = "This story was reported by " + " and ".join(srcs[:3]) + "."
    if item.get("status") == "unverified":
        line = f"This report comes from {srcs[0]} and has not yet been independently confirmed."
    elif item.get("status") == "official":
        line = f"This was announced by {srcs[0]}."
    scenes.append({"narration": line, "search": query})
    return {"title": title, "scenes": scenes, "method": "template"}


SYSTEM = (
    "You write scripts for 27, an international tech news channel. Write natural, "
    "professional English narration. Use ONLY the facts provided. Never invent numbers, "
    "quotes or details. Reply with JSON only."
)


def llm_script(item):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    facts = json.dumps({k: item.get(k) for k in ("title", "summary", "sources", "status")})
    prompt = (
        "Write a 45-60 second vertical-video script (about 120-150 words) as JSON: "
        '{"scenes":[{"narration":"...","search":"2-3 word stock footage query"}]} '
        "with 5-6 scenes. Scene 1 must be a strong hook. Last scene credits the source "
        "and, if status is unverified, says the report is not yet confirmed. Facts: " + facts
    )
    body = json.dumps({
        "model": MODEL, "temperature": 0.4, "max_tokens": 900,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://models.github.ai/inference/chat/completions", data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        text = json.load(resp)["choices"][0]["message"]["content"]
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    scenes = json.loads(text)["scenes"]
    scenes = [s for s in scenes if s.get("narration") and s.get("search")]
    if len(scenes) < 3:
        return None
    return {"title": item["title"], "scenes": scenes, "method": "llm"}


def make_script(item):
    if os.environ.get("USE_LLM") == "1":
        try:
            result = llm_script(item)
            if result:
                return result
        except Exception as exc:
            print(f"[WARN] LLM failed, using template: {exc}")
    return template_script(item)
