"""27 - FFmpeg video engine: 1080x1920, scenes + captions + 27 branding -> MP4."""
import subprocess
import textwrap
from pathlib import Path

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
BG = "0x0b1020"
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30",
       "-c:a", "aac", "-ar", "44100", "-ac", "2"]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + r.stderr[-1500:])


def chunks(text, size=6):
    w = text.split()
    return [" ".join(w[i:i + size]) for i in range(0, len(w), size)]


def captions(text, dur, work, tag):
    parts, total, t, filters = chunks(text), max(len(text), 1), 0.0, []
    for i, part in enumerate(parts):
        span = dur * len(part) / total
        f = Path(work) / f"cap_{tag}_{i}.txt"
        f.write_text(textwrap.fill(part, 20), encoding="utf-8")
        filters.append(
            f"drawtext=fontfile={FONT}:textfile={f}:fontcolor=white:fontsize=66:line_spacing=12:"
            f"box=1:boxcolor=black@0.55:boxborderw=26:x=(w-text_w)/2:y=h*0.66:"
            f"enable='between(t,{t:.2f},{t + span:.2f})'")
        t += span
    return filters


def scene(clip, wav, dur, text, out, work, tag):
    src = (["-stream_loop", "-1", "-i", str(clip)] if clip
           else ["-f", "lavfi", "-i", "gradients=s=1080x1920:r=30:c0=0x12306b:c1=0x3a1260:x0=0:y0=0:x1=1080:y1=1920"])
    vf = ["scale=1080:1920:force_original_aspect_ratio=increase", "crop=1080:1920", "fps=30",
          "setsar=1", "eq=brightness=-0.07:saturation=1.1", *(["vignette=PI/5"] if clip else []), "fade=t=in:st=0:d=0.3",
          f"drawtext=fontfile={FONT}:text='27':fontsize=72:fontcolor=white@0.85:x=60:y=90"]
    vf += captions(text, dur, work, tag)
    run(["ffmpeg", "-y", *src, "-i", str(wav), "-t", f"{dur:.2f}", "-vf", ",".join(vf),
         "-af", "aresample=44100,apad", *ENC, str(out)])


def card(big, small, dur, out):
    vf = (f"drawtext=fontfile={FONT}:text='{big}':fontsize=420:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2-120,"
          f"drawtext=fontfile={FONT}:text='{small}':fontsize=52:fontcolor=0x7fb2ff:x=(w-text_w)/2:y=h/2+220,"
          "fade=t=in:st=0:d=0.4")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={BG}:s=1080x1920:r=30",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(dur), "-vf", vf, *ENC, str(out)])


def concat(parts, out, work):
    lst = Path(work) / "list.txt"
    lst.write_text("".join(f"file '{Path(p).resolve()}'\n" for p in parts))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
