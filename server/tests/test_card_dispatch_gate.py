"""测试出卡查重升级：远端查重与自动自增跳过 (T043)。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
    )


def test_card_dispatch_gate_remote_check(tmp_path: Path) -> None:
    # 获取真实的项目根目录
    project_root = Path(__file__).resolve().parents[2]
    new_card_script = project_root / "scripts" / "new-card.sh"

    # 1. 准备 bare 远程仓库
    bare = tmp_path / "bare.git"
    subprocess.run(
        ["git", "init", "--bare", "-q", str(bare)],
        check=True,
        capture_output=True,
    )

    # 2. 准备 "other" 仓库（模拟远端，包含已提交卡片 clw001-remote.md）
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main")
    _git(other, "config", "user.email", "test@example.com")
    _git(other, "config", "user.name", "test")
    _git(other, "remote", "add", "origin", str(bare))

    # 创建 dummy commit 使得分支有基准
    (other / "README.md").write_text("initial", encoding="utf-8")
    _git(other, "add", "README.md")
    _git(other, "commit", "-qm", "init")
    _git(other, "push", "-q", "-u", "origin", "main")

    # 3. 准备 "local" 仓库（模拟本地，从刚才的 bare 克隆）
    local = tmp_path / "local"
    _git(tmp_path, "clone", "-q", str(bare), "local")
    _git(local, "config", "user.email", "test@example.com")
    _git(local, "config", "user.name", "test")

    # 4. 现在 "other" 写入 clw001-remote.md，代表远端已经占用了 clw001
    dispatch_dir = other / "docs" / "dispatch" / "clw"
    dispatch_dir.mkdir(parents=True)

    # 写入真实的 clw001 卡，结构必须合规以防 validate 报错
    card_body = (
        "# 任务卡 clw001 · 远程卡（OpenCode 执行）\n\n"
        "> 关联：TEST · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：clw · 日期：2026-08-10\n\n"
        "## 基准文件（先看）\n\n"
        "- 项目基准（README·权威索引）：`docs/projects/clw/README.md`\n\n"
        "## 目标\n\n一句话描述目标\n\n"
        "## 红线（先看）\n\n1. 无\n\n"
        "## 范围\n\n- `server/`\n\n"
        "## 步骤\n\n1. 步骤\n\n"
        "## 验收标准\n\n1. 验证\n\n"
        "## 回写要求\n\n更新为已回写\n\n"
        "## 人工批注\n\n无\n\n"
        "## 回写区\n\n**执行体**：OpenCode · 日期：\n"
    )
    (dispatch_dir / "clw001-remote.md").write_text(card_body, encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-qm", "add clw001-remote")
    _git(other, "push", "-q", "origin", "main")

    # 此时，在 local 仓库中：
    # 1. 并没有拉取最新提交，本地 docs/dispatch/clw/ 甚至都不存在，没有任何卡片。
    # 2. 我们使用 local 运行 scripts/new-card.sh，看它是否能 fetch 远端并：
    #    A. 自动跳过已被占用的 clw001，自动分配 clw002
    #    B. 如果显式指定 --id clw001，会报错拒绝。

    env = os.environ.copy()
    env["CCC_PYTHON_BIN"] = "python3"

    # 测试 A：显式指定被占用的 --id clw001-stale，应该被拒绝
    res = subprocess.run(
        [
            "bash",
            str(new_card_script),
            "--title", "Stale ID Card",
            "--project", "clw",
            "--id", "clw001-stale",
            "--related", "clw-plan-007",
            "--dispatch-dir", str(local / "docs" / "dispatch"),
        ],
        cwd=str(local),
        capture_output=True,
        text=True,
        env=env,
    )
    print("RES1 STDOUT:\n", res.stdout)
    print("RES1 STDERR:\n", res.stderr)
    assert res.returncode == 3
    assert "卡编号冲突" in res.stderr
    assert "clw001" in res.stderr

    # 测试 B：自动编号，应该自动生成 clw002 而不是 clw001
    res2 = subprocess.run(
        [
            "bash",
            str(new_card_script),
            "--title", "Auto Increment Card",
            "--project", "clw",
            "--related", "clw-plan-007",
            "--dispatch-dir", str(local / "docs" / "dispatch"),
        ],
        cwd=str(local),
        capture_output=True,
        text=True,
        env=env,
    )
    print("RES2 STDOUT:\n", res2.stdout)
    print("RES2 STDERR:\n", res2.stderr)
    assert res2.returncode == 0
    assert "clw002" in res2.stdout
    assert (local / "docs" / "dispatch" / "clw" / "clw002-auto-increment-card.md").is_file()


def test_new_card_flock_concurrency(tmp_path: Path) -> None:
    # 获取真实的项目根目录
    project_root = Path(__file__).resolve().parents[2]
    new_card_script = project_root / "scripts" / "new-card.sh"

    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)

    local = tmp_path / "local"
    _git(tmp_path, "clone", "-q", str(bare), "local")
    _git(local, "config", "user.email", "test@example.com")
    _git(local, "config", "user.name", "test")

    # 创建 initial commit
    (local / "README.md").write_text("initial", encoding="utf-8")
    _git(local, "add", "README.md")
    _git(local, "commit", "-qm", "init")
    _git(local, "push", "-q", "-u", "origin", "main")

    env = os.environ.copy()
    env["CCC_PYTHON_BIN"] = "python3"

    dispatch_dir = local / "docs" / "dispatch"

    args = [
        "bash",
        str(new_card_script),
        "--title", "Concurrent Card",
        "--project", "clw",
        "--related", "clw-plan-007",
        "--dispatch-dir", str(dispatch_dir),
    ]

    p1 = subprocess.Popen(args, cwd=str(local), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(args, cwd=str(local), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    out1, err1 = p1.communicate()
    out2, err2 = p2.communicate()

    print("P1 STDOUT:\n", out1)
    print("P1 STDERR:\n", err1)
    print("P2 STDOUT:\n", out2)
    print("P2 STDERR:\n", err2)

    assert p1.returncode == 0, f"P1 失败: {err1}"
    assert p2.returncode == 0, f"P2 失败: {err2}"

    files = list((dispatch_dir / "clw").glob("clw[0-9][0-9][0-9]-*.md"))
    assert len(files) == 2, f"期望 2 张卡，实际找到 {len(files)} 张: {files}"

    stems = sorted([f.stem for f in files])
    assert stems[0].startswith("clw001")
    assert stems[1].startswith("clw002")

