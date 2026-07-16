"""
Tests for Sichuan crawler.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import os
import pytest
from crawlers.sichuan.sichuan_crawler import SichuanCrawler


def test_run_dry_run_total():
    """Test that run() completes full pipeline and returns valid records."""
    os.environ["CRAWLER_DRY_RUN"] = "1"
    try:
        crawler = SichuanCrawler()
        results = crawler.run()

        assert isinstance(results, list)
        assert len(results) >= 1

        record = results[0]
        assert record["product_name"], "product_name should not be empty"
        assert record["reference_price"] > 0, "reference_price should be greater than 0"
    finally:
        del os.environ["CRAWLER_DRY_RUN"]


class TestSichuanCrawler:
    """Tests for SichuanCrawler"""

    def test_sichuan_import(self):
        """Test that SichuanCrawler can be imported."""
        assert SichuanCrawler is not None

    def test_sichuan_crawler_initialization(self):
        """Test SichuanCrawler instantiation."""
        crawler = SichuanCrawler()
        assert crawler
        assert crawler.config.name == "sichuan"

    def test_sichuan_crawl_dry_run_returns_list(self):
        """Test that dry-run crawl returns a list of records."""
        os.environ["CRAWLER_DRY_RUN"] = "1"
        try:
            crawler = SichuanCrawler()
            results = crawler.run()

            assert isinstance(results, list)
            assert len(results) >= 1
        finally:
            del os.environ["CRAWLER_DRY_RUN"]

    def test_sichuan_crawl_dryrun_record_has_required_fields(self):
        """Test that dry-run records contain required fields."""
        os.environ["CRAWLER_DRY_RUN"] = "1"
        try:
            crawler = SichuanCrawler()
            results = crawler.run()

            if results:
                record = results[0]
                assert "product_name" in record
                assert "spec" in record
                assert "manufacturer" in record
                assert "reference_price" in record
                assert "unit" in record
        finally:
            del os.environ["CRAWLER_DRY_RUN"]

    def test_sichuan_load_credential_empty_path(self):
        """Test that _load_credential returns empty dict when credential file doesn't exist."""
        crawler = SichuanCrawler()
        result = crawler._load_credential()

        assert isinstance(result, dict)
        assert result == {}
