#!/usr/bin/env python3
"""_code_indexer.py — CCC 二级文件索引引擎

FlowWeave 启发：三级扫描（文件→AST→程序关联）的简化版。

能力：
1. 文件级：glob + gitignore 过滤，追踪新增/修改/删除
2. AST 轻解析：Python 符号提取（import/class/def/async def/call），TypeScript/JS 符号提取
3. 增量缓存：仅重扫变动文件，缓存存 .ccc/index/
4. 查询接口：按符号查找、按文件路径查找、统计

用法：
  from _code_indexer import CodeIndexer
  indexer = CodeIndexer("/path/to/project")
  indexer.scan()  # 增量扫描
  indexer.full_scan()  # 全量扫描
  result = indexer.find_symbol("some_function")
"""

from __future__ import annotations
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Optional


# ── AST 轻解析：Python ──

_PY_IMPORT_PAT = re.compile(
    r'^import\s+([\w.]+(?:\s*,\s*[\w.]+)*)'
    r'|^from\s+([\w.]+)\s+import\s+(.+)$',
    re.MULTILINE,
)
_PY_CLASS_PAT = re.compile(
    r'^class\s+(\w+)\s*(?:\(.*?\))?\s*:', re.MULTILINE
)
_PY_DEF_PAT = re.compile(
    r'^(?:async\s+)?def\s+(\w+)\s*\(', re.MULTILINE
)
_PY_CALL_PAT = re.compile(
    r'(?<!def\s)(?<!\.)(\w+)\s*\('
)

# ── AST 轻解析：TypeScript / JavaScript ──

_TS_IMPORT_PAT = re.compile(
    r'import\s+(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]'
    r'|import\s+[\'"]([^\'"]+)[\'"]',
)
_TS_EXPORT_PAT = re.compile(
    r'export\s+(?:default\s+)?(?:class|function|const|let|var|interface|type)\s+(\w+)',
)
_TS_CLASS_PAT = re.compile(
    r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)', re.MULTILINE
)
_TS_FUNC_PAT = re.compile(
    r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(',
)
_TS_METHOD_PAT = re.compile(
    r'(?:async\s+)?(\w+)\s*=\s*(?:async\s+)?\(?[^)]*\)?\s*(?:=>|{)',
)
_TS_CALL_PAT = re.compile(
    r'(?<!function\s)(?<!class\s)(\w+)\s*\(',
)


# ── 文件过滤规则 ──

_DEFAULT_IGNORE_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", ".venv-hub",
    ".build", "vendor", "dist", "build", "egg-info", ".tox",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".ccc",
})
_DEFAULT_IGNORE_EXTS = frozenset({
    ".pyc", ".pyo", ".so", ".dll", ".dylib", ".o", ".a",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp3", ".mp4", ".wav", ".avi",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".log", ".lock",
})
_DEFAULT_SCAN_EXTS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
})


# ── 文件哈希（用于增量检测） ──

def _file_hash(path: Path) -> str:
    """快速 mtime+size 哈希，避免读大文件。"""
    try:
        st = path.stat()
        return f"{st.st_mtime_ns}:{st.st_size}"
    except OSError:
        return ""


