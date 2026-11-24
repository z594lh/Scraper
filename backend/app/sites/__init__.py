"""站点插件包：每个站点一个子包，彼此隔离。"""

from .registry import SITES, build_crawler, get_site, list_sites, workdir_of

__all__ = ["SITES", "build_crawler", "get_site", "list_sites", "workdir_of"]
