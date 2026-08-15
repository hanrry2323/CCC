#!/usr/bin/env python3
"""P6 迁移：hp M2-M5 22 个子项目 → 22 个方案 + roadmap.md 子项目结构化。

2026-08-16 流程改造（子项目层）。一次生成后校验，迁移记录保留本脚本。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLANS = ROOT / "docs" / "projects" / "hp" / "plans"
ROADMAP = ROOT / "docs" / "projects" / "hp" / "roadmap.md"

# (里程碑, 子项目id, 标题, 目标, 背景, 环境准备, 架构位置, 前置子项目)
SUBPROJECTS = [
    # M2 稳控与可恢复
    ("M2 · 稳控与可恢复", "2.1", "pipeline 源码回灌 SSOT",
     "把 hp 节点 pipeline 核心源码全部迁入 mac2017 SSOT 仓并纳入 git，消除源码丢失 P0。",
     "pipeline（ingest/chunker/embedder/search/config/parsers）源码只存在于 hp 部署机，mac2017 SSOT 仓没有——违反 README「服务源码必须进 git」规则。",
     "mac2017 hp 业务仓可写；hp 节点 /data/knowledge/pipeline 只读访问",
     "pipeline 全链路（ingest→chunker→embedder→search）",
     "无"),
    ("M2 · 稳控与可恢复", "2.2", "双仓 git 归一",
     "合并 mac2017 与 hp 节点两套独立 git 历史为单一线性真值，明确唯一 SSOT=mac2017。",
     "双仓无共同祖先（双仓漂移），互相有对方缺失的源码；SSOT 名不副实。",
     "双仓 SSH 访问 + git 历史合并演练环境",
     "SSOT 仓根与 hp 部署仓关系",
     "2.1"),
    ("M2 · 稳控与可恢复", "2.3", "运行时↔SSOT 对齐",
     "运行时 mcp_server（含 kb_status）回灌 SSOT；SSOT 领先部分回灌运行时；diff 确认两端一致。",
     "运行时比 SSOT 还新（kb_status 等改进未回灌），两端源码不一致。",
     "hp 节点服务访问 + mac2017 SSOT 可写",
     "mcp-server（运行时）↔ SSOT 仓",
     "2.1, 2.2"),
    ("M2 · 稳控与可恢复", "2.4", "全文摄入改造",
     "ingest 存全文 chunk（标题+摘要+全文+指针），knowledge_search 直接返回全文。",
     "现只存摘要/片段，检索命中还要跳原仓，无法直接消费全文。",
     "PG/pgvector 环境 + 摄入链路可跑",
     "ingest 写入 → chunks 表 → knowledge_search 读取",
     "2.3"),
    ("M2 · 稳控与可恢复", "2.5", "双库改主备",
     "HP 为主（全量语义底座），ccc-kb 降为离线降级副本（敏感隔离 + HP 挂兜底）。",
     "主备分层：ccc-kb 只存 CCC 决策/教训，敏感内容隔离不进 HP。",
     "ccc-kb 本地运行环境 + HP 索引访问",
     "HP 主库 ↔ ccc-kb 降级副本",
     "2.4"),
    ("M2 · 稳控与可恢复", "2.6", "凭据治理",
     "处理 .credentials-backup、轮换 .env 口令、清理 gitignore，禁止敏感材料进 git。",
     "敏感材料未跟踪、.env 含 DB 口令明文、rss-to-hp-kb.py 硬编码旧路径。",
     "hp 节点凭据文件访问（只读核对）",
     "运行时目录 .env / 凭据文件",
     "无"),
    ("M2 · 稳控与可恢复", "2.7", "可重建验证",
     "从 SSOT 全新部署到空机，端到端验证可恢复，产出灾备演练记录。",
     "验证 SSOT 能全新重建整套服务（PG/pgvector → pipeline → mcp/memory-store → 检索）。",
     "空机演练环境（或克隆环境）",
     "全栈重建链路",
     "2.1, 2.2, 2.3, 2.4, 2.5, 2.6"),
    # M3 可观测与告警
    ("M3 · 可观测与告警", "3.1", "健康三态探针",
     "对 postgres/ollama/memory-store/mcp-server/graph server 五个服务做三态探活（进程/端口/真实请求）。",
     "PG 僵尸事故（端口通连接全挂 20h 无人发现）后补齐可观测。",
     "五服务运行环境可探",
     "服务层健康监测",
     "无"),
    ("M3 · 可观测与告警", "3.2", "pg-health 前端渲染",
     "/ops/pg-health 后端已合入（1bbabfe5），补齐前端 renderPg 渲染。",
     "后端已就绪，前端无 commit，待办。",
     "前端 dev 环境 + 后端 /ops/pg-health 接口",
     "前端 consolePage /ops/pg-health",
     "3.1"),
    ("M3 · 可观测与告警", "3.3", "告警推送通道",
     "PG 僵尸/服务宕机/健康降级 → 主动推送（日志 + 通知通道），异常持续标记。",
     "无统一告警推送，异常靠人巡检。",
     "通知通道（日志/bark 等）",
     "告警输出层",
     "3.1"),
    ("M3 · 可观测与告警", "3.4", "悬空 cron 清理",
     "HP 节点遗留 cron / launchd 任务排查清理失效项。",
     "节点遗留定时任务可能误触发/失效。",
     "HP 节点访问（只读排查）",
     "HP 节点调度层",
     "无"),
    ("M3 · 可观测与告警", "3.5", "health 报告自动化",
     "daily 健康报告 + 异常标记，异常自动拉起/标记，避免静默失效。",
     "健康数据需定期汇总成报告供人审。",
     "scheduler 定时环境",
     "报告生成层",
     "3.3"),
    # M4 数据保鲜与质量
    ("M4 · 数据保鲜与质量", "4.1", "collector 加固",
     "多源采集恢复/加固（kb-collect 生产文件补齐、RSS 采集修复含硬编码路径），管道不再脆断。",
     "采集管道脆断，多个源停采。",
     "采集源访问 + collector 运行环境",
     "collector 采集链路",
     "无"),
    ("M4 · 数据保鲜与质量", "4.2", "旧数据重灌",
     "claude-code/ai-instruction/boss/research 等 last_ingest 停在 6 月的项目重新 ingest。",
     "多个大项目 last_ingest 停在 6 月，数据过期。",
     "PG + 各数据源访问",
     "ingest 回灌链路",
     "4.1"),
    ("M4 · 数据保鲜与质量", "4.3", "短 chunk 治理",
     "短 chunk 拦截/合并，目标 <15%，提升检索粒度。",
     "短 chunk 比例过高，检索碎片化。",
     "PG 数据访问",
     "chunk 治理（db/ingest）",
     "无"),
    ("M4 · 数据保鲜与质量", "4.4", "相关性优化",
     "knowledge_search 评分/排序改进（向量 + 关键词混合、domain 加权）。",
     "检索命中不够贴合主题。",
     "检索运行环境 + 评测样本",
     "knowledge_search 检索层",
     "4.3"),
    ("M4 · 数据保鲜与质量", "4.5", "定时入库监控",
     "collector 每日定时入库 + 入库结果监控（成功/失败/数据量变化），异常可查。",
     "入库结果不可见，失败静默。",
     "cron/scheduler 定时环境",
     "collector 监控层",
     "4.1"),
    # M5 生态消费
    ("M5 · 生态消费", "5.1", "mx 接入",
     "medio-0 方案/教训/决策回流 HP（建立 mx 域），开发时检索历史方案/教训。",
     "业务项目真正用起来知识库。",
     "mx 仓访问 + HP 写入权限",
     "mx 业务仓 ↔ HP 知识域",
     "无"),
    ("M5 · 生态消费", "5.2", "qb 深化",
     "qb 已有 103 docs，深化消费——回测结果/教训/决策沉淀 + 开发检索。",
     "qb 有基础但消费浅。",
     "qb 仓访问 + HP",
     "qb 业务仓 ↔ HP 知识域",
     "无"),
    ("M5 · 生态消费", "5.3", "xy 接入",
     "xianyu 建立知识域（现 0 docs），项目知识/决策/教训入 HP。",
     "xy 无知识域。",
     "xy 仓访问 + HP 写入",
     "xy 业务仓 ↔ HP 知识域",
     "无"),
    ("M5 · 生态消费", "5.4", "流程集成",
     "CCC 出卡/验收时 KB 检索 + 教训回流自动触发（Doc-Gate 四问联动）。",
     "把「查知识、记教训」变成流程动作而非自觉。",
     "CCC 流程环境 + HP 检索/写入",
     "CCC 出卡/验收流程 ↔ HP",
     "5.1, 5.2, 5.3"),
    ("M5 · 生态消费", "5.5", "质量回检",
     "消费方反馈 → 检索质量闭环（消费数据驱动 M4 质量优化迭代）。",
     "消费反馈未回流质量改进。",
     "HP 检索 + 消费方反馈渠道",
     "消费反馈 ↔ 质量闭环",
     "5.4"),
]

ARCH_POS_OVERRIDE = {}  # 大多数已在上面

def plan_body(num, mile, spid, title, goal, bg, env, arch, pre):
    return f"""# 方案 · {title}（{mile.split(' · ')[0]}）

