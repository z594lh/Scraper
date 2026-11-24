"""把环境变量写入 .env（保留注释与顺序），供设置页保存敏感信息。"""

from __future__ import annotations

from pathlib import Path

from .settings import ENV_PATH


def _encode(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def update_env(updates: dict[str, str]) -> None:
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    pending = dict(updates)
    result: list[str] = []
    for line in lines:
        key = None
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
        if key in pending:
            result.append(f"{key}={_encode(pending.pop(key))}")
        else:
            result.append(line)
    for key, value in pending.items():
        result.append(f"{key}={_encode(value)}")

    ENV_PATH.write_text("\n".join(result) + "\n", encoding="utf-8")


def env_path() -> Path:
    return ENV_PATH
