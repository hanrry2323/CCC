"""Crawler base classes and configuration for clawmed-ccc.

* :class:`CrawlerConfig` — 平台级配置 dataclass
* :class:`BaseCrawler` — 所有爬虫子类的抽象基类

统一入口 :meth:`BaseCrawler.run` 完成：
    加载凭证 → 登录 → 爬取 → 抽取 → 返回数据行列表
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CrawlerConfig:
    """平台级 Crawler 配置。"""

    name: str
    site_url: str
    required_fields: List[str] = field(default_factory=list)
    key_fields: List[str] = field(default_factory=list)
    engine: str = "requests"
    timeout: float = 30.0


class BaseCrawler(ABC):
    """Crawler 抽象基类。

    子类必须实现:
        - :meth:`login`        登录
        - :meth:`crawl`        抓取原始数据
        - :meth:`extract`      抽取数据行
        - :meth:`_load_credential` 加载凭证

    统一入口 :meth:`run` 串联全流程。
    """

    config: CrawlerConfig

    @abstractmethod
    def _load_credential(self) -> Dict[str, Any]:
        """加载平台凭证,返回 dict (如 user/pass/token 等)。"""

    @abstractmethod
    def login(self, credential: Dict[str, Any]) -> bool:
        """使用凭证登录,成功返回 True。"""

    @abstractmethod
    def crawl(self) -> Any:
        """爬取原始数据,实现层可自由返回 (list/dict/str/bytes)。"""

    @abstractmethod
    def extract(self, raw: Any) -> List[Dict[str, Any]]:
        """把原始数据抽取为规范化的数据行列表 (每行是 dict)。"""

    def run(self) -> List[Dict[str, Any]]:
        """平台统一入口:加载凭证 → 登录 → 爬取 → 抽取。"""
        credential = self._load_credential()
        if not self.login(credential):
            raise RuntimeError(f"[{self.config.name}] login failed")
        raw = self.crawl()
        return self.extract(raw)