def _file_hash_full(path: Path) -> str:
    """全内容 SHA256，用于精确检测。"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read())
        return h.hexdigest()[:16]
    except OSError:
        return ""


# ── AST 解析器 ──

def _parse_python(text: str) -> dict:
    """提取 Python 文件的 import/class/def/call 符号。"""
    imports = []
    classes = []
    funcs = []
    calls = set()

    for m in _PY_IMPORT_PAT.finditer(text):
        if m.group(1):
            for mod in m.group(1).split(","):
                imports.append(mod.strip())
        if m.group(2):
            module = m.group(2)
            targets = m.group(3).strip()
            # from X import a, b 或 from X import a as b
            for token in re.split(r",", targets):
                token = token.strip().split(" as ")[0].strip()
                imports.append(f"{module}.{token}")

    for m in _PY_CLASS_PAT.finditer(text):
        classes.append(m.group(1))

    for m in _PY_DEF_PAT.finditer(text):
        funcs.append(m.group(1))

    for m in _PY_CALL_PAT.finditer(text):
        name = m.group(1)
        if len(name) > 1 and not name.startswith("_"):
            calls.add(name)

    return {
        "language": "python",
        "imports": imports,
        "classes": classes,
        "functions": funcs,
        "calls": sorted(calls),
    }


def _parse_typescript(text: str) -> dict:
    """提取 TS/JS 文件的 import/export/class/func/call 符号。"""
    imports = []
    exports = []
    classes = []
    funcs = []
    calls = set()

    for m in _TS_IMPORT_PAT.finditer(text):
        imports.append(m.group(1) or m.group(2) or "")

    for m in _TS_EXPORT_PAT.finditer(text):
        exports.append(m.group(1))

    for m in _TS_CLASS_PAT.finditer(text):
        classes.append(m.group(1))

    for m in _TS_FUNC_PAT.finditer(text):
        funcs.append(m.group(1))

    for m in _TS_METHOD_PAT.finditer(text):
        name = m.group(1)
        if not name.startswith("_") and name not in ("if", "elif", "else", "for", "while", "return"):
            funcs.append(name)

    for m in _TS_CALL_PAT.finditer(text):
        name = m.group(1)
        if len(name) > 1 and not name.startswith("_"):
            calls.add(name)

    # 去重函数
    funcs = list(dict.fromkeys(funcs))

    return {
        "language": "typescript",
        "imports": imports,
        "exports": exports,
        "classes": classes,
        "functions": funcs,
        "calls": sorted(calls),
    }


_LANGUAGE_PARSERS = {
    ".py": _parse_python,
    ".js": _parse_typescript,
    ".ts": _parse_typescript,
    ".jsx": _parse_typescript,
    ".tsx": _parse_typescript,
    ".mjs": _parse_typescript,
    ".cjs": _parse_typescript,
}


# ── 主索引器 ──

class CodeIndexer:
    """二级文件索引引擎。

    cached 属性：
      .files[rel_path] = {"hash","mtime","size","parsed"}
      .symbol_map[symbol] = [rel_path, ...]
      .file_count, .symbol_count
    """

    def __init__(
        self,
        root: str | Path,
        *,
        cache_dir: str | Path | None = None,
        ignore_dirs: frozenset[str] | None = None,
        ignore_exts: frozenset[str] | None = None,
        scan_exts: frozenset[str] | None = None,
    ):
        self.root = Path(root).resolve()
        self.ignore_dirs = ignore_dirs or _DEFAULT_IGNORE_DIRS
        self.ignore_exts = ignore_exts or _DEFAULT_IGNORE_EXTS
        self.scan_exts = scan_exts or _DEFAULT_SCAN_EXTS

        if cache_dir is None:
            cache_dir = self.root / ".ccc" / "index"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._files: dict[str, dict[str, Any]] = {}
        self._symbol_map: dict[str, list[str]] = {}
        self._dirty = False

    @property
    def files(self) -> dict[str, dict[str, Any]]:
        return dict(self._files)

    @property
    def symbol_map(self) -> dict[str, list[str]]:
        return dict(self._symbol_map)

    @property
    def file_count(self) -> int:
        return len(self._files)

    @property
    def symbol_count(self) -> int:
        return len(self._symbol_map)

    # ── 持久化 ──

    def _cache_path(self) -> Path:
        return self.cache_dir / "code-index.json"

    def save(self) -> None:
        """原子写入索引缓存。"""
        data = {
            "version": 2,
            "root": str(self.root),
            "files": self._files,
            "symbol_map": self._symbol_map,
            "updated_at": time.time(),
        }
        tmp = self.cache_dir / ".code-index.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            tmp.rename(self._cache_path())
        except OSError:
            if tmp.exists():
                tmp.unlink()
            raise
        self._dirty = False

    def load(self) -> bool:
        """加载缓存，成功返回 True。"""
        path = self._cache_path()
        if not path.exists():
            return False
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") != 2 or data.get("root") != str(self.root):
                return False
            self._files = data.get("files", {})
            self._symbol_map = data.get("symbol_map", {})
            self._dirty = False
            return True
        except (json.JSONDecodeError, OSError):
            return False

    # ── 文件遍历 ──

    def _walk_files(self) -> list[Path]:
        """返回所有可扫描文件。"""
        files = []
        try:
            stack = [self.root]
            while stack:
                d = stack.pop()
                try:
                    for entry in os.scandir(d):
                        name = entry.name
                        if entry.is_dir(follow_symlinks=False):
                            if name not in self.ignore_dirs:
                                stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            ext = os.path.splitext(name)[1].lower()
                            if ext in self.scan_exts:
                                files.append(Path(entry.path))
                except PermissionError:
                    continue
        except PermissionError:
            pass
        return files

    # ── 扫描 ──

    def full_scan(self) -> dict[str, Any]:
        """全量扫描：遍历所有文件 + AST 解析 + 构建符号映射。"""
        self._files = {}
        self._symbol_map = {}
        files = self._walk_files()

        for fpath in files:
            try:
                rel = str(fpath.relative_to(self.root))
            except ValueError:
                continue

            h = _file_hash(fpath)
            try:
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except (OSError, PermissionError):
                continue

            ext = fpath.suffix.lower()
            parser = _LANGUAGE_PARSERS.get(ext)
            parsed = parser(text) if parser else {"language": "unknown", "note": f"no parser for {ext}"}

            self._files[rel] = {
                "hash": h,
                "mtime": fpath.stat().st_mtime,
                "size": len(text),
                "parsed": parsed,
            }

            for sym in parsed.get("classes", []):
                self._symbol_map.setdefault(sym, []).append(rel)
            for sym in parsed.get("functions", []):
                self._symbol_map.setdefault(sym, []).append(rel)
            for sym in parsed.get("exports", []):
                self._symbol_map.setdefault(sym, []).append(rel)

        self._dirty = True
        return self.stats()

    def scan(self) -> dict[str, Any]:
        """增量扫描：只重扫哈希变化的文件。"""
        if not self._files:
            return self.full_scan()

        files = self._walk_files()
        current_set = set()
        changed = 0
        added = 0
        removed = 0

        # 删除不存在的文件
        existing = {str(f.relative_to(self.root)): f for f in files}
        for rel in list(self._files.keys()):
            if rel not in existing:
                self._remove_file(rel)
                removed += 1

        # 新增 + 变更
        for fpath in files:
            try:
                rel = str(fpath.relative_to(self.root))
            except ValueError:
                continue
            current_set.add(rel)
            h = _file_hash(fpath)

            old_entry = self._files.get(rel)
            if old_entry and old_entry.get("hash") == h:
                continue  # 未变

            try:
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except (OSError, PermissionError):
                continue

            ext = fpath.suffix.lower()
            parser = _LANGUAGE_PARSERS.get(ext)
            parsed = parser(text) if parser else {"language": "unknown", "note": f"no parser for {ext}"}

            # 移除旧符号
            if old_entry:
                self._remove_symbols_for(rel)

            self._files[rel] = {
                "hash": h,
                "mtime": fpath.stat().st_mtime,
                "size": len(text),
                "parsed": parsed,
            }

            for sym in parsed.get("classes", []):
                self._symbol_map.setdefault(sym, []).append(rel)
            for sym in parsed.get("functions", []):
                self._symbol_map.setdefault(sym, []).append(rel)
            for sym in parsed.get("exports", []):
                self._symbol_map.setdefault(sym, []).append(rel)

            if old_entry:
                changed += 1
            else:
                added += 1

        self._dirty = True
        return {**self.stats(), "changed": changed, "added": added, "removed": removed}

    def _remove_file(self, rel: str) -> None:
        """从索引中移除文件。"""
        self._remove_symbols_for(rel)
        self._files.pop(rel, None)

    def _remove_symbols_for(self, rel: str) -> None:
        """移除该文件贡献的所有符号。"""
        entry = self._files.get(rel)
        if not entry:
            return
        parsed = entry.get("parsed", {})
        for sym_list in [parsed.get("classes", []), parsed.get("functions", []), parsed.get("exports", [])]:
            for sym in sym_list:
                files_list = self._symbol_map.get(sym, [])
                if rel in files_list:
                    files_list.remove(rel)
                if not files_list:
                    self._symbol_map.pop(sym, None)

    # ── 查询 ──

    def find_symbol(self, symbol: str) -> list[dict[str, Any]]:
        """查找符号定义位置。"""
        paths = self._symbol_map.get(symbol, [])
        return [
            {
                "file": p,
                "language": self._files.get(p, {}).get("parsed", {}).get("language", "unknown"),
            }
            for p in paths
        ]

    def search_symbol(self, query: str) -> list[dict[str, Any]]:
        """模糊搜索符号名。"""
        q = query.lower()
        results = []
        for sym, paths in self._symbol_map.items():
            if q in sym.lower():
                results.append({
                    "symbol": sym,
                    "files": paths,
                    "count": len(paths),
                })
        results.sort(key=lambda x: -x["count"])
        return results

    def get_file_info(self, rel_path: str) -> Optional[dict[str, Any]]:
        """获取文件索引信息。"""
        entry = self._files.get(rel_path)
        if not entry:
            return None
        return dict(entry)

    def get_language_stats(self) -> dict[str, int]:
        """按语言统计文件数和行数。"""
        langs: dict[str, dict] = {}
        for rel, entry in self._files.items():
            lang = entry.get("parsed", {}).get("language", "unknown")
            if lang not in langs:
                langs[lang] = {"files": 0, "lines": 0}
            langs[lang]["files"] += 1
            langs[lang]["lines"] += entry.get("size", 0)
        return langs

    def stats(self) -> dict[str, Any]:
        return {
            "files": self.file_count,
            "symbols": self.symbol_count,
            "root": str(self.root),
            "cache_dir": str(self.cache_dir),
        }

    def __repr__(self) -> str:
        return f"<CodeIndexer root={self.root} files={self.file_count} symbols={self.symbol_count}>"
