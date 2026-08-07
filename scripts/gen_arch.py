#!/usr/bin/env python3
"""gen_arch.py — ARCH JSON → Archify 架构图 HTML 批量生成器。

用法:
    python3 scripts/gen_arch.py [project ...]     # 指定项目；缺省全部（含 cluster）

依赖:
    Archify 运行时（bin/schemas/renderers）取自 HP 参考库：
    /data/knowledge/reference/agent-ecosystem/archify/archify/（SSH hp@192.168.3.131）
    首次运行自动 rsync 到本地缓存 ~/.cache/archify-run/，之后复用。

产物:
    server/web/legacy-chat/arch/<project>-arch.html（self-contained，看板 iframe 引用）
    并更新 server/web/data/arch/index.json（html 路径 + arch_version + updated_at）。
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

CCC_ROOT = Path(__file__).resolve().parents[1]
ARCH_DIR = CCC_ROOT / "server" / "web" / "data" / "arch"
OUT_DIR = CCC_ROOT / "server" / "web" / "legacy-chat" / "arch"
CACHE = Path.home() / ".cache" / "archify-run"

ARCHIFY_REMOTE = "hp@192.168.3.131:/data/knowledge/reference/agent-ecosystem/archify/archify/"

# 图库索引：project → 中文标题
TITLES = {
    "cluster": "集群全景",
    "ccc": "CCC 自动化开发平台",
    "qb": "qb",
    "medio-0": "medio-0",
    "quanthive": "QuantHive",
    "qxmap": "qx-map 知识地图",
}
SUBTLES = {
    "cluster": "所有项目 · 关联 · 基础设施",
    "ccc": "M1 中枢出卡 → GitHub → 2017 执行机审 → HP 知识",
    "qb": "CCC 产线自动化开发项目",
    "medio-0": "CCC 产线自动化开发项目",
    "quanthive": "独立轨道，禁 qh 出卡",
    "qxmap": "外脑 / 意图中枢 / 知识检索",
}


def ensure_runtime() -> Path:
    if not (CACHE / "bin" / "archify.mjs").exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(["rsync", "-az", ARCHIFY_REMOTE, str(CACHE) + "/"], check=True)
    return CACHE


def _conn_label_pos(components: list[dict], e: dict) -> dict:
    """垂直连接标签放右侧（labelDx），水平连接标签放下方（labelDy），避开组件。"""
    pos = {c["id"]: c.get("pos") for c in components}
    fa, ta = pos.get(e.get("from", "")), pos.get(e.get("to", ""))
    if fa and ta and abs(fa[0] - ta[0]) <= 40:
        return {"labelDx": 150}
    return {"labelDy": 30}


def build_candidate(arch: dict, project: str) -> dict:
    """ARCH → Archify candidate；自动补 owner tag 与 security-group（deployment-ownership 必需）。"""
    cand = {
        "schema_version": 1,
        "diagram_type": "architecture",
        "meta": {
            "title": TITLES.get(project, project),
            "subtitle": SUBTLES.get(project, ""),
            "output": f"{project}-arch.html",
            "visual_preset": "blueprint",
            "animation": "trace",
            "quality_profile": "showcase",
            "engineering_profile": "deployment-ownership",
        },
        "components": [],
        "boundaries": [],
        "connections": [],
    }
    for c in arch.get("components", []):
        comp = {
            "id": c["id"],
            "type": c.get("type", "backend"),
            "label": c.get("label", c["id"]),
        }
        if c.get("sublabel"):
            comp["sublabel"] = c["sublabel"]
        if c.get("pos"):
            comp["pos"] = c["pos"]
            comp["size"] = [120, 60]
        if project == "cluster":
            comp["tag"] = "集群"
        else:
            comp["tag"] = arch.get("owner", "产线")
        cand["components"].append(comp)
    # 缺 pos 的组件自动网格布局；有 pos 的保留
    missing = [comp for comp in cand["components"] if "pos" not in comp]
    if missing:
        COLS = 2 if len(missing) <= 4 else (4 if len(missing) >= 10 else 3)
        CELL_W, CELL_H, GAP_X, GAP_Y = 120, 60, 200, 170
        for i, comp in enumerate(missing):
            col = i % COLS
            row = i // COLS
            comp["pos"] = [40 + col * (CELL_W + GAP_X), 60 + row * (CELL_H + GAP_Y)]
            comp["size"] = [CELL_W, CELL_H]
    _db_ids = {c["id"] for c in cand["components"] if c.get("type") == "database"}
    non_cloud = [c["id"] for c in cand["components"] if c.get("type") != "cloud"]
    _sg_wrap = set(_db_ids) or set(non_cloud) if not _db_ids else set(_db_ids)
    _conns = []
    for e in arch.get("connections", []):
        conn = {"from": e.get("from", ""), "to": e.get("to", "")}
        # mechanism label：跨 security-group 边界才保留（deployment-ownership 要求）；其余去 label 减冲突
        _cross = (e.get("from") in _sg_wrap) != (e.get("to") in _sg_wrap)
        if e.get("label") and _cross:
            conn["label"] = e["label"]
            conn.update(_conn_label_pos(cand["components"], e))
        if e.get("variant"):
            conn["variant"] = e["variant"]
        _conns.append(conn)
    cand["connections"] = _conns
    # deployment-ownership：所有组件必须在 region 内；database 再套 security-group（同一共享 region）
    ids = [c["id"] for c in cand["components"]]
    cand["boundaries"].append({"kind": "region", "label": "运行域", "wraps": list(ids)})
    db_ids = [c["id"] for c in cand["components"] if c["type"] == "database"]
    if db_ids:
        cand["boundaries"].append({"kind": "security-group", "label": "数据私网", "wraps": db_ids})
    else:
        non_cloud = [c["id"] for c in cand["components"] if c.get("type") != "cloud"]
        if non_cloud:
            cand["boundaries"].append({"kind": "security-group", "label": "内网", "wraps": non_cloud})
    return cand


def main() -> None:
    projects = sys.argv[1:] or list(TITLES.keys())
    ensure_runtime()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    index_path = ARCH_DIR / "index.json"
    index = json.loads(index_path.read_text())
    today = date.today().isoformat()

    for project in projects:
        if project == "cluster":
            arch_path = ARCH_DIR / "cluster.json"
        else:
            arch_path = ARCH_DIR / f"{project}.json"
        if not arch_path.exists():
            print(f"!! 缺 ARCH: {project}")
            continue
        arch = json.loads(arch_path.read_text())
        cand = build_candidate(arch, project)
        cand_path = CACHE / f"{project}-candidate.json"
        cand_path.write_text(json.dumps(cand, ensure_ascii=False, indent=2))

        out_html = OUT_DIR / f"{project}-arch.html"
        r = subprocess.run(
            [
                "node",
                "bin/archify.mjs",
                "deliver",
                "architecture",
                str(cand_path),
                str(out_html),
                "--quality",
                "showcase",
            ],
            cwd=CACHE,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            # 自动降级：showcase 过严（标签重叠）→ standard 重试（记录）
            cand["meta"]["quality_profile"] = "standard"
            cand_path.write_text(json.dumps(cand, ensure_ascii=False, indent=2))
            r = subprocess.run(
                [
                    "node",
                    "bin/archify.mjs",
                    "deliver",
                    "architecture",
                    str(cand_path),
                    str(out_html),
                    "--quality",
                    "standard",
                ],
                cwd=CACHE,
                capture_output=True,
                text=True,
            )
            if r.returncode != 0:
                print(f"✗ {project}: deliver 失败（showcase+standard）\n{r.stderr[-300:]}")
                continue
            print(f"△ {project} → {out_html.name}（standard，showcase 过严降级）")
        else:
            print(f"✓ {project} → {out_html.name}（showcase）")
        # 更新 index
        ver = arch.get("arch_version", "1.0.0")
        for g in index["gallery"]:
            if g["project"] == project:
                g["html"] = f"/arch/{project}-arch.html"
                g["arch_version"] = ver
                g["updated_at"] = today
        index["updated_at"] = today

    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    print("index.json 已更新")


if __name__ == "__main__":
    main()
