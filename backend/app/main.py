from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.auth import router as auth_router
from app.api.backtest import router as backtest_router
from app.api.health import router as health_router
from app.api.model_config import router as model_config_router
from app.api.research import router as research_router
from app.api.reviews import router as reviews_router
from app.api.scores import router as scores_router
from app.api.scrape import router as scrape_router
from app.api.users import router as users_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="Sporttery 10x Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router, prefix="/api/auth")
app.include_router(users_router, prefix="/api/users")
app.include_router(scrape_router, prefix="/api/scrape")
app.include_router(scores_router, prefix="/api/scores")
app.include_router(backtest_router, prefix="/api/backtest")
app.include_router(model_config_router, prefix="/api/model-configs")
app.include_router(reviews_router, prefix="/api/reviews")
app.include_router(research_router, prefix="/api/research")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
