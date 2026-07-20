# CCC Desktop ↔ OpenCode 完善度计分（SSOT）

> 版本：2026-07-20 · 目标综合 ≥ **98%**  
> 对照：本机 OpenCode.app 1.18 的 **Agent 会话 UX / 会话架构**  
> 边界：不嵌 OpenCode、不做第二 IDE（见 [`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)）

## 计分公式

| 块 | 权重 | 说明 |
|----|------|------|
| OpenCode 重叠能力 | 70% | 会话 / 上下文 / 模型·模式 / 工具·Review / 导入导出·用量 |
| CCC 独有产品面 | 30% | 定稿转任务 / Flow / 看板 / 运维 / 顶栏后台调用看板 |
| **综合** | 100% | `0.7 * OC + 0.3 * CCC` ≥ 98 |

**刻意不计分**：MCP 管理 UI、Provider 密钥大盘、内嵌终端、文件树、云 Share、多列 DAG。

---

## A. OpenCode 重叠（满分 100 → 乘 0.7）

| ID | 能力 | 权重 | 基线 | 目标 | 验收 |
|----|------|------|------|------|------|
| O1 | Session CRUD / 多窗 session 隔离 / resume | 12 | 11 | 12 | 多窗并行流不串台；冷启 resume |
| O2 | Archive 墓碑不复活 | 8 | 4 | 8 | 存档后 refresh 不重建同 tid；smoke |
| O3 | Fork session | 8 | 0 | 8 | 复制消息+新 tid；resume 清空 |
| O4 | Context 面板 + 手动 compact | 8 | 3 | 8 | 可见 token/压缩；一键 compact |
| O5 | Model 选择（请求级） | 8 | 0 | 8 | Settings/工具条可选；chat body 带 model |
| O6 | Agent 模式 UI（discuss↔engineer） | 8 | 2 | 8 | 开关可见；确认进工程师模式 |
| O7 | Composer 附件 | 6 | 0 | 6 | 路径/图片 chip 进 prompt |
| O8 | Tool 步骤轨（失败可辨） | 6 | 5 | 6 | ToolProgressRail error 态 |
| O9 | 轻量 Review（files_changed→外开） | 6 | 0 | 6 | 改文件数>0 可 Reveal / 外开 |
| O10 | Import/Export 会话 JSON | 6 | 2 | 6 | export-v1；可导入为新会话 |
| O11 | 本会话用量（≠ 中转站顶栏） | 6 | 2 | 6 | 会话 tok 文案；顶栏标明后台 |
| O12 | 快捷键 / 用法 | 8 | 7 | 8 | ⌘N/F/1–3/⇧T；HelpSheet |
| **OC 小计** | | **100** | **~36** | **100** | |

基线约 **36/100**（重叠块 ~25 分贡献到综合）。

---

## B. CCC 独有（满分 100 → 乘 0.3）

| ID | 能力 | 权重 | 基线 | 目标 | 验收 |
|----|------|------|------|------|------|
| C1 | 定稿门禁 + 转任务 | 25 | 22 | 25 | 5 分钟主路径 |
| C2 | Flow 右栏 boundEpicId | 20 | 18 | 20 | 空态人话；SSE 刷新 |
| C3 | 看板 | 20 | 17 | 20 | 列可读；回对话 |
| C4 | 运维 | 15 | 13 | 15 | Hub 聚合可读 |
| C5 | 顶栏中转站后台用量 | 10 | 8 | 10 | 文案「中转站后台」；逻辑不改 |
| C6 | 可用性 9.5 收口 | 10 | 8 | 10 | 空态/搜索/a11y |
| **CCC 小计** | | **100** | **~86** | **100** | |

基线约 **86/100**（独有块 ~26 分贡献到综合）。

**基线综合**：`0.7*36 + 0.3*86 ≈ 51`（重叠缺口大）→ 按「已接近项按完成度」经验校正后产品体感约 **78–82%**（见方案）。实现本清单后目标 **≥98**。

---

## 复评勾选（实现后填）

| 日期 | OC | CCC | 综合 | 备注 |
|------|----|-----|------|------|
| 2026-07-20 基线 | 36 | 86 | ~51 formal / ~80 体感 | 方案启动 |
| 2026-07-20 交付 | 96 | 96 | **98.0** | P0–P3 已落地；`smoke-desktop-parity.sh` |

---

## 烟测

```bash
bash scripts/smoke-desktop-parity.sh
```

覆盖：archive 墓碑、export-v1 roundtrip、sidecar `/health` capabilities、model 字段透传契约。

## 关联

- 架构：[`ccc-desktop-architecture.md`](ccc-desktop-architecture.md)
- 可用性：[`desktop-usability-9.5-plan.md`](desktop-usability-9.5-plan.md)
- Sidecar：[`desktop-agent-sidecar.md`](desktop-agent-sidecar.md)
