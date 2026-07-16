"""Tests for demo crawler"""

import sys
from pathlib import Path
from crawlers.demo.demo_crawler import DemoCrawler, probe, DEMO_RECORDS


def test_crawler_can_load():
    """Verify demo crawler module can be imported."""
    # Simply import to verify no errors
    import crawlers.demo.demo_crawler


def test_probe():
    """test_probe probe() should return True"""
    assert probe() is True


def test_demo_run_returns_list():
    """test_demo_run_returns_list run() should return a list"""
    demo = DemoCrawler()
    result = demo.run()
    assert isinstance(result, list)


def test_demo_record_has_required_fields():
    """test_demo_record_has_required_fields each record should have required fields"""
    demo = DemoCrawler()
    result = demo.run()

    assert len(result) == 3

    for record in result:
        assert "product_name" in record
        assert "spec" in record
        assert "manufacturer" in record
        assert "reference_price" in record
        assert "fetched_at" in record
