"""Sichuan drug price crawler."""

from crawlers.base import BaseCrawler, CrawlerConfig
from typing import List, Dict, Any
import os
import json


class SichuanCrawler(BaseCrawler):
    """Sichuan drug price information crawler."""

    config = CrawlerConfig(name="sichuan", site_url="https://ggfw.scyb.org.cn")

    def _load_credential(self) -> dict:
        """Load credentials from file."""
        credential_path = os.path.expanduser("~/.ccc/credentials/sichuan-001.json")
        try:
            with open(credential_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def login(self, credential: dict) -> bool:
        """Login to Sichuan platform."""
        return True

    def crawl(self) -> list[dict[str, Any]]:
        """Crawl price data from Sichuan platform."""
        dry_run = os.environ.get("CRAWLER_DRY_RUN", "1") == "1"

        if dry_run:
            return self._crawl_dry_run()

        try:
            token = self._load_credential().get("token", "")
            data = self._fetch_price_data(token=token)
            return self._extract_price_records(data)
        except Exception as e:
            raise RuntimeError(f"Real-mode crawl failed: {e}")

    def _crawl_dry_run(self) -> list[dict[str, Any]]:
        """Return dry-run sample data (3 items)."""
        return [
            {
                "product_name": "阿司匹林肠溶片",
                "spec": "100mg*30片",
                "manufacturer": "阿司匹林肠溶片",
                "reference_price": 18.5,
                "unit": "盒",
                "last_updated": "2026-07-17T10:00:00Z",
            },
            {
                "product_name": "氨氯地平",
                "spec": "5mg*7片*2板",
                "manufacturer": "氨氯地平",
                "reference_price": 25.6,
                "unit": "盒",
                "last_updated": "2026-07-17T10:00:00Z",
            },
            {
                "product_name": "阿莫西林胶囊",
                "spec": "0.25g*24粒",
                "manufacturer": "阿莫西林胶囊",
                "reference_price": 32.0,
                "unit": "盒",
                "last_updated": "2026-07-17T10:00:00Z",
            },
        ]

    def _fetch_price_data(self, token: str) -> list[dict[str, Any]]:
        """Fetch price data from API."""
        import requests

        base_url = self._load_credential().get("base_url", "https://ggfw.scyb.org.cn")
        url = f"{base_url}/api/procurement/search"
        headers = {
            "Authorization": f"Bearer {token}",
        }
        params = {"query_type": "medication", "limit": 10}

        response = requests.post(url, headers=headers, json=params, timeout=30)
        response.raise_for_status()
        return response.json().get("data", [])

    def _extract_price_records(
        self, api_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Normalize API response to standardized crawler fields."""
        records = []
        for item in api_data:
            records.append(
                {
                    "product_name": item.get("name", ""),
                    "spec": item.get("spec", ""),
                    "manufacturer": item.get("manufacturer", ""),
                    "reference_price": item.get("price", 0.0),
                    "unit": item.get("unit", ""),
                    "last_updated": item.get("update_time", ""),
                }
            )
        return records

    def extract(self, raw):
        """Extract structured data from raw data."""
        if raw and isinstance(raw[0], dict) and "product_name" in raw[0]:
            return raw
        return self._extract_price_records(raw)
