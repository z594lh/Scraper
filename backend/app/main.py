"""FastAPI 入口：初始化数据库/调度器，托管前端静态文件。"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select

from . import scheduler
from .api import api_router
from .core.settings import DATA_DIR, FRONTEND_DIST, PROJECTS_DIR, settings
from .db import SessionLocal, init_db
from .models import Project
from .sites import get_site


def seed_default_project() -> None:
    """首次启动创建默认的盼之项目（配置来自站点的默认值）。"""
    db = SessionLocal()
    try:
        if db.scalar(select(func.count()).select_from(Project)):
            return
        site = get_site("panzhi")
        config = dict(site.default_config)
        project = Project(
            slug=site.code,
            name=f"{site.label} · {config.get('region') or '默认'}",
            site=site.code,
            config=config,
            schedule_minutes=0,
            notify_channels=[],
        )
        db.add(project)
        db.commit()
        (PROJECTS_DIR / site.code).mkdir(parents=True, exist_ok=True)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    if settings.pzds_chrome:
        os.environ["PZDS_CHROME"] = settings.pzds_chrome
    init_db()
    seed_default_project()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="数据中心", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
def health():
    return {"ok": True, "frontendBuilt": FRONTEND_DIST.exists()}


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if not FRONTEND_DIST.exists():
        return JSONResponse(
            {
                "detail": "前端尚未构建。开发模式请访问 http://localhost:5173，"
                "或执行 cd frontend && npm run build"
            },
            status_code=404,
        )
    candidate = (FRONTEND_DIST / full_path).resolve()
    if full_path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
        return FileResponse(candidate)
    return FileResponse(FRONTEND_DIST / "index.html")
