"""通用入库：对任意站点数据表做去重、NEW 标记、下架标记。

站点表都继承 ItemBase，所以这里不需要认识具体站点字段，
差异由各站点模型的 apply_crawl() 承担。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crawlers.base import CrawlItem
from ..models import Project, Run
from ..sites.spec import SiteSpec


def save_items(
    db: Session,
    project: Project,
    site: SiteSpec,
    run: Run,
    items: list[CrawlItem],
    now: datetime | None = None,
) -> tuple[list, bool]:
    """按商品编号去重入库，返回 (本次新增行, 是否首次运行)。

    - 库里没有过的编号才算 NEW；
    - 首次运行时只建立基线，不标记 NEW；
    - 本次未出现的编号标记为已下架。
    """
    now = now or datetime.now()
    model = site.item_model
    existing = {
        row.goods_no: row
        for row in db.scalars(select(model).where(model.project_id == project.id))
    }
    first_run = not existing

    present: set[str] = set()
    fresh: list = []
    for data in items:
        present.add(data.goods_no)
        row = existing.get(data.goods_no)
        created = row is None
        if created:
            row = model(project_id=project.id, goods_no=data.goods_no, first_seen_at=now)
            db.add(row)
        row.apply_crawl(data)
        row.last_seen_at = now
        row.last_run_id = run.id
        row.is_new = created and not first_run
        row.active = True
        if row.is_new:
            fresh.append(row)

    for goods_no, row in existing.items():
        if goods_no not in present:
            row.active = False
            row.is_new = False

    return fresh, first_run


def save_options(db: Session, site: SiteSpec, options: list[dict]) -> int:
    """同步站点筛选枚举（抓取时顺手采集，前端下拉从这里读）。"""
    model = site.option_model
    if model is None or not options:
        return 0
    now = datetime.now()
    for group in options:
        category = str(group.get("category") or "").strip()
        labels = [str(x).strip() for x in group.get("options") or [] if str(x).strip()]
        if not category or not labels:
            continue
        existing = {
            row.label: row
            for row in db.scalars(select(model).where(model.category == category))
        }
        seen: set[str] = set()
        for index, label in enumerate(labels):
            seen.add(label)
            row = existing.get(label)
            if row is None:
                row = model(category=category, label=label, first_seen_at=now)
                db.add(row)
            row.sort_order = index
            row.active = True
            row.last_seen_at = now
        for label, row in existing.items():
            if label not in seen:
                row.active = False
    db.commit()
    return len(options)
