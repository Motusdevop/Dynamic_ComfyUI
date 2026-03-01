import asyncio
from datetime import UTC, datetime

import docker
from docker.errors import NotFound

from app.core.settings import get_settings
from app.infrastructure.database import SessionLocal
from app.infrastructure.instance_repository import InstanceRepository


class AutoKillService:
    def __init__(self):
        self.settings = get_settings()
        self.client = docker.from_env()
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            await self._scan_and_stop_expired()
            await asyncio.sleep(self.settings.auto_kill_interval_seconds)

    async def _scan_and_stop_expired(self) -> None:
        async with SessionLocal() as db:
            repo = InstanceRepository(db)
            running = await repo.list_running()
            now = datetime.now(UTC)

            for instance in running:
                elapsed = (now - instance.created_at.replace(tzinfo=UTC)).total_seconds()
                if elapsed < self.settings.auto_kill_max_seconds:
                    continue

                try:
                    container = self.client.containers.get(instance.container_id)
                    container.stop(timeout=10)
                except NotFound:
                    pass

                await repo.update_status(instance, "stopped")
