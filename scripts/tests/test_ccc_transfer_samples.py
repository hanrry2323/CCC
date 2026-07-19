#!/usr/bin/env python3
"""定稿 ccc-transfer 样例：≥90% 无手填过门禁（本地解析，不调模型）。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "chat_server"))

from services.transfer_gate import validate_transfer_payload  # noqa: E402

FENCE_RE = re.compile(r"```\s*ccc-transfer\s*\n([\s\S]*?)\n```", re.I)

SAMPLES = [
    {
        "title": "订阅列表分页",
        "goal": "列表按页加载，滚动不丢选中",
        "acceptance": ["打开列表可见第 1 页", "滚到底自动加载下一页"],
        "pipeline": "dev",
        "feasibility": "ok",
        "executor_intent": "opencode",
    },
    {
        "title": "登录超时提示",
        "goal": "会话过期时白话提示并回登录",
        "acceptance": ["过期后点任意页看到提示", "确认后回到登录页"],
        "pipeline": "dev",
        "feasibility": "ok",
        "executor_intent": "opencode",
    },
    {
        "title": "导出 CSV",
        "goal": "把当前筛选结果导出为 CSV",
        "acceptance": ["点导出得到 .csv", "文件含表头与当前筛选行"],
        "pipeline": "dev",
        "feasibility": "ok",
        "executor_intent": "python",
    },
    {
        "title": "夜间静默推送关",
        "goal": "22:00–08:00 不发推送",
        "acceptance": ["配置保存成功", "窗口内无推送发送记录"],
        "pipeline": "ops",
        "feasibility": "ok",
        "executor_intent": "cli",
    },
    {
        "title": "搜索防抖",
        "goal": "输入停 300ms 再请求，减少连打",
        "acceptance": ["连打只发最后一次请求", "结果与最后关键字一致"],
        "pipeline": "dev",
        "feasibility": "ok",
        "executor_intent": "opencode",
    },
    {
        "title": "空状态插画",
        "goal": "无数据时显示引导文案与行动按钮",
        "acceptance": ["清空数据后可见空态", "按钮可跳到新建"],
        "pipeline": "dev",
        "feasibility": "ok",
        "executor_intent": "opencode",
    },
    {
        "title": "备份开关",
        "goal": "一键开关每日备份",
        "acceptance": ["开关状态可持久", "开启后目录出现当日备份"],
        "pipeline": "ops",
        "feasibility": "ok",
        "executor_intent": "cli",
    },
    {
        "title": "评论字数上限",
        "goal": "超过 500 字禁止提交并提示",
        "acceptance": ["501 字提交失败", "提示含字数上限"],
        "pipeline": "dev",
        "feasibility": "ok",
        "executor_intent": "opencode",
    },
    {
        "title": "主题跟随系统",
        "goal": "跟随 OS 浅/深色，可手动覆盖",
        "acceptance": ["系统切深色后界面跟随", "手动选浅色后保持浅色"],
        "pipeline": "dev",
        "feasibility": "ok",
        "executor_intent": "opencode",
    },
    {
        "title": "健康检查脚本",
        "goal": "运维脚本输出服务端口与版本",
        "acceptance": ["脚本退出码 0", "输出含 7777 与 VERSION"],
        "pipeline": "ops",
        "feasibility": "ok",
        "executor_intent": "python",
    },
]


def parse_fence(text: str) -> dict:
    m = FENCE_RE.search(text)
    assert m, "missing ccc-transfer fence"
    return json.loads(m.group(1))


def wrap_sample(s: dict) -> str:
    body = {
        **s,
        "plan_md": f"# Plan: {s['title']}\n\n## 目标\n{s['goal']}\n",
    }
    return (
        "结论：可以定稿转任务。\n\n"
        f"```ccc-transfer\n{json.dumps(body, ensure_ascii=False, indent=2)}\n```\n"
    )


def main() -> int:
    ok = 0
    for i, sample in enumerate(SAMPLES, 1):
        parsed = parse_fence(wrap_sample(sample))
        payload = {
            "project_id": "ccc-demo",
            "title": parsed["title"],
            "goal": parsed["goal"],
            "acceptance": parsed["acceptance"],
            "pipeline": parsed["pipeline"],
            "feasibility": parsed["feasibility"],
            "executor_intent": parsed.get("executor_intent") or "opencode",
            "plan_md": parsed.get("plan_md") or "x",
        }
        ok_flag, errs = validate_transfer_payload(payload)
        passed = ok_flag
        if not passed:
            print(f"  gate errors: {errs}", file=sys.stderr)
        if passed:
            ok += 1
        else:
            print(f"FAIL sample {i}: {sample['title']}", file=sys.stderr)

    rate = ok / len(SAMPLES)
    print(f"ccc-transfer samples: {ok}/{len(SAMPLES)} ({rate:.0%})")
    return 0 if rate >= 0.9 else 1


if __name__ == "__main__":
    raise SystemExit(main())
