#!/usr/bin/env python3
"""Шаг 1 авторизации Google: печатает ссылку согласия и сохраняет PKCE-сессию.

Переменные окружения:
  LERA_HERMES_HOME — каталог Hermes (по умолчанию ~/AppData/Local/hermes на Windows)
  LERA_CLIENT_SECRET — путь к client_secret.json (по умолчанию $LERA_HERMES_HOME/google_client_secret.json)
  LERA_PENDING — куда сохранить state/code_verifier (по умолчанию $LERA_HERMES_HOME/google_oauth_pending.json)

Своя сессия важна: общий файл перезаписывают другие сессии агента и cron, из-за чего
обмен кода падает с OAuth state mismatch.
"""
import json
import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import Flow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/tasks",
]
REDIRECT = "http://localhost:1"


def hermes_home() -> Path:
    env = os.environ.get("LERA_HERMES_HOME")
    if env:
        return Path(env)
    return Path.home() / "AppData" / "Local" / "hermes"


def main() -> int:
    home = hermes_home()
    secret = Path(os.environ.get("LERA_CLIENT_SECRET", home / "google_client_secret.json"))
    pending = Path(os.environ.get("LERA_PENDING", home / "google_oauth_pending.json"))

    if not secret.exists():
        print(f"ERROR: не найден {secret}")
        return 1

    flow = Flow.from_client_secrets_file(str(secret), scopes=SCOPES, redirect_uri=REDIRECT,
                                        autogenerate_code_verifier=True)
    auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")

    pending.parent.mkdir(parents=True, exist_ok=True)
    pending.write_text(json.dumps({"state": state, "code_verifier": flow.code_verifier,
                                   "redirect_uri": REDIRECT}, indent=2))
    print(auth_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
