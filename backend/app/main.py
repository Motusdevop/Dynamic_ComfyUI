from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import auth, instances, models
from app.infrastructure.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title="DynamicComfy API", lifespan=lifespan)
app.include_router(auth.router, prefix="/api")
app.include_router(instances.router, prefix="/api")
app.include_router(models.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
