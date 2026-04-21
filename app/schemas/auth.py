from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr = Field(description="Уникальный email аккаунта.")
    password: str = Field(min_length=8, max_length=128, description="Пароль, минимум 8 символов.")
    name: str | None = Field(default=None, description="Отображаемое имя (опционально).")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(description="Пароль пользователя.")


class TokenResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.access.payload",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh.payload",
                "token_type": "bearer",
            }
        }
    )

    access_token: str = Field(description="Короткоживущий JWT для заголовка `Authorization: Bearer ...`.")
    refresh_token: str = Field(description="Долгоживущий JWT для `POST /auth/refresh`.")
    token_type: str = Field(default="bearer", description="Всегда `bearer` (OAuth2 password flow совместимость).")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(description="Токен, выданный при логине или предыдущем refresh.")


class PasswordResetRequest(BaseModel):
    email: EmailStr = Field(description="Email аккаунта; письмо уйдёт только если пользователь существует.")


class PasswordResetConfirm(BaseModel):
    token: str = Field(description="Одноразовый токен из ссылки в письме.")
    new_password: str = Field(min_length=8, max_length=128, description="Новый пароль.")


class GoogleCallbackRequest(BaseModel):
    code: str = Field(description="Код авторизации от Google после редиректа.")
    redirect_uri: str | None = Field(
        default=None,
        description="Должен совпадать с зарегистрированным redirect URI (если отличается от настройки сервера).",
    )


class TelegramAuthRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str
