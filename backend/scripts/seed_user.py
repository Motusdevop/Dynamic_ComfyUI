import asyncio
import sys

from app.core.security import hash_password
from app.infrastructure.database import SessionLocal, init_db
from app.infrastructure.user_repository import UserRepository


async def main(username: str, password: str) -> None:
    await init_db()
    async with SessionLocal() as db:
        repo = UserRepository(db)
        existing = await repo.get_by_username(username)
        if existing:
            print(f"User '{username}' already exists")
            return
        await repo.create(username=username, hashed_password=hash_password(password))
        print(f"Created user '{username}'")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.seed_user <username> <password>")
        raise SystemExit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))

# docker compose run --rm api uv run python -m scripts.seed_user testuser testpass123
