# Python Trading Bot — MVP Backend

Монолит FastAPI: авторизация, API-ключи бирж, боты сетки (Binance Futures), Celery, Redis, PostgreSQL.

**Полная документация на русском:** [docs/ru/РУКОВОДСТВО.md](docs/ru/РУКОВОДСТВО.md) (API, env, соответствие плану).

---

## Требования

- **Python 3.12+**
- **PostgreSQL 16+** и **Redis 7+** (или только Docker для них / для всего стека)
- Для шифрования ключей биржи — переменная **`ENCRYPTION_KEY`** (ключ Fernet)

Сгенерировать ключ:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Скопируйте [`.env.example`](.env.example) в **`.env`** и заполните значения (минимум: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `ENCRYPTION_KEY`, при необходимости `CELERY_*`).

---

## Локальный запуск

### Вариант 1 — всё в Docker Compose (проще всего)

Из корня репозитория задайте **`ENCRYPTION_KEY`** (и при желании сильный `JWT_SECRET`) в файле `.env` или в окружении, затем:

```bash
docker compose up --build
```

Поднимутся: **PostgreSQL**, **Redis**, **backend** (Uvicorn + миграции Alembic при старте), **worker** (Celery), **bot-engine** (супервизор ботов).

- API: **http://localhost:8000** — документация: `/docs`, health: `/health`
- Опционально Telegram-бот (привязка OTP): в `.env` задайте `TELEGRAM_BOT_TOKEN`, затем:

```bash
docker compose --profile telegram up --build
```

Если `ENCRYPTION_KEY` пустой, создание API-ключей в приложении упадёт — задайте ключ до использования.

**Windows: ошибка `dockerDesktopLinuxEngine` / `The system cannot find the file specified`** — движок Docker не запущен или не установлен:

1. Установите [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/) (с WSL2 или Hyper-V по инструкции установщика).
2. Запустите **Docker Desktop** и дождитесь статуса «Running» (иконка в трее).
3. В PowerShell проверьте: `docker version` — должны быть и Client, и Server.
4. Повторите `docker compose up --build`.

Если Docker использовать не хотите — переходите к **варианту 2** или **3** (Postgres и Redis локально или только `db` + `redis` в Docker, когда он заработает).

---

### Вариант 2 — приложение на машине, БД в Docker

Поднять только инфраструктуру:

```bash
docker compose up -d db redis
```

В **`.env`** укажите строки для **localhost** (как в `.env.example`, порт Postgres `5432`, Redis `6379`).

Установка и миграции:

```bash
pip install -e ".[dev]"
alembic upgrade head
```

Процессы (в **отдельных терминалах** с тем же `.env` / виртуальным окружением):

```bash
# 1) API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 2) Celery
celery -A app.workers.celery_app worker --loglevel=info

# 3) Движок ботов (без него ордера на биржу не выставляются)
python -m app.workers.bot_engine_main

# 4) Опционально: Telegram для OTP
python -m app.bot.telegram
```

---

### Вариант 3 — без Docker (PostgreSQL и Redis установлены локально)

Настройте `DATABASE_URL` и `REDIS_URL` на ваши локальные инстансы, затем те же шаги: `pip install`, `alembic upgrade head`, и четыре процесса из варианта 2.

---

## Запуск на сервере (VPS / облако)

Общая схема та же, что и локально, с усилением безопасности:

1. **Секреты** — задать длинные случайные `JWT_SECRET` и `ENCRYPTION_KEY`, не коммитить `.env` в git.
2. **Docker Compose** — удобно для продакшена: скопировать проект на сервер, настроить `.env`, выполнить `docker compose up -d --build`.
3. **Порты** — наружу обычно открывают только **80/443**; приложение прячут за **Nginx** / Caddy / Traefik с TLS и проксированием на `127.0.0.1:8000`.
4. **Firewall** — ограничить SSH и HTTPS; прямой доступ к порту Postgres/Redis из интернета не давать.
5. **Данные** — том `pgdata` в Compose сохраняет PostgreSQL между перезапусками; делайте резервные копии БД отдельно.

Пример systemd unit для API без Docker (путь и пользователь подставьте свои):

```ini
[Service]
WorkingDirectory=/opt/python-trading-bot
EnvironmentFile=/opt/python-trading-bot/.env
ExecStart=/opt/python-trading-bot/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Аналогично можно оформить unit’ы для `celery` и `bot_engine_main`.

---

## Сервисы в `docker-compose.yml`

| Сервис      | Назначение |
|------------|------------|
| `db`       | PostgreSQL |
| `redis`    | Redis (кэш, pub/sub, Celery broker) |
| `backend`  | REST + WebSocket |
| `worker`   | Celery |
| `bot-engine` | Цикл торговых ботов |
| `telegram` | Профиль `telegram` — бот aiogram для OTP |

---

## Кратко на английском (для CI / README mirrors)

- **Local (all-in-Docker):** `docker compose up --build` — set `ENCRYPTION_KEY` in `.env`.
- **Local (dev):** `pip install -e ".[dev]"` → `alembic upgrade head` → run `uvicorn`, `celery`, `python -m app.workers.bot_engine_main`.
- **Server:** same Compose on a VM with strong secrets, reverse proxy TLS, no public DB/Redis.
