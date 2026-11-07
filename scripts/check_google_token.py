#!/usr/bin/env python3
"""Проверка живости Google-токена. Только чтение, ничего не меняет.

Печатает OK или ALERT — годится для cron-задачи с доставкой в мессенджер.

Переменные окружения:
  LERA_HERMES_HOME — каталог Hermes
  LERA_TOKEN — путь к google_token.json
"""
import json
import os
import sys
from pathlib import Path


def hermes_home() -> Path:
    env = os.environ.get("LERA_HERMES_HOME")
    if env:
        return Path(env)
    return Path.home() / "AppData" / "Local" / "hermes"


def main() -> int:
    token = Path(os.environ.get("LERA_TOKEN", hermes_home() / "google_token.json"))

    if not token.exists():
        print("🔴 Google: файла токена нет. Нужна повторная авторизация.")
        return 0

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except Exception as e:  # noqa: BLE001
        print(f"🔴 Google: не удалось загрузить библиотеки ({e}).")
        return 0

    try:
        creds = Credentials.from_authorized_user_file(str(token))
        creds.refresh(Request())
    except Exception as e:  # noqa: BLE001
        print("🔴 Google-доступ сломан — токен отозван или истёк.")
        print(f"Причина: {str(e)[:200]}")
        print("Нужна повторная авторизация: соберите ссылку через google_authurl.py.")
        return 0

    data = json.loads(token.read_text())
    print(f"✅ Google-доступ в порядке. Токен обновлён, прав: {len(data.get('scopes', []))}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
