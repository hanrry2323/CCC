"""human_status.py — 把 CCC 板上的英文状态/原因翻译成人话

不依赖 Protocol 扩展。dashboard 直接调这些函数把机器语言变成老板看得懂的话。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


# ── 状态翻译 ──

# 大 phase 名称（5 步开发流程）
PHASE_NAME = {
    1: "需求拆解",
    2: "写代码",
    3: "测试",
    4: "审查",
    5: "发布",
}
PHASE_TOTAL = 5

# status → 第几步
PHASE_INDEX = {
    "backlog":     1,  # 待办
    "planned":     1,  # 还在需求阶段
    "in_progress": 2,  # 写代码
    "testing":     3,
    "verified":    4,
    "released":    5,
    "abnormal":    0,  # 卡住，没有正常 phase
}

# 状态徽章（卡片右上角）
STATUS_PILL = {
    "backlog":     "待办",
    "planned":     "已计划",
    "in_progress": "开发中",
    "testing":     "测试中",
    "verified":    "已验证",
    "released":    "已发布",
    "abnormal":    "异常",
}


# ── 翻译函数 ──

def phase_cn(status: str) -> str:
    """in_progress → 写代码，testing → 测试中，等"""
    idx = PHASE_INDEX.get(status, 0)
    if idx == 0:
        return "卡住了"
    return PHASE_NAME[idx]


def status_pill_cn(status: str) -> str:
    return STATUS_PILL.get(status, status)


def phase_progress(status: str) -> tuple[str, int, int]:
    """返回 (phase 中文名, 第几步, 总步数)"""
    idx = PHASE_INDEX.get(status, 0)
    if idx == 0:
        return ("卡住了", 0, PHASE_TOTAL)
    return (PHASE_NAME[idx], idx, PHASE_TOTAL)


def human_who(task: dict) -> str:
    """谁在做什么 — 人类可读。assignee 空 → 自动化；非空 → "{name} 正在执行" """
    a = task.get("assignee")
    if not a:
        return "由 Claude Code 自动执行"
    return f"{a} 正在执行"


def human_action(status: str) -> str:
    """in_progress → 正在写代码；testing → 正在跑测试"""
    return {
        "backlog":     "等待规划",
        "planned":     "正在规划",
        "in_progress": "正在写代码",
        "testing":     "正在跑测试",
        "verified":    "正在审查",
        "released":    "已发布",
    }.get(status, "")


def elapsed_cn(started_iso: Optional[str], now: Optional[datetime] = None) -> str:
    """已开工多久 — 1 小时 12 分 / 23 分钟 / 45 秒"""
    if not started_iso:
        return "——"
    if now is None:
        now = datetime.now(timezone.utc)
    try:
        started = datetime.fromisoformat(str(started_iso).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return "——"
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    sec = int((now - started).total_seconds())
    if sec < 0:
        sec = 0
    if sec < 60:
        return f"{sec} 秒"
    if sec < 3600:
        m, s = divmod(sec, 60)
        return f"{m} 分 {s} 秒" if s else f"{m} 分钟"
    h, rem = divmod(sec, 3600)
    m = rem // 60
    return f"{h} 小时 {m} 分"


def eta_cn(eta_seconds: Optional[int]) -> str:
    """预计还需 5 分钟 / 1 小时 / ——（无数据）"""
    if not eta_seconds or eta_seconds <= 0:
        return "——"
    if eta_seconds < 60:
        return f"{eta_seconds} 秒"
    if eta_seconds < 3600:
        return f"{eta_seconds // 60} 分钟"
    h, rem = divmod(eta_seconds, 3600)
    m = rem // 60
    return f"{h} 小时 {m} 分" if m else f"{h} 小时"


def human_reason(task: dict) -> str:
    """异常原因 — 从 note 最后一行（quarantine 时追加）取，做常见模式翻译"""
    note = (task.get("note") or "").rstrip("\n")
    if not note:
        return "任务卡住了。"
    last_line = note.split("\n")[-1].strip()
    if not last_line:
        return "任务卡住了。"
    s = last_line
    # 常见模式翻译
    s = s.replace("PID ", "进程 PID ")
    s = s.replace(" not found", " 找不到了")
    s = s.replace("exit=", "退出码=")
    s = s.replace("audit > ", "审计超过 ")
    s = s.replace("timeout", "超时")
    s = s.replace("cancelled", "被取消")
    return s


def human_suggestion(task: dict) -> str:
    """根据 reason 类型给可执行建议"""
    reason = (task.get("note") or "").lower()
    if "not found" in reason or "exit=" in reason:
        return "点「重新执行」让系统再试一次，或点「查看详情」看更多日志。"
    if "timeout" in reason or "audit" in reason:
        return "点「重新执行」让系统再试一次，或联系开发者。"
    return "点「查看详情」看更多日志，或重新执行。"


def stuck_minutes(abnormal_at_iso: Optional[str], now: Optional[datetime] = None) -> int:
    """卡了多久 — 分钟"""
    if not abnormal_at_iso:
        return 0
    if now is None:
        now = datetime.now(timezone.utc)
    try:
        t = datetime.fromisoformat(str(abnormal_at_iso).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 0
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    sec = (now - t).total_seconds()
    return max(0, int(sec // 60))


def event_action_cn(to_column: str) -> str:
    """事件流（today_events）的中文动作"""
    return {
        "released": "已发布到生产环境",
        "verified": "通过测试，准备发布",
        "in_progress": "开始开发",
        "abnormal": "卡住了，需要人工介入",
        "planned": "开始规划",
        "testing": "进入测试",
        "backlog": "已放回待办",
    }.get(to_column, "状态变更")


# ── 今日事件工具 ──

def is_today(iso: str) -> bool:
    """v0.28.1: 统一用北京时间判断"今天"（避免 +08:00 与 UTC 跨零点日期不一致）"""
    if not iso:
        return False
    try:
        from datetime import timedelta
        beijing = timezone(timedelta(hours=8))
        parsed = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(beijing).date() == datetime.now(beijing).date()
    except (ValueError, TypeError):
        return False


def hhmm(iso: str) -> str:
    if not iso or len(iso) < 16:
        return ""
    return iso[11:16]


def enrich_task(task: dict) -> dict:
    """给一个 task 加 dashboard 要的所有人类字段。返回新 dict，不改原对象。"""
    out = dict(task)
    status = task.get("status", "")
    out["phase_cn"] = phase_cn(status)
    out["phase_name"], out["phase_index"], out["phase_total"] = phase_progress(status)
    out["status_pill_cn"] = status_pill_cn(status)
    out["human_who"] = human_who(task)
    out["human_action"] = human_action(status)
    out["elapsed_cn"] = elapsed_cn(task.get("updated_at") or task.get("created_at"))
    return out


def enrich_abnormal(task: dict) -> dict:
    """给一个 abnormal task 加 dashboard 要的卡住信息。"""
    out = dict(task)
    out["human_reason"] = human_reason(task)
    out["human_suggestion"] = human_suggestion(task)
    out["stuck_minutes"] = stuck_minutes(task.get("updated_at") or task.get("created_at"))
    return out
