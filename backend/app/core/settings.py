"""全局配置：路径、数据库与 .env 敏感信息。

约定：
- 仓库根目录 = backend/ 与 frontend/ 所在目录。
- backend/data/projects/<slug>/profile  每个项目独立的浏览器指纹
- .env  数据库口令、webhook 等敏感信息，不入库、不进前端明文
"""

from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = ROOT / "backend"
DATA_DIR = BACKEND_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
ENV_PATH = ROOT / ".env"
FRONTEND_DIST = ROOT / "frontend" / "dist"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH), env_file_encoding="utf-8", extra="ignore"
    )

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"
    scheduler_enabled: bool = True

    # MySQL
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "root"
    db_name: str = "scraper"
    database_url: str = ""

    # 通知渠道（敏感信息只从 .env 读取）
    notify_enabled: bool = True
    dingtalk_webhook: str = ""
    dingtalk_secret: str = ""
    wecom_webhook: str = ""

    # 浏览器可执行文件（虚拟机用），留空则用本机 Chrome 通道
    pzds_chrome: str = ""

    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{quote_plus(self.db_user)}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    def db_label(self) -> str:
        return f"{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()
