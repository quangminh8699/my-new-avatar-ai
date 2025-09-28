from sqlmodel import SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
import os

# Đọc URL từ .env hoặc đặt trực tiếp
# Ví dụ: mysql+pymysql://user:password@localhost:3306/avatar_db
DATABASE_URL = "mysql+pymysql://root:password@localhost:3306/my_new_avatart_ai"

# async engine
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)