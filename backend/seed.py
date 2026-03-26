"""Create the default dev user for MVP (no auth)."""

import asyncio
import uuid

from app.database import async_session
from app.models.user import User


async def main():
    async with async_session() as db:
        db.add(
            User(
                id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                email="dev@test.com",
                name="Dev User",
            )
        )
        await db.commit()
        print("Seed user created")


asyncio.run(main())
