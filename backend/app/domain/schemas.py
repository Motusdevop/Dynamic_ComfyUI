from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str

    model_config = {"from_attributes": True}


class InstanceOut(BaseModel):
    id: int
    user_id: int
    container_id: str
    port: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class InstanceControlOut(BaseModel):
    message: str
    status: str | None = None
    port: int | None = None
    container_id: str | None = None
    workspace_url: str | None = None


class SharedModelCreateIn(BaseModel):
    url: HttpUrl
    name: str | None = Field(default=None, max_length=255)


class SharedModelOut(BaseModel):
    id: int
    name: str
    url: str
    status: str

    model_config = {"from_attributes": True}
