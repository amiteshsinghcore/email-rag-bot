import asyncio
from sqlalchemy import select
from app.db.session import async_session_factory
from app.db.models.user import User
from app.core.security import get_password_hash

async def reset_password():
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == "admin@example.com"))
        user = result.scalar_one_or_none()
        
        if user:
            print(f"Found user: {user.email}")
            user.hashed_password = get_password_hash("admin123#")
            user.failed_login_attempts = 0
            user.locked_until = None
            await session.commit()
            print("Password has been reset to: admin123#")
            print("Account unlocked.")
        else:
            print("User admin@example.com not found.")

if __name__ == "__main__":
    asyncio.run(reset_password())
