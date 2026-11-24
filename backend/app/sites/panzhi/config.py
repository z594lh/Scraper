"""盼之站点的默认配置与表单 Schema（前端据此生成配置表单）。"""

from __future__ import annotations

from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "gameId": 63,
    "goodsCatalogueId": 6,
    "listUrl": "https://www.pzds.com/goodsList/63/6?goodsCatalogueId=6",
    "region": "浮生若梦",
    "priceMin": 0,
    "priceMax": 1000,
    "sections": {
        "珍品外观": [
            "白泽·太霄雷狩",
            "沧溟·太霄雷狩",
            "金辉驰梦",
            "天鹿引虹",
            "千星落纱",
            "焚天执衡",
        ],
        "载具飞剑": [
            "玄穹御风",
            "玄穹引霆",
            "南溟掠影",
            "沧海浮光",
            "绯月瑶",
            "踏夜尊",
        ],
    },
    "matchAny": True,
    "sortByNewest": True,
    "maxPages": 2,
    "clickGapSeconds": [8, 11],
}

# 表单 Schema：type 支持 text / number / switch / range / select / tags
CONFIG_SCHEMA: list[dict[str, Any]] = [
    {
        "group": "基础",
        "items": [
            {
                "key": "region",
                "label": "区服",
                "type": "text",
                "required": True,
                "help": "需与站点筛选项文字完全一致",
            },
            {"key": "listUrl", "label": "列表页地址", "type": "text", "required": True},
            {"key": "gameId", "label": "gameId", "type": "number"},
            {"key": "goodsCatalogueId", "label": "goodsCatalogueId", "type": "number"},
        ],
    },
    {
        "group": "筛选",
        "items": [
            {"key": "priceMin", "label": "最低价（元）", "type": "number"},
            {"key": "priceMax", "label": "最高价（元）", "type": "number"},
            {
                "key": "sections",
                "label": "外观标签",
                "type": "tags",
                "help": "按分组填写标签，命中任一即可",
            },
            {"key": "matchAny", "label": "同组标签命中任一", "type": "switch"},
            {"key": "sortByNewest", "label": "按发布时间排序", "type": "switch"},
            {"key": "maxPages", "label": "最多翻页数", "type": "number"},
        ],
    },
    {
        "group": "高级",
        "items": [
            {
                "key": "clickGapSeconds",
                "label": "点击间隔（秒）",
                "type": "range",
                "help": "间隔越小越容易被滑块拦截",
            },
            {
                "key": "profileDir",
                "label": "指纹目录",
                "type": "text",
                "placeholder": "留空使用 backend/data/projects/<slug>/profile",
            },
        ],
    },
]
