from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str | None
    role: UserRole
    is_active: bool
    telegram_notifications_enabled: bool

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: str | None = None
    telegram_notifications_enabled: bool | None = None


class TelegramSendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4096, description="Текст для отправки в привязанный Telegram-чат.")


class TelegramSendMessageResponse(BaseModel):
    ok: bool = True
