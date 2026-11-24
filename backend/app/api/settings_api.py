from __future__ import annotations

import os
import platform
import shutil
import sys

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.envfile import env_path, update_env
from ..core.settings import FRONTEND_DIST, PROJECTS_DIR, ROOT, settings
from ..notify import NotifyError, mask_secret, mask_webhook, send_dingtalk, send_wecom

router = APIRouter(prefix="/api/settings", tags=["settings"])


class NotifyUpdate(BaseModel):
    notifyEnabled: bool | None = None
    dingtalkWebhook: str | None = None
    dingtalkSecret: str | None = None
    wecomWebhook: str | None = None
    pzdsChrome: str | None = None


class TestPayload(BaseModel):
    channel: str


@router.get("")
def read_settings():
    return {
        "envFile": str(env_path()),
        "notifyEnabled": settings.notify_enabled,
        "schedulerEnabled": settings.scheduler_enabled,
        "dingtalk": {
            "configured": bool(settings.dingtalk_webhook),
            "masked": mask_webhook(settings.dingtalk_webhook),
        },
        "dingtalkSecret": {
            "configured": bool(settings.dingtalk_secret),
            "masked": mask_secret(settings.dingtalk_secret),
        },
        "wecom": {
            "configured": bool(settings.wecom_webhook),
            "masked": mask_webhook(settings.wecom_webhook),
        },
        "pzdsChrome": settings.pzds_chrome,
    }


@router.put("")
def save_settings(payload: NotifyUpdate):
    updates: dict[str, str] = {}
    if payload.notifyEnabled is not None:
        updates["NOTIFY_ENABLED"] = "true" if payload.notifyEnabled else "false"
        settings.notify_enabled = payload.notifyEnabled
    if payload.dingtalkWebhook is not None:
        updates["DINGTALK_WEBHOOK"] = payload.dingtalkWebhook.strip()
        settings.dingtalk_webhook = payload.dingtalkWebhook.strip()
    if payload.dingtalkSecret is not None:
        updates["DINGTALK_SECRET"] = payload.dingtalkSecret.strip()
        settings.dingtalk_secret = payload.dingtalkSecret.strip()
    if payload.wecomWebhook is not None:
        updates["WECOM_WEBHOOK"] = payload.wecomWebhook.strip()
        settings.wecom_webhook = payload.wecomWebhook.strip()
    if payload.pzdsChrome is not None:
        updates["PZDS_CHROME"] = payload.pzdsChrome.strip()
        settings.pzds_chrome = payload.pzdsChrome.strip()
        if settings.pzds_chrome:
            os.environ["PZDS_CHROME"] = settings.pzds_chrome
        else:
            os.environ.pop("PZDS_CHROME", None)
    update_env(updates)
    return read_settings()


@router.post("/notify/test")
def test_notify(payload: TestPayload):
    text = "### 监控台测试消息\n如果你看到这条消息，说明通知渠道配置成功。"
    try:
        if payload.channel == "dingtalk":
            send_dingtalk("监控台测试消息", text)
        elif payload.channel == "wecom":
            send_wecom("监控台测试消息", text)
        else:
            raise HTTPException(400, f"未知渠道: {payload.channel}")
    except NotifyError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "message": "已发送"}


@router.get("/system")
def system_info():
    chrome = settings.pzds_chrome or shutil.which("google-chrome") or shutil.which("chrome") or ""
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "root": str(ROOT),
        "projectsDir": str(PROJECTS_DIR),
        "database": settings.db_label(),
        "chrome": chrome or "本机 Chrome 通道（channel=chrome）",
        "frontendBuilt": FRONTEND_DIST.exists(),
        "envFile": str(env_path()),
    }
