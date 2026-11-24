"""盼之数据看板的列定义与序列化（前端按 columns 渲染表格）。"""

from __future__ import annotations

from typing import Any

from ...common.timeutil import iso
from .models import PanzhiItem

COLUMNS: list[dict[str, Any]] = [
    {"key": "goodsNo", "title": "编号", "width": 110, "type": "code"},
    {"key": "price", "title": "价格", "width": 92, "type": "price", "sortable": True},
    {"key": "serverName", "title": "区服", "width": 150, "type": "text", "ellipsis": True},
    {"key": "title", "title": "标题", "type": "text", "ellipsis": True},
    {"key": "labels", "title": "标签", "width": 220, "type": "tags"},
    {"key": "onStandTime", "title": "上架时间", "width": 125, "type": "datetime"},
    {"key": "firstSeenAt", "title": "首次发现", "width": 125, "type": "datetime"},
    {"key": "url", "title": "详情", "width": 70, "type": "link"},
]


def serialize(item: PanzhiItem) -> dict[str, Any]:
    return {
        "goodsNo": item.goods_no,
        "price": item.price,
        "title": item.title,
        "serverName": item.server_name,
        "labels": item.labels or [],
        "onStandTime": iso(item.on_stand_time),
        "createTime": iso(item.create_time),
        "firstSeenAt": iso(item.first_seen_at),
        "lastSeenAt": iso(item.last_seen_at),
        "isNew": item.is_new,
        "active": item.active,
        "url": item.url,
    }
