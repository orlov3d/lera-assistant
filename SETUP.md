# Полный цикл настройки Lera Assistant

Инструкция для агента Hermes и его владельца: от чистой машины до работающего
голосового ассистента с доступом к Google. Всё проверено на Windows 10,
Python 3.11, 4 ядра, 16 ГБ RAM.

Проходить **по порядку**. Каждый раздел заканчивается проверкой — не идти дальше,
пока она не прошла.

---

## 0. Что понадобится

| Компонент | Зачем | Проверка |
|---|---|---|
| Hermes Agent | среда, cron, доставка в мессенджер | `hermes --version` |
| `uv` | установка пакетов в venv Hermes | `uv --version` |
| `ffmpeg` | конвертация аудио | `ffmpeg -version` |
| Python 3.11 из venv Hermes | все скрипты запускаются **только** им | см. §1 |
| Chrome (или Chromium) | не обязателен, но удобен | — |
| Google-аккаунт | календарь, почта, таблицы | — |
| GitHub-аккаунт | бесплатный хостинг страниц для OAuth | `gh auth status` |

Каталог Hermes ниже обозначен как `$H`:

- Windows: `C:\Users\<USER>\AppData\Local\hermes`
- Python Hermes: `$H\hermes-agent\venv\Scripts\python.exe`

---

## 1. Окружение

```bash
PY="$H/hermes-agent/venv/Scripts/python.exe"
uv pip install --python "$PY" --quiet faster-whisper==1.2.1 edge-tts psutil
"$PY" -c "import faster_whisper, edge_tts; print('OK')"
```

**Правило:** системный Python не подходит — в нём нет `faster_whisper` и зависимостей
Hermes. Любой скрипт запускать интерпретатором `$PY`, иначе получите
`ModuleNotFoundError` и будете искать причину не там.

На Windows `terminal` работает через git-bash: пути `/c/Users/...` понимают только
bash-команды (`cd`, `ls`). Нативные программы (`git`, `curl`, `python`, `ffmpeg`)
таких путей не понимают — им передавать `C:/Users/...` с прямыми слэшами.

---

## 2. Ключи

Файл `$H/.env`:

```dotenv
# Google AI Studio — распознавание изображений и TTS
GOOGLE_API_KEY=<ключ из https://aistudio.google.com/app/apikey>
```

Больше ключей для базового цикла не нужно: локальное распознавание работает без
интернета, Edge-озвучка — без ключа вообще.

OAuth-клиент Google кладётся отдельным файлом `$H/google_client_secret.json` —
его вы создадите в §5. **Не коммитить его в git и не публиковать.**

---

## 3. Распознавание речи (локально, без интернета)

### 3.1 Модели

Качаем `curl`-ом: клиент HuggingFace внутри venv падает на `idna` при работе с сетью.

```bash
D="C:/Users/<USER>/.cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots/local"
mkdir -p "$D"
for f in config.json tokenizer.json vocabulary.txt model.bin; do
  curl -sL --retry 3 "https://huggingface.co/Systran/faster-whisper-small/resolve/main/$f" -o "$D/$f"
done
ls -la "$D"   # model.bin должен быть ~484 МБ, не 0
```

`model.bin` нулевого размера = curl не отработал. Проверять всегда.

Резервная тяжёлая модель (1,6 ГБ, точнее, но в 5 раз медленнее):

```bash
D="C:/Users/<USER>/.cache/huggingface/hub/models--dropbox-dash--faster-whisper-large-v3-turbo/snapshots/local"
mkdir -p "$D"
for f in config.json tokenizer.json vocabulary.json preprocessor_config.json model.bin; do
  curl -sL --retry 3 "https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo/resolve/main/$f" -o "$D/$f"
done
```

### 3.2 Скрипт

Готовый файл — [`scripts/transcribe_voice.py`](scripts/transcribe_voice.py).

```bash
"$PY" scripts/transcribe_voice.py "C:/путь/к/голосовому.ogg"
```

Вывод:

