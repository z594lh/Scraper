"""数据库连接与会话（MySQL）。"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .core.settings import settings

engine = create_engine(
    settings.db_url(),
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from . import models  # noqa: F401  平台表
    from . import sites  # noqa: F401  站点私有表（随站点注册自动建表）

    Base.metadata.create_all(engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """为已存在的库补新增列（create_all 不会改老表）。"""
    with engine.begin() as conn:
        has_pause = conn.exec_driver_sql("SHOW COLUMNS FROM projects LIKE 'pause_until'").first()
        if not has_pause:
            conn.exec_driver_sql(
                "ALTER TABLE projects ADD COLUMN pause_until DATETIME NULL "
                "COMMENT '定时暂停截止时间（风控触发后 2 小时内跳过定时任务）'"
            )


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
