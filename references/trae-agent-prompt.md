# Trae Agent 审查任务说明

> 本文档定义 Trae IDE agent 在 CCC 工作流中的三种审查任务。
> 每次执行时读取本文件，按对应章节操作。

---

## 通用规则

- **只审查，不改代码**。发现问题写报告，不动手修
- 报告统一写到项目下的 `.ccc/reviews/` 目录
- 报告格式见下方模板
- 不确定的发现标注 `uncertain: true`，不要硬下结论

---

## 三种任务

### 任务 1：每日 git 审查（定时执行）

> 频率：每天一次（建议 UTC 0 点 = 北京时间 8:00）
> 方式：Trae 定时任务自动触发

**步骤：**

1. `cd <project> && git log --oneline --since="24 hours ago"` 看昨天变更
2. 对有改动的文件做快速检查：
   - 是否有明文密码/Token 落入代码？
   - 是否有 `print()` / `console.log()` / `debugger` 残留？
   - 是否有被注释掉的测试或代码块？
   - `.env` / `.env.example` 是否忘记加对应项？
3. 对每个项目生成报告，合并为一个文件

**输出路径**：`<project>/.ccc/reviews/daily-YYYY-MM-DD.json`

---

### 任务 2：对抗性审查（手动触发）

> 触发条件：你告诉我"做对抗审查"，或开发完成后
> 方式：Trae 对话中手动触发

**步骤：**

1. 读项目所有核心源文件（`src/`、`dashboard/backend/`、`scripts/`）
2. 从攻击者视角审查：
   - 认证绕过风险（JWT/SSE/API 无鉴权路径）
   - 输入校验缺失（SQL 注入、命令注入、路径穿越）
   - 配置泄露（密文明文、fallback 密钥、CORS 裸奔）
   - 竞态条件（INCR + EXPIRE 非原子、多实例双写）
   - 日志泄露（URL 含密码、错误堆栈暴露路径）
3. 按严重度分级输出

**输出路径**：`<project>/.ccc/reviews/adversarial-YYYY-MM-DD.json`

---

### 任务 3：文档一致性审查（定时或手动）

> 频率：每周一次，或开发完后手动跑
> 方式：定时 或 对话中手动触发

**步骤：**

1. 检查以下文档是否过时：
   - `README.md`：项目名、版本号、架构描述与实际代码一致？
   - `CHANGELOG.md`：最近版本有记录？
   - `VERSION` / `VERSION.md`：与最新 tag 一致？
   - 文档中提到的路径/端口/命令能跑通？
2. 发现不一致只标注，不改

**输出路径**：`<project>/.ccc/reviews/doc-quality-YYYY-MM-DD.json`

---

## 报告格式（三种任务共用）

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-07-09T12:00:00+08:00",
  "project": "<项目名>",
  "source": "daily-scan | adversarial | doc-quality",
  "scope": "本次审查范围描述",
  "findings": [
    {
      "id": "F1",
      "severity": "critical | high | medium | low | info",
      "category": "security | config | code-quality | documentation | ops",
      "title": "简短标题",
      "file": "相对路径/文件名",
      "line": 123,
      "description": "问题描述，一句话说清",
      "recommendation": "修复建议，一句话",
      "uncertain": false,
      "auto_fixable": false
    }
  ],
  "summary": {
    "total": 0,
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0,
    "info": 0,
    "auto_fixable": 0
  }
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `severity` | 严重度。critical=必须立刻修 / high=尽快修 / medium=建议修 / low=顺手修 / info=仅仅是信息 |
| `category` | 分类。用于 CCC 拆任务时分到对应 phase |
| `uncertain` | 不确定的发现标 true，CCC 收到后会人工确认 |
| `auto_fixable` | true 表示 CCC 可以直接自动修（lint/配置/文档类）。false 表示需要人决策 |

---

## 各项目路径

| 项目 | 路径 | 备注 |
|------|------|------|
| CCC | `/Users/apple/program/CCC` | 框架本体 |
| xianyu | `/Users/apple/program/xianyu` | AI 内容分发平台 |
| qx | `/Users/apple/program/projects/qx` | 医药数据中台 v2.0 |
| qx-observer | `/Users/apple/program/qx-observer` | 战略指挥台 v8.x |
| qb | `/Users/apple/program/projects/qb` | 量化套利交易系统 |

---

## CCC 处理流程（供 Trae 了解后续链路）

```
Trae 写报告 → .ccc/reviews/  →  我评估 → 写 plan → 投 backlog → CCC 自动执行
               ↑ 你负责到这步      ↑ 我来         ↑ 投到 planned 开始跑
```

你只负责"发现→报告"。评估、决策、执行由 CCC 负责。