```
MODEL: small | 14.7s | audio 7.3s | ru 1.00 | logprob -0.21
--- TRANSCRIPT ---
текст расшифровки
--- END ---
```

`logprob` ниже `-0.75` печатает `LOW_CONFIDENCE` — расшифровку **обязательно**
показать пользователю и дождаться подтверждения.

### 3.3 Замеры, чтобы выбрать модель осознанно

| Модель | Размер | 7–10 с аудио | Пик RAM | Качество |
|---|---|---|---|---|
| base | 142 МБ | 3–4 с | ~350 МБ | «Лердоброе утро» — не годится |
| **small** | 484 МБ | 14–20 с | 689 МБ | рабочее, падежи иногда плывут |
| large-v3-turbo | 1,6 ГБ | 50–72 с | 1 874 МБ | точнее, но на CPU мучительно |

Вывод: по умолчанию `small`. Тяжёлую включать флагом `--escalate` только когда
`small` не разобрал.

### 3.4 Проверка

```bash
"$PY" scripts/transcribe_voice.py "C:/путь/к/тесту.ogg" | head -5
```

Должна быть строка `MODEL: small` и осмысленный текст.

---

## 4. Озвучка ответов

### 4.1 Конфигурация Hermes

Прямое редактирование `config.yaml` агенту запрещено платформой — только CLI:

```bash
hermes config set tts.provider edge
hermes config set tts.edge.voice ru-RU-SvetlanaNeural
hermes config get tts.provider     # edge
```

Edge — единственный русский женский голос в бесплатном наборе Microsoft, зато без
лимитов и без ключей. Живее — Gemini (голоса `Kore`, `Aoede`, `Leda`, `Zephyr`,
`Autonoe`), но на бесплатном ключе ~10 фраз в сутки:

```bash
hermes config set tts.provider gemini
hermes config set tts.gemini.voice Kore
```

При исчерпании квоты прилетает `HTTP 429 ... limit: 10, model: gemini-2.5-flash-tts`
— переключаться обратно на edge, пока не обнулится.

### 4.2 Голосовой пузырь в Telegram

Gemini и edge отдают mp3 — Telegram покажет его как файл. Чтобы ушло голосовое:

```bash
ffmpeg -y -i reply.mp3 -c:a libopus -b:a 40k reply.ogg
```

В ответе агенту:

```
MEDIA:C:\путь\reply.ogg
[[audio_as_voice]]
```

Скрипт [`scripts/tts_say.py`](scripts/tts_say.py) делает это одной командой.

### 4.3 Проверка

```bash
"$PY" scripts/tts_say.py "Проверка связи, Дмитрий Алексеевич." out.ogg
ffprobe -hide_banner out.ogg 2>&1 | grep -E "Audio|Duration"
```

Должен быть `opus`, частота 48 кГц, длительность больше нуля.

---

## 5. Google API: проект и клиент

### 5.1 Проект и API

1. https://console.cloud.google.com/ — создать проект (или взять существующий).
2. **APIs & Services → Library**, включить:
   - Gmail API
   - Google Calendar API
   - Google Drive API
   - Google Sheets API
   - Google Docs API
   - People API (нужен для контактов)
   - Tasks API
3. После включения подождать 1–2 минуты — иначе первый вызов вернёт `SERVICE_DISABLED`.

### 5.2 OAuth-клиент

**APIs & Services → Credentials → Create credentials → OAuth client ID**,
тип приложения — **Desktop app**. Скачать JSON, положить как
`$H/google_client_secret.json`.

Внутри (`installed`) должны быть `client_id`, `client_secret`, `redirect_uris`.
Loopback-редирект `http://localhost:1` Google принимает для desktop-клиента с любым
портом, менять `redirect_uris` не нужно.

### 5.3 Права (scopes)

```
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/gmail.modify
https://www.googleapis.com/auth/calendar
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/contacts.readonly
https://www.googleapis.com/auth/spreadsheets
https://www.googleapis.com/auth/documents
https://www.googleapis.com/auth/tasks
```

### 5.4 Первая авторизация

