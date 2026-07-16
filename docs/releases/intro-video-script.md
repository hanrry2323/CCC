# CCC 介绍视频脚本（60–90 秒）

> 横版 1080p 优先；可另导出竖版封面。  
> 画面素材对齐 [`../INTRO-WALKTHROUGH.md`](../INTRO-WALKTHROUGH.md)。  
> 成片由维护者本地录制后挂到 [GitHub Release](https://github.com/hanrry2323/CCC/releases) 或 README（仓库不强制提交大体积 mp4）。

---

## 元信息

| 项 | 值 |
|----|-----|
| 时长 | 60–90s |
| 画幅 | 1920×1080 |
| 语言 | 中文口播为主；片尾可叠英文一行 |
| BGM | 轻、无歌词；音量低于人声 |
| CTA | github.com/hanrry2323/CCC |

---

## 分轨时间轴

| 时间 | 画面 | 口播 |
|------|------|------|
| 0–10s | 黑场标题「CCC · Loop Engineer」或痛点字卡 | 「有模型、有脚本、有数据库——还是缺一台调度器。」 |
| 10–25s | 录屏：对齐 → 定稿 → 转任务（02→03→04） | 「CCC Hub 用几个快捷动作，把意图变成可执行任务。」 |
| 25–45s | 看板流转 + 可选失败重开（05→06） | 「Engine 自动编排：开发、验收、重试。人盯结果，不盯步骤。」 |
| 45–60s | 字卡对照：角色超市 vs 任务→Skill+Prompt | 「我们不做角色超市。任务路由工具，Skill 加 Prompt，就是无穷角色。」 |
| 60–80s | 字卡：CCC + 行业资产 = 垂直工具；可闪 QX | 「同一底座，挂上爬虫、数据库、worker 和自定义快捷键，就是垂直行业 AI 工具。」 |
| 80–90s | GitHub / Getting Started 画面 | 「开源 MIT。打开 Hub，三步开工。链接在简介。」 |

---

## 片尾字幕（建议）

```text
CCC — Connect–Claude Code
Loop Engineer · Hub 入口 · 无穷角色
github.com/hanrry2323/CCC
docs: INTRO.md · GETTING-STARTED.md
```

---

## 导出与挂载

1. 导出 `ccc-intro-v0421.mp4`（H.264）  
2. 可选封面 `ccc-intro-cover.png`（1280×720）放入 `docs/assets/intro/`  
3. `gh release upload v0.42.1 ccc-intro-v0421.mp4 --clobber`  
4. README 顶部可加：`[Watch intro](release-asset-url)`  

---

## 验收

- [ ] 口播与画面同步，无超时口误  
- [ ] 无内网密码、真实客户数据  
- [ ] 明确说出 Hub 入口 + 非角色超市 + 垂直配方  
