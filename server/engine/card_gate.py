"""卡校验门（ccc-plan-053 阶段2）：engine 派发前强制校验 DSH 产卡。

只对卡头「执行体：DSH」的卡做全量校验（053 全链流程中全部卡经 DSH 出卡）；
存量/测试夹具卡（其他执行体）不适用新卡头格式，直接放行。

五项校验（方案钉死，不得扩减）：
1. 必填字段齐全：关联 / 执行体 / 验收 / 状态 / 派发 / 项目 / 日期
2. 状态=待分派
3. 项目前缀在项目 registry（docs/projects/registry.yaml）
4. 验收标准 ≥1 条可核条目
5. 范围段列出的路径在仓内存在

非法卡处置：待分派卡落「作废」（状态机 TODO→REJECTED 非法转移，VOIDED 是
待分派卡唯一合法出池终态，语义=打回不入池）+ ledger `card_gate_reject` 告警
+ alerts 落盘留痕。
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.board.audit_ledger import record_action
from server.board.registry import forbidden_prefixes, load_projects
from server.engine.gates import GateResult
from server.engine.task import State, Work

HEADER_FIELDS = ("关联", "执行体", "验收", "状态", "派发", "项目", "日期")
REQUIRED_SECTIONS = ("目标", "实现要求", "红线", "范围", "步骤", "验收标准")
_TITLE_RE = re.compile(r"^# 任务卡 [A-Za-z]+\d+ · \S")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _header_fields(text: str) -> dict[str, str] | None:
    """解析卡头「> 关联：… · 执行体：…」引用行字段（前 6 行内首个引用行）。"""
    for line in text.splitlines()[:6]:
        s = line.strip()
        if not s.startswith(">"):
            continue
        fields: dict[str, str] = {}
        for part in s.lstrip(">").strip().split("·"):
            if "：" in part:
                key, value = part.split("：", 1)
                fields[key.strip()] = value.strip()
        return fields
    return None


def _section_lines(text: str, name: str) -> list[str]:
    """取 `## <name>` 小节正文行（到下一个 `## ` 或文末）。"""
    inside = False
    out: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.startswith(f"## {name}")
            continue
        if inside:
            out.append(line)
    return out


def _has_content(lines: list[str]) -> bool:
    return any(line.strip() for line in lines)


def validate_card(
    card_path: str | Path,
    *,
    repo_root: str | Path | None = None,
    project_prefixes: set[str] | None = None,
) -> list[str]:
    """校验单卡，返回问题清单（空=合法）。

    project_prefixes 供测试注入；None 时读项目 registry（读失败按平台故障
    跳过前缀项，不因平台问题批量打回业务卡）。
    """
    path = Path(card_path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"卡文件不可读: {exc}"]

    problems: list[str] = []
    if not _TITLE_RE.match(text):
        problems.append("首行须为「# 任务卡 <prefix><NNN> · 一句话标题」")

    fields = _header_fields(text) or {}
    if _header_fields(text) is None:
        problems.append("卡头缺「> 关联：…」引用行")
    missing = [f for f in HEADER_FIELDS if not fields.get(f)]
    if missing:
        problems.append(f"卡头缺必填字段: {'、'.join(missing)}")
    if fields.get("状态") != "待分派":
        problems.append(f"状态须为「待分派」，实际「{fields.get('状态', '') or '空'}」")
    if fields.get("日期") and not _DATE_RE.match(fields["日期"]):
        problems.append(f"日期格式须为 YYYY-MM-DD，实际「{fields['日期']}」")

    match = re.match(r"^([A-Za-z]+)\d+", path.stem)
    prefix = match.group(1) if match else ""
    if project_prefixes is None:
        try:
            project_prefixes = {p.prefix for p in load_projects()}
        except Exception:
            project_prefixes = None  # 平台故障：跳过前缀项
    if project_prefixes is not None:
        if prefix not in project_prefixes:
            problems.append(f"卡号前缀「{prefix or '空'}」不在项目 registry")
        elif fields.get("项目") and fields["项目"] != prefix:
            problems.append(f"卡头项目「{fields['项目']}」与卡号前缀「{prefix}」不一致")

    # A5：禁卡前缀（FORBIDDEN_CARD_PREFIXES）——即便前缀在 registry，命中禁表即拒单
    # （手工放卡 docs/dispatch/ccc/ 直达派发绕行门禁的断根：引擎队列与 card_gate 同源判据）
    if prefix:
        try:
            forbidden = forbidden_prefixes()
        except Exception:
            forbidden = frozenset()  # 平台故障：跳过禁表项，不因平台问题误伤
        if prefix.lower() in forbidden:
            problems.append(f"卡号前缀「{prefix}」在禁卡表（FORBIDDEN_CARD_PREFIXES）——禁止经 CCC Engine 派发（平台自研/独立轨道）")

    for name in REQUIRED_SECTIONS:
        if not _has_content(_section_lines(text, name)):
            problems.append(f"缺必备段或段为空:「{name}」")

    acceptance = [
        line.strip()
        for line in _section_lines(text, "验收标准")
        if line.strip() and not line.strip().startswith(("（", "("))
    ]
    if not acceptance:
        problems.append("验收标准须 ≥1 条可核条目")

    root = Path(repo_root) if repo_root else Path.cwd()
    for raw in _section_lines(text, "范围"):
        item = raw.strip().lstrip("-*").strip().strip("`").strip()
        if not item or item.startswith(("（", "(")):
            continue  # 空行与括注说明不视为路径
        if not (root / item).exists():
            problems.append(f"范围路径不存在: {item}")
    return problems


def _write_alert(log_dir: Path, card_id: str, problems: list[str]) -> None:
    """告警落盘（同文件覆盖写，与 short-session 告警同模式）。"""
    try:
        alerts_dir = log_dir / "alerts"
        alerts_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.fromtimestamp(time.time(), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        (alerts_dir / "card-gate.txt").write_text(
            f"[{stamp}] 卡校验门拦截: {card_id}\n" + "\n".join(f"- {p}" for p in problems) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def enforce_card_gate(
    work: Work,
    store: Any,
    log_dir: Path,
    *,
    repo_root: str | Path | None = None,
    project_prefixes: set[str] | None = None,
) -> GateResult:
    """派发门禁本体：DSH 卡非法 → 作废 + ledger 告警；非 DSH 卡直接放行。"""
    card_path = Path(work.card_path) if work.card_path else None
    text = ""
    if card_path is not None:
        try:
            text = card_path.read_text(encoding="utf-8")
        except OSError:
            text = ""
    fields = _header_fields(text) if text else None
    # A5：禁卡前缀断根——手工放卡（docs/dispatch/ccc/ 等禁前缀）无论执行体一律拒单
    # （new-card.sh CLI 与 validate.py 已拦，但引擎队列/手工放卡可绕行；此处与队列同源判据）
    if card_path is not None:
        stem_prefix = re.match(r"^([A-Za-z]+)\d+", card_path.stem)
        if stem_prefix:
            try:
                forbidden = forbidden_prefixes()
            except Exception:
                forbidden = frozenset()  # 平台故障：跳过禁表项，不因平台问题误伤
            if stem_prefix.group(1).lower() in forbidden:
                problems = [f"卡号前缀「{stem_prefix.group(1)}」在禁卡表（FORBIDDEN_CARD_PREFIXES）——禁止经 CCC Engine 派发"]
                record_action("card_gate_reject", work.id, source="engine", detail=problems[0][:300])
                if log_dir:
                    _write_alert(Path(log_dir), work.id, problems)
                work.transition(State.VOIDED, problems=[f"卡校验门拦截（非法卡不入池）: {p}" for p in problems])
                store.save_work(work)
                return GateResult(passed=False, reason="card_gate_forbidden")
    if fields is None or fields.get("执行体") != "DSH":
        return GateResult(passed=True)  # 非 DSH 产卡不走新校验门
    if work.state is not State.TODO:
        return GateResult(passed=True)  # 门禁只拦待分派卡

    problems = validate_card(card_path or "", repo_root=repo_root, project_prefixes=project_prefixes)
    if not problems:
        return GateResult(passed=True)

    record_action("card_gate_reject", work.id, source="engine", detail="; ".join(problems)[:300])
    if log_dir:
        _write_alert(Path(log_dir), work.id, problems)
    work.transition(State.VOIDED, problems=[f"卡校验门拦截（非法卡不入池）: {p}" for p in problems])
    store.save_work(work)
    return GateResult(passed=False, reason="card_gate")
