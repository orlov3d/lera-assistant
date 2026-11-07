#!/usr/bin/env python3
"""Транскрипция голосового сообщения локальной faster-whisper.

Usage: transcribe_voice.py <audio path> [--model auto|base|small] [--lang ru] [--fast]

По умолчанию: модель small (если скачана), VAD, доменный промпт для имён/терминов.
Выводит текст, время и уверенность; LOW_CONFIDENCE — повод переспросить у пользователя.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time

DOMAIN_PROMPT = (
    "Разговор с личным ассистентом Лерой. Слова: Лера, Дмитрий, Числобог, Ростелеком, "
    "Бегичево, Триглав, Веста, Владимир, Соня, Альфа-Счёт, Google, Telegram, Макс, "
    "финансы, баланс, лимит, платёж, задача, календарь, деревня, отчёт."
)
PREFERRED = ["small", "base"]
FALLBACK_HEAVY = "large-v3-turbo"
LOW_CONF = -0.75


def find_snapshot(model_name: str = "base") -> str | None:
    """Ищет модель в кеше HF по любому репозиторию вида *faster-whisper-<name>."""
    hub = os.path.expanduser("~/.cache/huggingface/hub")
    pattern = os.path.join(hub, f"models--*faster-whisper-{model_name}", "snapshots", "*")
    dirs = [d for d in glob.glob(pattern) if os.path.exists(os.path.join(d, "model.bin"))]
    return sorted(dirs)[-1] if dirs else None


def pick_model(requested: str) -> tuple[str, str]:
    if requested and requested != "auto":
        path = find_snapshot(requested)
        if not path:
            raise SystemExit(f"Модель faster-whisper-{requested} не найдена в кеше")
        return requested, path
    for name in PREFERRED:
        path = find_snapshot(name)
        if path:
            return name, path
    raise SystemExit("Ни одна модель faster-whisper не найдена в кеше")


def to_wav(src: str) -> str:
    if src.lower().endswith(".wav"):
        return src
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    out = os.path.join(tempfile.gettempdir(), f"stt_{os.getpid()}.wav")
    subprocess.run([ffmpeg, "-y", "-i", src, "-ar", "16000", "-ac", "1", out],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--model", default="auto", help="auto | base | small")
    ap.add_argument("--lang", default="ru")
    ap.add_argument("--fast", action="store_true", help="beam_size=1: быстрее на ~30%%")
    ap.add_argument("--escalate", action="store_true",
                    help="при низкой уверенности повторить на large-v3-turbo")
    args = ap.parse_args()

    if not os.path.exists(args.audio):
        print(f"ERROR: файл не найден: {args.audio}")
        return 1

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from faster_whisper import WhisperModel

    name, path = pick_model(args.model)
    wav = to_wav(args.audio)
    t0 = time.time()
    model = WhisperModel(path, device="cpu", compute_type="int8",
                         local_files_only=True, cpu_threads=os.cpu_count())
    segments, info = model.transcribe(
        wav, language=args.lang or None, beam_size=1 if args.fast else 5, vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300),
        condition_on_previous_text=False, temperature=0.0,
        initial_prompt=DOMAIN_PROMPT,
    )
    segments = list(segments)
    text = " ".join(s.text.strip() for s in segments).strip()
    conf = sum(s.avg_logprob for s in segments) / len(segments) if segments else -9

    print(f"MODEL: {name} | {time.time()-t0:.1f}s | audio {info.duration:.1f}s | {info.language} {info.language_probability:.2f} | logprob {conf:.2f}")
    print("--- TRANSCRIPT ---")
    print(text if text else "(пусто — речь не распознана)")
    print("--- END ---")
    if not text:
        print(f"EMPTY: аудио длится {info.duration:.1f} с — скорее всего запись прервалась, а не сбой модели")
    if text and conf < -0.75:
        print("LOW_CONFIDENCE: расшифровка ненадёжна — переспросить у пользователя")

    weak = (not text) or conf < LOW_CONF
    if args.escalate and weak and name != FALLBACK_HEAVY:
        heavy = find_snapshot(FALLBACK_HEAVY)
        if heavy:
            print(f"ESCALATE: уверенность низкая ({conf:.2f}) — повтор на {FALLBACK_HEAVY}")
            t1 = time.time()
            from faster_whisper import WhisperModel
            hm = WhisperModel(heavy, device="cpu", compute_type="int8",
                              local_files_only=True, cpu_threads=os.cpu_count())
            hs, _ = hm.transcribe(
                wav, language=args.lang or None, beam_size=1 if args.fast else 5, vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300),
                condition_on_previous_text=False, temperature=0.0,
                initial_prompt=DOMAIN_PROMPT)
            hs = list(hs)
            text2 = " ".join(s.text.strip() for s in hs).strip()
            conf2 = sum(s.avg_logprob for s in hs) / len(hs) if hs else -9.0
            print(f"MODEL: {FALLBACK_HEAVY} | {time.time()-t1:.1f}s | logprob {conf2:.2f}")
            print("--- TRANSCRIPT (heavy) ---")
            print(text2 if text2 else "(пусто — речь не распознана)")
            print("--- END ---")
            if text2 and conf2 > conf:
                text, conf = text2, conf2
    return 0 if text else 2


if __name__ == "__main__":
    sys.exit(main())
