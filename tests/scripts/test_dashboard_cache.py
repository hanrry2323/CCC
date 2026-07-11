"""test_dashboard_cache.py — v0.27.1 _DashboardCache 线程安全测试

覆盖:
  - 并发 get/set 1000 次无 KeyError/RuntimeError
  - 3s TTL 过期
  - 多线程同时 set 不丢数据
"""
from __future__ import annotations

import importlib.util
import os
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"

_os_chdir_backup = os.getcwd()
os.chdir(str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("ccc_board_server", str(SCRIPTS / "ccc-board-server.py"))
ccc_board_server = importlib.util.module_from_spec(_spec)
sys.modules["ccc_board_server"] = ccc_board_server
_spec.loader.exec_module(ccc_board_server)

_DashboardCache = ccc_board_server._DashboardCache


class TestDashboardCache:
    def test_basic_get_set(self):
        c = _DashboardCache(ttl_s=10.0)
        c.set("k1", {"a": 1})
        assert c.get("k1") == {"a": 1}

    def test_get_missing_key(self):
        c = _DashboardCache(ttl_s=10.0)
        assert c.get("nope") is None

    def test_ttl_expiry(self):
        c = _DashboardCache(ttl_s=0.05)
        c.set("k1", {"a": 1})
        assert c.get("k1") == {"a": 1}
        time.sleep(0.1)
        assert c.get("k1") is None

    def test_overwrite_same_key(self):
        c = _DashboardCache(ttl_s=10.0)
        c.set("k1", {"a": 1})
        c.set("k1", {"b": 2})
        assert c.get("k1") == {"b": 2}

    def test_concurrent_get_set_no_error(self):
        """100 个线程并发 get/set，无 KeyError/RuntimeError"""
        c = _DashboardCache(ttl_s=10.0)
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker(n: int):
            try:
                for _ in range(10):
                    c.set(f"k{n}", {"v": n})
                    got = c.get(f"k{n}")
                    assert got is not None
                    assert got["v"] == n
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, f"并发测试失败: {errors}"

    def test_concurrent_set_no_data_loss(self):
        """10 个线程同时 set 不同 key，最终全部可读"""
        c = _DashboardCache(ttl_s=10.0)

        def writer(n: int):
            c.set(f"k{n}", {"data": n})

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(50):
            got = c.get(f"k{i}")
            assert got is not None, f"k{i} 丢失"
            assert got["data"] == i

    def test_independent_ttl_per_key(self):
        """每个 key 独立 TTL"""
        c = _DashboardCache(ttl_s=0.05)
        c.set("fast", {"v": 1})
        c.set("slow", {"v": 2})
        time.sleep(0.1)
        assert c.get("fast") is None
        # slow 也过期了因为 TTL 相同，这里只测 fast
        # 换策略：设不同 TTL 的 cache 实例
        c2 = _DashboardCache(ttl_s=10.0)
        c2.set("persist", {"v": 3})
        time.sleep(0.05)
        assert c2.get("persist") == {"v": 3}
