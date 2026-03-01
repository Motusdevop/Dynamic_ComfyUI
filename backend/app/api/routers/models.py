import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.domain.models import User
from app.domain.schemas import SharedModelCreateIn, SharedModelOut
from app.infrastructure.database import SessionLocal
from app.infrastructure.shared_model_repository import SharedModelRepository
from app.services.model_downloader import ModelDownloader

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[SharedModelOut])
async def list_models(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SharedModelOut]:
    return await SharedModelRepository(db).list_all()


@router.post("/download", response_model=SharedModelOut)
async def download_model(
    payload: SharedModelCreateIn,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SharedModelOut:
    model = await ModelDownloader(db).enqueue_download(url=str(payload.url), name=payload.name)

    async def _download(model_id: int) -> None:
        async with SessionLocal() as background_db:
            await ModelDownloader(background_db).download_model_file(model_id)

    asyncio.create_task(_download(model.id))
    return model
