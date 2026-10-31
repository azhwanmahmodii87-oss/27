"""27 - Voice-over with Piper TTS (free, open source)."""
import subprocess
import sys

VOICE = "en_US-lessac-medium"


def synth(text, out_wav, voice=VOICE):
    subprocess.run([sys.executable, "-m", "piper", "--model", voice, "--output_file", str(out_wav)],
                   input=text.encode("utf-8"), check=True)


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())
