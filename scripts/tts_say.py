#!/usr/bin/env python3
"""Озвучка текста в ogg/opus (голосовой пузырь Telegram).

Провайдеры:
  edge    — бесплатно, без лимитов, без ключей (нужен пакет edge-tts)
  gemini  — живее, но на бесплатном ключе ~10 фраз в сутки (нужен GOOGLE_API_KEY)

Использование:
  python tts_say.py "текст" out.ogg [--provider edge|gemini] [--voice ru-RU-SvetlanaNeural|Kore]

Требует ffmpeg в PATH.
"""
import argparse
import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

GEMINI_MODEL = "gemini-2.5-flash-preview-tts"


def google_key() -> str:
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        if os.environ.get(name):
            return os.environ[name]
    env_file = Path(os.environ.get("LERA_HERMES_HOME",
                                   str(Path.home() / "AppData" / "Local" / "hermes"))) / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            for name in ("GOOGLE_API_KEY=", "GEMINI_API_KEY="):
                if s.startswith(name) and not s.startswith("#"):
                    return s.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def to_ogg(src: str, dst: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-i", src, "-c:a", "libopus", "-b:a", "40k", dst],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def say_edge(text: str, voice: str, out: str) -> None:
    import edge_tts

    tmp = Path(tempfile.gettempdir()) / "tts_edge.mp3"
    asyncio.run(edge_tts.Communicate(text, voice).save(str(tmp)))
    to_ogg(str(tmp), out)


def say_gemini(text: str, voice: str, out: str) -> None:
    import urllib.request

    key = google_key()
    if not key:
        raise SystemExit("нет GOOGLE_API_KEY / GEMINI_API_KEY")

    body = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    data = json.load(urllib.request.urlopen(req, timeout=120))
    pcm = base64.b64decode(data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])

    raw = Path(tempfile.gettempdir()) / "tts_gemini.raw"
    raw.write_bytes(pcm)
    subprocess.run(["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(raw),
                    "-c:a", "libopus", "-b:a", "40k", out],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("out")
    ap.add_argument("--provider", default="edge", choices=["edge", "gemini"])
    ap.add_argument("--voice", default=None)
    args = ap.parse_args()

    if args.provider == "gemini":
        say_gemini(args.text, args.voice or "Kore", args.out)
    else:
        say_edge(args.text, args.voice or "ru-RU-SvetlanaNeural", args.out)
    print("OK:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
