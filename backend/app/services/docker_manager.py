from dataclasses import dataclass
from pathlib import Path
import socket

import docker
from docker.errors import ImageNotFound, NotFound
from docker.models.containers import Container
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

    def _find_free_port(self) -> int:
        active_ports = set()
        for container in self.client.containers.list():
            ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
            bindings = ports.get("8188/tcp") or []
            if not bindings:
                continue
            host_port = bindings[0].get("HostPort")
            if host_port:
                active_ports.add(int(host_port))

        for port in range(self.settings.port_range_start, self.settings.port_range_end + 1):
            if port not in active_ports and self._is_host_port_free(port):
                return port
        raise RuntimeError("No free ports available in configured range")

    @staticmethod
    def _is_host_port_free(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            return sock.connect_ex(("127.0.0.1", port)) != 0

    def _ensure_user_output_dir(self, user_id: int) -> Path:
        output = self.settings.users_data_path / str(user_id) / "output"
        output.mkdir(parents=True, exist_ok=True)
        return output

    def _run_container(self, user_id: int, port: int) -> Container:
        user_output = self._ensure_user_output_dir(user_id)
        self.settings.shared_models_path.mkdir(parents=True, exist_ok=True)

        device_requests = None

        if self.settings.enable_gpu:
            device_requests = [DeviceRequest(count=-1, capabilities=[["gpu"]])]

        try:
            return self.client.containers.run(
                image=self.settings.comfy_base_image,
                detach=True,
                ports={"8188/tcp": port},
                device_requests=device_requests,
                volumes={
                    str(self.settings.shared_models_path): {"bind": "/opt/comfyui/models", "mode": "ro"},
                    str(user_output): {"bind": "/opt/comfyui/output", "mode": "rw"},
                },
                labels={"dynamiccomfy.user_id": str(user_id)},
                name=f"dynamiccomfy-u{user_id}-p{port}",
            )
        except ImageNotFound as exc:
            image = self.settings.comfy_base_image
            raise RuntimeError(
                f"Base image '{image}' was not found. Build or pull it first, or update COMFY_BASE_IMAGE."
            ) from exc

    async def start_for_user(self, user: User) -> StartResult:
        existing = await self.instances.get_running_by_user(user.id)
        if existing:
            return StartResult(
                container_id=existing.container_id,
                port=existing.port,
                workspace_url=f"http://{self.settings.server_public_host}:{existing.port}",
            )

        port = self._find_free_port()
        container = self._run_container(user.id, port)
        await self.instances.create(
            user_id=user.id,
            container_id=container.id,
            port=port,
            status="running",
        )

        return StartResult(
            container_id=container.id,
            port=port,
            workspace_url=f"http://{self.settings.server_public_host}:{port}",
        )

    async def stop_for_user(self, user: User) -> bool:
        instance = await self.instances.get_running_by_user(user.id)
        if instance is None:
            return False

        try:
            container = self.client.containers.get(instance.container_id)
            container.stop(timeout=10)
        except NotFound:
            pass

        await self.instances.update_status(instance, "stopped")
        return True

    async def status_for_user(self, user: User) -> tuple[str, int | None, str | None, str | None]:
        instance = await self.instances.get_running_by_user(user.id)
        if instance is None:
            return "stopped", None, None, None

        try:
            container = self.client.containers.get(instance.container_id)
            container.reload()
            state = container.attrs.get("State", {}).get("Status", "unknown")
        except NotFound:
            state = "missing"

        if state != "running":
            await self.instances.update_status(instance, "stopped")
            return "stopped", None, None, None

        url = f"http://{self.settings.server_public_host}:{instance.port}"
        return "running", instance.port, instance.container_id, url
