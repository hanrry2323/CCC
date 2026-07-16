# CCC 介绍 Walkthrough — 截图分镜与旁白

> 按序截图，文件放入 [`assets/intro/`](assets/intro/)。  
> 配音可直接念「旁白」列；视频时间轴见 [`releases/intro-video-script.md`](releases/intro-video-script.md)。

---

## 拍摄环境

- URL：`http://127.0.0.1:7777`（或局域网 IP）· 账密 `ccc` / `ccc`  
- 主题：浅色（对外截图更清晰）  
- 桌面：1440×900 或 1512×982；手机：iPhone 逻辑分辨率竖屏一张（07）  
- 脱敏：勿入真实客户数据、密钥、内网未授权 IP（可用示例项目名）

---

## 分镜表

| # | 文件名 | 画面 | 旁白（约） |
|---|--------|------|------------|
| 01 | `01-hub-home.png` | Hub 对话首页：品牌 + 空状态或短对话 + 底部 composer | 「入口不是 IDE，是 CCC Hub——人对意图，系统对闭环。」 |
| 02 | `02-quick-actions.png` | 快捷栏特写：对齐基线 · 下一步 · 定稿方案 · 转任务 · ··· | 「四个快捷动作形成肌肉记忆：对齐、建议、定稿、转任务。」 |
| 03 | `03-dispatch-block.png` | 助手消息中的 `CCC_DISPATCH` 块（可裁切敏感路径） | 「定稿把方案冻成可执行契约，而不是又一段闲聊。」 |
| 04 | `04-dispatch-card.png` | 转任务卡：标题 / 项目 / Skill 软偏好 / 下达并开工 | 「一点下达：挂上 plan 与 phases，可选 Skill 软偏好，开工。」 |
| 05 | `05-board.png` | 看板：任务在某一列（planned 或 in_progress） | 「Loop 在看板上跑：拆解、开发、验收、重试，人盯结果。」 |
| 06 | `06-console.png` | 控制台或 runtime 条：控制面 + 失败/重开 | 「失败可重开；控制面默认关闭常驻，安全由你显式打开。」 |
| 07 | `07-mobile.png`（可选） | iPhone 竖屏：对话 + 输入框同屏可见 | 「手机也能一屏用完，不用整页乱滑。」 |

---

## 操作步骤（建议拍摄顺序）

1. 启动 Hub/Board，登录，新开对话，选示例项目 → 拍 **01**  
2. 保证快捷栏可见（有字即可）→ 拍 **02**  
3. 点「定稿方案」，等 `CCC_DISPATCH` 出现 → 拍 **03**  
4. 点「转任务」，卡片展开（可选勾 1 个 Skill）→ 拍 **04**（可先不点下达，或下达后立刻拍）  
5. 打开看板 `#/board` → 拍 **05**  
6. 打开控制台或展示 runtime 状态条 → 拍 **06**  
7. 手机 Safari 硬刷新后 → 拍 **07**  

---

## README / INTRO 引用示例

```markdown
![Hub 首页](assets/intro/01-hub-home.png)
```

占位说明见 [`assets/intro/README.md`](assets/intro/README.md)。

---

## 验收

- [ ] 01–06 文件存在且可读  
- [ ] 无密钥 / 真实客户数据  
- [ ] README「截图导览」可改为嵌入图片（可选）  
- [ ] 旁白时长合计适合 60–90s 视频  
