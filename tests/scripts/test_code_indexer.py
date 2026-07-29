"""测试 _code_indexer — 二级扫描引擎"""

import json
import os
import tempfile
from pathlib import Path
import pytest

from _code_indexer import CodeIndexer, _parse_python, _parse_typescript


class TestPythonParser:
    def test_imports(self):
        code = "import os\nimport json, sys\nfrom pathlib import Path\nfrom typing import Optional"
        result = _parse_python(code)
        assert "os" in result["imports"]
        assert "json" in result["imports"]
        assert "pathlib.Path" in result["imports"]
        assert "typing.Optional" in result["imports"]

    def test_classes(self):
        code = "class Foo:\n    pass\nclass Bar(Base):\n    pass"
        result = _parse_python(code)
        assert "Foo" in result["classes"]
        assert "Bar" in result["classes"]

    def test_functions(self):
        code = "def hello():\n    pass\nasync def world():\n    pass"
        result = _parse_python(code)
        assert "hello" in result["functions"]
        assert "world" in result["functions"]

    def test_calls(self):
        code = "print('hi')\nos.path.join('a', 'b')\nresult = some_func()"
        result = _parse_python(code)
        assert "print" in result["calls"]
        assert "some_func" in result["calls"]


class TestTypeScriptParser:
    def test_imports(self):
        code = "import React from 'react'\nimport { useState } from 'react'\nimport * as lib from './lib'"
        result = _parse_typescript(code)
        assert "react" in result["imports"]
        assert "./lib" in result["imports"]

    def test_exports(self):
        code = "export class Foo {}\nexport default function bar() {}\nexport const BAZ = 1"
        result = _parse_typescript(code)
        assert "Foo" in result["exports"]
        assert "bar" in result["exports"]
        assert "BAZ" in result["exports"]

    def test_classes_functions(self):
        code = "class MyClass {}\nfunction myFunc() {}\nconst arrow = () => {}"
        result = _parse_typescript(code)
        assert "MyClass" in result["classes"]
        assert "myFunc" in result["functions"]

    def test_calls(self):
        code = "console.log('test')\ndoSomething()"
        result = _parse_typescript(code)
        assert "log" in result["calls"]
        assert "doSomething" in result["calls"]


class TestCodeIndexer:
    def test_empty_dir(self, tmp_path):
        idx = CodeIndexer(tmp_path)
        stats = idx.full_scan()
        assert stats["files"] == 0
        assert stats["symbols"] == 0

    def test_scan_python_file(self, tmp_path):
        (tmp_path / "hello.py").write_text(
            "import os\nclass Greeter:\n    def greet(self):\n        pass\n"
        )
        idx = CodeIndexer(tmp_path)
        stats = idx.full_scan()
        assert stats["files"] == 1
        assert stats["symbols"] >= 1  # Greeter

        found = idx.find_symbol("Greeter")
        assert len(found) >= 1
        assert found[0]["file"] == "hello.py"

    def test_scan_ts_file(self, tmp_path):
        (tmp_path / "app.ts").write_text(
            "import React from 'react'\nexport class App {}\nexport function start() {}\n"
        )
        idx = CodeIndexer(tmp_path)
        stats = idx.full_scan()
        assert stats["files"] == 1

        found = idx.find_symbol("App")
        assert len(found) >= 1

    def test_search_symbol_fuzzy(self, tmp_path):
        (tmp_path / "lib.py").write_text("def get_user(): pass\ndef get_order(): pass\n")
        idx = CodeIndexer(tmp_path)
        idx.full_scan()
        results = idx.search_symbol("user")
        assert len(results) >= 1
        assert any(r["symbol"] == "get_user" for r in results)

    def test_multi_file_scan(self, tmp_path):
        (tmp_path / "a.py").write_text("def func_a(): pass\nclass A: pass\n")
        (tmp_path / "b.py").write_text("def func_b(): pass\nclass B: pass\n")
        idx = CodeIndexer(tmp_path)
        stats = idx.full_scan()
        assert stats["files"] == 2
        assert stats["symbols"] >= 4

    def test_cache_persistence(self, tmp_path):
        (tmp_path / "mod.py").write_text("def hello(): pass\n")
        idx = CodeIndexer(tmp_path)
        idx.full_scan()
        idx.save()

        idx2 = CodeIndexer(tmp_path)
        loaded = idx2.load()
        assert loaded
        assert idx2.file_count == 1
        assert idx2.find_symbol("hello")

    def test_cache_stale_on_change(self, tmp_path):
        (tmp_path / "mod.py").write_text("def hello(): pass\n")
        idx = CodeIndexer(tmp_path)
        idx.full_scan()
        idx.save()

        # 修改文件
        (tmp_path / "mod.py").write_text("def world(): pass\n")
        idx2 = CodeIndexer(tmp_path)
        idx2.load()
        stats = idx2.scan()
        assert stats.get("changed", 0) >= 1
        assert idx2.find_symbol("hello") == []  # 旧符号移除了
        assert idx2.find_symbol("world")       # 新符号找到了

    def test_ignore_dirs(self, tmp_path):
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "main.py").write_text("def main(): pass\n")
        (tmp_path / ".git").mkdir(parents=True)
        (tmp_path / "__pycache__").mkdir(parents=True)

        idx = CodeIndexer(tmp_path)
        stats = idx.full_scan()
        assert stats["files"] == 1  # 只扫了 src/main.py
        assert idx.find_symbol("main")

    def test_language_stats(self, tmp_path):
        (tmp_path / "a.py").write_text("def f(): pass\n")
        (tmp_path / "b.ts").write_text("function g() {}\n")
        idx = CodeIndexer(tmp_path)
        idx.full_scan()
        stats = idx.get_language_stats()
        assert "python" in stats
        assert "typescript" in stats
