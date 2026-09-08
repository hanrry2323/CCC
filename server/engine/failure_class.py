"""server/engine/failure_class.py — 失败分类 + 统一路由 + infra 环境自检（v2.0 P2）。

三类失败（老板定稿 v2.0 宪章 P2 阶段）：
- INFRA    「infra」    通道/环境/超时/网络——冷却 + 环境自检，不消耗预算
- BUSINESS 「business」 代码/测试/门禁不通过——打回 + 计 reject 预算
- PROTOCOL 「protocol」 verdict 格式/schema 非法——一次修复轮，仍失败计预算

phase2 与 engine 收单共用本模块为单一分类源；散乱的 ``transient_probe`` 旗标/
关键字判断收敛为 ``classify_failure``。预算字段（sidecar 结构化）：
- ``business_reject_count``：business 类打回计数（上限 3，默认）
- ``protocol_retry_count``：protocol 类失败计数（上限 3，默认）
- ``awaiting_human`` / ``exhausted_class``：预算耗尽 → 待人工结构化终态
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from server.engine.task import State

if TYPE_CHECKING:
    from server.engine.store import BoardStore
    from server.engine.task import Work

logger = logging.getLogger("ccc.engine.failure_class")

# 每类预算默认上限 3；只紧不松（cfg 可调但默认不放宽）
DEFAULT_BUDGET = 3


class FailureClass(StrEnum):
    INFRA = "infra"
    BUSINESS = "business"
    PROTOCOL = "protocol"


def classify_failure(
    *,
    retryable: bool = False,
    protocol_failure: bool = False,
    reasons: list[str] | None = None,
) -> FailureClass:
    """统一失败分类：protocol（verdict 协议非法）> infra（重试/网络/超时）> business。

    - ``protocol_failure``：verdict 格式/schema 非法（fail-closed 语义不变）。
    - ``retryable``：既有 is_retryable_failure 判定的基建故障。
    - 其余按理由文本含基建关键词兜底判 infra，否则 business。
    """
    joined = " ".join(str(r) for r in (reasons or [])).lower()
    if protocol_failure or "protocol：" in joined or "protocol:" in joined:
        return FailureClass.PROTOCOL
    if retryable:
        return FailureClass.INFRA
    # 无歧义的基建标记才判 infra；「超时」等由 is_retryable_failure 日志扫描精确判定
    # （engine 会话超时在无 infra 日志特征时属业务重试/打回，见 test_engine_main 超时用例）。
    infra_kw = (
        "基础设施",
        "worktree",
        "网络",
        "网关",
        "通道",
        "预检",
        "上游",
    )
    if any(kw in joined for kw in infra_kw):
        return FailureClass.INFRA
    return FailureClass.BUSINESS


def budget_limit(cfg: dict, cls: FailureClass, default: int = DEFAULT_BUDGET) -> int:
    """读取该类预算上限；只紧不松（缺失/非法回落 default，不向下放宽）。"""
    key = {
        FailureClass.BUSINESS: "PHASE2_REJECT_MAX_STRIKES",
        FailureClass.PROTOCOL: "PHASE2_PROTOCOL_MAX_STRIKES",
    }.get(cls)
    if not key:
        return default
    try:
        return max(1, int(cfg.get(key) or default))
    except (TypeError, ValueError):
        return default


def read_budget_count(current: dict, cls: FailureClass) -> int:
    """读该卡该类预算计数（business 兼容旧 reject_count 字段）。"""
    if cls is FailureClass.PROTOCOL:
        return int(current.get("protocol_retry_count") or 0)
    return int(current.get("business_reject_count") or current.get("reject_count") or 0)


def budget_exhausted(current: dict, cls: FailureClass, cfg: dict) -> bool:
    """该类计数是否已达上限。"""
    return read_budget_count(current, cls) >= budget_limit(cfg, cls)


def increment_budget(
    log_dir: str | Path,
    card_id: str,
    cls: FailureClass,
    cfg: dict,
) -> tuple[int, bool]:
    """递增该类预算计数并写 sidecar；返回 (count, exhausted)。

    - business 类同时写兼容旧字段 ``reject_count``（存量消费方仍可读）；
    - 达到预算上限 → 同时写 ``reject_budget_exhausted=true`` + ``awaiting_human``。
    """
    from server.engine.runtime_state import read_card_state, write_card_state  # noqa: PLC0415

    current = read_card_state(log_dir).get(str(card_id), {})
    count = read_budget_count(current, cls) + 1
    limit = budget_limit(cfg, cls)
    exhausted = count >= limit
    kw: dict[str, Any] = {}
    if cls is FailureClass.BUSINESS:
        kw["business_reject_count"] = count
        kw["reject_count"] = count
    else:
        kw["protocol_retry_count"] = count
    kw["reject_budget_exhausted"] = exhausted
    if exhausted:
        kw["awaiting_human"] = True
        kw["exhausted_class"] = cls.value
    write_card_state(log_dir, str(card_id), **kw)
    return count, exhausted


def mark_awaiting_human(
    log_dir: str | Path,
    card_id: str,
    cls: FailureClass,
    exhausted: bool = False,
    count: int | None = None,
) -> None:
    """预算耗尽 → sidecar 结构化终态：awaiting_human + exhausted_class。"""
    from server.engine.runtime_state import write_card_state  # noqa: PLC0415

    write_card_state(
        log_dir,
        str(card_id),
        reject_budget_exhausted=exhausted,
        awaiting_human=exhausted,
        exhausted_class=cls.value if exhausted else None,
        business_reject_count=count if cls is FailureClass.BUSINESS and count is not None else None,
        protocol_retry_count=count if cls is FailureClass.PROTOCOL and count is not None else None,
    )


def terminal_reject_state(cls: FailureClass) -> str:
    """预算耗尽的打回卡头：与「打回」同一 base_state，reason 标注待人工。"""
    label = "PROTOCOL" if cls is FailureClass.PROTOCOL else "REJECT"
    return f"打回（{label} 预算耗尽，待人工）"


# ───────────────────────── infra 环境自检（只读 · 不修改环境）─────────────────────────


def _probe_http_status(url: str, timeout: float = 5.0) -> int | None:
    """GET 探活返回 HTTP code；连接失败返回 None。"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:  # noqa: BLE001
        return None


