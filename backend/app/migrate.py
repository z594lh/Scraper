"""结构升级脚本：平台表补注释 + 站点私有表 + 旧数据迁移。

用法（backend 目录）：python cli.py migrate
脚本可重复执行，已完成的部分会自动跳过。
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import inspect, select, text

from .common.timeutil import parse_dt
from .core.settings import PROJECTS_DIR
from .db import SessionLocal, engine, init_db
from .models import Project

PROJECT_DDL = """
ALTER TABLE projects
  MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `site` VARCHAR(32) NOT NULL COMMENT '站点编码（panzhi/crab…），决定数据表与表单',
  MODIFY COLUMN `slug` VARCHAR(64) NOT NULL COMMENT '项目唯一标识，同时作为数据目录名',
  MODIFY COLUMN `name` VARCHAR(128) NOT NULL COMMENT '项目名称',
  MODIFY COLUMN `enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用（关闭后不参与定时抓取）',
  MODIFY COLUMN `config` JSON NULL COMMENT '该站点的筛选配置',
  MODIFY COLUMN `schedule_minutes` INT NOT NULL DEFAULT 0 COMMENT '定时抓取间隔（分钟，0=关闭）',
  MODIFY COLUMN `notify_channels` JSON NULL COMMENT '通知渠道列表（dingtalk/wecom）',
  MODIFY COLUMN `notify_rules` JSON NULL COMMENT '通知规则（新增条数阈值/执行失败/执行完成）',
  MODIFY COLUMN `created_at` DATETIME NOT NULL COMMENT '创建时间',
  MODIFY COLUMN `updated_at` DATETIME NOT NULL COMMENT '更新时间',
  COMMENT='监控项目（站点实例）'
"""

RUN_DDL = """
ALTER TABLE runs
  MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键',
  MODIFY COLUMN `project_id` INT NOT NULL COMMENT '所属项目（projects.id）',
  MODIFY COLUMN `status` VARCHAR(16) NOT NULL COMMENT '运行状态：running/success/failed',
  MODIFY COLUMN `trigger` VARCHAR(16) NOT NULL COMMENT '触发方式：manual/cli/schedule',
  MODIFY COLUMN `started_at` DATETIME NOT NULL COMMENT '开始时间',
  MODIFY COLUMN `finished_at` DATETIME NULL COMMENT '结束时间',
  MODIFY COLUMN `total` INT NOT NULL DEFAULT 0 COMMENT '本次抓取条数',
  MODIFY COLUMN `new_count` INT NOT NULL DEFAULT 0 COMMENT '本次新增条数',
  MODIFY COLUMN `message` TEXT NOT NULL COMMENT '失败原因或说明',
  MODIFY COLUMN `filters` JSON NULL COMMENT '本次生效的筛选条件',
  MODIFY COLUMN `log` TEXT NOT NULL COMMENT '运行日志',
  COMMENT='抓取运行记录'
"""


def _columns(table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {idx["name"] for idx in inspect(engine).get_indexes(table)}


def _rename_legacy_site(steps: list[str]) -> None:
    """老版本的 projects.kind -> projects.site，并把 pzds 统一为 panzhi。"""
    tables = inspect(engine).get_table_names()
    if "projects" not in tables:
        return
    cols = _columns("projects")
    if "kind" in cols and "site" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE projects CHANGE COLUMN `kind` `site` "
                    "VARCHAR(32) NOT NULL DEFAULT 'panzhi' "
                    "COMMENT '站点编码（panzhi/crab…），决定数据表与表单'"
                )
            )
        steps.append("projects.kind 已改名为 projects.site")
    if "site" in _columns("projects"):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE projects SET site='panzhi' WHERE site IN ('pzds','pzds-2')")
            )
    if "ix_projects_site" not in _indexes("projects"):
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE projects ADD INDEX ix_projects_site (`site`)"))
        steps.append("projects.site 已补索引")


def _migrate_items(steps: list[str]) -> None:
    """旧平台表 items -> panzhi_items_data，完成后删除 items。"""
    if "items" not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT project_id, goods_no, price, title, server, labels, on_stand_time, "
                "create_time, url, first_seen_at, last_seen_at, last_run_id, is_new, active "
                "FROM items"
            )
        ).mappings().all()
        for row in rows:
            conn.execute(
                text(
                    """
                    INSERT IGNORE INTO panzhi_items_data
                      (project_id, goods_no, price, title, url, is_new, active,
                       first_seen_at, last_seen_at, last_run_id,
                       server_name, labels, on_stand_time, create_time)
                    VALUES
                      (:project_id, :goods_no, :price, :title, :url, :is_new, :active,
                       :first_seen_at, :last_seen_at, :last_run_id,
                       :server_name, :labels, :on_stand_time, :create_time)
                    """
                ),
                {
                    "project_id": row["project_id"],
                    "goods_no": row["goods_no"],
                    "price": row["price"],
                    "title": row["title"] or "",
                    "url": row["url"] or "",
                    "is_new": 1 if row["is_new"] else 0,
                    "active": 1 if row["active"] else 0,
                    "first_seen_at": row["first_seen_at"],
                    "last_seen_at": row["last_seen_at"],
                    "last_run_id": row["last_run_id"],
                    "server_name": row["server"] or "",
                    "labels": row["labels"],
                    "on_stand_time": parse_dt(row["on_stand_time"]),
                    "create_time": parse_dt(row["create_time"]),
                },
            )
        conn.execute(text("DROP TABLE items"))
    steps.append(f"items -> panzhi_items_data 迁移 {len(rows)} 条，旧表已删除")


def _rename_default_project(steps: list[str]) -> None:
    """默认项目 slug 从 pzds 改成 panzhi，指纹目录一起搬过去。"""
    db = SessionLocal()
    try:
        project = db.scalar(select(Project).where(Project.slug == "pzds"))
        if project is None:
            return
        if db.scalar(select(Project).where(Project.slug == project.site)) is not None:
            return
        project.slug = project.site
        db.commit()
        src = PROJECTS_DIR / "pzds"
        dst = PROJECTS_DIR / project.site
        if src.exists() and not dst.exists():
            src.rename(dst)
        steps.append("默认项目 pzds -> panzhi（含指纹目录）")
    finally:
        db.close()


def _ensure_notify_rules(steps: list[str]) -> None:
    """新增通知规则列（新增阈值/失败/完成）。"""
    if "projects" not in inspect(engine).get_table_names():
        return
    if "notify_rules" in _columns("projects"):
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE projects ADD COLUMN `notify_rules` JSON NULL "
                "COMMENT '通知规则（新增条数阈值/执行失败/执行完成）' "
                "AFTER `notify_channels`"
            )
        )
    steps.append("projects.notify_rules 已添加")


def _fix_panzhi_urls(steps: list[str]) -> None:
    """修正历史盼之详情链接：goodsDetail/<编号>/6 -> goodsDetails/<编号>。"""
    if "panzhi_items_data" not in inspect(engine).get_table_names():
        return
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, url FROM panzhi_items_data "
                "WHERE url LIKE '%goodsDetail/%'"
            )
        ).all()
        for row in rows:
            url = row.url.replace("/goodsDetail/", "/goodsDetails/")
            url = re.sub(r"/6$", "", url)
            conn.execute(
                text("UPDATE panzhi_items_data SET url = :url WHERE id = :id"),
                {"url": url, "id": row.id},
            )
    if rows:
        steps.append(f"盼之详情链接已修正 {len(rows)} 条")


def _seed_panzhi_options(steps: list[str]) -> None:
    """首次建表时用默认配置初始化筛选枚举，之后由每次抓取自动同步。"""
    if "panzhi_options_data" not in inspect(engine).get_table_names():
        return
    from .sites.panzhi.config import DEFAULT_CONFIG

    with engine.begin() as conn:
        if conn.execute(text("SELECT COUNT(*) FROM panzhi_options_data")).scalar():
            return
        now = datetime.now()
        for category, labels in (DEFAULT_CONFIG.get("sections") or {}).items():
            for index, label in enumerate(labels):
                conn.execute(
                    text(
                        "INSERT IGNORE INTO panzhi_options_data "
                        "(category, label, sort_order, active, first_seen_at, last_seen_at) "
                        "VALUES (:category, :label, :sort, 1, :now, :now)"
                    ),
                    {
                        "category": category,
                        "label": label,
                        "sort": index,
                        "now": now,
                    },
                )
    steps.append("盼之筛选枚举已用默认配置初始化（后续抓取自动同步）")


def run() -> list[str]:
    steps: list[str] = []
    _rename_legacy_site(steps)
    _ensure_notify_rules(steps)
    init_db()  # 创建各站点私有数据表（带表/字段注释）
    steps.append("站点私有数据表已就绪")
    _migrate_items(steps)
    _rename_default_project(steps)
    _fix_panzhi_urls(steps)
    _seed_panzhi_options(steps)

    tables = inspect(engine).get_table_names()
    with engine.begin() as conn:
        if "projects" in tables:
            conn.execute(text(PROJECT_DDL))
        if "runs" in tables:
            conn.execute(text(RUN_DDL))
    steps.append("projects/runs 表与字段注释已补齐")
    return steps
