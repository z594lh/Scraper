"""盼之代售（pzds）账号自动筛选。

站点用阿里云 WAF + wasm 签名保护列表接口，直接请求无法通过，
因此这里用本机 Chrome（patchright）打开真实页面，用界面点击的方式应用筛选，
再读取页面自身的接口响应。已验证：两次点击间隔约 10 秒不会被滑块拦截。

用法：
    python pzds.py login          # 首次：扫码登录，登录态保存在 .profile/
    python pzds.py run            # 按 config.json 筛选并输出
    python pzds.py run --pages 1  # 指定最多翻页数
"""

import argparse
import json
import os
import random
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from patchright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / ".profile"
CONFIG_PATH = ROOT / "config.json"
STATE_PATH = ROOT / "state.json"
RESULTS_DIR = ROOT / "results"
API_PAGE = "goodsPublic/page"


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def open_page(p, cfg=None):
    # 默认用本机 Chrome 通道；虚拟机等环境可用 PZDS_CHROME 指定浏览器路径，
    # 避免影响系统默认浏览器（channel 与 executable_path 不能同时给）。
    exe = os.environ.get("PZDS_CHROME") or (cfg or {}).get("chromeExecutable")

    def launch(extra):
        opts = dict(
            headless=False,  # headless 会被 WAF 拦截
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            viewport={"width": 1440, "height": 960},
        )
        opts.update(extra)
        ctx = p.chromium.launch_persistent_context(str(PROFILE), **opts)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(15000)
        return ctx, page

    if exe:
        return launch({"executable_path": exe})
    try:
        return launch({"channel": "chrome"})
    except Exception:
        # 没有标准安装路径的 Chrome 时，回退到系统可执行文件
        fallback = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium")
        if not fallback:
            raise
        return launch({"executable_path": fallback})


def is_logged_in(page):
    if "/login" in page.url:
        return False
    return page.get_by_text("登录/注册").count() == 0


def click_visible_text(page, text):
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


def first_visible(page, selector):
    loc = page.locator(selector)
    for i in range(loc.count()):
        item = loc.nth(i)
        try:
            if item.is_visible():
                return item
        except Exception:
            continue
    return None


def check_agreement(page):
    """勾选“服务协议”复选框（element-ui 原生 input 隐藏，需点可视区域）。"""
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


