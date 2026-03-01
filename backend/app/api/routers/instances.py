from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.domain.models import User
from app.domain.schemas import InstanceControlOut
from app.services.docker_manager import DockerManager

router = APIRouter(prefix="/instances", tags=["instances"])


@router.post("/start", response_model=InstanceControlOut)
async def start_instance(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InstanceControlOut:
    manager = DockerManager(db)
    result = await manager.start_for_user(user)
    status, _, _, _ = await manager.status_for_user(user)
    return InstanceControlOut(
        message="Instance ready" if status == "running" else "Instance unavailable",
        status="running",
        port=result.port,
        container_id=result.container_id,
        workspace_url=result.workspace_url,
    )


@router.post("/stop", response_model=InstanceControlOut)
async def stop_instance(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InstanceControlOut:
    manager = DockerManager(db)
    stopped = await manager.stop_for_user(user)
    return InstanceControlOut(
        message="Instance stopped" if stopped else "No running instance",
        status="stopped",
        workspace_url=None,
    )


@router.get("/status")
async def instance_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    status, port, container_id, workspace_url = await DockerManager(db).status_for_user(user)
    return {
        "status": status,
        "port": port,
        "container_id": container_id,
        "workspace_url": workspace_url,
    }
