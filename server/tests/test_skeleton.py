"""CCC 新服务端 · 骨架冒烟测试。

验证：
1. server/ 目录结构完整，每目录有 README
2. config 加载器：正常加载 / 缺项报错 / 空值报错 / 可选键默认值
3. executors.example.json 锁定契约 §7 五角色 schema（角色集合 / 分类 / 绑定非空）
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

# ── 项目根 ──
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = PROJECT_ROOT / "server"


# ── 辅助 ──

def _server_subdirs() -> list[str]:
    """返回 server/ 下应有的一级子目录名。"""
    return ["engine", "board", "web", "relay", "config", "deploy", "tests"]


def _write_env(lines: list[str]) -> str:
    """写临时 .env 文件，返回路径。"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".env", delete=False, encoding="utf-8"
    ) as f:
        f.write("\n".join(lines) + "\n")
        return f.name


# ════════════════════════════════════════════════════════════
# 1. 目录结构
# ════════════════════════════════════════════════════════════

class TestDirectoryStructure:
    """断言 server/ 骨架完整，每目录有 README。"""

    @pytest.mark.parametrize("subdir", _server_subdirs())
    def test_subdir_exists(self, subdir: str) -> None:
        target = SERVER_DIR / subdir
        assert target.is_dir(), f"missing server/{subdir}/"

    @pytest.mark.parametrize("subdir", _server_subdirs())
    def test_readme_exists(self, subdir: str) -> None:
        readme = SERVER_DIR / subdir / "README.md"
        assert readme.is_file(), f"missing server/{subdir}/README.md"
        content = readme.read_text(encoding="utf-8").strip()
        assert len(content) > 10, f"server/{subdir}/README.md is too short"

    def test_server_readme_exists(self) -> None:
        readme = SERVER_DIR / "README.md"
        assert readme.is_file(), "missing server/README.md"


# ════════════════════════════════════════════════════════════
# 2. Config 加载器
# ════════════════════════════════════════════════════════════

class TestConfigLoader:
    """config 加载器：正常加载 / 缺项 / 空值 / 可选默认 四用例。"""

    REQUIRED_FIXTURE = [
        "ENGINE_PORT=8001",
        "BOARD_PORT=8002",
        "WEB_PORT=8003",
        "RELAY_PORT=8004",
        "DATA_DIR=/tmp/ccc/data",
        "LOG_DIR=/tmp/ccc/logs",
        "RELAY_UPSTREAM_URL=http://example.com/v1",
        "EXECUTOR_REGISTRY_PATH=/tmp/ccc/executors.json",
    ]

    @pytest.fixture
    def loader(self):
        # 动态 import，避免 import 时执行副作用
        sys.path.insert(0, str(PROJECT_ROOT))
        from server.config.loader import load_config, ConfigError  # type: ignore[import-untyped]
        return load_config, ConfigError

    def test_load_normal(self, loader) -> None:
        """正常加载：写入所有必填项 + 可选键显式值，应返回完整字典。"""
        load_config, _ = loader
        env_path = _write_env(
            self.REQUIRED_FIXTURE + ["RELAY_UPSTREAM_KEY=sk-test", "PYTHON_BIN=/opt/bin/python3"]
        )
        try:
            cfg = load_config(env_path)
            assert cfg["ENGINE_PORT"] == "8001"
            assert cfg["BOARD_PORT"] == "8002"
            assert cfg["WEB_PORT"] == "8003"
            assert cfg["RELAY_PORT"] == "8004"
            assert cfg["DATA_DIR"] == "/tmp/ccc/data"
            assert cfg["LOG_DIR"] == "/tmp/ccc/logs"
            assert cfg["RELAY_UPSTREAM_URL"] == "http://example.com/v1"
            assert cfg["EXECUTOR_REGISTRY_PATH"] == "/tmp/ccc/executors.json"
            assert cfg["RELAY_UPSTREAM_KEY"] == "sk-test"
            assert cfg["PYTHON_BIN"] == "/opt/bin/python3"
        finally:
            Path(env_path).unlink(missing_ok=True)

    def test_load_missing_key(self, loader) -> None:
        """缺项：应抛出 ConfigError。"""
        load_config, ConfigError = loader
        env_path = _write_env(["ENGINE_PORT=8001", "BOARD_PORT=8002"])  # 故意缺失其余必填项
        try:
            with pytest.raises(ConfigError, match="missing required config key"):
                load_config(env_path)
        finally:
            Path(env_path).unlink(missing_ok=True)

    def test_load_empty_required(self, loader) -> None:
        """必填项为空值：应抛出 ConfigError。"""
        load_config, ConfigError = loader
        env_path = _write_env(["ENGINE_PORT="] + self.REQUIRED_FIXTURE[1:])
        try:
            with pytest.raises(ConfigError, match="required config keys are empty"):
                load_config(env_path)
        finally:
            Path(env_path).unlink(missing_ok=True)

    def test_load_optional_default(self, loader) -> None:
        """可选键缺省：RELAY_UPSTREAM_KEY / PYTHON_BIN 缺省为空字符串。"""
        load_config, _ = loader
        env_path = _write_env(self.REQUIRED_FIXTURE)  # 不含可选键
        try:
            cfg = load_config(env_path)
            assert cfg["RELAY_UPSTREAM_KEY"] == ""
            assert cfg["PYTHON_BIN"] == ""
        finally:
            Path(env_path).unlink(missing_ok=True)

    def test_load_file_not_found(self, loader) -> None:
        """文件不存在：应抛出 ConfigError。"""
        load_config, ConfigError = loader
        with pytest.raises(ConfigError, match="config file not found"):
            load_config("/tmp/nonexistent_config_file_abc123.env")


