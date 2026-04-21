from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.openapi import OPENAPI_RESPONSES_PROTECTED
from app.db.session import get_db
from app.models import User
from app.services import bot_service, market_service

router = APIRouter(responses=OPENAPI_RESPONSES_PROTECTED)


@router.get(
    "/symbols",
    summary="Символы для пользователя",
    description="Символы из конфигураций ботов пользователя с разрешёнными данными рынка.",
)
async def market_symbols(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    user_syms = await bot_service.symbols_for_user(db, user.id)
    resolved = await market_service.resolve_user_symbols(user_syms)
    return {"symbols": resolved}
