"""盼之代售（pzds.com）爬虫实现。

站点用阿里云 WAF + wasm 签名保护列表接口，直接请求无法通过，
因此用有头 Chrome（patchright）打开真实页面，用界面点击应用筛选，
再读取页面自身的接口响应。两次点击间隔约 10 秒可降低滑块概率。

本模块只负责“打开页面 → 应用筛选 → 拿到列表”，
NEW 判定、入库、通知由平台层（runner + common.store）统一处理。
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import time
from pathlib import Path
from typing import Any

from patchright.sync_api import sync_playwright

from ...core.settings import settings
from ...crawlers.base import BaseCrawler, CrawlError, CrawlItem, CrawlResult
from .config import DEFAULT_CONFIG

API_PAGE = "goodsPublic/page"
LOGIN_HINT = "登录态无效，请先在监控台点击「登录」，或运行 python cli.py login"

__all__ = ["DEFAULT_CONFIG", "PzdsCrawler"]


class NotLoggedInError(RuntimeError):
    """登录态缺失。"""


# ---------- 浏览器 ----------

def open_page(p, profile_dir: Path):
    # 默认用本机 Chrome 通道；虚拟机可用 PZDS_CHROME 指定浏览器路径。
    exe = os.environ.get("PZDS_CHROME") or settings.pzds_chrome
    profile_dir.mkdir(parents=True, exist_ok=True)

    def launch(extra):
        opts = dict(
            headless=False,  # headless 会被 WAF 拦截
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            viewport={"width": 1440, "height": 960},
        )
        opts.update(extra)
        ctx = p.chromium.launch_persistent_context(str(profile_dir), **opts)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(15000)
        return ctx, page

    if exe:
        return launch({"executable_path": exe})
    try:
        return launch({"channel": "chrome"})
    except Exception:
        fallback = (
            shutil.which("google-chrome")
            or shutil.which("google-chrome-stable")
            or shutil.which("chromium")
        )
        if not fallback:
            raise
        return launch({"executable_path": fallback})


def is_logged_in(page) -> bool:
    if "/login" in page.url:
        return False
    return page.get_by_text("登录/注册").count() == 0


def click_visible_text(page, text: str) -> bool:
    items = page.get_by_text(text, exact=True)
    for i in range(items.count()):
        loc = items.nth(i)
        try:
            if loc.is_visible() and loc.inner_text().strip() == text:
                loc.click(timeout=4000)
                return True
        except Exception:
            continue
    return False


def first_visible(page, selector: str):
    loc = page.locator(selector)
    for i in range(loc.count()):
        item = loc.nth(i)
        try:
            if item.is_visible():
                return item
        except Exception:
            continue
    return None


def check_agreement(page) -> bool:
    """勾选“服务协议”（element-ui 原生 input 隐藏，需点可视区域）。"""
    boxes = page.locator(".el-checkbox")
    for i in range(boxes.count()):
        box = boxes.nth(i)
        try:
            if not box.is_visible():
                continue
            native = box.locator("input.el-checkbox__original")
            if native.count() and native.first.is_checked():
                return True
            box.locator(".el-checkbox__inner").click(timeout=4000)
            page.wait_for_timeout(300)
            print("已勾选服务协议", flush=True)
            return True
        except Exception:
            continue
    return False


def wait_login(page, seconds: int) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline and not is_logged_in(page):
        time.sleep(2)
    return is_logged_in(page)


def login_manual(profile_dir: Path, list_url: str, timeout_seconds: int = 300):
    """网页端触发：打开可见浏览器，等用户手动完成登录。"""
    with sync_playwright() as p:
        ctx, page = open_page(p, profile_dir)
        try:
            page.goto(list_url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(3000)
            if is_logged_in(page):
                return True, "已处于登录状态"
            try:
                page.get_by_text("登录/注册").first.click(timeout=8000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            ok = wait_login(page, timeout_seconds)
            if ok:
                page.wait_for_timeout(2000)
                return True, "登录成功，登录态已保存"
            return False, f"等待登录超时（{timeout_seconds} 秒）"
        finally:
            ctx.close()


def login_interactive(profile_dir: Path, list_url: str) -> int:
    """终端交互式手机验证码登录（无显示器环境使用）。"""
    with sync_playwright() as p:
        ctx, page = open_page(p, profile_dir)
        try:
            page.goto(list_url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(3000)
            if is_logged_in(page):
                print("已处于登录状态，无需重复登录。", flush=True)
                return 0

            try:
                page.get_by_text("登录/注册").first.click(timeout=8000)
            except Exception:
                pass
            page.wait_for_timeout(2500)

            phone_input = first_visible(page, 'input[placeholder="请输入手机号"]')
            if not phone_input:
                print("未识别到验证码登录表单，请在浏览器窗口内手动完成登录…", flush=True)
                ok = wait_login(page, 600)
                print("登录成功，登录态已保存。" if ok else "等待登录超时。", flush=True)
                return 0 if ok else 1

            phone_input.click()
            phone_input.fill(input("请输入登录手机号: ").strip())
            print("已填写手机号:", phone_input.input_value(), flush=True)
            if not click_visible_text(page, "获取验证码"):
                print("未能自动点击“获取验证码”，如页面可见请手动点击。", flush=True)
            code = input("请输入收到的短信验证码: ").strip()
            code_input = first_visible(page, 'input[placeholder="请输入验证码"]')
            if code_input:
                code_input.fill(code)
                print("已填入验证码，长度", len(code), flush=True)
            submit = first_visible(page, "button.login-btn")
            if submit:
                check_agreement(page)
                submit.click()
            page.wait_for_timeout(3000)
            msgs = page.evaluate(
                """() => Array.from(document.querySelectorAll('.el-message, .el-message__content, [class*=toast], [role=alert]'))
                .map(e => (e.innerText||'').trim()).filter(Boolean).slice(0,5)"""
            )
            if msgs:
                print("页面提示:", msgs, flush=True)
            ok = wait_login(page, 60)
            if not ok and waf_blocked(page):
                print("出现滑块验证，请稍后重试。", flush=True)
                return 1
            print("登录成功，登录态已保存。" if ok else "登录未成功，请重新执行 login。", flush=True)
            return 0 if ok else 1
        finally:
            ctx.close()


# ---------- 页面操作 ----------

def section_item(page, label: str):
    if not label:
        return page.locator(".filter-item").first
    return page.locator(".filter-item").filter(
        has=page.locator(".filter-item-label-name", has_text=label)
    ).first


def human_click(page, loc) -> None:
    box = loc.bounding_box()
    if not box:
        loc.click(timeout=6000)
        return
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    page.mouse.move(x - random.randint(40, 120), y - random.randint(30, 90), steps=6)
    page.wait_for_timeout(random.randint(120, 300))
    page.mouse.move(x, y, steps=5)
    page.wait_for_timeout(random.randint(60, 180))
    page.mouse.click(x, y)


def expand_panel(page) -> None:
    for i in range(page.get_by_text("展开", exact=True).count()):
        try:
            page.get_by_text("展开", exact=True).nth(i).click(timeout=2000)
            page.wait_for_timeout(500)
        except Exception:
            pass
    page.wait_for_timeout(800)


def waf_blocked(page) -> bool:
    return page.locator("#waf_nc_block").count() > 0


def click_opt(page, label: str, text: str, gap) -> bool:
    item = section_item(page, label).locator(".opt-item").filter(has_text=text)
    for i in range(item.count()):
        cand = item.nth(i)
        if cand.inner_text().strip() != text:
            continue
        cand.scroll_into_view_if_needed(timeout=3000)
        page.wait_for_timeout(random.randint(300, 600))
        human_click(page, cand)
        page.wait_for_timeout(int(random.uniform(*gap) * 1000))
        if waf_blocked(page):
            raise RuntimeError("出现滑块验证，已中止")
        return True
    print(f"  警告：未找到选项 {label}/{text}", flush=True)
    return False


def set_match_any(page, label: str) -> bool:
    """把某个筛选区块切到“有一个就行”（searchType=ONE）。"""
    item = section_item(page, label)
    cb = item.locator(".filter-item-checkbox").first
    if cb.count() == 0:
        return False
    cb.scroll_into_view_if_needed(timeout=3000)
    cb.hover()
    page.wait_for_timeout(700)
    opt = item.locator(".drop-item").filter(has_text="有一个就行")
    if opt.count() == 0:
        return False
    try:
        opt.first.click(timeout=4000)
    except Exception:
        return False
    page.wait_for_timeout(int(random.uniform(8, 11) * 1000))
    return True


def apply_price(page, low, high) -> None:
    inputs = page.locator('input[placeholder="最低值"], input[placeholder="最高值"]')
    if inputs.count() < 2:
        print("警告：未找到价格输入框", flush=True)
        return
    inputs.nth(0).scroll_into_view_if_needed()
    inputs.nth(0).click()
    inputs.nth(0).fill(str(low))
    inputs.nth(1).click()
    inputs.nth(1).fill(str(high))
    inputs.nth(1).press("Tab")
    page.wait_for_timeout(1200)
    inputs.nth(1).press("Enter")
    page.wait_for_timeout(4000)


def sort_newest(page) -> None:
    sorts = page.locator(".sort-item").filter(has_text="发布时间")
    if sorts.count() == 0:
        print("警告：未找到“发布时间”排序", flush=True)
        return
    try:
        sorts.first.click(timeout=4000)
        page.wait_for_timeout(4000)
    except Exception:
        print("警告：切换“发布时间”排序失败", flush=True)


# ---------- 抓取 ----------

def read_options(page) -> list[dict]:
    """采集页面上所有筛选分组的选项，供前端下拉使用。

    站点改了标签（新增/下架外观）时，下次抓取会自动同步，
    不需要改代码或手工维护枚举。
    """
    groups: list[dict] = []
    blocks = page.locator(".filter-item")
    for i in range(blocks.count()):
        block = blocks.nth(i)
        try:
            label_loc = block.locator(".filter-item-label-name").first
            if label_loc.count() == 0:
                continue
            category = label_loc.inner_text().strip()
            opts = block.locator(".opt-item")
            names: list[str] = []
            seen: set[str] = set()
            for j in range(opts.count()):
                try:
                    text = opts.nth(j).inner_text().strip()
                except Exception:
                    continue
                if text and text not in seen:
                    seen.add(text)
                    names.append(text)
            if category and names:
                groups.append({"category": category, "options": names})
        except Exception:
            continue
    return groups


def collect(config: dict[str, Any], profile_dir: Path, max_pages: int):
    captured: list[tuple[dict, dict]] = []  # (request_body, response_json)
    gap = config.get("clickGapSeconds") or [8, 11]

    def on_response(resp):
        if API_PAGE not in resp.url:
            return
        try:
            body = json.loads(resp.request.post_data or "{}")
            captured.append((body, resp.json()))
        except Exception:
            pass

    with sync_playwright() as p:
        ctx, page = open_page(p, profile_dir)
        page.on("response", on_response)
        page.goto(config["listUrl"], wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(4000)

        if not is_logged_in(page):
            ctx.close()
            raise NotLoggedInError(LOGIN_HINT)

        expand_panel(page)
        options = read_options(page)
        click_opt(page, "", config["region"], gap)

        for label, tags in config["sections"].items():
            for tag in tags:
                click_opt(page, label, tag, gap)
            if config.get("matchAny", True):
                set_match_any(page, label)
                page.wait_for_timeout(1500)

        apply_price(page, config["priceMin"], config["priceMax"])
        if config.get("sortByNewest"):
            sort_newest(page)
        page.wait_for_timeout(3000)

        # 找到最后一次完整筛选的响应
        final = None
        for body, data in reversed(captured):
            action = body.get("action") or {}
            if action.get("maxPrice") and len(
                action.get("goodsSearchActions") or []
            ) == len(config["sections"]):
                final = (body, data)
                break
        if final is None and captured:
            final = captured[-1]
        if final is None:
            ctx.close()
            raise RuntimeError("未捕获到列表接口响应，请稍后重试")

        records: dict[str, dict] = {}
        for rec in (final[1].get("data") or {}).get("records") or []:
            if rec.get("goodsNo"):
                records[rec["goodsNo"]] = rec
        signature = json.dumps(
            final[0].get("action") or {}, sort_keys=True, ensure_ascii=False
        )
        has_next = bool((final[1].get("data") or {}).get("exInfo", {}).get("next"))

        for _ in range(max(0, max_pages - 1)):
            if not has_next:
                break
            before = len(captured)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.mouse.wheel(0, 5000)
            page.wait_for_timeout(int(random.uniform(*gap) * 1000))
            if waf_blocked(page):
                print("翻页时出现滑块验证，停止翻页", flush=True)
                break
            new_batches = [
                x
                for x in captured[before:]
                if json.dumps(
                    (x[0].get("action") or {}), sort_keys=True, ensure_ascii=False
                )
                == signature
            ]
            if not new_batches:
                break
            for _, data in new_batches:
                for rec in (data.get("data") or {}).get("records") or []:
                    if rec.get("goodsNo"):
                        records[rec["goodsNo"]] = rec
            has_next = bool(
                (new_batches[-1][1].get("data") or {}).get("exInfo", {}).get("next")
            )

        chips = [config["region"], f"¥{config['priceMin']}-{config['priceMax']}"]
        for label, tags in config["sections"].items():
            chips.append(f"{label}:{'/'.join(tags)}")
        ctx.close()

    rows = []
    for rec in records.values():
        rows.append(
            {
                "goodsNo": rec.get("goodsNo"),
                "price": _to_price(rec.get("price")),
                "title": _clean_text(rec.get("title")),
                "server": rec.get("simpleMessage") or "",
                "labels": rec.get("sellingPointLabels") or [],
                "onStandTime": rec.get("onStandTime"),
                "createTime": rec.get("createTime"),
                "url": f"https://www.pzds.com/goodsDetails/{rec.get('goodsNo')}",
            }
        )
    rows.sort(key=lambda r: (r.get("createTime") or ""), reverse=True)
    return rows, chips, options


def _to_price(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(value) -> str:
    """去掉标题里的高亮 HTML 片段，避免表格里显示标签源码。"""
    return _TAG_RE.sub("", value or "").strip()


class PzdsCrawler(BaseCrawler):
    kind = "panzhi"
    label = "盼之代售"
    description = "pzds.com 账号列表，按区服/价格/外观标签筛选，需要登录态。"
    default_config = DEFAULT_CONFIG

    def _cfg(self) -> dict[str, Any]:
        cfg = {**self.config}
        gap = cfg.get("clickGapSeconds") or [8, 11]
        cfg["clickGapSeconds"] = [float(gap[0]), float(gap[1])]
        cfg["sections"] = cfg.get("sections") or {}
        return cfg

    def run(self, max_pages: int | None = None) -> CrawlResult:
        cfg = self._cfg()
        pages = max_pages or int(cfg.get("maxPages") or 1)
        try:
            rows, chips, option_groups = collect(cfg, self.profile_dir, pages)
        except NotLoggedInError as exc:
            raise CrawlError(str(exc)) from exc
        except RuntimeError as exc:
            raise CrawlError(f"{exc}（可在项目配置里把“点击间隔”调大，或稍后重试）") from exc

        items = [
            CrawlItem(
                goods_no=str(row["goodsNo"]),
                price=row["price"],
                title=row["title"],
                url=row["url"],
                extra={
                    "server": row["server"],
                    "labels": row["labels"],
                    "onStandTime": row["onStandTime"],
                    "createTime": row["createTime"],
                },
            )
            for row in rows
            if row.get("goodsNo")
        ]
        log = f"筛选条件: {' | '.join(chips)}\n抓取到 {len(items)} 个号"
        return CrawlResult(items=items, filters=chips, log=log, options=option_groups)

    def login(self, timeout_seconds: int = 300) -> tuple[bool, str]:
        return login_manual(self.profile_dir, self.config["listUrl"], timeout_seconds)

    def login_cli(self) -> int:
        return login_interactive(self.profile_dir, self.config["listUrl"])
