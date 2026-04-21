from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.schemas.auth import (
    GoogleCallbackRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TelegramAuthRequest,
    TokenResponse,
)
from app.core.openapi import OPENAPI_RESPONSES_AUTH
from app.services import auth_service

router = APIRouter(responses=OPENAPI_RESPONSES_AUTH)


@router.post(
    "/register",
    response_model=TokenResponse,
    summary="Регистрация",
    description="Создаёт пользователя и сразу возвращает пару JWT (access + refresh).",
)
@limiter.limit("30/minute")
async def register(request: Request, body: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        user = await auth_service.register_user(db, body.email, body.password, body.name)
        _, access, refresh = await auth_service.issue_tokens(db, user)
        return TokenResponse(access_token=access, refresh_token=refresh)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход по email и паролю",
    description="Проверяет учётные данные и возвращает JWT. Используйте `access_token` в Swagger **Authorize**.",
)
@limiter.limit("60/minute")
async def login(request: Request, body: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        user, access, refresh = await auth_service.login_user(db, body.email, body.password)
        return TokenResponse(access_token=access, refresh_token=refresh)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Обновление токенов",
    description="По действительному `refresh_token` выдаёт новую пару access/refresh.",
)
async def refresh_token(body: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        user, access, refresh = await auth_service.refresh_session(db, body.refresh_token)
        return TokenResponse(access_token=access, refresh_token=refresh)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


@router.get(
    "/google",
    summary="URL для OAuth Google",
    description="Возвращает ссылку на страницу авторизации Google (если OAuth настроен в окружении).",
)
async def google_auth_url():
    s = get_settings()
    if not s.google_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google OAuth not configured")
    return {"authorize_url": auth_service.google_authorize_url()}


@router.post(
    "/google",
    response_model=TokenResponse,
    summary="Callback Google OAuth",
    description="Обменивает `code` от Google на сессию пользователя и JWT.",
)
async def google_callback(body: GoogleCallbackRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        user, access, refresh = await auth_service.google_exchange_code(db, body.code, body.redirect_uri)
        return TokenResponse(access_token=access, refresh_token=refresh)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/telegram",
    response_model=TokenResponse,
    summary="Вход через Telegram Login Widget",
    description="Принимает поля, которые присылает Telegram после виджета; проверяет подпись и выдаёт JWT.",
)
async def telegram_auth(body: TelegramAuthRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    data = body.model_dump()
    try:
        user, access, refresh = await auth_service.telegram_login(db, data)
        return TokenResponse(access_token=access, refresh_token=refresh)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/reset-password",
    summary="Запрос сброса пароля",
    description="Идемпотентный ответ: всегда 200, письмо уходит только если email зарегистрирован.",
)
async def reset_password_request(body: PasswordResetRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    await auth_service.request_password_reset(db, body.email)
    return {"detail": "If the email exists, a reset link was sent."}


@router.post(
    "/reset-password/confirm",
    summary="Подтверждение нового пароля",
    description="Принимает одноразовый токен из письма и устанавливает новый пароль.",
)
async def reset_password_confirm(body: PasswordResetConfirm, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        await auth_service.confirm_password_reset(db, body.token, body.new_password)
        return {"detail": "Password updated"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

