"""定时任务：按项目配置的间隔分钟数调度抓取。"""

from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from . import runner
from .core.settings import settings
from .db import SessionLocal
from .models import Project

log = logging.getLogger("uvicorn.error")
scheduler = BackgroundScheduler(timezone="Asia/Shanghai", daemon=True)


def _job(project_id: int) -> None:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project and project.pause_until and project.pause_until > datetime.now():
            log.info("项目 %s 风控暂停中（至 %s），跳过本次定时任务", project_id, project.pause_until)
            return
    finally:
        db.close()
    try:
        runner.start_run(project_id, trigger="schedule")
    except runner.BusyError:
        log.info("项目 %s 仍在抓取中，跳过本次定时任务", project_id)
    except Exception:
        log.exception("定时任务启动失败: project=%s", project_id)


def sync_jobs() -> None:
    if not settings.scheduler_enabled:
        return
    scheduler.remove_all_jobs()
    db = SessionLocal()
    try:
        projects = db.scalars(
            select(Project).where(Project.schedule_minutes > 0, Project.enabled.is_(True))
        )
        for project in projects:
            scheduler.add_job(
                _job,
                "interval",
                minutes=max(1, project.schedule_minutes),
                args=[project.id],
                id=f"project-{project.id}",
                max_instances=1,
                coalesce=True,
                replace_existing=True,
            )
    finally:
        db.close()


def start() -> None:
    if not settings.scheduler_enabled:
        return
    if not scheduler.running:
        scheduler.start()
    sync_jobs()


def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