# ════════════════════════════════════════════════════════════
# 3. Executors 示例 JSON（契约 §7 五角色）
# ════════════════════════════════════════════════════════════

class TestExecutorsExample:
    """executors.example.json 锁定契约 §7 五角色 schema。

    - 角色集合 = 五角色（开发执行体 ×2 / 维护执行体 / 管理席 / 验收席）
    - 执行体行（开发/维护）分类 ∈ {可后台 CLI, 手动 GUI}
    - 席行（管理/验收）分类为「—」（不执行任务，分类不适用）
    - 当前绑定非空；无旧类型（opencode/python/ollama/cli/auto）
    """

    EXECUTORS_PATH = SERVER_DIR / "config" / "executors.example.json"
    VALID_CATEGORIES = frozenset({"可后台 CLI", "手动 GUI"})
    NOT_APPLICABLE_CATEGORY = "—"
    REQUIRED_FIELDS = frozenset({"角色", "分类", "当前绑定", "备注"})

    # 契约 §7 五角色（角色 / 分类规则；绑定只断言非空，不锁具体工具）
    CONTRACT_ROLES: list[dict[str, str]] = [
        {"角色": "开发执行体", "分类": "手动 GUI"},
        {"角色": "开发执行体", "分类": "可后台 CLI"},
        {"角色": "维护执行体", "分类": "可后台 CLI"},
        {"角色": "管理席", "分类": NOT_APPLICABLE_CATEGORY},
        {"角色": "验收席", "分类": NOT_APPLICABLE_CATEGORY},
    ]
    EXECUTOR_ROLES = frozenset({"开发执行体", "维护执行体"})
    STAFF_ROLES = frozenset({"管理席", "验收席"})
    LEGACY_ROLES = frozenset({"opencode", "python", "ollama", "cli", "auto"})

    @pytest.fixture(scope="class")
    def executors_data(self):
        assert self.EXECUTORS_PATH.is_file(), (
            f"executors.example.json not found: {self.EXECUTORS_PATH}"
        )
        with open(self.EXECUTORS_PATH, encoding="utf-8") as f:
            return json.load(f)

    def test_json_parseable(self, executors_data) -> None:
        assert isinstance(executors_data, dict)
        assert "executors" in executors_data
        assert isinstance(executors_data["executors"], list)

    def test_each_executor_has_required_fields(self, executors_data) -> None:
        for idx, entry in enumerate(executors_data["executors"]):
            missing = self.REQUIRED_FIELDS - entry.keys()
            assert not missing, f"executor[{idx}] missing fields: {missing}"

    def test_roles_match_contract_section_7(self, executors_data) -> None:
        """角色集合 = 契约 §7 五角色（多集精确匹配，含开发执行体 ×2）。"""
        actual = [(e["角色"], e["分类"]) for e in executors_data["executors"]]
        expected = [(c["角色"], c["分类"]) for c in self.CONTRACT_ROLES]
        assert sorted(actual) == sorted(expected), (
            f"executors 未对齐契约 §7 五角色:\n  expected={expected}\n  actual={actual}"
        )

    def test_executor_category_valid(self, executors_data) -> None:
        """执行体行（开发/维护）分类 ∈ {可后台 CLI, 手动 GUI}。"""
        for idx, entry in enumerate(executors_data["executors"]):
            if entry["角色"] in self.EXECUTOR_ROLES:
                assert entry["分类"] in self.VALID_CATEGORIES, (
                    f"executor[{idx}] 分类 '{entry['分类']}' 非法 "
                    f"(allowed: {sorted(self.VALID_CATEGORIES)})"
                )

    def test_staff_category_not_applicable(self, executors_data) -> None:
        """席行（管理/验收）分类为「—」；且不得使用可后台 CLI / 手动 GUI。"""
        for idx, entry in enumerate(executors_data["executors"]):
            if entry["角色"] in self.STAFF_ROLES:
                assert entry["分类"] == self.NOT_APPLICABLE_CATEGORY, (
                    f"staff[{idx}] 分类应为 '{self.NOT_APPLICABLE_CATEGORY}'，"
                    f"实际 '{entry['分类']}'"
                )

    def test_binding_non_empty(self, executors_data) -> None:
        """当前绑定非空（绑定具体值按环境配置，不锁死）。"""
        for idx, entry in enumerate(executors_data["executors"]):
            assert entry.get("当前绑定", "").strip(), f"executor[{idx}] 当前绑定为空"

    def test_no_legacy_roles(self, executors_data) -> None:
        """无旧类型角色（opencode/python/ollama/cli/auto）。"""
        roles = {e["角色"] for e in executors_data["executors"]}
        overlap = roles & self.LEGACY_ROLES
        assert not overlap, f"executors 含已废弃角色: {sorted(overlap)}"
