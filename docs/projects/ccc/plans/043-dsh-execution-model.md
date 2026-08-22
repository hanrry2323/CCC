# 方案 · DSH 执行模型定稿与接入（S2 · CCC×DSH 整合）

> 项目：ccc · 编号：ccc-plan-043 · 状态：已确定 · 作者：Claude Code（W1·S140-01@M1） · 工具：Claude Code
> 创建：2026-08-22 · 更新：2026-08-22
> 关联卡：无（平台自研红线：M1 主窗口直接开发 + 异席机审，不走 engine）
> 关联方案：ccc-plan-029（DSH 接入）、042（质量机械验证）、033（人审两环节修订）
> 依据：qx-map `docs/s2-dsh-execution-model-design.md`（详细设计）+ `__archive__/decisions/ccc-dsh整合决策定稿-2026-08-22.md`
> 里程碑：CCC×DSH 整合（8 步计划 S2）

## 目标

把「CCC×DSH 深度绑定」的 S2 执行模型**定稿并接入准备**：DSH 作为开发/机审/质量/运营内核，与 CCC 状态机映射，为 S3（engine 调度改造）铺路。

## 背景（决策已定，本方案为技术落地）

老板 2026-08-22 决策（14 项定稿）：
- CCC = 编排外壳；DSH = 开发/机审/质量/运营内核。
- 人审两环节：出卡 / 审核合入（合入即验收）。
- DSH 执行模型 = 按任务 Cordis 插件编排 + 关键项目常驻会话（混合）。
- DSH 模型直连 + 免费默认（ox-alpha-free）；2017 中转站待退役。
- 运营子 Agent 只执行 SOP 流程、禁止改代码（权限 preset 机械强制）。

DSH 实测（0.1.1-rc.2）：默认已是 opencode-go 直连 + ox-alpha-free；cordis.yml 插件体系就位；agent-presets 机制存在；headless 会话 + end-seed。

## 功能卡 / 设计要点

### 1. 派发接缝（S3 前置）
- Engine dispatch 调 **DSH headless RPC**（建会话执行），不 spawn 子进程。
- 并发槽位对到 CCC 槽位上限；失败/超时/重试路径定义。

### 2. 内部工作流链（Cordis 插件编排）
```
load-card → plan → implement → self-test → audit → writeback
```
- 每步产出进 DSH 会话；机审结论落 CCC ledger（machine_audit_pass 单源）。
- 失败路径：打回 + 原因进卡。

### 3. 状态机映射契约
- 待分派→执行中（派发起编排）→ 已回写（DSH 完成提交）→ 机审（DSH audit）→ 审核合入（人审层）。
- 超时→打回（reason=timeout）；中断可 resume（end-seed）。

### 4. 运营子 Agent
- 一项目一常驻会话；**只执行 SOP 流程、禁止改代码**（权限 preset = workspace-read + SOP-script-run，机械强制）。

### 5. 模型回退链（S2 探索项）
- 实测 DSH 是否原生支持「主+回退」模型链；不支持则加「检测 429/402→切模型重试」路由层。
- **免费模型稳定性实测**：ox-alpha-free 跑一次真实开发链（读卡→改码→自测→回写）；不稳退 mimo-v2.5/hy3。

> **2026-08-22 实测结论（S1 前置，已解决）**：
> 1. 首次探测 429 = **DSH launchd 未配 OPENCODE_GO_API_KEY + ~/.zshrc 旧 key 配额耗尽**（双因）。
> 2. **老板配新 OpenCode key**（已写 `com.deepseek.dsh-web.plist` EnvironmentVariables + `~/.zshrc`，用户本地配置，不进仓）→ **ox-alpha-free 正常响应**。
> 3. **关键验证：ox-alpha-free 带 tools 可工作**（DSH headless 实测真实列出目录 13 文件/9 目录，非幻觉）——免费模型做开发的障碍解除。注意：`~/.zshrc` 里 claude-ox 别名注释「ox-alpha-free 拒绝 tools[1210]」是 Claude Code CLI 场景（`--tools ""`），**DSH headless 场景 tools 可用**，两者不冲突。
> 4. **回退机制仍保留（降为常规保险）**：免费配额确实会耗尽（本次就是），S3 仍落地「429→切备用模型重试」；备用候选 mimo-v2.5/hy3（同 provider 直连）。

## 验收标准

- [ ] 设计定稿已确认（5 技术点）——✅ 已完成
- [ ] 免费模型稳定性实测：DSH 跑通一条真实开发链，记录稳定性结论（稳/退哪个备用模型）
- [ ] 模型回退链：实测 DSH 原生 fallback 支持情况；不支持则路由层方案定稿
- [ ] 状态机映射契约成文（本方案 §3）——✅ 已定
- [ ] 落成后 S3 可启动（engine 调度→DSH 派发的设计输入就绪）

## 执行顺序

```
S2 立项（本方案）→ S1 单机化收口 → 模型实测（S1 前置）→ S3 engine 调度改造
```

## 红线

平台自研：改 server/engine、board、scripts 走 M1 主窗口直接开发 + 异席机审；设计/文档先行，代码改动每步带失败重现测试。
