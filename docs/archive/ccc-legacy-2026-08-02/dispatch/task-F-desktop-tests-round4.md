# 任务书 F · 桌面端测试基建 + AppModel 安全拆分（窗口 2）

> 本文件是给 Claude Code 的整段指令，复制全部内容到窗口 2 即可。  
> 背景：桌面端零自动化测试，AppModel.swift 6387 行不敢拆——先补行为锁，再拆安全点。

## 0. 先读

1. `CLAUDE.md`
2. `desktop/README.md`、`desktop/Sources/CCCDesktop/` 结构
3. `docs/dispatch/2026-08-01-squad-dispatch-plan.md`（硬规则必须遵守）

## 1. 任务目标

1. **测试基建**：`desktop/Package.swift` 加测试 target（Swift Testing 或 XCTest，按项目现状选），CI 可跑
2. **行为锁（核心链路）**：`TransferDraftParser`、`SkillRefResolver`、`LocalSessionStore` 编解码（含旧盘项兜底）、`TransferRequest` 字段——把桌面端转任务链路的行为钉死
3. **AppModel 安全拆分**：只抽 1–2 个纯逻辑/低风险点（如 verdict/请求构建），行为不变，有前后行为对比证据；**不做大爆炸、不碰 UI/状态**
4. 构建 + 测试全绿

## 2. 允许范围

- `desktop/`（Swift）全部相关文件、`desktop/Package.swift`、测试文件
- 与测试基建相关的 CI/脚本配置（变更列入报告）

## 3. 红线（禁止）

- `app/`、`scripts/`、web 前端、`src-tauri/`（本窗口只做 Swift 桌面端）
- 4000/4100 relay 相关、密钥/凭据/签名证书类文件
- 启动产线；AppModel 大爆炸拆分（一次只拆 1–2 个安全点）
- 提交 main

## 4. 流程（spec-first 门）

第一轮：`/plan` 输出「测试基建方案 + 行为锁清单 + 拆分候选（含为什么安全）」，**不写代码**。  
确认后实现：先测试后拆分，测试全绿再提交。

## 5. 验收标准

- `swift test` 全绿（基建可用，命令与结果贴证据）
- 行为锁覆盖转任务核心链路（解析 → 映射 → 持久化 → 请求）
- 拆分的点有「拆分前后行为一致」证据；未拆的大模块继续列暂缓
- 提交在 `codex/ws-6-desktop-tests` 分支

## 6. 完成报告格式

发现 → 动作 → 证据 → 遗留（含下一步拆分候选）
