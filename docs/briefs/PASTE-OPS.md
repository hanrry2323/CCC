# PASTE-OPS · 工厂派单板（用户只复制）

> 架构窗维护本文件。用户：**不讨论、不加需求**，按序把「粘贴包」贴进对应窗。  
> 模型路由：[`../product/cursor-model-routing.md`](../product/cursor-model-routing.md)

## 流水线状态

| 序号 | brief | 状态 | 窗 |
|------|-------|------|-----|
| F0 | 建制 | done | — |
| F1 | 断线恢复 | done `eeaf388` | — |
| F1-2 | 投递三态零谎报 | done `578e7fe` | — |
| F2-1 | soak N=5 + orphan=0 | done `9af1fb4` | — |
| F2-2 | 双机版本对齐核对 | done `555b9bc` | — |
| F3-1 | qb 业务向闭环 | done `327fd86`（流畅基线第一档） | — |
| F3-2 | hp 业务向闭环 | accepted · **现在开工** | 编排 · **Auto** |
| F3-3 | xianyu 业务向闭环 | queued | — |
| H-1 | `epic_done` 流事件补齐（hotfix 候选） | queued | — |

---

## 粘贴包 A · 壳窗 / 过桥窗

```
本波次 F3-2 只派编排窗。壳 / 过桥待命，无 brief 勿改代码。
```

---

## 粘贴包 B · 编排窗 · F3-2 开工（现在贴这个）

```
模型：Auto
只认 brief：docs/briefs/2026-07-21-f3-hp-business-closure.md
白名单：apps/hp/（业务仓；按需读/写业务文档）
        scripts/smoke-hp-biz-small.sh（若需新增/调整；可仿 qb 模板）
        docs/product/hub-shell-phase8-hp.md（追加证据链段，不动既有结论）
        docs/product/hub-shell-phase-status.md（仅新增 F3-2 行）
        docs/briefs/2026-07-21-f3-hp-business-closure.md（填 §8）
禁止：改 Engine 主循环、改 Hub API、改 Desktop、改 transfer/flow 契约、改无关文件。
做完：填 brief §8 证据链 → commit → 回复「F3-2 done <hash>」
提交说明建议：
test(hp): business-intent small epic to released with evidence chain (F3-2)
注意：若遇 abnormal，回贴现象，不改 Engine；架构开 hotfix。
```

---

## 粘贴包 C · 架构窗自动节奏

1. 见「F3-2 done」→ 验收 → 写 F3-3（xianyu）  
2. F3 退出条件：qb/hp/xianyu 各 ≥1 笔业务向 epic→released 少干预 → 宣告流畅基线  
3. 候选 hotfix H-1（`epic_done` 流事件）在 F3 后开