```bash
"$PY" scripts/google_authurl.py            # печатает ссылку, сохраняет PKCE-сессию
# пользователь открывает ссылку, разрешает доступ
"$PY" scripts/google_exchange.py "http://localhost:1/?state=...&code=..."
```

Пользователь увидит `http://localhost:1/?...` с ошибкой «страница недоступна» —
это нормально: нужен **адрес из строки браузера целиком**, а не открывшаяся страница.

`google_authurl.py` хранит `state` и `code_verifier` в своём файле
(`google_oauth_pending.json`). Общий файл `setup.py` перезаписывают параллельные
сессии — обмен падает с `OAuth state mismatch`.

---

## 6. Публикация приложения: убрать 7-дневную смерть токена

**Симптом:** авторизация прошла, через несколько дней
`invalid_grant: Token has been expired or revoked`, и так по кругу.

**Причина:** тип приложения External + **Publishing status = Testing**. В песочнице
Google выдаёт refresh-токен ровно на 7 дней. Переавторизация не лечит, только
откладывает.

**Лечение:** перевести приложение в **In production**.

### 6.1 Заполнить Branding

https://console.cloud.google.com/auth/branding?project=&lt;PROJECT&gt;

`Publish app` в Audience неактивна, пока это не сделано — подпись под кнопкой прямо
говорит: *«To publish your app, you must complete your configuration on the Branding
page»*.

1. **Authorized domains** → `+ Add domain` → `<USER>.github.io`
   (домен добавлять **раньше** ссылок на нём).
2. **Application home page** → `https://<USER>.github.io/lera-assistant/`
3. **Application privacy policy link** → `https://<USER>.github.io/lera-assistant/privacy.html`
4. **Application terms of service link** → `https://<USER>.github.io/lera-assistant/terms.html`
5. **Developer contact information → Email addresses** (обязательное поле).
6. **Save**. Серая кнопка означает «чего-то не хватает», а не «нет изменений».

### 6.2 Страницы для Branding бесплатно

Свой домен не нужен — подойдёт GitHub Pages (`github.io` есть в Public Suffix List,
поэтому Google считает его самостоятельным доменом):

```bash
gh repo create <USER>/lera-assistant --public --description "public pages"
# в пустую папку: index.html, privacy.html, terms.html
cd <folder> && git init -q && git add -A \
  && git -c user.name="<NAME>" -c user.email="<EMAIL>" commit -q -m "public pages" \
  && git branch -M main && git remote add origin https://github.com/<USER>/lera-assistant.git \
  && git push -u origin main
gh api -X POST repos/<USER>/lera-assistant/pages -f 'source[branch]=main' -f 'source[path]=/'
```

Сборка ~40 секунд, обязательно дождаться 200 перед тем как давать ссылки:

```bash
for i in 1 2 3 4 5 6; do
  st=$(gh api repos/<USER>/lera-assistant/pages/builds/latest --jq .status)
  code=$(curl -s -o /dev/null -w "%{http_code}" https://<USER>.github.io/lera-assistant/)
  echo "$i build=$st http=$code"; [ "$code" = "200" ] && break; sleep 20
done
```

На страницах — только название, назначение, политика и контакт. Ничего личного.

### 6.3 Опубликовать

Audience → **Publish app** → диалог *«Push to production?»* → **Confirm**.

- Статус станет **In production**.
- Появится предупреждение «требуется верификация» — **игнорировать**, ничего не
  отправлять. Для restricted-скоупов (Gmail, Drive) верификация означает платный
  аудит CASA: недели и деньги. Личному ассистенту она не нужна.
- Лимит 100 пользователей не мешает: пользователей один.

### 6.4 Одна повторная авторизация

Токены, выданные **до** публикации, свой 7-дневный срок сохраняют. После публикации
пройти §5.4 заново — новый токен будет долгоживущим.

При согласии появится экран «Google не проверил это приложение» →
**«Дополнительно» → «Перейти на страницу <app> (небезопасно)»**. Для собственного
приложения это нормально.

### 6.5 Проверка

