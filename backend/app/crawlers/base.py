"""爬虫契约：站点爬虫继承 BaseCrawler，站点数据表继承 ItemBase。

分层约定：
- 平台层负责：项目/运行记录、调度、入库（NEW 判定）、通知、静态页面；
- 站点层只负责：怎么打开页面拿到数据、自己的表结构、自己的表单与看板列。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from ..core.settings import DATA_DIR
from ..db import Base


class CrawlError(RuntimeError):
    """抓取失败（可预期，例如登录态失效、被风控拦截）。"""


@dataclass
class CrawlItem:
    """一条抓取结果。

    站点私有字段统一放 extra，由站点表的 apply_crawl() 解释，
    这样平台层的入库逻辑不需要认识任何站点字段。
    """

    goods_no: str
    price: float | None = None
    title: str = ""
    url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawlResult:
    items: list[CrawlItem]
    filters: list[str] = field(default_factory=list)
    log: str = ""
    # 站点筛选枚举：[{"category": "珍品外观", "options": ["踏夜尊", ...]}, ...]
    options: list[dict[str, Any]] = field(default_factory=list)


class ItemBase(Base):
    """站点数据表公共列（本身不建表），子类只需追加自己的业务列。"""

    __abstract__ = True

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="主键"
    )
    project_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="所属监控项目（projects.id）"
    )
    goods_no: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="站点商品编号"
    )
    price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="售价（元）")
    title: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", comment="商品标题"
    )
    url: Mapped[str] = mapped_column(
        String(512), nullable=False, default="", comment="详情页链接"
    )
    raw: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="原始数据快照，便于后续加字段回填"
    )
    is_new: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True, comment="是否本次抓取新增"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True, comment="当前是否在售"
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="首次抓到时间"
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="最近一次抓到时间"
    )
    last_run_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="最近命中的运行记录（runs.id）"
    )

    def apply_crawl(self, data: CrawlItem) -> None:
        """把抓取结果写到本行；站点表覆盖此方法补充私有字段。"""
        self.price = data.price
        self.title = data.title
        self.url = data.url
        self.raw = data.extra or None


class BaseCrawler:
    kind: ClassVar[str] = ""
    label: ClassVar[str] = ""
    description: ClassVar[str] = ""
    default_config: ClassVar[dict[str, Any]] = {}

    def __init__(self, config: dict[str, Any], workdir: Path):
        self.config = {**self.default_config, **(config or {})}
        self.workdir = workdir
        self.workdir.mkdir(parents=True, exist_ok=True)

    @property
    def profile_dir(self) -> Path:
        """浏览器指纹目录；配置了 profileDir 则以其为准（相对路径基于 data/）。"""
        custom = self.config.get("profileDir")
        if custom:
            path = Path(custom)
            return path if path.is_absolute() else DATA_DIR / path
        return self.workdir / "profile"

    def run(self, max_pages: int | None = None) -> CrawlResult:
        raise NotImplementedError

    def login(self, timeout_seconds: int = 300) -> tuple[bool, str]:
        raise CrawlError(f"{self.label} 暂不支持网页端登录")

    def login_cli(self) -> int:
        """终端交互式登录，供无显示器环境使用。返回进程退出码。"""
        raise CrawlError(f"{self.label} 暂不支持终端登录")
