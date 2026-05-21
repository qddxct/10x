from fastapi import APIRouter

from app.core.database import check_db_alive

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "db": "ok" if check_db_alive() else "down"}
