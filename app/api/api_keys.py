from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.openapi import OPENAPI_RESPONSES_API_KEYS
from app.db.session import get_db
from app.models import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyOut
from app.services import api_key_service, audit_service

router = APIRouter(responses=OPENAPI_RESPONSES_API_KEYS)


@router.post(
    "",
    response_model=ApiKeyOut,
    summary="Добавить API-ключ биржи",
    description="Секрет шифруется на сервере; в ответе только маскированный ключ.",
)
async def create_key(
    body: ApiKeyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    try:
        row = await api_key_service.create_api_key(
            db,
            user,
            exchange=body.exchange,
            api_key=body.api_key,
            api_secret=body.api_secret,
            label=body.label,
        )
        await audit_service.audit(
            db,
            actor_user_id=user.id,
            action="api_key.create",
            entity_type="api_key",
            entity_id=str(row.id),
        )
        return ApiKeyOut(
            id=row.id,
            exchange=row.exchange,
            label=row.label,
            api_key_masked=api_key_service.masked_api_key(row),
            created_at=row.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "",
    response_model=list[ApiKeyOut],
    summary="Список API-ключей",
    description="Все не удалённые ключи пользователя с маскированным значением.",
)
async def list_keys(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    rows = await api_key_service.list_api_keys(db, user.id)
    return [
        ApiKeyOut(
            id=r.id,
            exchange=r.exchange,
            label=r.label,
            api_key_masked=api_key_service.masked_api_key(r),
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить API-ключ",
    description="Мягкое удаление; тело ответа пустое (**204**).",
)
async def delete_key(
    key_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    ok = await api_key_service.soft_delete_api_key(db, user.id, key_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await audit_service.audit(
        db,
        actor_user_id=user.id,
        action="api_key.delete",
        entity_type="api_key",
        entity_id=str(key_id),
    )
