"""
Sichuan price crawler adapter.
Packaged as BaseCrawler subclass for clawmed-ccc.
"""

from crawlers.base import BaseCrawler, CrawlerConfig
from typing import List, Dict, Any, Optional
import os
import json
import logging


class SichuanCrawler(BaseCrawler):
    """
    Sichuan medical equipment procurement center price crawler.
    Supports dry-run and real mode.
    """

    def __init__(self):
        self.config = CrawlerConfig(name="sichuan", site_url="https://ggfw.scyb.org.cn")

    def _load_credential(self) -> Dict[str, Any]:
        """
        Try to load credentials from ~/.ccc/credentials/sichuan-001.json.
        If not found, return empty dict to trigger dry-run mode.
        """
        logging.basicConfig(level=logging.INFO)
        cred_path = os.path.expanduser("~/.ccc/credentials/sichuan-001.json")
        if os.path.exists(cred_path):
            try:
                with open(cred_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load credentials: {e}")
        return {}

    def login(self, credential: Optional[Dict] = None) -> bool:
        """
        Login to Sichuan system.
        In dry-run mode, return True immediately.
        In real mode, validate credential contains valid base_url.
        """
        if os.environ.get("CRAWLER_DRY_RUN", "1") == "1":
            return True

        if not credential or "base_url" not in credential:
            raise ValueError("Missing base_url in credential for real mode")
        return True

    def crawl(self, credential: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Crawl Sichuan medical equipment procurement center.
        Returns price list for items.
        """
        dry_run = os.environ.get("CRAWLER_DRY_RUN", "1") == "1"

        if dry_run:
            return self._crawl_dry_run()

        try:
            token = credential.get("token", "")
            data = self._fetch_price_data(token=token)
            return self._extract_price_records(data)
        except Exception as e:
            logging.error(f"Real-mode crawl failed: {e}")
            raise

    def _crawl_dry_run(self) -> List[Dict[str, Any]]:
        """
        Return hardcoded mock data for dry-run validation.
        """
        logging.basicConfig(level=logging.INFO)
        return [
            {
                "name": "阿司匹林肠溶片",
                "spec": "100mg*30片",
                "manufacturer": "AdBlue制药",
                "price": 18.50,
                "unit": "盒",
                "update_time": "2026-07-15",
            },
            {
                "name": "氨氯地平苯磺酸钙",
                "spec": "5mg*7片",
                "manufacturer": "Red Moon Pharma",
                "price": 32.80,
                "unit": "板",
                "update_time": "2026-07-16",
            },
            {
                "name": "阿莫西林胶囊",
                "spec": "0.25g*24粒",
                "manufacturer": "BlueVital",
                "price": 12.60,
                "unit": "板",
                "update_time": "2026-07-14",
            },
        ]

    def _fetch_price_data(self, token: str) -> List[Dict[str, Any]]:
        """
        Real API call to fetch price data from Sichuan system.
        Simplified version of qx fetch_price_data.
        """
        import requests

        url = "https://ggfw.scyb.org.cn/api/procurement/search"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        params = {"query_type": "medication", "limit": 10}

        response = requests.post(url, headers=headers, json=params, timeout=30)
        response.raise_for_status()
        return response.json().get("data", [])

    def _extract_price_records(
        self, api_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Normalize API response to standardized crawler fields.
        """
        records = []
        for item in api_data:
            record = {
                "product_name": item.get("name", ""),
                "spec": item.get("spec", ""),
                "manufacturer": item.get("manufacturer", ""),
                "reference_price": item.get("price", 0.0),
                "unit": item.get("unit", ""),
                "last_updated": item.get("update_time", ""),
            }
            records.append(record)
        return records

    def extract(self, raw):
        """
        Entry point for external usage to extract records from raw data.
        Delegates to internal _extract_price_records method.
        """
        return self._extract_price_records(raw)
