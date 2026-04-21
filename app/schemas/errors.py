from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Стандартное тело ошибки FastAPI (`HTTPException`)."""

    detail: str | list[dict] = Field(
        description="Текст ошибки или список полей валидации (422).",
        examples=["Not authenticated"],
    )