def normalize_base_root(url: str) -> str:
    """ANTHROPIC_BASE_URL 归一：裸根/完整端点统一到根（http://host:port）。

    ``http://127.0.0.1:3456/v1/messages`` → ``http://127.0.0.1:3456``。
    连续剥掉已知端点段（``/messages``、``/v1``、``/api``）直至不再命中。
    """
    url = (url or "").strip().rstrip("/")
    changed = True
    while changed:
        changed = False
        for suffix in ("/messages", "/v1", "/api"):
            if url.endswith(suffix):
                url = url[: -len(suffix)].rstrip("/")
                changed = True
    return url


def run_infra_selfcheck(cfg: dict, *, card_id: str = "", worktree: str = "") -> dict[str, Any]:
    """infra 类失败触发的四项环境自检（只读），结果追加到 ledger。

    1. 3456 通道连通（``<root>/v1/models`` HTTP code）；
    2. worktree ``.venv/bin/pytest`` 存在（fallback 仓内 ``.venv-hub/bin/pytest``）；
    3. ``ANTHROPIC_BASE_URL`` 值（归一后的根）；
    4. verdict 工件目录（EXECUTOR_LOG_DIR）写入权限。

    自检只读不修改环境；结果 ``all_ok=true`` → 归因执行体侧；``any_fail`` →
    归因基础设施侧（调用方升级告警）。异常不阻断主流程。
    """
    results: dict[str, Any] = {}

    # 1. 3456 通道连通（模型探针端点）
    try:
        from server.engine.dsh_gateway import _gateway_channel

        base_url, model = _gateway_channel()
    except Exception:  # noqa: BLE001
        base_url, model = "", ""
    root = normalize_base_root(base_url)
    status = _probe_http_status(f"{root}/v1/models")
    results["channel_3456"] = {"root": root, "model": model, "http_code": status}
    results["channel_ok"] = status is not None and 200 <= status < 500

    # 2. worktree .venv/bin/pytest 存在（fallback 仓内 .venv-hub/bin/pytest）
    pytest_ok = False
    candidates: list[Path] = []
    if worktree:
        candidates.append(Path(worktree).expanduser() / ".venv" / "bin" / "pytest")
    try:
        candidates.append(Path(__file__).resolve().parents[2] / ".venv-hub" / "bin" / "pytest")
    except Exception:  # noqa: BLE001
        pass
    for cand in candidates:
        if cand.is_file():
            pytest_ok = True
            break
    results["worktree_pytest"] = {"path": str(candidates[0] if candidates else ""), "exists": pytest_ok}

    # 3. ANTHROPIC_BASE_URL 值（归一后）
    results["anthropic_base_url"] = {"normalized_root": root or (base_url or "")}

    # 4. verdict 工件目录写入权限
    log_dir = ""
    writable = False
    try:
        from server.engine.logpaths import audit_log_dir  # noqa: PLC0415

        log_dir = audit_log_dir(cfg)
        log_dir.mkdir(parents=True, exist_ok=True)
        writable = os.access(str(log_dir), os.W_OK)
    except Exception:  # noqa: BLE001
        # log_dir 提前初始化，异常路径照常返回 writable=False，不抛 UnboundLocalError。
        writable = False
    results["verdict_dir_writable"] = {"path": str(log_dir), "writable": writable}

    results["all_ok"] = bool(results.get("channel_ok") and pytest_ok and writable)
    try:
        from server.board.audit_ledger import record_action  # noqa: PLC0415

        record_action(
            "infra_selfcheck",
            card_id or "gateway",
            source="phase2",
            detail=json.dumps(results, ensure_ascii=False),
            failure_class=FailureClass.INFRA.value,
        )
    except Exception:  # noqa: BLE001
        logger.exception("infra 自检 ledger 追加失败（不阻断）")
    return results


