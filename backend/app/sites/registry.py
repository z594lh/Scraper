"""站点注册表：新增站点在这里登记一行，表结构/表单/看板自动生效。"""

from __future__ import annotations

from pathlib import Path

from ..core.settings import PROJECTS_DIR
from ..crawlers.base import CrawlError
from .panzhi import SITE as PANZHI

SITES = {site.code: site for site in (PANZHI,)}


def get_site(code: str):
    site = SITES.get(code)
    if site is None:
        raise CrawlError(f"未注册的站点: {code}")
    return site


def list_sites() -> list[dict]:
    return [site.to_dict() for site in SITES.values()]


def build_crawler(site_code: str, config: dict, slug: str):
    site = get_site(site_code)
    return site.crawler(config, PROJECTS_DIR / slug)


def workdir_of(slug: str) -> Path:
    return PROJECTS_DIR / slug
