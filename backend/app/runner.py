"""抓取执行器：后台线程执行，每个项目单并发，结果入库并触发通知。

平台层职责：调度、去重入库（NEW/下架）、通知；
具体怎么抓、抓哪些字段由站点包（app/sites/<code>）决定。
"""

from __future__ import annotations

import threading
import traceback
from datetime import datetime, timedelta

from .common.store import save_items, save_options
from .crawlers.base import CrawlError
from .db import SessionLocal
from .models import Project, Run
from .notify import build_new_items_message, normalize_rules, send_to
from .sites import build_crawler, get_site, workdir_of

RISK_PAUSE_HOURS = 2  # 触发风控后暂停定时的时长
RISK_KEYWORDS = ("滑块", "风控", "验证")

_running: set[int] = set()
_state_lock = threading.Lock()
_login_tasks: dict[int, dict] = {}


class BusyError(RuntimeError):
    pass


def _is_risk(message: str) -> bool:
    """是否是风控/滑块类失败。"""
    return any(keyword in message for keyword in RISK_KEYWORDS)


def _pause_schedule(project: Project, run: Run) -> None:
    """风控触发后把该项目定时任务暂停一段时间。"""
    project.pause_until = datetime.now() + timedelta(hours=RISK_PAUSE_HOURS)
    note = (
        f"\n风控触发：定时任务暂停 {RISK_PAUSE_HOURS} 小时，"
        f"至 {project.pause_until:%Y-%m-%d %H:%M:%S}（手动抓取不受影响）"
    )
    run.log = (run.log or "") + note


def is_running(project_id: int) -> bool:
    with _state_lock:
        return project_id in _running


def _notify(project: Project, run: Run, db, messages: list[tuple[str, str]]) -> None:
    """按通知规则发送消息，结果写进运行日志。"""
    if not messages or not project.notify_channels:
        return
    results: list[dict] = []
    for title, text in messages:
        results.extend(send_to(project.notify_channels, title, text))
    summary = "；".join(
        f"{item['channel']}:{'成功' if item['ok'] else item['message']}" for item in results
    )
    run.log = (run.log or "") + f"\n通知结果: {summary}"
    db.commit()


def _execute(run_id: int, project_id: int, trigger: str) -> None:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        run = db.get(Run, run_id)
        if project is None or run is None:
            return
        try:
            site = get_site(project.site)
            crawler = build_crawler(project.site, project.config or {}, project.slug)
            result = crawler.run()
            fresh, first_run = save_items(db, project, site, run, result.items)
            save_options(db, site, result.options)
            run.status = "success"
            run.total = len(result.items)
            run.new_count = len(fresh)
            run.filters = result.filters
            project.pause_until = None  # 抓取成功即解除风控暂停
            log = result.log or ""
            if first_run:
                log += "\n首次运行：已建立基线，本次不标记 NEW"
            else:
                log += f"\n新增 {len(fresh)} 个"
            run.log = log
            run.finished_at = datetime.now()
            db.commit()

            rules = normalize_rules(project.notify_rules)
            messages: list[tuple[str, str]] = []
            if (
                fresh
                and rules["newItems"]["enabled"]
                and len(fresh) >= rules["newItems"]["threshold"]
            ):
                messages.append(build_new_items_message(project.name, fresh))
            if rules["runFinished"]["enabled"]:
                messages.append(
                    (
                        f"{project.name} 抓取完成",
                        f"### 抓取完成\n- 抓到 **{len(result.items)}** 个\n- 新增 **{len(fresh)}** 个",
                    )
                )
            _notify(project, run, db, messages)
        except CrawlError as exc:
            run.status = "failed"
            run.message = str(exc)
            if _is_risk(run.message):
                _pause_schedule(project, run)
            run.finished_at = datetime.now()
            db.commit()
            if normalize_rules(project.notify_rules)["runFailed"]["enabled"]:
                _notify(
                    project,
                    run,
                    db,
                    [(f"{project.name} 抓取失败", f"### 抓取失败\n{exc}")],
                )
        except Exception as exc:  # 未预期异常保留堆栈，方便排查
            run.status = "failed"
            run.message = f"{type(exc).__name__}: {exc}"
            run.log = traceback.format_exc()
            if _is_risk(run.message):
                _pause_schedule(project, run)
            run.finished_at = datetime.now()
            db.commit()
            if normalize_rules(project.notify_rules)["runFailed"]["enabled"]:
                _notify(
                    project,
                    run,
                    db,
                    [(f"{project.name} 抓取失败", f"### 抓取失败\n{run.message}")],
                )
    finally:
        db.close()
        with _state_lock:
            _running.discard(project_id)


def start_run(project_id: int, trigger: str = "manual") -> Run:
    with _state_lock:
        if project_id in _running:
            raise BusyError("该项目正在抓取中，请等待完成")
        _running.add(project_id)
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            with _state_lock:
                _running.discard(project_id)
            raise BusyError("项目不存在")
        get_site(project.site)  # 站点未注册时尽早失败
        run = Run(
            project_id=project.id, status="running", trigger=trigger, started_at=datetime.now()
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        workdir_of(project.slug).mkdir(parents=True, exist_ok=True)
        threading.Thread(
            target=_execute, args=(run.id, project.id, trigger), daemon=True
        ).start()
        return run
    finally:
        db.close()


def login_status(project_id: int) -> dict:
    with _state_lock:
        return dict(_login_tasks.get(project_id) or {"state": "idle", "message": ""})


def _do_login(project_id: int, timeout_seconds: int) -> None:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            raise CrawlError("项目不存在")
        crawler = build_crawler(project.site, project.config or {}, project.slug)
        ok, message = crawler.login(timeout_seconds)
        with _state_lock:
            _login_tasks[project_id] = {
                "state": "success" if ok else "failed",
                "message": message,
                "finishedAt": datetime.now().isoformat(timespec="seconds"),
            }
    except Exception as exc:
        with _state_lock:
            _login_tasks[project_id] = {
                "state": "failed",
                "message": f"{type(exc).__name__}: {exc}",
                "finishedAt": datetime.now().isoformat(timespec="seconds"),
            }
    finally:
        db.close()


def start_login(project_id: int, timeout_seconds: int = 300) -> dict:
    with _state_lock:
        current = _login_tasks.get(project_id)
        if current and current.get("state") == "running":
            raise BusyError("登录窗口已打开，请先完成登录")
        _login_tasks[project_id] = {
            "state": "running",
            "message": "正在打开浏览器，请在弹出的窗口中完成登录（完成后自动关闭）",
            "startedAt": datetime.now().isoformat(timespec="seconds"),
        }
    threading.Thread(target=_do_login, args=(project_id, timeout_seconds), daemon=True).start()
    return login_status(project_id)
