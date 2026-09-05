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
    return ["engine", "board", "web", "config", "deploy", "tests"]


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
        "DATA_DIR=/tmp/ccc/data",
        "LOG_DIR=/tmp/ccc/logs",
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
            self.REQUIRED_FIXTURE + ["CCC_WORKTREE_BASE=/tmp/ccc/wt", "PYTHON_BIN=/opt/bin/python3"]
        )
        try:
            cfg = load_config(env_path)
            assert cfg["ENGINE_PORT"] == "8001"
            assert cfg["BOARD_PORT"] == "8002"
            assert cfg["WEB_PORT"] == "8003"
            assert cfg["DATA_DIR"] == "/tmp/ccc/data"
            assert cfg["LOG_DIR"] == "/tmp/ccc/logs"
            assert cfg["EXECUTOR_REGISTRY_PATH"] == "/tmp/ccc/executors.json"
            assert cfg["CCC_WORKTREE_BASE"] == "/tmp/ccc/wt"
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
        """可选键缺省：PYTHON_BIN / SCHEDULER_* / CLUSTER_TARGETS 缺省（RELAY_* 已随中转站退役移除）。"""
        load_config, _ = loader
        env_path = _write_env(self.REQUIRED_FIXTURE)  # 不含可选键
        try:
            cfg = load_config(env_path)
            assert cfg["CCC_WORKTREE_BASE"] == ""
            assert cfg["PYTHON_BIN"] == ""
            assert cfg["SCHEDULER_INTERVAL"] == "60"
            assert cfg["SCHEDULER_DISPATCH_DIR"] == ""
            assert cfg["CLUSTER_TARGETS"] == ""
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

    - 角色集合 = 五角色（开发执行体 ×3 / 维护执行体 / 管理席 / 验收席；开发执行体含可后台 CLI×2）
    - 执行体行（开发/维护）分类 ∈ {可后台 CLI, 手动 GUI}
    - 席行（管理/验收）分类为「—」（不执行任务，分类不适用）
    - 当前绑定非空；无旧类型（opencode/python/ollama/cli/auto）
    - OpenCode 可后台 CLI 行参数模板须同时含 --auto 与 --dir {worktree}（防 exit0 假成功）
    """

    EXECUTORS_PATH = SERVER_DIR / "config" / "executors.example.json"
    VALID_CATEGORIES = frozenset({"可后台 CLI", "手动 GUI"})
    NOT_APPLICABLE_CATEGORY = "—"
    REQUIRED_FIELDS = frozenset({"角色", "分类", "当前绑定", "备注"})

    # 契约：开发仅 OpenCode（2026-08-15 F5 定）+ 维护 + 管理 + 双机审 CLI（验收席）+ DSH 只读取证/审计
    # DSH 槽 2026-08-18 P4 升级：分类「—」→「可后台 CLI」（headless 探针跑通，经 wrapper run-executor.sh 拉起）
    CONTRACT_ROLES: list[dict[str, str]] = [
        {"角色": "开发执行体", "分类": "可后台 CLI"},
        {"角色": "维护执行体", "分类": "可后台 CLI"},
        {"角色": "管理席", "分类": NOT_APPLICABLE_CATEGORY},
        {"角色": "验收席", "分类": "可后台 CLI"},
        {"角色": "只读取证/审计执行体", "分类": "可后台 CLI"},
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
        """角色集合 = 契约 §7 角色（多集精确匹配，含 DSH 只读取证/审计）。"""
        actual = [(e["角色"], e["分类"]) for e in executors_data["executors"]]
        expected = [(c["角色"], c["分类"]) for c in self.CONTRACT_ROLES]
        assert sorted(actual) == sorted(expected), (
            f"executors 未对齐契约 §7 角色:\n  expected={expected}\n  actual={actual}"
        )

    def test_executor_category_valid(self, executors_data) -> None:
        """开发/维护/验收（可后台）分类 ∈ {可后台 CLI, 手动 GUI}；管理席为 —。"""
        for idx, entry in enumerate(executors_data["executors"]):
            if entry["角色"] in self.STAFF_ROLES and entry["角色"] != "验收席":
                continue
            if entry["角色"] == "管理席":
                continue
            if entry["角色"] in self.EXECUTOR_ROLES or (
                entry["角色"] == "验收席" and entry["分类"] == "可后台 CLI"
            ):
                assert entry["分类"] in self.VALID_CATEGORIES, (
                    f"executor[{idx}] 分类 '{entry['分类']}' 非法 "
                    f"(allowed: {sorted(self.VALID_CATEGORIES)})"
                )

    def test_staff_category_not_applicable(self, executors_data) -> None:
        """管理席分类为「—」；验收席可为可后台 CLI（机审）。"""
        for idx, entry in enumerate(executors_data["executors"]):
            if entry["角色"] == "管理席":
                assert entry["分类"] == self.NOT_APPLICABLE_CATEGORY, (
                    f"staff[{idx}] 分类应为 '{self.NOT_APPLICABLE_CATEGORY}'，"
                    f"实际 '{entry['分类']}'"
                )
            if entry["角色"] == "验收席":
                assert entry["分类"] in (
                    self.NOT_APPLICABLE_CATEGORY,
                    "可后台 CLI",
                ), f"验收席分类非法: {entry['分类']}"

    def test_binding_non_empty(self, executors_data) -> None:
        """当前绑定非空（绑定具体值按环境配置，不锁死）。"""
        for idx, entry in enumerate(executors_data["executors"]):
            assert entry.get("当前绑定", "").strip(), f"executor[{idx}] 当前绑定为空"

    def test_no_legacy_roles(self, executors_data) -> None:
        """无旧类型角色（opencode/python/ollama/cli/auto）。"""
        roles = {e["角色"] for e in executors_data["executors"]}
        overlap = roles & self.LEGACY_ROLES
        assert not overlap, f"executors 含已废弃角色: {sorted(overlap)}"

    def test_dsh_executor_contract(self, executors_data) -> None:
        """2026-08-22 工具收口：中间环节（开发/维护/验收）全部 DSH（dsh-executor.sh/dsh-auditor.sh）。

        契约：可后台 CLI 行的 DSH wrapper 必须①命令指向 dsh-*.sh②参数模板为位置参数
        （card_path work_id worktree role）③注入提示=false（wrapper 自读，防污染位置参数）。
        防回归：OpenCode 已移除，注册表不得再出现 opencode 引用。
        """
        import json

        dsh_rows = [
            e for e in executors_data["executors"]
            if e.get("分类") == "可后台 CLI" and "dsh" in str(e.get("命令", "")).lower()
        ]
        assert dsh_rows, "example 注册表缺少 DSH 可后台 CLI 行（2026-08-22 收口契约）"
        for entry in dsh_rows:
            assert "scripts/dsh-" in str(entry.get("命令", "")), f"DSH 行命令须指向 dsh-*.sh: {entry.get('命令')}"
            tpl = entry.get("参数模板", "")
            for ph in ("{card_path}", "{work_id}", "{worktree}"):
                assert ph in tpl, f"DSH 行参数模板缺 {ph}"
            assert entry.get("注入提示", True) is False, "DSH wrapper 须 注入提示=false"
        # 执行体绑定/命令无 OpenCode（备注提及环境变量/回退说明不在此列）
        for e in executors_data["executors"]:
            assert str(e.get("当前绑定", "")) != "OpenCode", "当前绑定不得为 OpenCode"
            assert "opencode" not in str(e.get("命令", "")).lower(), "命令不得指向 opencode"


# ── 批E（2026-09-04）：cc-auditor.sh 语法门禁 ──

def test_cc_auditor_script_bash_syntax() -> None:
    """cc-auditor.sh（后段验收席 claude wrapper）必须通过 bash -n 语法检查。

    批E 第五步：wrapper 是核心产线行为变更，语法门禁入测试（轻量）。
    批G（2026-09-05）：机械测试证据工作目录随 TEST_WORKDIR，
    不再依赖 $(pwd)（主仓 cwd 假失败修复）。
    """
    script = PROJECT_ROOT / "scripts" / "cc-auditor.sh"
    assert script.is_file(), f"cc-auditor.sh 缺失: {script}"
    text = script.read_text(encoding="utf-8")
    assert "TEST_WORKDIR" in text and "test_workdir" in text, "必须声明测试证据工作目录（TEST_WORKDIR）"
    assert 'TEST_WORKDIR="${BIZ_WORKTREE:-${WORKTREE:-$REPO_ROOT}}"' in text, "业务 worktree 选择顺序必须为 BIZ_WORKTREE → WORKTREE → 主仓"
    assert 'test-evidence.sh" "$AUDIT_CARD" "$TEST_WORKDIR"' in text, "test-evidence 必须指向 TEST_WORKDIR"
    import subprocess

    res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert res.returncode == 0, f"bash -n 失败: {res.stderr}"


# ── 批F（2026-09-05）：DSH 权限协商修复 ──

def test_dsh_executor_prompt_blocks_redundant_sandbox_escalation() -> None:
    """DSH 执行 wrapper 的 prompt 必须禁止重复 sandbox 权限升级。

    静态契约：只读 wrapper 源文本，断言 prompt 授权段含「不得再传 sandbox_permissions /
    不得请求权限升级 / 不要发起 escalation / 不要无限重试」语义，并过 bash -n。
    不启动真实 DSH（测试不拉起子进程跑 wrapper 本体）。
    """
    import subprocess

    script = PROJECT_ROOT / "scripts" / "dsh-executor.sh"
    assert script.is_file(), f"dsh-executor.sh 缺失: {script}"

    res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert res.returncode == 0, f"bash -n 失败: {res.stderr}"

    text = script.read_text(encoding="utf-8")
    assert "已由 wrapper 预先授予 danger-full-access" in text
    assert "不得再传 sandbox_permissions" in text
    assert "不得请求权限升级" in text
    assert "不要发起 escalation" in text
    assert "不要无限重试" in text

    # 静态契约只检查 prompt 源文本，不启动真实 DSH。
    prompt_start = text.index('PROMPT="')
    prompt_end = text.index('"\n\n# ccc073', prompt_start)
    prompt = text[prompt_start:prompt_end]
    assert "sandbox_permissions" in prompt
    assert "权限升级" in prompt
    assert "danger-full-access" in prompt
