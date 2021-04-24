import asyncio
from contextvars import ContextVar

from fastapi import Depends
from sqlalchemy import Column, Integer, MetaData, orm, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_base, declared_attr, selectinload, sessionmaker
from sqlalchemy.orm.exc import UnmappedClassError
from starlette.middleware.base import BaseHTTPMiddleware

from api.settings import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


class Query:
    def __get__(self, obj, type_):
        try:
            mapper = orm.class_mapper(type_)
            if mapper:
                return orm.Query(mapper)
        except UnmappedClassError:
            return None


class Base:
    @declared_attr
    def __tablename__(cls):
        # i.e. Store->stores, WalletxStore -> walletsxstores
        return "x".join(map(lambda x: x + "s", cls.__name__.lower().split("x")))

    id = Column(Integer, primary_key=True, index=True)


# format from settings
CONNECTION_STR = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(CONNECTION_STR, pool_pre_ping=True, future=True, echo=True)
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False, class_=AsyncSession, future=True
)
Base = declarative_base(cls=Base)
Base.query = Query()
Base.metadata = MetaData(
    naming_convention={
        "ix": "%(column_0_label)s_idx",
        "uq": "%(table_name)s_%(column_0_name)s_key",
        "ck": "%(table_name)s_%(constraint_name)s_check",
        "fk": "%(table_name)s_%(column_0_name)s_%(referred_table_name)s_fkey",
        "pk": "%(table_name)s_pkey",
    }
)


async def get_db():
    session = SessionLocal()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError as ex:
        await session.rollback()
        raise ex
    finally:
        await session.close()


database_dep = Depends(get_db)