def _infra_cooldown_seconds(cfg: dict[str, Any]) -> int:
    try:
        return max(0, int(cfg.get("EXECUTOR_INFRA_COOLDOWN_SECONDS") or 60))
    except (TypeError, ValueError):
        return 60


def _hold_infra_failure(
    store: BoardStore,
    work: Work,
    log_dir: Path,
    reasons: list[str],
    cfg: dict[str, Any],
    *,
    phase: str,
    infra_count: int | None = None,
    cooldown_seconds: int | None = None,
) -> None:
    """基础设施/引擎侧故障：不进业务重试预算、不打回；记冷却时间，冷却后自动续跑。

    - phase=audit：卡保持「已回写」，机审队列冷却后自动续审。
    - phase=run：卡回「待分派」，派发队列冷却后自动重派。

    （2026-09-05 解环：自 main.py 归位本模块——infra 挂起属失败分类路由域，
    phase2 不再为它依赖 engine.main。）
    """
    from datetime import datetime, timedelta, timezone

    strikes = infra_count if infra_count is not None else 0
    power = max(0, strikes - 1)
    base = (
        max(0, int(cooldown_seconds))
        if cooldown_seconds is not None
        else _infra_cooldown_seconds(cfg)
    )
    cooldown = base * (2**power)

    try:
        max_cooldown = int(cfg.get("EXECUTOR_INFRA_COOLDOWN_MAX_SECONDS") or 1800)
    except (TypeError, ValueError):
        max_cooldown = 1800

    cooldown = min(cooldown, max_cooldown)

    until = (
        (datetime.now(timezone.utc) + timedelta(seconds=cooldown)).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    # P2：infra 类失败触发环境自检（只读），结果追加 ledger 供归因。
    try:
        selfcheck = run_infra_selfcheck(cfg, card_id=work.id)
        if not selfcheck.get("all_ok"):
            from server.board.audit_ledger import record_action  # noqa: PLC0415

            record_action(
                "infra_selfcheck_fail",
                work.id,
                source="engine",
                detail=f"infra 自检 any_fail（归因基础设施侧）: {selfcheck}",
                failure_class="infra",
            )
    except Exception:
        logger.exception("infra 自检执行异常（不阻断冷却）")
    if phase == "run" and work.state is State.RUNNING:
        try:
            work.transition(State.TODO, problems=reasons)
        except Exception:
            pass
    try:
        store.save_work(work)
    except Exception:
        pass
    from server.engine.runtime_state import write_card_state

    if infra_count is None:
        infra_count = 0

    write_card_state(
        log_dir,
        work.id,
        state=work.state.value,
        retry_count=work.retry_count,
        reason=reasons[0] if reasons else "基础设施故障",
        infra_cooldown_until=until,
        infra_count=infra_count,
    )
    logger.warning(
        "基础设施失败（冷却 %ds 后自动续%s，不计重试预算）: work=%s reason=%s",
        cooldown,
        "审" if phase == "audit" else "派",
        work.id,
        reasons[0] if reasons else "",
    )
