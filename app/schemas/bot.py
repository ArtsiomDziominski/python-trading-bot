from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_serializer, field_validator

from app.models.enums import BotLifecycleStatus, BotType, EngineState, GridDirection, VolumeMode


class GridFuturesConfig(BaseModel):
    symbol: str = Field(min_length=3, max_length=64)
    direction: GridDirection
    initial_amount: Decimal = Field(gt=0)
    grid_orders_count: int = Field(ge=1, le=500)
    grid_step_percent: Decimal = Field(gt=0, le=100)
    volume_mode: VolumeMode
    start_price: Decimal | None = Field(default=None, gt=0)
    auto_restart: bool = False


class BotPatch(BaseModel):
    """Обновление конфига сетки; `config_version` увеличивается на сервере."""

    config: GridFuturesConfig


class BotCreate(BaseModel):
    api_key_id: int
    bot_type: BotType = BotType.GRID_FUTURES
    config: GridFuturesConfig

    @field_validator("bot_type")
    @classmethod
    def mvp_type(cls, v: BotType) -> BotType:
        if v != BotType.GRID_FUTURES:
            raise ValueError("Only GRID_FUTURES is supported in MVP")
        return v


class BotLiquidationCheck(BaseModel):
    """Тело запроса расчёта ликвидации: конфиг сетки, якорная цена, баланс, плечо."""

    bot_type: BotType = BotType.GRID_FUTURES
    config: GridFuturesConfig
    current_price: Decimal | None = Field(
        default=None,
        gt=0,
        description="Якорная цена, если config.start_price null (без запроса к бирже)",
    )
    total_balance: Decimal = Field(gt=0, description="USDT balance for rough margin check only")
    leverage: Decimal = Decimal("10")

    @field_validator("bot_type")
    @classmethod
    def mvp_type(cls, v: BotType) -> BotType:
        if v != BotType.GRID_FUTURES:
            raise ValueError("Only GRID_FUTURES is supported in MVP")
        return v

    @field_validator("leverage")
    @classmethod
    def positive_leverage(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("leverage must be greater than 0")
        return v


class LiquidationCheckOut(BaseModel):
    """Ответ POST /bots/check-liquidation."""

    liquidation_price: Decimal
    avg_entry_price: Decimal
    total_base_quantity: Decimal

    @field_serializer("liquidation_price", "avg_entry_price", "total_base_quantity", when_used="json")
    def serialize_decimals(self, v: Decimal) -> int | float:
        if v == v.to_integral_value():
            return int(v)
        return float(v)


class BotOut(BaseModel):
    id: int
    user_id: int
    api_key_id: int
    bot_type: BotType
    symbol: str
    lifecycle_status: BotLifecycleStatus
    engine_state: EngineState
    engine_error: str | None
    config: dict[str, Any]
    config_version: int
    created_at: object
    updated_at: object | None
    deleted_at: object | None = None

    model_config = {"from_attributes": True}


class BotEventOut(BaseModel):
    id: int
    bot_id: int
    event_type: str
    payload: dict[str, Any] | None
    created_at: object

    model_config = {"from_attributes": True}


class BotStopAllFailure(BaseModel):
    bot_id: int
    detail: str


class BotsStopAllResponse(BaseModel):
    stopped: list[BotOut]
    failed: list[BotStopAllFailure]


class BotsCloseAllResponse(BaseModel):
    closed: list[BotOut]
    failed: list[BotStopAllFailure]


class BotsRemoveAllResponse(BaseModel):
    removed: list[BotOut]
    failed: list[BotStopAllFailure]
