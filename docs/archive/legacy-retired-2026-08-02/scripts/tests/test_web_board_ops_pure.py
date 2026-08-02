"""窗口 J 前端纯函数单测 — node subprocess（沿用 test_web_js_pure.py 基建）。

覆盖本轮抽取的三个纯函数模块：
- boardFilter.js：看板关键词/大卡状态筛选 + 流转列排序（client-side，后端无 q/status/sort）
- boardLoadGate.js：轮询与移卡竞态门（suppress 挂起重绘 + latest-wins 丢旧响应）
- opsRed.js：运维「只看红灯」聚合（各域红灯/告警条目统一收集）
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
FRONTEND = SCRIPTS / "chat_server" / "frontend"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(
    NODE is None, reason="node 不在 PATH（CI 无 JS 依赖时优雅跳过）"
)


def _run_pure(module_rel: str, body: str) -> None:
    js = FRONTEND / module_rel
    code = (
        "const assert = (c, m) => { if (!c) throw new Error(m); };\n"
        "import * as m from '" + str(js) + "';\n" + body
    )
    r = subprocess.run(
        [NODE, "--input-type=module", "-e", code],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 0, r.stderr + r.stdout


# ── boardFilter：关键词 ─────────────────────────────────────────────


def test_board_filter_keyword_matches():
    """关键词：空/空白 → 全过；大小写不敏感；命中 id/title/parent_id/description。"""
    _run_pure(
        "js/boardFilter.js",
        r"""
        assert(m.matchesKeyword({ id: 't1', title: '修复登录', description: 'desc' }, '') === true, '空关键词全过');
        assert(m.matchesKeyword({ id: 't1', title: '修复登录' }, '   ') === true, '空白关键词全过');
        assert(m.matchesKeyword(null, 'x') === false, 'null task 不匹配');
        assert(m.matchesKeyword({ id: 't1', title: '修复登录', description: 'handle login' }, 'LOGIN') === true, '大小写不敏感');
        assert(m.matchesKeyword({ id: 'ep-123', title: 'x' }, 'ep-123') === true, '命中 id');
        assert(m.matchesKeyword({ id: 't1', title: 'x', parent_id: 'EP1' }, 'ep1') === true, '命中 parent_id');
        assert(m.matchesKeyword({ id: 't1', title: 'x', description: '重构 relay 路由' }, 'relay') === true, '命中 description');
        assert(m.matchesKeyword({ id: 't1', title: 'x' }, '不存在的词') === false, '未命中');
        """,
    )


# ── boardFilter：大卡状态筛选 ───────────────────────────────────────


def test_board_filter_split_status():
    """大卡 split_status 筛选：空 → 全过；别名（active/blocked）归一匹配。"""
    _run_pure(
        "js/boardFilter.js",
        r"""
        const epics = [
          { id: 'a', split_status: 'pending' },
          { id: 'b', split_status: 'running' },
          { id: 'c', split_status: 'active' },   // 别名 → running
          { id: 'd', split_status: 'failed' },
          { id: 'e', split_status: 'blocked' },  // 别名 → failed
          { id: 'f', split_status: 'done' },
          { id: 'g' },                           // 缺省 → pending
        ];
        assert(m.filterEpicsBySplit(epics, '').length === 7, '空状态全过');
        assert(m.filterEpicsBySplit(epics, 'running').length === 2, 'running 含 active 别名');
        assert(m.filterEpicsBySplit(epics, 'failed').length === 2, 'failed 含 blocked 别名');
        assert(m.filterEpicsBySplit(epics, 'done').length === 1, 'done');
        assert(m.filterEpicsBySplit(epics, 'planned').length === 0, 'planned 无命中');
        assert(m.filterEpicsBySplit(null, 'done').length === 0, 'null → []');
        """,
    )


# ── boardFilter：排序 ───────────────────────────────────────────────


def test_board_sort_tasks():
    """流转列排序：默认 created_at 升序（与服务端一致）、updated 降序、title 中文；非变异。"""
    _run_pure(
        "js/boardFilter.js",
        r"""
        const tasks = [
          { id: 'b', title: 'Beta',   created_at: '2026-08-01T10:00:00', updated_at: '2026-08-02T10:00:00' },
          { id: 'a', title: 'Alpha',  created_at: '2026-08-01T09:00:00', updated_at: '2026-08-01T10:00:00' },
          { id: 'c', title: 'Charlie', created_at: '2026-08-01T11:00:00', updated_at: '2026-08-03T10:00:00' },
        ];
        const def = m.sortTasks(tasks, 'default').map((t) => t.id).join('');
        assert(def === 'abc', '默认 created_at 升序: ' + def);
        const upd = m.sortTasks(tasks, 'updated').map((t) => t.id).join('');
        assert(upd === 'cba', 'updated 降序: ' + upd);
        const title = m.sortTasks(tasks, 'title').map((t) => t.id).join('');
        assert(title === 'abc', 'title 排序(ASCII): ' + title);
        assert(m.sortTasks(tasks, '').map((t) => t.id).join('') === 'abc', '空 key → 默认');
        assert(tasks.length === 3, '不修改入参');
        assert(m.sortTasks(null, 'default').length === 0, 'null → []');
        // 中文标题不炸（ICU 排序结果由 locale 决定，只断言稳定返回）
        const zh = m.sortTasks(
          [{ id: 'x', title: '中文字卡' }, { id: 'y', title: 'Alpha' }],
          'title'
        );
        assert(zh.length === 2, '中文标题排序不炸');
        """,
    )


# ── boardLoadGate：竞态门 ──────────────────────────────────────────


def test_board_load_gate_sequence():
    """竞态门：suppress 期间 begin → null（轮询挂起）；旧 seq 非最新（丢旧响应）。"""
    _run_pure(
        "js/boardLoadGate.js",
        r"""
        const g = m.createLoadGate();
        assert(g.begin() === 1, '首请求 seq=1');
        assert(g.begin() === 2, 'seq 自增');
        assert(g.isLatest(1) === false, '旧 seq 非最新');
        assert(g.isLatest(2) === true, '新 seq 最新');
        g.suppress();
        assert(g.begin() === null, 'suppress 期间挂起新请求');
        assert(g.isSuppressed() === true, 'isSuppressed=true');
        g.suppress();
        g.resume();
        assert(g.isSuppressed() === true, '嵌套 suppress 计数');
        g.resume();
        assert(g.isSuppressed() === false, '全部 resume 后解除');
        const s = g.begin();
        assert(s === 3, 'resume 后恢复 seq: ' + s);
        assert(g.isLatest(2) === false && g.isLatest(3) === true, 'latest-wins');
        """,
    )


def test_board_load_gate_resume_bounds():
    """resume 越界不把计数打到负；未 suppress 可正常请求。"""
    _run_pure(
        "js/boardLoadGate.js",
        r"""
        const g = m.createLoadGate();
        g.resume();
        g.resume();
        assert(g.isSuppressed() === false, 'resume 不越界为负');
        assert(g.begin() !== null, '未 suppress 可正常请求');
        """,
    )


# ── opsRed：只看红灯聚合 ───────────────────────────────────────────


def test_ops_red_collect_empty():
    """空/缺键 agg → []（不抛）；redCount 为 0。"""
    _run_pure(
        "js/opsRed.js",
        r"""
        assert(JSON.stringify(m.collectRedItems(null)) === '[]', 'null → []');
        assert(JSON.stringify(m.collectRedItems({})) === '[]', '{} → []');
        assert(m.redCount(m.collectRedItems({})) === 0, 'redCount 0');
        """,
    )


def test_ops_red_collect_domains():
    """各域红灯收集：风险/端口(关键 vs 普通)/机器/部署/工作区异常/relay；engine 去重。"""
    _run_pure(
        "js/opsRed.js",
        r"""
        const agg = {
          risks: { risks: [
            { id: 'engine-down', severity: 'high', title: 'Engine 停', detail: 'd' },
            { severity: 'medium', title: '磁盘占用', detail: '', workspace: 'qb' },
          ]},
          overview: {
            down_ports: [{ port: 7777, name: 'Hub', label: 'h' }, { port: 9999, name: 'x', label: 'l' }],
            machines: [{ name: 'm1', ip: '10.0.0.1', role: 'worker', reachable: false },
                       { name: 'm2', ip: '10.0.0.2', role: 'worker', reachable: true }],
          },
          deploy: { targets: [
            { name: 't1', ip: '1.2.3.4', role: 'svc', reachable: false },
            { name: 't2', ip: '1.2.3.5', role: 'svc', reachable: true, checks: [{ label: 'api', alive: false }] },
          ]},
          workspaces: { workspaces: [{ workspace: 'qb', abnormal: 2, path: '/x' }, { workspace: 'ok', abnormal: 0 }] },
          domains: { relay: { ok: false, error: 'conn refused' } },
          control: { engine_running: false },
        };
        const items = m.collectRedItems(agg);
        assert(items.length === 9, '总条目 9: ' + items.length);
        const byDomain = {};
        items.forEach((it) => { (byDomain[it.domain] = byDomain[it.domain] || []).push(it); });
        assert(byDomain.risks.length === 2, 'risks 2');
        assert(byDomain.risks[0].severity === 'high', 'high 风险');
        assert(byDomain.risks[1].severity === 'warn', 'medium → warn');
        assert(byDomain.ports.length === 2, 'ports 2');
        assert(byDomain.ports[0].severity === 'high', '关键端口 7777 → high');
        assert(byDomain.ports[1].severity === 'warn', '普通端口 → warn');
        assert(byDomain.machines.length === 1, '仅不可达机器');
        assert(byDomain.deploy.length === 2, '部署目标不可达 + 检查 down');
        assert(byDomain.deploy[0].severity === 'high' && byDomain.deploy[1].severity === 'warn', '部署 severity');
        assert(byDomain.workspaces.length === 1, '仅 abnormal 工作区');
        assert(byDomain.relay.length === 1 && byDomain.relay[0].severity === 'warn', 'relay warn');
        assert(!byDomain.engine, 'engine-down 已由 risks 覆盖，不重复报');
        assert(m.redCount(items) === 9, 'redCount 汇总');
        """,
    )
