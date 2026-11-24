"""项目与数据接口：平台表（projects/runs）+ 站点私有数据表。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from .. import runner
from ..crawlers.base import CrawlError
from ..db import get_db
from ..models import Project, Run
from ..notify import normalize_rules
from ..sites import get_site, list_sites

router = APIRouter(prefix="/api", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    site: str
    config: dict | None = None
    scheduleMinutes: int = 0
    notifyChannels: list[str] = []
    notifyRules: dict | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    config: dict | None = None
    scheduleMinutes: int | None = Field(default=None, ge=0, le=1440)
    notifyChannels: list[str] | None = None
    notifyRules: dict | None = None


def _slugify(db: Session, name: str, site_code: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or site_code
    slug = base
    index = 2
    while db.scalar(select(Project.id).where(Project.slug == slug)) is not None:
        slug = f"{base}-{index}"
        index += 1
    return slug


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def _normalize_config(site_code: str, config: dict[str, Any] | None) -> dict[str, Any]:
    """站点默认值兜底，并校验必填项（由站点 CONFIG_SCHEMA 声明）。"""
    site = get_site(site_code)
    merged = {**site.default_config, **(config or {})}
    missing = [
        item["label"]
        for group in site.config_schema
        for item in group["items"]
        if item.get("required") and not str(merged.get(item["key"], "")).strip()
    ]
    if missing:
        raise HTTPException(400, f"缺少必填配置：{'、'.join(missing)}")
    return merged


def _run_dict(run: Run) -> dict:
    duration = None
    if run.finished_at and run.started_at:
        duration = int((run.finished_at - run.started_at).total_seconds())
    return {
        "id": run.id,
        "status": run.status,
        "trigger": run.trigger,
        "startedAt": _iso(run.started_at),
        "finishedAt": _iso(run.finished_at),
        "duration": duration,
        "total": run.total,
        "newCount": run.new_count,
        "message": run.message,
        "filters": run.filters or [],
        "log": run.log or "",
    }


def _counts(db: Session, project: Project, site) -> tuple[int, int]:
    model = site.item_model
    item_count = db.scalar(
        select(func.count())
        .select_from(model)
        .where(model.project_id == project.id, model.active.is_(True))
    )
    new_count = db.scalar(
        select(func.count())
        .select_from(model)
        .where(
            model.project_id == project.id,
            model.active.is_(True),
            model.is_new.is_(True),
        )
    )
    return item_count or 0, new_count or 0


def _project_dict(db: Session, project: Project, detail: bool = False) -> dict:
    site = get_site(project.site)
    last_run = db.scalars(
        select(Run)
        .where(Run.project_id == project.id, Run.status != "running")
        .order_by(Run.started_at.desc())
        .limit(1)
    ).first()
    item_count, new_count = _counts(db, project, site)
    data = {
        "id": project.id,
        "slug": project.slug,
        "name": project.name,
        "site": project.site,
        "siteLabel": site.label,
        "table": site.table,
        "enabled": project.enabled,
        "config": project.config or {},
        "scheduleMinutes": project.schedule_minutes,
        "notifyChannels": project.notify_channels or [],
        "notifyRules": normalize_rules(project.notify_rules),
        "createdAt": _iso(project.created_at),
        "updatedAt": _iso(project.updated_at),
        "itemCount": item_count,
        "newCount": new_count,
        "running": runner.is_running(project.id),
        "lastRun": _run_dict(last_run) if last_run else None,
        "login": runner.login_status(project.id),
    }
    if detail:
        data["siteSpec"] = site.to_dict()
    return data


@router.get("/sites")
def sites():
    return list_sites()


@router.get("/sites/{site_code}/options")
def site_options(site_code: str, db: Session = Depends(get_db)):
    """站点筛选枚举（抓取时同步），前端配置表单的候选值。"""
    try:
        site = get_site(site_code)
    except CrawlError as exc:
        raise HTTPException(404, str(exc)) from exc
    model = site.option_model
    if model is None:
        return {"code": site_code, "categories": [], "updatedAt": None}
    rows = db.scalars(
        select(model)
        .where(model.active.is_(True))
        .order_by(model.category, model.sort_order)
    ).all()
    groups: dict[str, list[str]] = {}
    latest: datetime | None = None
    for row in rows:
        groups.setdefault(row.category, []).append(row.label)
        if latest is None or row.last_seen_at > latest:
            latest = row.last_seen_at
    return {
        "code": site_code,
        "categories": [
            {"category": category, "options": options}
            for category, options in groups.items()
        ],
        "updatedAt": _iso(latest),
    }


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    projects = db.scalars(select(Project).order_by(Project.id)).all()
    recent: list[dict] = []
    total_items = 0
    total_new = 0
    for project in projects:
        site = get_site(project.site)
        model = site.item_model
        active_items, new_items = _counts(db, project, site)
        total_items += active_items
        total_new += new_items
        rows = db.scalars(
            select(model)
            .where(model.project_id == project.id, model.active.is_(True))
            .order_by(model.first_seen_at.desc())
            .limit(20)
        ).all()
        for row in rows:
            recent.append(
                {
                    **site.serialize(row),
                    "projectId": project.id,
                    "projectSlug": project.slug,
                    "projectName": project.name,
                    "site": project.site,
                }
            )
    recent.sort(key=lambda row: row.get("firstSeenAt") or "", reverse=True)
    return {
        "projects": [_project_dict(db, p) for p in projects],
        "recentItems": recent[:20],
        "totals": {
            "projects": len(projects),
            "items": total_items,
            "newItems": total_new,
        },
    }


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    projects = db.scalars(select(Project).order_by(Project.id)).all()
    return [_project_dict(db, p) for p in projects]


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    try:
        site = get_site(payload.site)
    except CrawlError as exc:
        raise HTTPException(400, str(exc)) from exc
    config = _normalize_config(site.code, payload.config)
    project = Project(
        slug=_slugify(db, payload.name, site.code),
        name=payload.name.strip(),
        site=site.code,
        config=config,
        schedule_minutes=max(0, payload.scheduleMinutes),
        notify_channels=payload.notifyChannels,
        notify_rules=normalize_rules(payload.notifyRules),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_dict(db, project, detail=True)


@router.get("/projects/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    return _project_dict(db, project, detail=True)


@router.put("/projects/{project_id}")
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    if payload.name is not None:
        project.name = payload.name.strip()
    if payload.enabled is not None:
        project.enabled = payload.enabled
    if payload.config is not None:
        project.config = _normalize_config(project.site, payload.config)
    if payload.scheduleMinutes is not None:
        project.schedule_minutes = payload.scheduleMinutes
    if payload.notifyChannels is not None:
        project.notify_channels = payload.notifyChannels
    if payload.notifyRules is not None:
        project.notify_rules = normalize_rules(payload.notifyRules)
    db.commit()
    db.refresh(project)

    from ..scheduler import sync_jobs

    sync_jobs()
    return _project_dict(db, project, detail=True)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    site = get_site(project.site)
    # 站点私有数据表里的行也要删掉（runs 由 relationship cascade 处理）
    db.execute(delete(site.item_model).where(site.item_model.project_id == project.id))
    db.delete(project)
    db.commit()

    from ..scheduler import sync_jobs

    sync_jobs()
    return None


@router.post("/projects/{project_id}/run")
def run_project(project_id: int, db: Session = Depends(get_db)):
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "项目不存在")
    try:
        run = runner.start_run(project_id)
    except runner.BusyError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"runId": run.id, "status": run.status}


@router.get("/projects/{project_id}/runs")
def project_runs(project_id: int, limit: int = 20, db: Session = Depends(get_db)):
    runs = db.scalars(
        select(Run)
        .where(Run.project_id == project_id)
        .order_by(Run.started_at.desc())
        .limit(min(limit, 100))
    ).all()
    return [_run_dict(r) for r in runs]


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "运行记录不存在")
    return _run_dict(run)


@router.get("/projects/{project_id}/items")
def project_items(
    project_id: int,
    only_new: bool = False,
    include_inactive: bool = False,
    q: str = "",
    limit: int = 300,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    site = get_site(project.site)
    model = site.item_model
    stmt = select(model).where(model.project_id == project.id)
    if not include_inactive:
        stmt = stmt.where(model.active.is_(True))
    if only_new:
        stmt = stmt.where(model.is_new.is_(True))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(model.goods_no.like(like), model.title.like(like)))
    stmt = stmt.order_by(model.is_new.desc(), model.first_seen_at.desc()).limit(
        min(limit, 1000)
    )
    rows = db.scalars(stmt).all()
    return {
        "site": site.code,
        "table": site.table,
        "columns": site.columns,
        "items": [site.serialize(row) for row in rows],
    }


@router.post("/projects/{project_id}/login")
def project_login(project_id: int, timeout_seconds: int = 300, db: Session = Depends(get_db)):
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "项目不存在")
    try:
        return runner.start_login(project_id, min(max(timeout_seconds, 30), 900))
    except runner.BusyError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/projects/{project_id}/login")
def project_login_status(project_id: int):
    return runner.login_status(project_id)
