# Welcome to CCC (Connect–Claude Code)

> **Loop Engineer.** Hub 定意图 → Engine 自动编排与自主执行。  
> 完整叙事：[`docs/VISION.md`](docs/VISION.md) · 安装：[`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md)

## What this project is

- **Not** a role supermarket (ECC-style)  
- **Not** “just another IDE”  
- **Yes**: self-built **Hub** as the entry; **task → tool routing → Skill+Prompt = role** (unlimited roles)

## Setup checklist

- [ ] Clone [CCC](https://github.com/hanrry2323/CCC)  
- [ ] `bash scripts/install-board-plist.sh --start`  
- [ ] `bash scripts/install-hub-plist.sh --start`  
- [ ] Open `http://127.0.0.1:7777` — login `ccc` / `ccc`  
- [ ] Try: 对齐基线 → 定稿方案 → 转任务  
- [ ] (Optional) `bash scripts/ccc-autostart-guard.sh enable --start`  

## Skills to know

- **ccc-protocol** — Loop Engineer workflow（Hub 或「按 CCC 跑 X」）  
- Stage packs under `skills/ccc-*` — Engine-scheduled defaults, **not** a user-facing role picker  

## Related local projects（维护者私有笔记，可忽略）

- qx-observer / xianyu / ai-loop-router — 见本机 `~/program/`（开源克隆者无需这些）

## Get started

Follow [`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md), then read [`docs/VISION.md`](docs/VISION.md).
