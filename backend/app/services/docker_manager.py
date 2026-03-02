from dataclasses import dataclass
import socket
import time

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound
from docker.types import DeviceRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.domain.models import User
from app.infrastructure.instance_repository import InstanceRepository


@dataclass
class StartResult:
    container_id: str
    port: int
    workspace_url: str


class DockerManager:
    def __init__(self, db: AsyncSession):
        self.settings = get_settings()
        self.db = db
        self.instances = InstanceRepository(db)
        self.client = docker.from_env()

    async def start_for_user(self, user: User) -> StartResult:
        running = await self.instances.get_running_by_user(user.id)
        if running:
            return StartResult(
                container_id=running.container_id,
                port=running.port,
                workspace_url=self._workspace_url(running.port),
            )

        host_port = await self._allocate_port()
        container_name = f"dynamiccomfy-u{user.id}-{int(time.time())}"
        ports = {f"{self.settings.comfy_internal_port}/tcp": host_port}

        run_kwargs: dict = {
            "image": self.settings.comfy_base_image,
            "detach": True,
            "name": container_name,
            "ports": ports,
            "labels": {
                "app": "dynamiccomfy",
                "user_id": str(user.id),
            },
        }
        if self.settings.enable_gpu:
            run_kwargs["device_requests"] = [DeviceRequest(count=-1, capabilities=[["gpu"]])]

        try:
            container = self.client.containers.run(**run_kwargs)
        except ImageNotFound as exc:
            raise RuntimeError(f"Docker image not found: {self.settings.comfy_base_image}") from exc
        except (APIError, DockerException) as exc:
            raise RuntimeError(f"Failed to start container: {exc.explanation if isinstance(exc, APIError) else str(exc)}") from exc

        await self.instances.create(
            user_id=user.id,
            container_id=container.id,
            port=host_port,
            status="running",
        )
        return StartResult(
            container_id=container.id,
            port=host_port,
            workspace_url=self._workspace_url(host_port),
        )

    async def stop_for_user(self, user: User) -> bool:
        running = await self.instances.get_running_by_user(user.id)
        if not running:
            return False

        try:
            container = self.client.containers.get(running.container_id)
            container.stop(timeout=10)
        except NotFound:
            pass
        except (APIError, DockerException) as exc:
            raise RuntimeError(f"Failed to stop container: {exc.explanation if isinstance(exc, APIError) else str(exc)}") from exc

        await self.instances.update_status(running, "stopped")
        return True

    async def status_for_user(self, user: User) -> tuple[str, int | None, str | None, str | None]:
        running = await self.instances.get_running_by_user(user.id)
        if not running:
            return "stopped", None, None, None

        try:
            container = self.client.containers.get(running.container_id)
            container.reload()
            state = (container.status or "").lower()
        except NotFound:
            state = "missing"
        except (APIError, DockerException):
            state = "unknown"

        if state not in {"created", "running", "restarting"}:
            await self.instances.update_status(running, "stopped")
            return "stopped", None, None, None

        return "running", running.port, running.container_id, self._workspace_url(running.port)

    async def _allocate_port(self) -> int:
        running = await self.instances.list_running()
        busy_ports = {instance.port for instance in running}

        for port in range(self.settings.port_range_start, self.settings.port_range_end + 1):
            if port in busy_ports:
                continue
            if self._is_port_available(port):
                return port
        raise RuntimeError("No free port available for a new ComfyUI instance")

    @staticmethod
    def _is_port_available(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return sock.connect_ex(("127.0.0.1", port)) != 0

    def _workspace_url(self, port: int) -> str:
        return f"http://{self.settings.server_public_host}:{port}"
