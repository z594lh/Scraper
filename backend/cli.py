"""终端运维入口：数据库初始化/迁移、登录、单次抓取。

用法（在 backend 目录执行）：
    python cli.py migrate
    python cli.py login --project panzhi
    python cli.py run --project panzhi
"""

from __future__ import annotations

import argparse
import sys
import time

from app import runner
from app.core.settings import DATA_DIR
from app.crawlers.base import CrawlError
from app.db import SessionLocal, init_db
from app.models import Project, Run
from app.sites import build_crawler


def _resolve_project(slug: str | None) -> Project:
    db = SessionLocal()
    try:
        query = db.query(Project)
        project = (
            query.filter(Project.slug == slug).first() if slug else query.order_by(Project.id).first()
        )
        if project is None:
            raise SystemExit("没有可用项目，请先启动一次服务或在监控台新建项目")
        db.expunge(project)
        return project
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="cli.py")
    parser.add_argument("command", choices=["init-db", "migrate", "login", "run"])
    parser.add_argument("--project", help="项目 slug，默认第一个项目")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.command == "migrate":
        from app.migrate import run as migrate

        for step in migrate():
            print(f"- {step}", flush=True)
        print("迁移完成", flush=True)
        return

    init_db()
    if args.command == "init-db":
        print("数据库已初始化")
        return

    project = _resolve_project(args.project)
    crawler = build_crawler(project.site, project.config or {}, project.slug)

    if args.command == "login":
        try:
            sys.exit(crawler.login_cli())
        except CrawlError as exc:
            print(exc, flush=True)
            sys.exit(1)

    try:
        run = runner.start_run(project.id, trigger="cli")
    except runner.BusyError as exc:
        print(exc, flush=True)
        sys.exit(1)

    while runner.is_running(project.id):
        time.sleep(1)

    db = SessionLocal()
    try:
        result = db.get(Run, run.id)
        print(result.log or "", flush=True)
        if result.status == "success":
            print(f"完成：抓到 {result.total} 个，新增 {result.new_count} 个", flush=True)
        else:
            print(f"失败：{result.message}", flush=True)
        sys.exit(0 if result.status == "success" else 1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
