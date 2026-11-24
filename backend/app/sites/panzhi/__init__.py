"""盼之站点包：数据表、配置 Schema、看板列、爬虫实现。"""

from ..spec import SiteSpec
from .columns import COLUMNS, serialize
from .config import CONFIG_SCHEMA, DEFAULT_CONFIG
from .crawler import PzdsCrawler
from .models import PanzhiItem, PanzhiOption

SITE = SiteSpec(
    code="panzhi",
    label="盼之代售",
    description="pzds.com 账号列表，按区服/价格/外观标签筛选，需要登录态。",
    table=PanzhiItem.__tablename__,
    crawler=PzdsCrawler,
    item_model=PanzhiItem,
    default_config=DEFAULT_CONFIG,
    config_schema=CONFIG_SCHEMA,
    columns=COLUMNS,
    serialize=serialize,
    option_model=PanzhiOption,
)

__all__ = ["SITE", "PanzhiItem", "PzdsCrawler"]
