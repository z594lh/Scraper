"""平台数据模型：监控项目与运行记录。

站点商品数据不在平台表里，而是各站点自己的数据表
（例如盼之的 panzhi_items_data，见 app/sites/<code>/models.py）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now()


class Project(Base):
    """一个监控项目 = 某个站点的一次具体抓取需求（如“盼之·浮生若梦”）。"""

    __tablename__ = "projects"
    __table_args__ = {"comment": "监控项目（站点实例）"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="主键"
    )
    site: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="站点编码（panzhi/crab…），决定数据表与表单",
    )
    slug: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="项目唯一标识，同时作为数据目录名",
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="项目名称")
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用（关闭后不参与定时抓取）"
    )
    config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="该站点的筛选配置"
    )
    schedule_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="定时抓取间隔（分钟，0=关闭）"
    )
    notify_channels: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="通知渠道列表（dingtalk/wecom）"
    )
    notify_rules: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="通知规则（新增条数阈值/执行失败/执行完成）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=now, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=now, onupdate=now, comment="更新时间"
    )

    runs: Mapped[list["Run"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Run(Base):
    """一次抓取运行记录（所有站点共用）。"""

    __tablename__ = "runs"
    __table_args__ = {"comment": "抓取运行记录"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="主键"
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目（projects.id）",
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="running", comment="运行状态：running/success/failed"
    )
    trigger: Mapped[str] = mapped_column(
        String(16), nullable=False, default="manual", comment="触发方式：manual/cli/schedule"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=now, comment="开始时间"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="结束时间"
    )
    total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="本次抓取条数"
    )
    new_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="本次新增条数"
    )
    message: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="失败原因或说明"
    )
    filters: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="本次生效的筛选条件"
    )
    log: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="运行日志")

    project: Mapped[Project] = relationship(back_populates="runs")
