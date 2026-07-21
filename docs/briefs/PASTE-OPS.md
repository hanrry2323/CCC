# PASTE-OPS · 工厂派单板（用户只复制）

> 架构窗维护本文件。用户：**不讨论、不加需求**，按序把「粘贴包」贴进对应窗。  
> 模型路由：[`../product/cursor-model-routing.md`](../product/cursor-model-routing.md)

## 流水线状态

| 序号 | brief | 状态 | 窗 |
|------|-------|------|-----|
| F0 | 建制 | done | — |
| F1 | 断线恢复 | **done** `eeaf388`（架构已合入；手测可选） | — |
| F1-2 | 投递三态零谎报 | accepted · **现在开工** | 壳 · **Auto** |
| F1-3 | （下一批由架构写） | queued | — |

---

## 粘贴包 A · 壳窗 · F1 已合入（可跳过）

```
F1 已由架构合入：eeaf388。无需再提交断线恢复。
（可选）按 docs/briefs/2026-07-21-f1-disconnect-recovery.md §7 手测一次；有问题只回贴现象，勿扩范围。
下一步直接做粘贴包 B。
```

---

## 粘贴包 B · 壳窗 · F1-2 开工（现在贴这个）

```
模型：Auto
只认 brief：docs/briefs/2026-07-21-f1-transfer-delivery-honesty.md
白名单：AppModel.swift / Models.swift / ContentView.swift（仅投递态）
禁止：改契约字段、改 Engine、改 sidecar、改无关文件。
做完：填 brief §8 → commit → 回复「F1-2 done <hash>」
提交说明建议：
fix(desktop): keep transfer delivery phases honest (F1-2)
```

---

## 粘贴包 C · 过桥窗 / 编排窗

```
本波次 F1 / F1-2 默认不开。无 brief 勿改代码。待命。
```

---

## 架构窗自动节奏（给架构自己）

1. 见「F1 committed」→ 确认 git → 必要时补 §9  
2. 用户贴 B 后壳交付 → 架构验收 F1-2 → 写 F1-3 brief + 更新本 PASTE-OPS  
3. 重复直至 `four-role-fluency-charter` F1 退出条件满足，再进 F2
