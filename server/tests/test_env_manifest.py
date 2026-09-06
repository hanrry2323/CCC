"""P3 环境声明式（env-manifest）校验测试。

覆盖三场景（指令 §4）：
1. manifest 存在且各 bin 路径真实存在 → 校验通过；
2. manifest 文件不存在 → 默认回退（pytest/ruff 兜底），不拦截；
3. manifest 存在但声明的 bin 路径无效（symlink 展开后缺失）→ 派发前拒绝。
另含 load_manifest / manifest_path / engine _ensure_business_worktree 集成。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from server.engine.env_manifest import (
    DEFAULT_PYTEST,
    DEFAULT_RUFF,
    ENV_MANIFEST_MISSING_MARKER,
    load_manifest,
    manifest_path,
    validate_manifest,
)
from server.engine.main import _ensure_business_worktree
from server.engine.task import Work


def _make_manifest_dir(tmp_path: Path, prefix: str = "zz") -> Path:
    d = tmp_path / "projects" / prefix
    d.mkdir(parents=True)
    return d


def _make_env_with_bins(worktree: Path, *rels: str, target: Path | None = None) -> Path:
    """worktree/.venv 符号链接 → 目标环境；按 rels 各建 bin。

    模拟 engine 挂载：``.venv`` 是 symlink 指向真实环境，``.venv/bin/<name>``
    经 symlink 展开后真实存在。共用同一 target（多 bin 同居一环境）。
    """
    target = target or (worktree / "_real-env")
    (target / "bin").mkdir(parents=True, exist_ok=True)
    for rel in rels:
        bin_path = target / "bin" / Path(rel).name
        bin_path.write_text("#!/bin/sh\n", encoding="utf-8")
        bin_path.chmod(0o755)
    link_venv = worktree / ".venv"
    if link_venv.is_symlink() or link_venv.exists():
        link_venv.unlink()  # 防先建实目录抢 symlink 位
    link_venv.symlink_to(target, target_is_directory=True)
    return target


class TestLoadManifest:
    def test_load_valid(self, tmp_path: Path) -> None:
        d = _make_manifest_dir(tmp_path)
        mf = d / "env-manifest.json"
        mf.write_text(json.dumps({"python_bin": ".venv/bin/python"}), encoding="utf-8")
        data = load_manifest(mf)
        assert data == {"python_bin": ".venv/bin/python"}

    def test_load_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert load_manifest(tmp_path / "no.json") is None

    def test_load_invalid_json_returns_none(self, tmp_path: Path) -> None:
        mf = tmp_path / "bad.json"
        mf.write_text("{ not json", encoding="utf-8")
        assert load_manifest(mf) is None

    def test_load_non_dict_returns_none(self, tmp_path: Path) -> None:
        mf = tmp_path / "list.json"
        mf.write_text("[1, 2]", encoding="utf-8")
        assert load_manifest(mf) is None


class TestManifestPath:
    def test_layout(self, tmp_path: Path) -> None:
        assert manifest_path(tmp_path, "zz") == tmp_path / "docs" / "projects" / "zz" / "env-manifest.json"


class TestValidateManifest:
    def test_manifest_absent_default_fallback_ok(self, tmp_path: Path) -> None:
        """manifest 缺失 → 默认回退；回退路径存在 → ok。"""
        worktree = tmp_path / "wt"
        worktree.mkdir(parents=True)
        _make_env_with_bins(worktree, DEFAULT_PYTEST, DEFAULT_RUFF, target=tmp_path / "env")
        ok, problems = validate_manifest(None, worktree, prefix="zz")
        assert ok is True
        assert problems == []

    def test_manifest_absent_default_fallback_missing_warns_not_block(self, tmp_path: Path) -> None:
        """manifest 缺失且回退路径也不在 → WARN（不拦截）。"""
        wt = tmp_path / "wt-empty"
        wt.mkdir(parents=True)
        ok, problems = validate_manifest(None, wt, prefix="zz")
        assert ok is True
        assert any("默认回退路径不存在" in p for p in problems)

    def test_manifest_valid_all_bins_exist(self, tmp_path: Path) -> None:
        d = _make_manifest_dir(tmp_path)
        mf = d / "env-manifest.json"
        mf.write_text(
            json.dumps(
                {
                    "python_bin": ".venv/bin/python",
                    "pytest_bin": ".venv/bin/pytest",
                    "ruff_bin": ".venv/bin/ruff",
                }
            ),
            encoding="utf-8",
        )
        worktree = tmp_path / "wt"
        worktree.mkdir(parents=True)
        _make_env_with_bins(
            worktree,
            ".venv/bin/python",
            ".venv/bin/pytest",
            ".venv/bin/ruff",
            target=tmp_path / "real-env",
        )
        ok, problems = validate_manifest(load_manifest(mf), worktree, prefix="zz")
        assert ok is True
        assert problems == []

    def test_manifest_missing_bin_rejects(self, tmp_path: Path) -> None:
        """manifest 存在但 pytest_bin 缺失 → 派发前拒绝（FAIL_FAST）。"""
        d = _make_manifest_dir(tmp_path)
        mf = d / "env-manifest.json"
        mf.write_text(
            json.dumps(
                {
                    "python_bin": ".venv/bin/python",
                    "pytest_bin": ".venv/bin/pytest",
                }
            ),
            encoding="utf-8",
        )
        worktree = tmp_path / "wt"
        worktree.mkdir(parents=True)
        _make_env_with_bins(worktree, ".venv/bin/python", target=tmp_path / "real-env")
        # pytest 不创建
        ok, problems = validate_manifest(load_manifest(mf), worktree, prefix="zz")
        assert ok is False
        assert any("pytest_bin" in p and "不存在" in p for p in problems)

    def test_manifest_invalid_all_missing(self, tmp_path: Path) -> None:
        d = _make_manifest_dir(tmp_path)
        mf = d / "env-manifest.json"
        mf.write_text(
            json.dumps(
                {
                    "python_bin": ".venv/bin/python",
                    "pytest_bin": ".venv/bin/pytest",
                    "ruff_bin": ".venv/bin/ruff",
                }
            ),
            encoding="utf-8",
        )
        wt = tmp_path / "wt-empty"
        wt.mkdir(parents=True)
        ok, problems = validate_manifest(load_manifest(mf), wt, prefix="zz")
        assert ok is False
        assert len(problems) == 3


class TestEngineIntegration:
    """_ensure_business_worktree 挂载 venv 后按 manifest 校验（FAIL_FAST 拦截）。"""

    def _make_biz_repo(self, tmp_path: Path) -> Path:
        repo = tmp_path / "bizrepo"
        repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo), check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=str(repo), check=True, capture_output=True
        )
        (repo / "seed.txt").write_text("seed", encoding="utf-8")
        subprocess.run(["git", "add", "seed.txt"], cwd=str(repo), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), check=True, capture_output=True)
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=str(repo), check=True)
        return repo

    def _make_project(self, repo: Path, root: Path):
        from server.board.registry import ProjectEntry

        return ProjectEntry(
            prefix="zz",
            id="zz",
            name="zz",
            display="zz",
            taskable=True,
            forbidden=False,
            status="active",
            path_m1=None,
            path_mac2017=str(repo),
            location="mac2017-apps",
            isolation_worktree_root=str(root),
            isolation_max_concurrent=1,
        )

    def test_fail_fast_when_manifest_bin_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """manifest 存在但 pytest_bin 缺失 → _ensure_business_worktree 拒绝。"""
        repo = self._make_biz_repo(tmp_path)
        wt_root = tmp_path / ".ccc-wt" / "zz"
        proj = self._make_project(repo, wt_root)
        work = Work(id="zz001", role="开发执行体", project="zz", card_path="docs/dispatch/zz/zz001-x.md")
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # 业务仓 .venv 只含 python（pytest 缺失）
        source = repo / ".venv"
        (source / "bin").mkdir(parents=True)
        (source / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")
        (source / "bin" / "python").chmod(0o755)

        # manifest → tmp projects dir（monkeypatch manifest_path）
        mf_dir = _make_manifest_dir(tmp_path, prefix="zz")
        (mf_dir / "env-manifest.json").write_text(
            json.dumps({"python_bin": ".venv/bin/python", "pytest_bin": ".venv/bin/pytest"}),
            encoding="utf-8",
        )

        def _fake_manifest_path(_root, prefix: str):
            return mf_dir / "env-manifest.json"

        monkeypatch.setattr("server.engine.env_manifest.manifest_path", _fake_manifest_path)

        wt, err = _ensure_business_worktree(work, proj, log_dir)
        assert wt is None
        assert err is not None
        assert ENV_MANIFEST_MISSING_MARKER in err
        assert "pytest_bin" in err

    def test_pass_when_manifest_bins_exist(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """manifest 存在且 bin 齐 → 正常返回 worktree。"""
        repo = self._make_biz_repo(tmp_path)
        wt_root = tmp_path / ".ccc-wt" / "zz"
        proj = self._make_project(repo, wt_root)
        work = Work(id="zz002", role="开发执行体", project="zz", card_path="docs/dispatch/zz/zz002-x.md")
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        source = repo / ".venv"
        (source / "bin").mkdir(parents=True)
        for name in ("python", "pytest", "ruff"):
            p = source / "bin" / name
            p.write_text("#!/bin/sh\n", encoding="utf-8")
            p.chmod(0o755)

        mf_dir = _make_manifest_dir(tmp_path, prefix="zz")
        (mf_dir / "env-manifest.json").write_text(
            json.dumps(
                {
                    "python_bin": ".venv/bin/python",
                    "pytest_bin": ".venv/bin/pytest",
                    "ruff_bin": ".venv/bin/ruff",
                }
            ),
            encoding="utf-8",
        )

        def _fake_manifest_path(_root, prefix: str):
            return mf_dir / "env-manifest.json"

        monkeypatch.setattr("server.engine.env_manifest.manifest_path", _fake_manifest_path)

        wt, err = _ensure_business_worktree(work, proj, log_dir)
        assert err is None
        assert wt is not None
        assert (Path(wt) / ".venv" / "bin" / "pytest").is_file()