def wait_login(page, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline and not is_logged_in(page):
        time.sleep(2)
    return is_logged_in(page)


def do_login(cfg):
    """终端交互式手机验证码登录（虚拟机无显示器时使用）。"""
    with sync_playwright() as p:
        ctx, page = open_page(p, cfg)
        page.goto(cfg["listUrl"], wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(3000)
        if is_logged_in(page):
            print("已处于登录状态，无需重复登录。", flush=True)
            ctx.close()
            return 0

        try:
            page.get_by_text("登录/注册").first.click(timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(2500)

        phone_input = first_visible(page, 'input[placeholder="请输入手机号"]')
        if phone_input:
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
            msgs = page.evaluate("""() => Array.from(document.querySelectorAll('.el-message, .el-message__content, [class*=toast], [role=alert]')).map(e => (e.innerText||'').trim()).filter(Boolean).slice(0,5)""")
            if msgs:
                print("页面提示:", msgs, flush=True)
            page.screenshot(path=str(ROOT / "login_after.png"))
            page.wait_for_timeout(3000)
            ok = wait_login(page, 60)
            if not ok and waf_blocked(page):
                page.screenshot(path=str(ROOT / "login_blocked.png"))
                print("出现滑块验证，截图已存 login_blocked.png，请稍后重试。", flush=True)
                ctx.close()
                return 1
            print("登录成功，登录态已保存。" if ok else "登录未成功，请重新执行 login。", flush=True)
            ctx.close()
            return 0 if ok else 1

        print("未识别到验证码登录表单，请在浏览器窗口内手动完成登录…", flush=True)
        ok = wait_login(page, 600)
        print("登录成功，登录态已保存。" if ok else "等待登录超时。", flush=True)
        ctx.close()
        return 0 if ok else 1


# ---------- 页面操作 ----------

def section_item(page, label):
    if not label:
        return page.locator(".filter-item").first
    return page.locator(".filter-item").filter(
        has=page.locator(".filter-item-label-name", has_text=label)
    ).first


def human_click(page, loc):
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


def expand_panel(page):
    for i in range(page.get_by_text("展开", exact=True).count()):
        try:
            page.get_by_text("展开", exact=True).nth(i).click(timeout=2000)
            page.wait_for_timeout(500)
        except Exception:
            pass
    page.wait_for_timeout(800)


def waf_blocked(page):
    return page.locator("#waf_nc_block").count() > 0


def click_opt(page, label, text, gap):
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


def set_match_any(page, label):
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


def apply_price(page, low, high):
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


def sort_newest(page):
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

def collect(cfg, max_pages):
    captured = []  # (request_body, response_json)
    gap = cfg.get("clickGapSeconds") or [8, 11]

    def on_response(resp):
        if API_PAGE not in resp.url:
            return
        try:
            body = json.loads(resp.request.post_data or "{}")
            captured.append((body, resp.json()))
        except Exception:
            pass

    with sync_playwright() as p:
        ctx, page = open_page(p, cfg)
        page.on("response", on_response)
        page.goto(cfg["listUrl"], wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(4000)

        if not is_logged_in(page):
            ctx.close()
            print("登录态无效，请先执行: python pzds.py login", flush=True)
            return None

        expand_panel(page)
        click_opt(page, "", cfg["region"], gap)

        for label, tags in cfg["sections"].items():
            for tag in tags:
                click_opt(page, label, tag, gap)
            if cfg.get("matchAny", True):
                set_match_any(page, label)
                page.wait_for_timeout(1500)

        apply_price(page, cfg["priceMin"], cfg["priceMax"])
        if cfg.get("sortByNewest"):
            sort_newest(page)
        page.wait_for_timeout(3000)

        # 找到最后一次完整筛选的响应
        final = None
        for body, data in reversed(captured):
            action = body.get("action") or {}
            if action.get("maxPrice") and len(action.get("goodsSearchActions") or []) == len(cfg["sections"]):
                final = (body, data)
                break
        if final is None and captured:
            final = captured[-1]
        if final is None:
            ctx.close()
            print("未捕获到列表接口响应", flush=True)
            return None

        records = {}
        for rec in (final[1].get("data") or {}).get("records") or []:
            if rec.get("goodsNo"):
                records[rec["goodsNo"]] = rec
        signature = json.dumps(final[0].get("action") or {}, sort_keys=True, ensure_ascii=False)
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
            new_batches = [x for x in captured[before:]
                           if json.dumps((x[0].get("action") or {}), sort_keys=True, ensure_ascii=False) == signature]
            if not new_batches:
                break
            for _, data in new_batches:
                for rec in (data.get("data") or {}).get("records") or []:
                    if rec.get("goodsNo"):
                        records[rec["goodsNo"]] = rec
            has_next = bool((new_batches[-1][1].get("data") or {}).get("exInfo", {}).get("next"))

        chips = [cfg["region"], f"¥{cfg['priceMin']}-{cfg['priceMax']}"]
        for label, tags in cfg["sections"].items():
            chips.append(f"{label}:{'/'.join(tags)}")
        ctx.close()

    rows = []
    for rec in records.values():
        rows.append({
            "goodsNo": rec.get("goodsNo"),
            "price": rec.get("price"),
            "title": (rec.get("title") or "").strip(),
            "server": rec.get("simpleMessage"),
            "labels": rec.get("sellingPointLabels") or [],
            "onStandTime": rec.get("onStandTime"),
            "createTime": rec.get("createTime"),
            "url": f"https://www.pzds.com/goodsDetail/{rec.get('goodsNo')}/6",
        })
    rows.sort(key=lambda r: (r.get("createTime") or ""), reverse=True)
    return rows, chips


def mark_new(rows):
    """返回 (new_ids, first_run)。首次运行只建立基线，不标记 NEW。"""
    seen = {}
    first_run = not STATE_PATH.exists()
    if not first_run:
        try:
            seen = json.loads(STATE_PATH.read_text(encoding="utf-8")).get("seen", {})
        except Exception:
            seen = {}
    now = datetime.now().isoformat(timespec="seconds")
    fresh = set()
    for row in rows:
        if row["goodsNo"] not in seen:
            if not first_run:
                fresh.add(row["goodsNo"])
            seen[row["goodsNo"]] = now
    STATE_PATH.write_text(json.dumps({"seen": seen}, ensure_ascii=False, indent=1), encoding="utf-8")
    return fresh, first_run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["login", "run"])
    parser.add_argument("--pages", type=int, default=None)
    args = parser.parse_args()

    cfg = load_config()
    if args.command == "login":
        sys.exit(do_login(cfg))

    try:
        result = collect(cfg, args.pages or cfg.get("maxPages", 1))
    except RuntimeError as e:
        print(f"已停止：{e}。请稍后重试，或把 config.json 的 clickGapSeconds 调大。", flush=True)
        sys.exit(3)
    if result is None:
        sys.exit(2)

    rows, chips = result
    fresh, first_run = mark_new(rows)

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / ("match_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
    out.write_text(json.dumps({"filters": chips, "items": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"共 {len(rows)} 个号，结果已写入 {out}", flush=True)
    if first_run:
        print("首次运行：已把当前结果记为基线，下次运行起会标记 NEW。", flush=True)
    for row in rows:
        flag = "NEW " if row["goodsNo"] in fresh else "    "
        print(f"{flag}¥{row['price']:<7} {row['goodsNo']}  {row['server']}  {row['title'][:40]}", flush=True)


if __name__ == "__main__":
    main()
