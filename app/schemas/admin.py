from pydantic import BaseModel, EmailStr

from app.models.enums import UserRole


class UserAdminOut(BaseModel):
    id: int
    email: EmailStr
    name: str | None
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}


class UserRolePatch(BaseModel):
    role: UserRole
