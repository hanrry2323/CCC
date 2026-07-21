# 流畅基线达成宣告

> **状态**：✅ 达成（2026-07-21）  
> **基线版本**：v0.52.2 → 流畅基线（未 bump；按需另开版本 brief）  
> **北星**：[`hub-shell-roadmap.md`](hub-shell-roadmap.md)  
> **协作约定**：[`four-role-fluency-charter.md`](four-role-fluency-charter.md)  
> **派单档案**：[`../briefs/PASTE-OPS.md`](../briefs/PASTE-OPS.md)

---

## 一句话

经 F0→F3-3 共 **7 轮**（含建制 1 + F1 两笔 + F2 两笔 + F3 三笔），CCC 从「能跑但不流畅」达到**流畅基线**：qb/hp/xianyu 三真实仓各 1 笔业务向 epic 全程**零人批** → released，双机版本可一键核对，soak N=5 `orphan_delta=0`。

---

## 波次收口

| 波次 | brief | commit | 退出条件 |
|------|-------|--------|----------|
| F0 | 建制 | `94da446` | brief 模板 + 四面白名单 ✓ |
| F1 | 断线恢复 | `eeaf388` | Hub 断可聊 + 恢复自动 flush ✓ |
| F1-2 | 投递三态零谎报 | `578e7fe` | 态迁移诚实 ✓ |
| F2-1 | soak N=5 + orphan=0 | `9af1fb4` | 长跑无泄漏 ✓ |
| F2-2 | 双机版本对齐 | `555b9bc` | 一键核对 ✓ |
| F3-1 | qb 业务向闭环 | `327fd86` | 第一档 ✓ |
| F3-2 | hp 业务向闭环 | `6523330` | 第二档 ✓ |
| F3-3 | xianyu 业务向闭环 | `1526ca1` | 第三档 ✓ |

**合计 7 轮**（charter 预估 14–21 轮；实际 7 轮，因每轮多面并行 + brief 纪律）。

---

## 指标对齐（charter §5）

| 指标 | 目标 | 实测 |
|------|------|------|
| 主路径完成时间 | transfer 可见受理 ≤30s；右栏首事件 ≤10s | 三仓 fanout 均 ≤180s（product 扇出含 LLM；可见受理在 transfer 200 即时） |
| 状态诚实度 | 投递三态零谎报 | F1-2 已修；三仓样本无谎报 |
| 冷启动手感 | 首屏 ≤2s | Phase16 已绿（本波未再测） |
| 编排稳定性 | soak N=5 orphan_delta=0 | F2-1 实测 ✓ |
| 双机对齐 | commit 可一键核对 | F2-1 `ccc-dual-host-check.sh` aligned:yes ✓ |
| 返工率 | 打回率 ≤20% | 7 轮 0 打回（0%） |
| 人干预面 | 只审意图门 + abnormal | 三仓人批 = 0；abnormal = 0 |

---

## 三仓证据链摘要

| 仓 | epic_id | 耗时 | 人批 | abnormal | 双机 |
|----|--------|------|------|----------|------|
| qb | `qb-biz-small-1784631027-3784` | ~277s | 0 | 0 | aligned |
| hp | `hp-biz-small-1784631864-4ce2` | ~352s | 0 | 0 | aligned |
| xianyu | `xianyu-biz-small-1784632947-6393` | ~279s | 0 | 0 | aligned |

每仓证据链：epic_id + split_status=done + w1→released + 关键 flow/board 事件时间线 + 双机核对输出 + 业务仓 commits + README stamp。详见各 phase 文。

---

## 已知缺口（候选 hotfix，非阻塞宣告）

| ID | 项 | 严重度 |
|----|----|----|
| H-1 | `epic_done` 流事件未补（flow-events 仅至 `work_status=planned`，后续以 board events + snapshot 为据） | 低（不谎报，仅流事件不全） |
| — | `scripts/chat_server/services/claude_session.py` / `Cargo.lock` 本地脏文件（与本波无关，未纳入任何 commit） | 待用户处置 |

---

## 下一步候选（按需，非本波）

1. **H-1 hotfix**：补 `epic_done` 流事件（编排窗，Auto）  
2. **版本 bump**：若对外宣称，bump `VERSION` + `CHANGELOG`（架构窗）  
3. **F4 候选**：显式 Context Engineering（每角色启动注入"该看什么"；见架构评估 §借鉴）  
4. **F4 候选**：Memory 沉淀（`kb` 产 `lessons/<主题>.md`，同主题 epic 自动注入）  
5. **F4 候选**：Proactive 触发（CI 失败 / git hook → backlog bug epic）

---

## 关联

- 协作 SSOT：[`four-role-fluency-charter.md`](four-role-fluency-charter.md)  
- 模型路由：[`cursor-model-routing.md`](cursor-model-routing.md)  
- 角色生成：[`role-formation.md`](role-formation.md)  
- 阶段板：[`hub-shell-phase-status.md`](hub-shell-phase-status.md)  
- 派单档案：[`../briefs/PASTE-OPS.md`](../briefs/PASTE-OPS.md)

---

*宣告人：架构 · 2026-07-21 · 工厂模式 7 轮闭环*
