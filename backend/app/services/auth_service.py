from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password, hash_password
from app.domain.schemas import TokenOut
from app.infrastructure.user_repository import UserRepository


class AuthService:
    def __init__(self, db: AsyncSession):
        self.users = UserRepository(db)

    async def login(self, username: str, password: str) -> TokenOut:
        user = await self.users.get_by_username(username)
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        token = create_access_token(subject=user.username)
        return TokenOut(access_token=token)