> 项目：hp · 编号：hp-plan-{num} · 状态：已确认 · 作者：Claude（中枢） · 工具：Claude Code
> 创建：2026-08-16 · 更新：2026-08-16
> 关联卡：无
> 关联方案：无
> 里程碑：{mile}
> 子项目：{spid} {title}
> 环境准备：{env}

## 目标

{goal}

## 背景

{bg}

## 功能卡

### 实施「{title}」
目标：完成子项目 {spid} {title}，交付可验收产物。
颗粒度：子项目级（1-2 卡）。
依赖：无
架构位置：{arch}

## 验收标准

- [ ] {title}完成，验收点可复核（命令/可观察结果）

## 备注

前置子项目（依赖）：{pre}——按依赖顺序逐步转卡，前置卡完成后本子项目才能独立验收。
"""

def main():
    PLAN_NUMS = {  # 子项目id → 方案编号 + ASCII slug（validate 要求 slug 小写字母/数字/连字符）
        "2.1": ("008", "pipeline-ssot-backfill"),
        "2.2": ("009", "dual-repo-merge"),
        "2.3": ("010", "runtime-ssot-align"),
        "2.4": ("011", "fulltext-ingest"),
        "2.5": ("012", "dual-db-primary-backup"),
        "2.6": ("013", "credential-governance"),
        "2.7": ("014", "rebuildable-verification"),
        "3.1": ("015", "health-triple-probe"),
        "3.2": ("016", "pg-health-frontend"),
        "3.3": ("017", "alert-channel"),
        "3.4": ("018", "orphan-cron-cleanup"),
        "3.5": ("019", "health-report-auto"),
        "4.1": ("020", "collector-harden"),
        "4.2": ("021", "stale-data-reingest"),
        "4.3": ("022", "short-chunk-governance"),
        "4.4": ("023", "relevance-optimize"),
        "4.5": ("024", "ingest-monitor"),
        "5.1": ("025", "mx-integration"),
        "5.2": ("026", "qb-deepen"),
        "5.3": ("027", "xy-integration"),
        "5.4": ("028", "flow-integration"),
        "5.5": ("029", "quality-feedback"),
    }
    PLANS.mkdir(parents=True, exist_ok=True)
    for mile, spid, title, goal, bg, env, arch, pre in SUBPROJECTS:
        num, slug = PLAN_NUMS[spid]
        fname = f"{num}-{slug}.md"
        fpath = PLANS / fname
        if fpath.exists():
            print(f"SKIP exists: {fname}")
            continue
        fpath.write_text(plan_body(num, mile, spid, title, goal, bg, env, arch, pre), encoding="utf-8")
        print(f"WROTE: {fname}")

    # roadmap.md 子项目结构化：从零重建 M2-M5（M1/M6 原文保留），草案池保留
    text = ROADMAP.read_text(encoding="utf-8")
    lines = text.split("\n")
    # 提取草案池 + M1 + M6 原文块
    draft_lines = []
    m1_lines = []
    m6_lines = []
    cur = None
    for ln in lines:
        s = ln.strip()
        if s.startswith("## 草案池"):
            cur = "draft"; continue
        if s.startswith("## 里程碑"):
            cur = None; continue
        if s.startswith("### "):
            cur = s[4:].strip(); continue
        if cur == "draft" and ln.strip():
            draft_lines.append(ln)
        if cur and cur.startswith("M1"):
            m1_lines.append(ln)
        if cur and cur.startswith("M6"):
            m6_lines.append(ln)

    # 描述模板（保留原意 + 收回说明）
    MILE_DESC = {
        "M2 · 稳控与可恢复": "让 HP **可恢复、可重建**——pipeline 源码回灌 SSOT、双仓 git 归一、运行时与 SSOT 对齐、全文摄入改造（主备分层基础）、凭据治理、可重建灾备验证。开发（mac2017）与部署（hp 节点）彻底隔离。（2026-08-15 原 hp-plan-004 已按流程改造作废；2026-08-16 按子项目重新立项）",
        "M3 · 可观测与告警": "HP 健康三态探针 + 故障自动发现——PG 僵尸事故（端口通连接全挂，20h 无人发现）后补齐可观测与告警，不再靠人巡检。（2026-08-15 原 hp-plan-005 已作废；2026-08-16 按子项目重新立项）",
        "M4 · 数据保鲜与质量": "数据不过期、检索质量稳——collector 加固、旧数据重灌（多个大项目 last_ingest 停在 6 月）、短 chunk 治理、相关性优化。（2026-08-15 原 hp-plan-006 已作废；2026-08-16 按子项目重新立项）",
        "M5 · 生态消费": "业务项目真正用起来——mx/qb/xy 接入知识库，CCC 出卡/验收流程与 KB 检索、教训回流联动。（2026-08-15 原 hp-plan-007 已作废；2026-08-16 按子项目重新立项）",
    }

    sub_by_mile = {}
    for mile, spid, title, *_ in SUBPROJECTS:
        sub_by_mile.setdefault(mile, []).append((spid, title, f"hp-plan-{PLAN_NUMS[spid][0]}"))

    # 按 SUBPROJECTS 顺序构建 M2-M5 块
    new_lines = ["# HP 知识库 线路图", "", "> 项目：hp · 更新：2026-08-16", "", "## 草案池", ""]
    new_lines += [ln for ln in draft_lines if ln.strip()] if draft_lines else ["无。"]
    new_lines += ["", "## 里程碑", ""]
    # M1（原文保留，去末尾空行）
    new_lines += ["### M1 · 知识库底座固化"]
    new_lines += [ln for ln in m1_lines if ln.strip()] if m1_lines else []
    new_lines += [""]
    # M2-M5
    seen = set()
    for mile, spid, title, *_ in SUBPROJECTS:
        if mile in seen:
            continue
        seen.add(mile)
        new_lines.append(f"### {mile}")
        new_lines.append("- 状态：待启动")
        ids = ", ".join(f"hp-plan-{PLAN_NUMS[sid][0]}" for sid, _t, _p in sub_by_mile[mile])
        new_lines.append(f"- 关联方案：{ids}")
        new_lines.append(f"- 描述：{MILE_DESC[mile]}")
        new_lines.append("- 子项目：")
        for sid, t2, pid2 in sub_by_mile[mile]:
            new_lines.append(f"  - {sid} {t2} · 状态：计划中 · 方案：{pid2}")
        new_lines.append("")
    # M6（原文保留）
    new_lines.append("### M6 · 演进（远期待定）")
    new_lines += [ln for ln in m6_lines if ln.strip()] if m6_lines else []
    new_lines.append("")
    ROADMAP.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
    print("roadmap.md rebuilt (M2-M5 结构化子项目)")

if __name__ == "__main__":
    main()
