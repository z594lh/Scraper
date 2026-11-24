"""盼之商品数据表：panzhi_items_data。

表名以站点编码开头，与其他站点的表完全隔离；
公共列来自 ItemBase，这里只放盼之特有的业务列。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from ...common.timeutil import parse_dt
from ...crawlers.base import CrawlItem, ItemBase
from ...db import Base


class PanzhiItem(ItemBase):
    __tablename__ = "panzhi_items_data"
    __table_args__ = (
        UniqueConstraint("project_id", "goods_no", name="uq_panzhi_project_goods"),
        {"comment": "盼之代售商品数据（站点私有表）"},
    )

    server_name: Mapped[str] = mapped_column(
        String(128), nullable=False, default="", comment="区服（如：浮生若梦）"
    )
    labels: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="外观标签列表")
    on_stand_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="上架时间"
    )
    create_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="商品创建时间"
    )

    def apply_crawl(self, data: CrawlItem) -> None:
        super().apply_crawl(data)
        self.server_name = str(data.extra.get("server") or "")
        self.labels = data.extra.get("labels") or []
        self.on_stand_time = parse_dt(data.extra.get("onStandTime"))
        self.create_time = parse_dt(data.extra.get("createTime"))


class PanzhiOption(Base):
    """盼之筛选项枚举：每次抓取顺手采集，前端下拉从这里读。

    这样站点新增的外观标签（如“曜日尊”）会自动出现在配置里，
    不用改代码或手工维护常量。
    """

    __tablename__ = "panzhi_options_data"
    __table_args__ = (
        UniqueConstraint("category", "label", name="uq_panzhi_option"),
        {"comment": "盼之筛选项枚举（抓取时同步）"},
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="主键"
    )
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="筛选分组（如：珍品外观/载具飞剑/区服）"
    )
    label: Mapped[str] = mapped_column(String(128), nullable=False, comment="选项文字")
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="站点展示顺序"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="最近一次抓取是否仍存在"
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="首次采集时间"
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="最近采集时间"
    )
