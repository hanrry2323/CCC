"""前端纯函数单测 — node subprocess（沿用 test_epic_five_state.py 的 node 用法）。

覆盖窗口 A2 抽取的三个纯函数模块：
- boardSigs.js：epic 列 diff 签名（子卡发布 → 签名变化，进度条刷新依据）
- chatErrors.js：友好错误文案 + 重试目标选择
- opsSelectors.js：日审报告选择（兼容 items/reviews/reports）
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


def test_board_sigs_epic_progress_fingerprint():
    """子卡进入 released 集合 → epic 签名变化（epic 进度条刷新依据）。"""
    _run_pure(
        "js/boardSigs.js",
        r"""
        const tasks = [
          { id: 'ep1', split_status: 'running', updated_at: 't0', child_ids: ['w1', 'w2'] },
        ];
        const sigA = m.epicColumnSig(tasks, new Set(['w1']));
        const sigB = m.epicColumnSig(tasks, new Set(['w1', 'w2']));
        assert(sigA !== sigB, '子卡发布后签名必须变化');
        assert(m.releasedChildCount(tasks[0], new Set(['w1', 'w2'])) === 2, 'count=2');
        assert(m.releasedChildCount(tasks[0], new Set(['x'])) === 0, 'none released');
        assert(m.releasedChildCount({ id: 'ep2' }, new Set()) === 0, 'no child_ids');
        assert(m.releasedChildCount(null, new Set()) === 0, 'null task');
        """,
    )


def test_chat_errors_friendly_mapping():
    """HTTP 状态码 → 友好中文错误文案（streamChat 原 inline 映射抽出）。"""
    _run_pure(
        "js/chatErrors.js",
        r"""
        assert(m.friendlyChatError(401, 'x').indexOf('鉴权') >= 0, '401 文案');
        assert(m.friendlyChatError(403, 'denied') === 'denied', '403 用 detail');
        assert(m.friendlyChatError(403, null).indexOf('project_path') >= 0, '403 兜底');
        assert(m.friendlyChatError(503, null).indexOf('不可达') >= 0, '503 兜底');
        assert(m.friendlyChatError(429, 'x').indexOf('并发') >= 0, '429 文案');
        assert(m.friendlyChatError(500, null).indexOf('HTTP 500') >= 0, '兜底带状态码');
        assert(m.friendlyChatError(500, 'boom') === 'boom', '兜底用 detail');
        """,
    )


def test_chat_errors_last_user_message():
    """重试目标：取最后一条 user 消息。"""
    _run_pure(
        "js/chatErrors.js",
        r"""
        assert(m.lastUserMessage([]) === null, 'empty');
        assert(m.lastUserMessage(null) === null, 'null');
        const msgs = [
          { role: 'user', content: 'a' },
          { role: 'assistant', content: 'r' },
          { role: 'user', content: 'b' },
          { role: 'assistant', content: 'x' },
        ];
        const last = m.lastUserMessage(msgs);
        assert(last !== null && last.content === 'b', '取最后一条 user');
        """,
    )


def test_ops_selectors_daily_items():
    """日审报告选择：items/reviews/reports 三键任一生效，缺失回退 []。"""
    _run_pure(
        "js/opsSelectors.js",
        r"""
        assert(JSON.stringify(m.dailyItems({ items: [1] })) === '[1]', 'items 生效');
        assert(JSON.stringify(m.dailyItems({ reviews: [2] })) === '[2]', 'reviews 生效');
        assert(JSON.stringify(m.dailyItems({ reports: [3] })) === '[3]', 'reports 生效');
        assert(JSON.stringify(m.dailyItems({ items: null, reports: [3] })) === '[3]', 'reports 兜底(null items)');
        assert(JSON.stringify(m.dailyItems({ reports: [3] })) === '[3]', 'reports 兜底(无 items)');
        assert(JSON.stringify(m.dailyItems(null)) === '[]', 'null → []');
        assert(JSON.stringify(m.dailyItems({})) === '[]', '空对象 → []');
        """,
    )


def test_auth_role_and_headers():
    """鉴权纯函数：canWriteRole / authHeaders（窗口 A3）。"""
    _run_pure(
        "js/auth.js",
        r"""
        assert(m.canWriteRole('operator') === true, 'operator 可写');
        assert(m.canWriteRole('viewer') === false, 'viewer 只读');
        assert(m.canWriteRole('') === false, '无角色只读');
        const h = m.authHeaders('tok123');
        assert(h.Authorization === 'Bearer tok123', 'Bearer 头');
        assert(JSON.stringify(m.authHeaders('')) === '{}', '无 token 空头');
        """,
    )


def test_chat_status_conn_state_machine():
    """断连状态机：failure → down（幂等）；recovery → ok（窗口 I）。"""
    _run_pure(
        "js/chatStatus.js",
        r"""
        assert(m.nextConnStatus(m.CONN_OK, 'failure') === m.CONN_DOWN, 'failure → down');
        assert(m.nextConnStatus(m.CONN_DOWN, 'failure') === m.CONN_DOWN, 'down+failure 幂等');
        assert(m.nextConnStatus(m.CONN_DOWN, 'recovery') === m.CONN_OK, 'recovery → ok');
        assert(m.nextConnStatus(m.CONN_OK, 'recovery') === m.CONN_OK, 'ok+recovery 保持');
        """,
    )


def test_chat_status_classify_health():
    """健康判定：正常 models → ok；空 models → empty-models；fetch 失败 → unreachable。"""
    _run_pure(
        "js/chatStatus.js",
        r"""
        assert(
          m.classifyHealth({ fetchFailed: false, payload: { models: ['flash'] } }) === m.HEALTH_OK,
          '正常 models → ok',
        );
        assert(
          m.classifyHealth({ fetchFailed: false, payload: { models: [] } }) === m.HEALTH_EMPTY_MODELS,
          '空 models → empty-models',
        );
        assert(
          m.classifyHealth({ fetchFailed: false, payload: null }) === m.HEALTH_EMPTY_MODELS,
          'payload null → empty-models',
        );
        assert(
          m.classifyHealth({ fetchFailed: false, payload: { models: 'x' } }) === m.HEALTH_EMPTY_MODELS,
          'models 非数组 → empty-models',
        );
        assert(
          m.classifyHealth({ fetchFailed: true, payload: null }) === m.HEALTH_UNREACHABLE,
          'fetch 失败 → unreachable',
        );
        assert(m.classifyHealth(null) === m.HEALTH_UNREACHABLE, 'null → unreachable');
        """,
    )


def test_chat_status_health_warn_text():
    """模型档位警告文案：ok → ''；两种异常态 → 非空。"""
    _run_pure(
        "js/chatStatus.js",
        r"""
        assert(m.healthWarnText(m.HEALTH_OK) === '', 'ok → 无警告');
        assert(m.healthWarnText(m.HEALTH_UNREACHABLE).length > 0, 'unreachable → 有警告');
        assert(m.healthWarnText(m.HEALTH_EMPTY_MODELS).length > 0, 'empty-models → 有警告');
        assert(m.connBannerText().length > 0, '断连横幅文案非空');
        """,
    )


def test_chat_status_wait_hint_text():
    """首包等待提示：超时且无首包 → 文案；有首包/未超时 → ''。"""
    _run_pure(
        "js/chatStatus.js",
        r"""
        assert(m.waitHintText(1000, 12000, false) === '', '未超时 → 空');
        assert(m.waitHintText(12000, 12000, false).length > 0, '超时无首包 → 提示');
        assert(m.waitHintText(20000, 12000, false).length > 0, '超时更长 → 提示');
        assert(m.waitHintText(20000, 12000, true) === '', '有首包 → 空');
        assert(m.waitHintText(0, 0, false).length > 0, 'elapsed=timeout=0 边界 → 提示');
        assert(m.waitHintText(0, 0, true) === '', 'elapsed=0 有首包 → 空');
        """,
    )
