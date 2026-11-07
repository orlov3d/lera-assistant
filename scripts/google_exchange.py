#!/usr/bin/env python3
"""Шаг 2 авторизации Google: обменивает код из адресной строки на токен.

Использование:
  python google_exchange.py "http://localhost:1/?state=...&code=...&scope=..."

Пишет google_token.json. Требует, чтобы PKCE-сессию сохранил google_authurl.py.
"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google_auth_oauthlib.flow import Flow


def hermes_home() -> Path:
    env = os.environ.get("LERA_HERMES_HOME")
    if env:
        return Path(env)
    return Path.home() / "AppData" / "Local" / "hermes"


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: google_exchange.py <redirect URL or code>")
        return 1

    home = hermes_home()
    secret = Path(os.environ.get("LERA_CLIENT_SECRET", home / "google_client_secret.json"))
    token = Path(os.environ.get("LERA_TOKEN", home / "google_token.json"))
    pending_path = Path(os.environ.get("LERA_PENDING", home / "google_oauth_pending.json"))

    if not pending_path.exists():
        print(f"ERROR: нет PKCE-сессии {pending_path} — сначала запустите google_authurl.py")
        return 1

    raw = sys.argv[1].strip()
    pending = json.loads(pending_path.read_text())

    code = raw
    granted = None
    if raw.startswith("http"):
        params = parse_qs(urlparse(raw).query)
        if "code" not in params:
            print("ERROR: в ссылке нет параметра code")
            return 1
        code = params["code"][0]
        st = (params.get("state") or [None])[0]
        if st and st != pending["state"]:
            print("ERROR: state mismatch — ссылка от другой сессии, сгенерируйте новую")
            return 1
        scope_val = (params.get("scope") or [""])[0].strip()
        if scope_val:
            granted = scope_val.split()

    flow = Flow.from_client_secrets_file(
        str(secret), scopes=granted, redirect_uri=pending["redirect_uri"],
        state=pending["state"], code_verifier=pending["code_verifier"])

    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    flow.fetch_token(code=code)

    payload = json.loads(flow.credentials.to_json())
    payload.setdefault("type", "authorized_user")
    if granted:
        payload["scopes"] = granted
    token.write_text(json.dumps(payload, indent=2))

    print("OK: token saved to", token)
    print("scopes:", len(payload.get("scopes", [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
