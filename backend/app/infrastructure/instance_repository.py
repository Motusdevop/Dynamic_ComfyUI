from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Instance


class InstanceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_running_by_user(self, user_id: int) -> Instance | None:
        query = select(Instance).where(Instance.user_id == user_id, Instance.status == "running")
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_container_id(self, container_id: str) -> Instance | None:
        query = select(Instance).where(Instance.container_id == container_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_running(self) -> list[Instance]:
        query = select(Instance).where(Instance.status == "running")
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, user_id: int, container_id: str, port: int, status: str = "running") -> Instance:
        instance = Instance(user_id=user_id, container_id=container_id, port=port, status=status)
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update_status(self, instance: Instance, status: str) -> Instance:
        instance.status = status
        await self.db.commit()
        await self.db.refresh(instance)
        return instance
