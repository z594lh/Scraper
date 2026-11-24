"""通知渠道：钉钉、企业微信。敏感信息全部来自 .env。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse
from typing import Iterable

import httpx

from .core.settings import settings


class NotifyError(RuntimeError):
    pass


# 通知规则：新增数据（阈值）、执行失败、每次执行完成
DEFAULT_NOTIFY_RULES: dict = {
    "newItems": {"enabled": True, "threshold": 1},
    "runFailed": {"enabled": True},
    "runFinished": {"enabled": False},
}


def normalize_rules(rules: dict | None) -> dict:
    """合并默认值并做类型兜底，供接口与执行器共用。"""
    data = rules if isinstance(rules, dict) else {}
    new_items = data.get("newItems") if isinstance(data.get("newItems"), dict) else {}
    failed = data.get("runFailed") if isinstance(data.get("runFailed"), dict) else {}
    finished = data.get("runFinished") if isinstance(data.get("runFinished"), dict) else {}
    try:
        threshold = max(1, int(new_items.get("threshold", 1)))
    except (TypeError, ValueError):
        threshold = 1
    return {
        "newItems": {
            "enabled": bool(new_items.get("enabled", True)),
            "threshold": threshold,
        },
        "runFailed": {"enabled": bool(failed.get("enabled", True))},
        "runFinished": {"enabled": bool(finished.get("enabled", False))},
    }


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def mask_webhook(value: str) -> str:
    """webhook 只返回尾部片段，避免前端拿到完整 token。"""
    if not value:
        return ""
    tail = value[-6:] if len(value) > 6 else value
    return f"****{tail}"


def _dingtalk_url(webhook: str, secret: str) -> str:
    if not secret:
        return webhook
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest))
    sep = "&" if "?" in webhook else "?"
    return f"{webhook}{sep}timestamp={timestamp}&sign={sign}"


def _post(url: str, payload: dict) -> dict:
    try:
        resp = httpx.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # 网络/解析异常统一转成可读错误
        raise NotifyError(f"请求失败: {exc}") from exc
    if data.get("errcode") not in (0, None):
        raise NotifyError(f"{data.get('errcode')}: {data.get('errmsg')}")
    return data


def send_dingtalk(title: str, text: str, webhook: str = "", secret: str = "") -> None:
    webhook = webhook or settings.dingtalk_webhook
    secret = secret or settings.dingtalk_secret
    if not webhook:
        raise NotifyError("未配置 DINGTALK_WEBHOOK")
    _post(
        _dingtalk_url(webhook, secret),
        {"msgtype": "markdown", "markdown": {"title": title, "text": text}},
    )


def send_wecom(title: str, text: str, webhook: str = "") -> None:
    webhook = webhook or settings.wecom_webhook
    if not webhook:
        raise NotifyError("未配置 WECOM_WEBHOOK")
    _post(webhook, {"msgtype": "markdown", "markdown": {"content": text}})


def send_to(channels: Iterable[str], title: str, text: str) -> list[dict]:
    """按渠道发送，返回每个渠道的结果，单渠道失败不影响其他渠道。"""
    results: list[dict] = []
    if not settings.notify_enabled:
        return [{"channel": "all", "ok": False, "message": "通知已关闭（NOTIFY_ENABLED=false）"}]
    for channel in channels:
        try:
            if channel == "dingtalk":
                send_dingtalk(title, text)
            elif channel == "wecom":
                send_wecom(title, text)
            else:
                raise NotifyError(f"未知渠道: {channel}")
            results.append({"channel": channel, "ok": True, "message": "ok"})
        except NotifyError as exc:
            results.append({"channel": channel, "ok": False, "message": str(exc)})
    return results


def build_new_items_message(project_name: str, items: list, limit: int = 10) -> tuple[str, str]:
    """生成“有新上架”通知内容。"""
    title = f"{project_name} 新上架 {len(items)} 个"
    lines = [f"### {title}"]
    for item in items[:limit]:
        price = f"¥{item.price:.0f}" if item.price is not None else "价格未知"
        desc = " ".join(
            x for x in [getattr(item, "server_name", ""), item.title] if x
        )
        lines.append(f"- {price} **{item.goods_no}** {desc}")
        if item.url:
            lines.append(f"  [查看详情]({item.url})")
    if len(items) > limit:
        lines.append(f"- 其余 {len(items) - limit} 个请打开监控台查看")
    return title, "\n".join(lines)
