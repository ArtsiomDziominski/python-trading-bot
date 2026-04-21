from pydantic import BaseModel, Field

from app.models.enums import ExchangeType


class ApiKeyCreate(BaseModel):
    exchange: ExchangeType = ExchangeType.BINANCE
    api_key: str = Field(min_length=1, max_length=512)
    api_secret: str = Field(min_length=1, max_length=512)
    label: str = Field(default="default", max_length=128)


class ApiKeyOut(BaseModel):
    id: int
    exchange: ExchangeType
    label: str
    api_key_masked: str
    created_at: object

    model_config = {"from_attributes": True}
