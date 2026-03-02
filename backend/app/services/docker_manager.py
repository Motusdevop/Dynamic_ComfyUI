from dataclasses import dataclass
from pathlib import Path
import time

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound
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

    def _ensure_user_output_dir(self, user_id: int) -> Path:
        output = self.settings.users_data_path / str(user_id) / "output"
        output.mkdir(parents=True, exist_ok=True)
        return output

    def _ensure_user_workspace_dir(self, user_id: int) -> Path:
        workspace = self.settings.users_data_path / str(user_id) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def _ensure_user_temp_dir(self, user_id: int) -> Path:
        temp = self.settings.users_data_path / str(user_id) / "temp"
        temp.mkdir(parents=True, exist_ok=True)
        return temp

    def _container_name(self, user_id: int, port: int) -> str:
        return f"dynamiccomfy-u{user_id}-p{port}"

    def _remove_stale_user_containers(self, user_id: int) -> None:
        stale = self.client.containers.list(
            all=True,
            filters={"label": f"dynamiccomfy.user_id={user_id}"},
        )
        for container in stale:
            try:
                container.remove(force=True)
            except NotFound:
                continue
            except DockerException:
                continue

    def _wait_until_ready(self, container: Container) -> None:
        deadline = time.monotonic() + self.settings.comfy_start_timeout_seconds
        running_since = None
        while time.monotonic() < deadline:
            try:
                container.reload()
            except NotFound as exc:
                raise RuntimeError("Container disappeared during startup.") from exc

            state = container.attrs.get("State", {})
            status = state.get("Status")
            if status in {"exited", "dead"}:
                logs = container.logs(tail=80).decode("utf-8", errors="replace").strip()
                raise RuntimeError(
                    f"ComfyUI container exited during startup. Last logs:\n{logs or '<empty>'}"
                )

            if status == "running":
                if running_since is None:
                    running_since = time.monotonic()
                elif time.monotonic() - running_since >= 3:
                    return
            else:
                running_since = None

            time.sleep(1)

        raise RuntimeError(
            f"ComfyUI did not become ready in {self.settings.comfy_start_timeout_seconds} seconds."
        )

    def _run_container(self, user_id: int, port: int) -> Container:
        user_output = self._ensure_user_output_dir(user_id)
        user_workspace = self._ensure_user_workspace_dir(user_id)
        user_temp = self._ensure_user_temp_dir(user_id)
        self.settings.shared_models_path.mkdir(parents=True, exist_ok=True)

        device_requests = None
        environment = None

        if self.settings.enable_gpu:
            device_requests = [DeviceRequest(count=-1, capabilities=[["gpu"]])]
            environment = {"NVIDIA_VISIBLE_DEVICES": "all"}

        try:
            self._remove_stale_user_containers(user_id)

            container = self.client.containers.run(
                image=self.settings.comfy_base_image,
                detach=True,
                ports={f"{self.settings.comfy_internal_port}/tcp": port},
                device_requests=device_requests,
                environment=environment,
                volumes={
                    str(self.settings.shared_models_path): {
                        "bind": self.settings.comfy_container_models_dir,
                        "mode": "ro",
                    },
                    str(user_workspace): {
                        "bind": self.settings.comfy_container_user_dir,
                        "mode": "rw",
                    },
                    str(user_output): {
                        "bind": self.settings.comfy_container_output_dir,
                        "mode": "rw",
                    },
                    str(user_temp): {
                        "bind": self.settings.comfy_container_temp_dir,
                        "mode": "rw",
                    },
                },
                labels={"dynamiccomfy.user_id": str(user_id)},
                name=self._container_name(user_id, port),
                command=[
                    "python3",
                    "main.py",
                    "--listen",
                    "0.0.0.0",
                    "--port",
                    str(self.settings.comfy_internal_port),
                    "--base-directory",
                    self.settings.comfy_container_user_dir,
                    "--output-directory",
                    self.settings.comfy_container_output_dir,
                    "--temp-directory",
                    self.settings.comfy_container_temp_dir,
                ],
            )
            self._wait_until_ready(container)
            return container
        except ImageNotFound as exc:
            image = self.settings.comfy_base_image
            raise RuntimeError(
                f"Base image '{image}' was not found. Build or pull it first, or update COMFY_BASE_IMAGE."
            ) from exc
        except APIError as exc:
            details = str(exc)
            if self.settings.enable_gpu:
                details = (
                    f"{details}. If this host has no NVIDIA runtime, set ENABLE_GPU=false."
                )
            raise RuntimeError(f"Failed to start container: {details}") from exc
        except DockerException as exc:
            raise RuntimeError(f"Docker connection error: {exc}") from exc

    @staticmethod
    def _is_port_allocation_error(exc: RuntimeError) -> bool:
        message = str(exc).lower()
        return "port is already allocated" in message or "bind for 0.0.0.0" in message

    async def start_for_user(self, user: User) -> StartResult:
        existing = await self.instances.get_running_by_user(user.id)
        if existing:
            return StartResult(
                container_id=existing.container_id,
                port=existing.port,
                workspace_url=f"http://{self.settings.server_public_host}:{existing.port}",
            )

        candidate_ports = range(self.settings.port_range_start, self.settings.port_range_end + 1)
        active_ports = set()
        container_port_key = f"{self.settings.comfy_internal_port}/tcp"
        for c in self.client.containers.list():
            ports = c.attrs.get("NetworkSettings", {}).get("Ports", {})
            bindings = ports.get(container_port_key) or []
            if not bindings:
                continue
            host_port = bindings[0].get("HostPort")
            if host_port:
                active_ports.add(int(host_port))

        run_error: RuntimeError | None = None
        container = None
        port = None
        for candidate in candidate_ports:
            if candidate in active_ports:
                continue
            try:
                container = self._run_container(user.id, candidate)
                port = candidate
                break
            except RuntimeError as exc:
                if self._is_port_allocation_error(exc):
                    run_error = exc
                    continue
                raise

        if container is None or port is None:
            if run_error:
                raise RuntimeError(
                    "Could not allocate a free host port for ComfyUI in configured range."
                ) from run_error
            raise RuntimeError("No free ports available in configured range")

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
            container.remove()
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
