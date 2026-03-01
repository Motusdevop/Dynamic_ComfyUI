from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.infrastructure.shared_model_repository import SharedModelRepository


class ModelDownloader:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.repo = SharedModelRepository(db)

    def _derive_name(self, url: str) -> str:
        path = Path(urlparse(url).path)
        return path.name or "model.bin"

    async def enqueue_download(self, url: str, name: str | None = None):
        model = await self.repo.get_by_url(url)
        if model is not None:
            return model
        final_name = name or self._derive_name(url)
        return await self.repo.create(name=final_name, url=url, status="downloading")

    async def download_model_file(self, model_id: int) -> None:
        models = await self.repo.list_all()
        target = next((m for m in models if m.id == model_id), None)
        if target is None:
            return

        self.settings.shared_models_path.mkdir(parents=True, exist_ok=True)
        file_path = self.settings.shared_models_path / target.name

        try:
            async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
                async with client.stream("GET", target.url) as response:
                    response.raise_for_status()
                    with open(file_path, "wb") as out:
                        async for chunk in response.aiter_bytes():
                            out.write(chunk)
            await self.repo.update_status(target, "ready")
        except Exception:
            await self.repo.update_status(target, "failed")
