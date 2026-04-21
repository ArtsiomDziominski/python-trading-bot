from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/health",
    summary="Проверка доступности",
    description="Возвращает `{\"status\": \"ok\"}` если процесс приложения отвечает. Не проверяет БД или Redis.",
    response_model=dict[str, str],
)
async def health() -> dict[str, str]:
    return {"status": "ok"}
