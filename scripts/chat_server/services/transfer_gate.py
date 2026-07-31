"""转任务聊透门禁 — Desktop Transfer Gate（仅允许写 epic）。

契约：docs/product/transfer-gate.md · LPSN P/N
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

VALID_FEASIBILITY = frozenset({"ok", "blocked"})


def _references_root() -> Path:
    """references/ 库根路径（platform 仓 CCC）。"""
    return Path(__file__).resolve().parents[3] / "references"


def _validate_skill_ref(skill_ref: str) -> bool:
    """检查 references/skills/<path>/skill.md 是否存在。

    skill_ref 形如 'skills/write-code' 或 'skills/write-code@a1b2c3d'（带 hash 时只校验路径部分）。
    """
    if not skill_ref:
        return False
    # 去掉 @<hash> 后缀
    path_part = skill_ref.split("@", 1)[0].strip("/")
    if not path_part.startswith("skills/"):
        return False
    skill_md = _references_root() / path_part / "skill.md"
    return skill_md.is_file()


def _validate_prompt_ref(prompt_ref: str) -> bool:
    """检查 references/prompts/<path>.md 是否存在。

    prompt_ref 形如 'prompts/write-code-prompt' 或 'prompts/write-code-prompt@a1b2c3d'。
    """
    if not prompt_ref:
        return False
    path_part = prompt_ref.split("@", 1)[0].strip("/")
    if not path_part.startswith("prompts/"):
        return False
    prompt_md = _references_root() / f"{path_part}.md"
    return prompt_md.is_file()


# 旧 executor_intent → skill_ref 映射（向后兼容，硬切换过渡期仅记 warning）
_EXECUTOR_INTENT_TO_SKILL_REF = {
    "opencode": "skills/write-code",
    "python": "skills/script-seed",
    "cli": "skills/ops",
    "ollama": "skills/write-code",
    "auto": "skills/write-code",
    "bug": "skills/bug-fix",
}


def _intent_probe():
    scripts = Path(__file__).resolve().parents[2]
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import _intent_probe as mod

    return mod


def validate_transfer_payload(
    body: dict[str, Any],
    *,
    workspace: Path | str | None = None,
) -> tuple[bool, list[dict]]:
    """返回 (ok, errors)。errors 项为 {code, message}。"""
    errors: list[dict] = []
    if not isinstance(body, dict):
        return False, [{"code": "invalid_body", "message": "JSON object required"}]

    # Agent 常写长标题；软裁到 80，空才拒（避免 outbox 耗尽仍无人感知）
    title = str(body.get("title") or "").strip()
    if len(title) > 80:
        title = title[:80].rstrip()
        body["title"] = title
    if not title:
        errors.append(
            {
                "code": "missing_title",
                "message": "需要 1–80 字可执行中文标题",
            }
        )

    # 垃圾戳记/冒烟/探针卫生卡：禁止进 backlog（与 _board_garbage 对齐）
    try:
        scripts = Path(__file__).resolve().parents[2]
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from _board_garbage import is_garbage_board_card as _is_garbage

        probe_id = str(body.get("epic_id") or "").strip() or title
        if _is_garbage(
            probe_id,
            {"id": probe_id, "title": title, "tags": body.get("tags") or []},
        ) or _is_garbage(
            title.lower().replace(" ", "-")[:80],
            {"id": "", "title": title, "tags": body.get("tags") or []},
        ):
            errors.append(
                _err(
                    "garbage_stamp_card",
                    "禁止投递探针/戳记/冒烟/Layer2 LPSN 卫生卡",
                    "改投真实业务意图（如 qb 域门 B4.2/B5）；戳记类勿进看板。",
                )
            )
    except Exception:
        pass  # intentional — optional garbage classifier

    goal = str(body.get("goal") or "").strip()
    if not goal:
        errors.append({"code": "missing_goal", "message": "需要明确目标（goal）"})

    acceptance = body.get("acceptance")
    if isinstance(acceptance, list):
        acc_ok = any(str(x or "").strip() for x in acceptance)
    else:
        acc_ok = bool(str(acceptance or "").strip())
    if not acc_ok:
        errors.append(
            {
                "code": "missing_acceptance",
                "message": "需要至少一条验收意图（acceptance）",
            }
        )

    pipeline = str(body.get("pipeline") or "").strip()
    if not pipeline:
        errors.append(
            {
                "code": "missing_pipeline",
                "message": "需要产线/项目执行意图（pipeline）",
            }
        )

    feasibility = str(body.get("feasibility") or "").strip().lower()
    if feasibility not in VALID_FEASIBILITY:
        errors.append(
            {
                "code": "feasibility_blocked",
                "message": "feasibility 必须为 ok 或 blocked",
            }
        )
    elif feasibility == "blocked":
        reason = str(body.get("feasibility_reason") or "").strip()
        errors.append(
            {
                "code": "feasibility_blocked",
                "message": reason or "Agent 评估不可执行（feasibility=blocked）",
            }
        )

    # skill_ref / prompt_ref 必填校验（新架构 · 硬切换）
    skill_ref = str(body.get("skill_ref") or "").strip()
    if not skill_ref:
        errors.append(
            {
                "code": "missing_skill_ref",
                "message": "需要 Skill 库路径引用（skill_ref，如 skills/write-code）",
            }
        )
    elif not _validate_skill_ref(skill_ref):
        errors.append(
            {
                "code": "invalid_skill_ref",
                "message": f"Skill 库路径不存在: {skill_ref}",
            }
        )

    prompt_ref = str(body.get("prompt_ref") or "").strip()
    if not prompt_ref:
        errors.append(
            {
                "code": "missing_prompt_ref",
                "message": "需要 Prompt 库路径引用（prompt_ref，如 prompts/write-code-prompt）",
            }
        )
    elif not _validate_prompt_ref(prompt_ref):
        errors.append(
            {
                "code": "invalid_prompt_ref",
                "message": f"Prompt 库路径不存在: {prompt_ref}",
            }
        )

    # 旧字段 executor_intent 向后兼容：若存在且无 skill_ref，映射并记 warning（不阻断）
    legacy_intent = str(body.get("executor_intent") or "").strip().lower()
    if legacy_intent and not skill_ref:
        # 硬切换期：旧字段仅用于映射推断，不再做枚举校验
        pass

    project_id = str(body.get("project_id") or body.get("project") or "").strip()
    if not project_id:
        errors.append(
            {
                "code": "project_not_dispatchable",
                "message": "缺少 project_id",
            }
        )

    plan_md = str(body.get("plan_md") or "").strip()

    ip = _intent_probe()
    hygiene = ip.is_hygiene_transfer(body)
    if not hygiene and acc_ok:
        # 分查 acceptance / plan：plan 内「## 验收」编号列表不得盖掉顶部 acceptance 子弹
        acc_norm = normalize_acceptance(acceptance)
        acc_cmds = list(ip.extract_probe_commands(acc_norm) or [])
        plan_cmds = list(ip.extract_probe_commands(plan_md) or []) if plan_md else []
        cmds = acc_cmds or plan_cmds
        if not cmds:
            errors.append(
                _err(
                    "missing_intent_probe",
                    "业务 epic 的验收须含 ≥1 条可重放意图探针"
                    "（如 DRY_RUN=true .venv/bin/python … / python3 … / pytest）",
                    "acceptance 写可执行命令（pytest / python3 -c assert / DRY_RUN=…），"
                    "禁止散文或 test -f 假绿。",
                )
            )
        else:
            weak = _check_acceptance_strength(cmds, plan_md=plan_md)
            if weak:
                errors.append(weak)
            budget = _check_acceptance_budget(cmds)
            if budget:
                errors.append(budget)

        if plan_md:
            # Hub 会用 acceptance 重建 plan_md；顶部已有强探针时，
            # 不要因 Agent 草稿 plan 缺「## 验收」整单 400（会误报成「投递失败/Hub 问题」）。
            plan_err = _check_plan_preview(
                plan_md,
                require_acceptance_section=not bool(acc_cmds),
            )
            if plan_err:
                errors.append(plan_err)

    if workspace and not hygiene:
        n_err = check_next_intent_gate(body, Path(workspace))
        if n_err:
            errors.append(n_err)

    align_err = validate_plan_goal_alignment(body)
    if align_err:
        errors.append(align_err)

    # FlowWeave 启发：敏感路径不得进意图卡 scope（薄能力 · 产线门禁）
    sens_err = _check_sensitive_scope(body)
    if sens_err:
        errors.append(sens_err)

    # 文/码分轨；OpenCode 颗粒度仅史径（最小路径：长意图不挡 scope≤5）
    if not hygiene:
        text_err = _check_text_task_agent_track(body)
        if text_err:
            errors.append(text_err)
        if not _min_pipeline_on():
            gran_err = _check_opencode_work_granularity(body)
            if gran_err:
                errors.append(gran_err)

    # Ensure every error carries fix_hint for Agent training loop
    for e in errors:
        if isinstance(e, dict) and "fix_hint" not in e:
            e["fix_hint"] = _default_fix_hint(str(e.get("code") or ""))

    return (len(errors) == 0), errors


_CODE_EXTS = (
    ".py",
    ".rs",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".java",
    ".swift",
    ".kt",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".sh",
    ".toml",
    ".yaml",
    ".yml",
)
_TEXT_NAME_HINTS = (
    "changelog",
    "claude.md",
    "agents.md",
    "goal.md",
    "dev-plan",
    "dev_plan",
    "readme",
    "version",
    "agent-mind",
    "decided.json",
    "digest.md",
    "sop.md",
    "authority",
)
_TEXT_PATH_PREFIXES = (
    "docs/",
    ".ccc/agent-mind/",
    "references/",
)


def _collect_scope_paths(body: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("scope", "files", "paths"):
        val = body.get(key)
        if isinstance(val, list):
            paths.extend(str(x).strip() for x in val if str(x).strip())
        elif isinstance(val, str) and val.strip():
            paths.append(val.strip())
    plan_md = str(body.get("plan_md") or "")
    in_scope = False
    for line in plan_md.splitlines():
        s = line.strip()
        if s.startswith("#"):
            low = s.lstrip("#").strip().lower()
            in_scope = low.startswith("范围") or low.startswith("scope")
            continue
        if not in_scope:
            continue
        item = s.lstrip("-*").strip().strip("`")
        if not item or item.startswith("http"):
            continue
        token = item.split()[0]
        if "/" in token or "." in token:
            paths.append(token)
    # dedupe preserve order
    out: list[str] = []
    seen: set[str] = set()
    for p in paths:
        key = p.replace("\\", "/").lstrip("./")
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _is_text_only_path(path: str) -> bool:
    p = path.replace("\\", "/").lstrip("./").lower()
    if any(p.startswith(pref) for pref in _TEXT_PATH_PREFIXES):
        return True
    if p in ("version", "changelog.md", "changelog", "claude.md", "agents.md"):
        return True
    if any(h in p for h in _TEXT_NAME_HINTS) and not p.endswith(_CODE_EXTS):
        # VERSION file (no ext)
        if p == "version" or p.endswith("/version"):
            return True
        if p.endswith((".md", ".txt", ".rst", ".json")):
            return True
    if p.endswith((".md", ".txt", ".rst")) and not any(
        x in p for x in ("test", "spec")
    ):
        return True
    return False


def _is_code_path(path: str) -> bool:
    p = path.replace("\\", "/").lstrip("./").lower()
    if p.endswith(_CODE_EXTS):
        return True
    if "/tests/" in f"/{p}" or p.startswith("tests/"):
        return True
    if p.startswith("src/") or p.startswith("app/") or p.startswith("scripts/"):
        return not _is_text_only_path(p)
    return False


def _check_text_task_agent_track(body: dict[str, Any]) -> dict[str, str] | None:
    """纯文案/脑包/changelog 卡不得进 OpenCode 产线（文/码分轨）。"""
    pipeline = str(body.get("pipeline") or "dev").strip().lower()
    if pipeline in ("ops", "hygiene", "board", "board_ops"):
        return None
    # 新架构：从 skill_ref 推断执行器；write-code/script-seed/ops 类才查纯文
    skill_ref = str(body.get("skill_ref") or "").strip().lower()
    # 非写码类 skill（如 code-review）不查纯文分轨
    if skill_ref and not skill_ref.startswith(("skills/write-code", "skills/script-seed", "skills/ops")):
        return None
    paths = _collect_scope_paths(body)
    title = str(body.get("title") or "")
    goal = str(body.get("goal") or "")
    blob = f"{title}\n{goal}".lower()
    text_markers = (
        "changelog",
        "更新 version",
        "bump version",
        "版本正规化",
        "写文档",
        "补文档",
        "规划文",
        "dev-plan",
        "对齐文档",
        "agent-mind",
        "decided",
        "只改文档",
        "文案",
    )
    looks_text_intent = any(m in blob for m in text_markers)
    if paths:
        if all(_is_text_only_path(p) for p in paths) and not any(
            _is_code_path(p) for p in paths
        ):
            return _err(
                "text_task_agent_track",
                f"纯文本 scope（{', '.join(paths[:4])}）不得进 OpenCode 产线",
                "文/码分轨：文档/changelog/VERSION/脑包由对话 Agent（Hub mind / 本机 CCC）完成；"
                "只把含 src|tests|scripts 代码实现的卡 transfer。见 "
                "docs/briefs/2026-07-30-granularity-text-code-commit.md。",
            )
    elif looks_text_intent:
        # 无显式 scope 但标题目标是文案
        acc = body.get("acceptance") or []
        if not isinstance(acc, list):
            acc = [acc]
        acc_join = "\n".join(str(a) for a in acc).lower()
        codeish = any(
            x in acc_join
            for x in ("pytest", "cargo test", "npm test", "python3 -c", "DRY_RUN")
        ) and not all(
            any(t in str(a).lower() for t in ("version", "changelog", "grep -q", "docs/"))
            for a in acc
            if str(a).strip()
        )
        if not codeish:
            return _err(
                "text_task_agent_track",
                "标题/目标像纯文案任务，缺少代码 scope",
                "文案/版本叙述/脑包勿投产线；Agent 自轨完成。代码实现另开小卡（scope≤5 文件 + pytest）。",
            )
    return None


def _min_pipeline_on() -> bool:
    try:
        from engine.min_pipeline import enabled as _mp_on

        return bool(_mp_on())
    except Exception:
        return True  # fail-open to thin gate


def _check_opencode_work_granularity(body: dict[str, Any]) -> dict[str, str] | None:
    """史径：OpenCode 小卡 scope≤5。最小路径下 transfer 不调用本函数。"""
    paths = _collect_scope_paths(body)
    if len(paths) > 5:
        return _err(
            "plan_scope_too_wide",
            f"scope 列出 {len(paths)} 个文件（上限 5）",
            "大意图拆多张意图卡；每张给 OpenCode 的 work：≤5 文件 · 1 phase · 1～2 强探针。"
            "（最小路径下此检查已关；oversized 改在 fanout 拦内部 work。）",
        )
    plan = str(body.get("plan_md") or "")
    step_hits = len(
        re.findall(r"(?m)^(?:#{2,3}\s*)?(?:步骤|Step)\s*\d+", plan)
    ) + len(re.findall(r"(?m)^\d+\.\s+\S+", plan))
    if step_hits >= 6:
        return _err(
            "plan_scope_too_wide",
            f"plan 步骤约 {step_hits} 步，易 OpenCode hang",
            "禁止 Step1–6 一把梭；Engine plan 阶段再拆内部 work。",
        )
    return None


def _check_sensitive_scope(body: dict[str, Any]) -> dict[str, str] | None:
    """拒把 .env / credentials / control.json 等写入 scope。"""
    try:
        scripts = Path(__file__).resolve().parents[2]
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from _diff_check import check_paths, any_blocked

        paths: list[str] = []
        for key in ("scope", "files", "paths"):
            val = body.get(key)
            if isinstance(val, list):
                paths.extend(str(x) for x in val if str(x).strip())
            elif isinstance(val, str) and val.strip():
                paths.append(val.strip())
        plan_md = str(body.get("plan_md") or "")
        for line in plan_md.splitlines():
            s = line.strip().lstrip("-*").strip()
            if not s or s.startswith("#"):
                continue
            # 启发式：像路径的行
            if "/" in s or s.endswith((".py", ".ts", ".js", ".md", ".json", ".yaml", ".yml", ".env")):
                # 去掉行内说明
                token = s.split()[0].strip("`")
                if token and not token.startswith("http"):
                    paths.append(token)
        flags = check_paths(paths)
        if any_blocked(flags):
            sample = ", ".join(f.get("path") or "" for f in flags if f.get("level") == "block")[:120]
            return _err(
                "sensitive_scope",
                f"意图卡 scope 含敏感路径：{sample}",
                "从 scope/plan 去掉 .env、credentials、密钥、control.json；改业务源码路径。",
            )
    except Exception:
        pass  # intentional — optional safety net
    return None


def _err(code: str, message: str, fix_hint: str) -> dict[str, str]:
    return {"code": code, "message": message, "fix_hint": fix_hint}


def _default_fix_hint(code: str) -> str:
    hints = {
        "missing_title": "title 写 1–80 字可执行中文意图。",
        "missing_goal": "goal 写清要做成什么；与 plan_md 同向。",
        "missing_acceptance": "acceptance 至少一条可重放探针命令。",
        "missing_pipeline": "pipeline 填 dev（或对应产线）。",
        "missing_intent_probe": "加 pytest/python3/DRY_RUN 探针，禁散文验收。",
        "acceptance_weak": "换成行为探针：pytest / python3 -c assert / DRY_RUN，禁 test -f。",
        "acceptance_too_wide": "acceptance 压到 1～2 条本卡强探针；下一意图另开卡。",
        "acceptance_mixed_intent": "本卡只留 unit/本卡脚本探针；paper/e2e 另开 L1 卡。",
        "plan_acceptance_weak": "plan_md 补 ## 验收 + 强探针；单意图单卡。",
        "plan_scope_too_wide": "缩小 scope：单卡≤5 文件、单顶层目录、单 phase；大意图拆多卡。",
        "plan_goal_conflict": "改齐 plan_md 与 goal（勿降 CLOSE/净 edge）。",
        "intent_not_stable": "对齐未完成 L1 目标，或 supersede_goals / abandon_prior。",
        "feasibility_blocked": "先解阻塞或改可行性评估后再定稿。",
        "garbage_stamp_card": "禁止探针/戳记/冒烟/Layer2 LPSN 卫生卡；改投真实业务意图。",
        "sensitive_scope": "从 scope/plan 去掉 .env/密钥/control.json；只写业务源码路径。",
        "text_task_agent_track": "文案/changelog/VERSION/脑包由对话 Agent 完成，勿进 OpenCode；代码另开小卡。",
    }
    return hints.get(code, "按拒因改 ccc-transfer 后再定稿；读 digest「近期定卡教训」。")


def _check_acceptance_strength(
    cmds: list[str], *, plan_md: str = ""
) -> dict[str, str] | None:
    """Reject existence-only false greens (R5) before board write."""
    try:
        scripts = Path(__file__).resolve().parents[2]
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from _acceptance_strength import is_strong_enough, plan_is_hygiene_or_ops

        ok_s, reason_s = is_strong_enough(
            cmds,
            require_strong=True,
            exempt=plan_is_hygiene_or_ops(plan_md) if plan_md else False,
        )
        if not ok_s:
            return _err(
                "acceptance_weak",
                f"验收探针过弱（{reason_s}）：禁止仅 test -f 等存在性假绿",
                "acceptance 改为 pytest / python3 -c assert / DRY_RUN=true …；"
                "对照 post-exhaust acceptance_fail 桶。",
            )
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger("ccc.transfer_gate").warning(
            "acceptance strength check failed: %s", exc
        )
    return None


def _check_acceptance_budget(cmds: list[str]) -> dict[str, str] | None:
    """Cap probe count + ban mixing unit-card probes with later-stage e2e.

    Failure case (qb 2026-07-29): fees/unit epic also demanded paper_intent_probe
    → salvage acceptance_cmd_failed / hang. See intent-card-sop.md.
    """
    uniq: list[str] = []
    seen: set[str] = set()
    for c in cmds:
        key = " ".join(str(c).split())
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append(key)
    # 最小路径：长意图可多探针（上限 8）；史径仍 3
    max_probes = 8 if _min_pipeline_on() else 3
    if len(uniq) > max_probes:
        return _err(
            "acceptance_too_wide",
            f"acceptance 抽出 {len(uniq)} 条探针（上限 {max_probes}）",
            "压到可执行探针；长意图可多条，但仍禁纸面散文。"
            "见 docs/product/loop-engineer-authority.md 最小可跑通 v1。",
        )
    joined = "\n".join(uniq).lower()
    has_unit = "pytest" in joined or "python3 -c" in joined or "python -c" in joined
    has_late = any(
        x in joined
        for x in (
            "paper_intent_probe",
            "paper-intent-probe",
            "60s",
            "end-to-end",
            "e2e",
        )
    )
    # unit + late-stage on same card → hang / acceptance_cmd_failed
    if has_unit and has_late and len(uniq) >= 2:
        return _err(
            "acceptance_mixed_intent",
            "本卡同时含单元探针与 paper/e2e 后期探针，易 hang",
            "删掉 paper_intent_probe/e2e，只留本卡 pytest；"
            "paper/Layer2 作为下一张 L1 目标另定稿。",
        )
    return None


def _check_plan_preview(
    plan_md: str,
    *,
    require_acceptance_section: bool = True,
) -> dict[str, str] | None:
    """Lightweight plan_md lint + scope width preview before backlog."""
    if require_acceptance_section:
        try:
            scripts = Path(__file__).resolve().parents[2]
            if str(scripts) not in sys.path:
                sys.path.insert(0, str(scripts))
            import phase_lint

            ok, errs = phase_lint.validate_plan_acceptance(
                plan_md, require_probe=True
            )
            if not ok:
                msg = "; ".join(str(e) for e in (errs or [])[:3]) or "plan_md 验收不合格"
                return _err(
                    "plan_acceptance_weak",
                    msg,
                    "plan_md 必须有 ## 验收 + ≥1 条强探针；禁散文/弱探针。"
                    "（也可只在 acceptance 写强探针，Hub 会补 plan。）",
                )
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger("ccc.transfer_gate").warning(
                "plan_md probe strength check failed: %s", exc
            )

    # Multi-root scope / too many phases → hang risk (post-exhaust hang bucket)
    try:
        scripts = Path(__file__).resolve().parents[2]
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        from _plan_adopt import synthesize_phases_from_plan, backfill_scopes

        phases = backfill_scopes(synthesize_phases_from_plan(plan_md), plan_md)
        # 最小路径：长意图 plan 可多 phase；内部 work oversized 由 fanout 拦
        if _min_pipeline_on():
            return None
        if len(phases) > 2:
            return _err(
                "plan_scope_too_wide",
                f"plan 合成约 {len(phases)} 个 phase，易 hang；请压到 ≤2（优先 1）",
                "OpenCode 只接小卡：单卡单 phase、scope≤5 文件；禁 Step1–6 一次做完。",
            )
        roots: set[str] = set()
        file_count = 0
        for p in phases:
            scopes = p.get("scope") or []
            file_count += len([s for s in scopes if str(s).strip()])
            for s in scopes:
                part = str(s).strip().replace("\\", "/").lstrip("./")
                if not part:
                    continue
                top = part.split("/", 1)[0]
                if top and top not in (".ccc",):
                    roots.add(top)
        if file_count > 5:
            return _err(
                "plan_scope_too_wide",
                f"plan phases 合计 scope≈{file_count} 文件（上限 5）",
                "拆多张意图卡；每张给 OpenCode ≤5 文件。",
            )
        if len(roots) > 2:
            return _err(
                "plan_scope_too_wide",
                f"scope 跨 {len(roots)} 个顶层目录（{', '.join(sorted(roots)[:5])}），易串行 hang",
                "缩小白名单到同一顶层（如仅 src/ 或仅 tests/）；对照 hang 优化 hint。",
            )
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger("ccc.transfer_gate").warning(
            "plan scope width check failed: %s", exc
        )
    return None


def validate_plan_goal_alignment(body: dict[str, Any]) -> dict | None:
    """Reject plan_md that walks back capabilities promised in goal/title.

    Example: goal requires CLOSE/平仓 but plan says「交给上层 / 不做 CLOSE / 只发 OPEN」.
    """
    goal = str(body.get("goal") or "")
    title = str(body.get("title") or "")
    plan = str(body.get("plan_md") or "")
    if not plan.strip():
        return None

    g = f"{title}\n{goal}".lower()
    p = plan.lower()

    close_intent = any(
        k in g
        for k in (
            "close_long",
            "close_short",
            "close_long/close_short",
            "反向平仓",
            "平仓动作",
            "发 close",
            "发出 close",
            "close 动作",
        )
    ) or (
        "close" in g
        and any(k in g for k in ("平仓", "反向", "close_long", "close_short", "动作"))
    )

    if close_intent:
        downgrade = any(
            k in p
            for k in (
                "上层处理",
                "交给上层",
                "不追踪仓位",
                "不做 close",
                "不发 close",
                "保持 open",
                "仍只发 open",
                "只发 open",
                "简化处理为",
                "close 交给",
            )
        )
        # Explicit: plan keeps OPEN-only while goal asked for CLOSE
        if downgrade or (
            ("open_long" in p or "open_short" in p or "只发 open" in p)
            and any(
                k in p
                for k in ("不做 close", "不发 close", "上层", "不追踪", "保持 open")
            )
        ):
            return _err(
                "plan_goal_conflict",
                "plan_md 与 goal 冲突：goal 要求 CLOSE/反向平仓，"
                "但 plan 降级为不做 CLOSE / 交给上层。请改齐后再定稿。",
                "plan_md 写明 CLOSE_LONG/CLOSE_SHORT 与仓位追踪；禁止「交给上层」。",
            )

    # Shared cost / net-edge: plan must not defer if goal requires it
    if any(k in g for k in ("共享 cost", "round_trip_cost", "净 edge", "净edge")):
        if any(
            k in p
            for k in ("不做净 edge", "延后扣费", "暂不抽 cost", "不做共享 cost")
        ):
            return _err(
                "plan_goal_conflict",
                "plan_md 与 goal 冲突：goal 要求扣费/共享 cost，plan 却延后或不做。",
                "plan 必须落地共享 cost / 净 edge；禁止延后。",
            )

    return None


def check_next_intent_gate(body: dict[str, Any], workspace: Path) -> dict | None:
    """If L1 has unfinished product goals, require supersede/abandon for new product epic."""
    if body.get("supersede_goals") is True or body.get("intent_supersede") is True:
        return None
    if str(body.get("abandon_prior") or "").strip().lower() in ("1", "true", "yes"):
        return None
    try:
        from chat_server.services import agent_mind
    except ImportError:
        try:
            from . import agent_mind
        except ImportError:
            return None

    decided = agent_mind.load_decided(Path(workspace))
    unfinished = agent_mind.unfinished_product_goals(decided)
    if not unfinished:
        return None
    blob = (
        str(body.get("title") or "")
        + " "
        + str(body.get("goal") or "")
    ).lower()
    for g in unfinished:
        text = str(g.get("text") or "").lower()
        if text and text[:24] in blob:
            return None
    titles = ", ".join(
        str(g.get("text") or g.get("id") or "")[:40] for g in unfinished[:3]
    )
    return {
        "code": "intent_not_stable",
        "message": (
            f"同仓仍有未达 intent_stable 的产品目标（{titles}）。"
            "先确认稳定/放弃，或传 supersede_goals=true / abandon_prior=true 后再开下一意图。"
        ),
    }


def normalize_acceptance(acceptance: Any) -> str:
    if isinstance(acceptance, list):
        lines = [f"- {str(x).strip()}" for x in acceptance if str(x or "").strip()]
        return "\n".join(lines)
    return str(acceptance or "").strip()


def build_epic_description(body: dict[str, Any]) -> str:
    """拼 epic.description：含 gate 快照，供 Engine 扇出。"""
    goal = str(body.get("goal") or "").strip()
    acc = normalize_acceptance(body.get("acceptance"))
    pipeline = str(body.get("pipeline") or "").strip()
    skill_ref = str(body.get("skill_ref") or "").strip()
    prompt_ref = str(body.get("prompt_ref") or "").strip()
    plan_md = str(body.get("plan_md") or "").strip()
    skills = body.get("skills_hint") or []
    if not isinstance(skills, list):
        skills = []
    skills_s = ", ".join(str(s) for s in skills if str(s).strip())

    bump = body.get("bump_version") is True
    human_note = str(body.get("human_note") or "").strip()
    parts = [
        "## Transfer Gate",
        f"- pipeline: {pipeline}",
        f"- skill_ref: {skill_ref}",
        f"- prompt_ref: {prompt_ref}",
        "- feasibility: ok",
        f"- bump_version: {'true' if bump else 'false'}",
    ]
    if skills_s:
        parts.append(f"- skills_hint: {skills_s}")
    if human_note:
        parts.extend(["", "## 人工备注", human_note])
    parts.extend(["", "## 目标", goal, "", "## 验收", acc])
    if plan_md:
        parts.extend(["", "## Plan", plan_md])
    thread_id = str(body.get("thread_id") or "").strip()
    if thread_id:
        parts.extend(["", f"_thread_id: {thread_id}_"])
    return "\n".join(parts)[:10000]


def build_plan_md(body: dict[str, Any]) -> str:
    plan_md = str(body.get("plan_md") or "").strip()
    if plan_md:
        if not (
            "## 验收" in plan_md
            or "## 验证" in plan_md
            or "## Acceptance" in plan_md
        ):
            acc = normalize_acceptance(body.get("acceptance"))
            plan_md = plan_md.rstrip() + f"\n\n## 验收\n{acc}\n"
        return plan_md
    title = str(body.get("title") or "任务").strip()
    goal = str(body.get("goal") or "").strip()
    acc = normalize_acceptance(body.get("acceptance"))
    return (
        f"# Plan: {title}\n\n"
        f"## 目标\n{goal}\n\n"
        f"## 验收\n{acc}\n"
    )


def _looks_like_util_probe_transfer(body: dict[str, Any]) -> bool:
    """Single-file open-intent / scripts/*_probe.py mechanical transfer."""
    title = str(body.get("title") or "").lower()
    goal = str(body.get("goal") or "").lower()
    plan = str(body.get("plan_md") or "").lower()
    blob = f"{title}\n{goal}\n{plan}"
    markers = (
        "open-intent",
        "open_intent",
        "开放意图",
        "ccc_open_intent",
        "util_probe",
    )
    if any(m in blob for m in markers):
        return True
    if "scripts/" in blob and "_probe.py" in blob and "paper_intent_probe" not in blob:
        return True
    return False


def resolve_complexity(body: dict[str, Any]) -> str:
    """归一 complexity；多步回归/冒烟禁止落 small（否则扇出强制单卡易 hang）。"""
    raw = str(body.get("complexity") or "medium").strip().lower()
    if raw in ("sm",):
        raw = "small"
    if raw not in ("small", "medium", "large"):
        raw = "medium"

    # Mechanical util/open-intent probes: allow small (metadata); reviewer uses util_probe kind
    if _looks_like_util_probe_transfer(body) and raw == "medium":
        acceptance = body.get("acceptance") or []
        if not isinstance(acceptance, list):
            acceptance = [acceptance]
        acc_lines = [str(a) for a in acceptance if str(a).strip()]
        if 0 < len(acc_lines) <= 3:
            return "small"

    if raw != "small":
        return raw

    title = str(body.get("title") or "")
    goal = str(body.get("goal") or "")
    plan = str(body.get("plan_md") or "")
    acceptance = body.get("acceptance") or []
    if not isinstance(acceptance, list):
        acceptance = [acceptance]
    acc_lines = [str(a) for a in acceptance if str(a).strip()]
    blob = f"{title}\n{goal}\n{plan}\n" + "\n".join(acc_lines)

    cmdish = 0
    for s in acc_lines:
        if any(
            tok in s
            for tok in (
                "python ",
                "python3 ",
                "pytest",
                "bash ",
                "DRY_RUN",
                "startup_check",
                "&&",
                "exit",
                ".venv/",
            )
        ):
            cmdish += 1

    multi_markers = (
        "startup_check",
        "pytest",
        "data_engine",
        "order_gateway",
        "三件套",
        "回归冒烟",
        "回归烟测",
        "回归测试",
    )
    hits = sum(1 for m in multi_markers if m in blob)
    if cmdish >= 3 or hits >= 3:
        return "medium"
    return raw


def resolve_skill_ref(body: dict[str, Any]) -> str:
    """归一 skill_ref。

    新架构（硬切换）：
    - 优先读 body['skill_ref']
    - 缺失时从旧 executor_intent 映射（向后兼容，记 warning 到 stderr）
    - 仍缺失则兜底 skills/write-code
    """
    skill_ref = str(body.get("skill_ref") or "").strip()
    if skill_ref:
        return skill_ref

    # 向后兼容：从旧 executor_intent 映射
    legacy_intent = str(body.get("executor_intent") or "").strip().lower()
    if legacy_intent and legacy_intent in _EXECUTOR_INTENT_TO_SKILL_REF:
        import sys as _sys
        print(
            f"[transfer_gate] WARNING: body 无 skill_ref，从旧 executor_intent={legacy_intent!r} "
            f"映射为 skill_ref={_EXECUTOR_INTENT_TO_SKILL_REF[legacy_intent]!r}",
            file=_sys.stderr,
        )
        return _EXECUTOR_INTENT_TO_SKILL_REF[legacy_intent]

    # 兜底
    return "skills/write-code"


def resolve_executor_from_skill(skill_ref: str) -> str:
    """从 skill_ref 推断默认执行器。

    读 references/skills/<path>/skill.md 的「默认执行器」字段；
    缺失或读取失败则兜底 opencode。
    """
    if not skill_ref:
        return "opencode"

    path_part = skill_ref.split("@", 1)[0].strip("/")
    skill_md = _references_root() / path_part / "skill.md"
    if not skill_md.is_file():
        return "opencode"

    try:
        content = skill_md.read_text(encoding="utf-8")
        # 解析「默认执行器：xxx」或「默认执行器 | xxx」格式
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("默认执行器"):
                # 提取冒号或竖线后的值
                for sep in ("：", ":", "|"):
                    if sep in line:
                        executor = line.split(sep, 1)[1].strip().lower()
                        # 去掉括号注释
                        if "（" in executor:
                            executor = executor.split("（", 1)[0].strip()
                        if executor:
                            return executor
                        break
    except Exception:
        pass

    return "opencode"


# ===== 以下为旧 executor_intent 归一逻辑的史径保留（仅供 _epic_default_executor 过渡期复用）=====
# 新架构下应使用 resolve_skill_ref + resolve_executor_from_skill，不再直接调用 resolve_executor_intent。


def resolve_executor_intent(body: dict[str, Any]) -> str:
    """[已废弃 · 史径保留] 归一执行面。新架构请用 resolve_skill_ref + resolve_executor_from_skill。

    仍保留供 _product_fanout._epic_default_executor 过渡期调用；
    新代码禁止调用本函数。
    """
    skill_ref = resolve_skill_ref(body)
    return resolve_executor_from_skill(skill_ref)
