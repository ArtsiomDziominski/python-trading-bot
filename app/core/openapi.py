from importlib.metadata import PackageNotFoundError, version

from starlette import status

from app.schemas.errors import ErrorDetail


def app_version() -> str:
    try:
        return version("python-trading-bot")
    except PackageNotFoundError:
        return "0.1.0"


API_DESCRIPTION = """
## Аутентификация

Почти все эндпоинты (кроме `health`, части `auth` и публичных редиректов) требуют **JWT** в заголовке:

`Authorization: Bearer <access_token>`

1. Получите пару токенов через `POST /auth/register`, `POST /auth/login`, `POST /auth/google`, `POST /auth/telegram` или `POST /auth/refresh`.
2. В Swagger UI нажмите **Authorize**, вставьте только значение токена (без префикса `Bearer` — его подставит UI).
3. `access_token` живёт ограниченное время; обновите сессию через `POST /auth/refresh` с `refresh_token`.

## WebSocket

`GET /ws/ws?token=<access_token>` — тот же access JWT, что и для HTTP (в query-параметре, не в заголовке).

## Лимиты

Часть маршрутов защищена rate limiting (slowapi). При превышении возможен ответ **429 Too Many Requests**.

## Роли и админка

Раздел **admin** доступен только пользователям с ролями **support**, **admin** или **superadmin** (см. описание операций).
"""


OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "health",
        "description": "Проверка живости сервиса, мониторинг и балансировщики.",
    },
    {
        "name": "auth",
        "description": "Регистрация, вход, OAuth (Google), Telegram Login, сброс пароля, обновление токенов.",
    },
    {
        "name": "user",
        "description": "Текущий пользователь: профиль, настройки уведомлений, привязка Telegram.",
    },
    {
        "name": "telegram",
        "description": "Отправка тестового сообщения в привязанный Telegram-чат (`POST /user/telegram/send`).",
    },
    {
        "name": "admin",
        "description": "Административные операции: список пользователей, смена ролей (требуются повышенные права).",
    },
    {
        "name": "api-keys",
        "description": "Управление API-ключами бирж (хранение зашифровано; в ответах — маскированные ключи).",
    },
    {
        "name": "bots",
        "description": "Сеточные боты Binance Futures: создание, остановка, закрытие, история событий.",
    },
    {
        "name": "market",
        "description": "Справочники и рыночные данные в контексте символов пользователя.",
    },
    {
        "name": "ws",
        "description": "WebSocket: поток событий пользователя (Redis pub/sub). Токен передаётся query-параметром `token`.",
    },
]


SWAGGER_UI_PARAMETERS: dict = {
    "persistAuthorization": True,
    "displayRequestDuration": True,
    "filter": True,
    "tryItOutEnabled": True,
}


OPENAPI_RESPONSES_AUTH = {
    status.HTTP_400_BAD_REQUEST: {
        "model": ErrorDetail,
        "description": "Ошибка валидации или бизнес-логики (занятый email, неверный код OAuth и т.д.).",
    },
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorDetail,
        "description": "Неверный логин/пароль или недействительный refresh token.",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": ErrorDetail,
        "description": "Сервис не сконфигурирован (например, Google OAuth).",
    },
}


OPENAPI_RESPONSES_PROTECTED = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorDetail,
        "description": "Нет Bearer-токена или access token недействителен/истёк.",
    },
    status.HTTP_403_FORBIDDEN: {
        "model": ErrorDetail,
        "description": "Недостаточно прав (в т.ч. для операций admin).",
    },
}


OPENAPI_RESPONSES_API_KEYS = {
    **OPENAPI_RESPONSES_PROTECTED,
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorDetail,
        "description": "API-ключ не найден или уже удалён.",
    },
}


OPENAPI_RESPONSES_ADMIN = {
    **OPENAPI_RESPONSES_PROTECTED,
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorDetail,
        "description": "Пользователь не найден.",
    },
}
