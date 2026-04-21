from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import admin, api_keys, auth, bots, health, market, user, ws
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.logging import setup_logging
from app.core.openapi import API_DESCRIPTION, OPENAPI_TAGS, SWAGGER_UI_PARAMETERS, app_version

setup_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from app.core.redis_client import close_redis

    await close_redis()


app = FastAPI(
    title=settings.app_name,
    description=API_DESCRIPTION,
    version=app_version(),
    openapi_tags=OPENAPI_TAGS,
    swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(user.router, prefix="/user", tags=["user"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
app.include_router(bots.router, prefix="/bots", tags=["bots"])
app.include_router(market.router, prefix="/market", tags=["market"])
app.include_router(ws.router, prefix="/ws", tags=["ws"])