```bash
"$PY" scripts/check_google_token.py
```

Ожидаем `✅ Google-доступ в порядке`. Дополнительно убедиться, что в
`google_token.json` есть `refresh_token` и **отсутствует** `refresh_token_expires_in`.

### 6.6 Что публикацией не лечится

Токен всё равно отзовётся при: смене пароля Google, ручном отзыве доступа в
https://myaccount.google.com/permissions, полугоде без использования.

**Internal вместо External** (без проверки и без 7 дней) доступен только аккаунтам
Google Workspace со своим доменом. Для личного Gmail его не выбрать — проверять тип
аккаунта: `drive.about().get(fields='user')` → поле `hd` пустое у личного Gmail.

---

## 7. Сторожевой контроль

`scripts/check_google_token.py` — read-only: обновляет токен и печатает `✅` либо `🔴`
с причиной. Ставить еженедельно, чтобы о поломке узнавать до падения брифинга:

```bash
mkdir -p "$H/scripts" && cp scripts/check_google_token.py "$H/scripts/"
hermes cron create "0 9 * * 1" --name google_token_watchdog \
  --script check_google_token.py --no-agent --deliver telegram
hermes cron run <JOB_ID>       # проверить немедленно
```

**Важно:** скрипт для cron должен лежать в `$H/scripts/`, а не в папке скилла —
иначе создание задачи падает с «Script file not found».

---

## 8. Грабли (собрано на своих ошибках)

| Симптом | Причина | Решение |
|---|---|---|
| `ModuleNotFoundError: No module named 'pytz'` / любой другой | скрипт запущен системным Python | запускать `$H/hermes-agent/venv/Scripts/python.exe` |
| `ModuleNotFoundError: No module named 'hermes_tools'` | это внутренний модуль execute_code, а не venv | проверки писать обычным Python + `google-api-python-client` |
| `FileNotFoundError` на `/tmp/...` | нативный бинарь не понимает MSYS-путь | передавать `C:/...` |
| `model.bin` 0 байт | curl не отработал, путь был MSYS | перекачать с `C:/...` и проверить размер |
| `OAuth state mismatch` | общий `google_oauth_pending.json` перезаписан другой сессией | своя PKCE-сессия в отдельном файле |
| `invalid_grant` каждые 7 дней | статус Testing | §6, публикация в Production |
| `Publish app` серая | не заполнен Branding | §6.1 |
| `SERVICE_DISABLED` | API не включён или не прошло 1–2 минуты | включить в Library, подождать |
| `HTTP 429` на TTS | бесплатная квота Gemini (10/сутки) | переключить на edge |
| Google отдаёт «подозрительный трафик» | автоматизация с серверного IP | работать из браузера владельца, не скрейпить |
| cron: `Script file not found` | скрипт не в `$H/scripts/` | скопировать туда |
| Cron-сводка падает целиком | пропала библиотека после обновления пакетов | `uv pip install --python $PY <пакет>` и прогнать вручную |

---

## 9. Как агент должен общаться

Правило владельца, зафиксировано 06.11.2026:

> «Когда я тебе делаю аудиосообщение, ты так же по умолчанию отвечай аудиоответами.
> Если только я специально не попрошу ответить текстом.»

Порядок работы с голосовым:

1. Расшифровать локально, **ничего не выполнять**.
2. Показать текст расшифровки.
3. Если `LOW_CONFIDENCE` или в тексте есть суммы, имена, даты — переспросить.
4. После подтверждения — выполнять.
5. Ответить голосом.

---

## 10. Структура

```
lera-assistant/
├── index.html              # публичная страница (Branding)
├── privacy.html            # политика конфиденциальности
├── terms.html              # условия использования
├── SETUP.md                # эта инструкция
└── scripts/
    ├── transcribe_voice.py # локальное распознавание
    ├── tts_say.py          # озвучка в ogg
    ├── google_authurl.py   # шаг 1 авторизации
    ├── google_exchange.py  # шаг 2 авторизации
    └── check_google_token.py # проверка живости токена
```

Лицензия MIT.
