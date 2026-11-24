"""站点接入契约：新增一个站点 = 新增一个 sites/<code>/ 包并登记到 registry。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..crawlers.base import BaseCrawler, ItemBase


@dataclass(frozen=True)
class SiteSpec:
    """一个站点（业务线）的全部元信息。

    code        站点编码，同时作为数据表前缀，例如 panzhi -> panzhi_items_data
    item_model  站点私有数据表模型（继承 ItemBase）
    config_schema 前端据此渲染「新建项目 / 项目配置」表单
    columns     前端据此渲染数据看板表格
    serialize   把站点数据行转成前端 JSON
    """

    code: str
    label: str
    description: str
    table: str
    crawler: type[BaseCrawler]
    item_model: type[ItemBase]
    default_config: dict[str, Any]
    config_schema: list[dict[str, Any]]
    columns: list[dict[str, Any]]
    serialize: Callable[[Any], dict[str, Any]]
    option_model: type | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "description": self.description,
            "table": self.table,
            "defaultConfig": self.default_config,
            "configSchema": self.config_schema,
            "columns": self.columns,
        }
