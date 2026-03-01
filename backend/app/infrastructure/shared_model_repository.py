from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import SharedModel


class SharedModelRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> list[SharedModel]:
        result = await self.db.execute(select(SharedModel).order_by(SharedModel.id.desc()))
        return list(result.scalars().all())

    async def get_by_url(self, url: str) -> SharedModel | None:
        result = await self.db.execute(select(SharedModel).where(SharedModel.url == url))
        return result.scalar_one_or_none()

    async def create(self, name: str, url: str, status: str = "downloading") -> SharedModel:
        model = SharedModel(name=name, url=url, status=status)
        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)
        return model

    async def update_status(self, model: SharedModel, status: str) -> SharedModel:
        model.status = status
        await self.db.commit()
        await self.db.refresh(model)
        return model
