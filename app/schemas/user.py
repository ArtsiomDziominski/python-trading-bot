from pydantic import BaseModel, EmailStr

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
