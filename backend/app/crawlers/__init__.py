"""爬虫通用契约（站点实现在 app/sites/<code>/ 下）。"""

from .base import BaseCrawler, CrawlError, CrawlItem, CrawlResult, ItemBase

__all__ = ["BaseCrawler", "CrawlError", "CrawlItem", "CrawlResult", "ItemBase"]
