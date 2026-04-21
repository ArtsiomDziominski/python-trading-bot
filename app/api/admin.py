from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.openapi import OPENAPI_RESPONSES_ADMIN
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole
from app.schemas.admin import UserAdminOut, UserRolePatch
from app.services import audit_service

router = APIRouter(responses=OPENAPI_RESPONSES_ADMIN)


@router.get(
    "/users",
    response_model=list[UserAdminOut],
    summary="Список пользователей (админ)",
    description="Доступно ролям **support**, **admin**, **superadmin**; пагинация `skip` / `limit` (макс. 500).",
)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.SUPPORT, UserRole.ADMIN, UserRole.SUPERADMIN))],
    skip: int = 0,
    limit: int = 100,
):
    result = await db.execute(select(User).order_by(User.id).offset(skip).limit(min(limit, 500)))
    return list(result.scalars().all())


@router.patch(
    "/users/{user_id}/role",
    response_model=UserAdminOut,
    summary="Сменить роль пользователя",
    description="Только **admin** и **superadmin**; нельзя менять собственную роль этим вызовом.",
)
async def patch_user_role(
    user_id: int,
    body: UserRolePatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN))],
):
    if user_id == actor.id and body.role != actor.role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change own role here")
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    old = target.role
    target.role = body.role
    await audit_service.audit(
        db,
        actor_user_id=actor.id,
        action="user.role_change",
        entity_type="user",
        entity_id=str(user_id),
        payload={"from": old.value, "to": body.role.value},
    )
    return target
