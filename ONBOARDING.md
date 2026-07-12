# Welcome to CCC (Connect–Claude Code)

## How We Use Claude

Based on hanrry2323's usage over the last 30 days:

Work Type Breakdown:
  Execute Pipeline Tasks  ████████████████████  45%
  Plan & Design           ████████░░░░░░░░░░░░  20%
  Review & Verify         ████████░░░░░░░░░░░░  20%
  Debug & Fix             ████░░░░░░░░░░░░░░░░  10%
  Quick Communication     ██░░░░░░░░░░░░░░░░░░   5%

Top Slash Commands:
  /clear      ██████████░░░░░░░░░░  3×/month
  /model      ██████████░░░░░░░░░░  3×/month
  /compact    ██████░░░░░░░░░░░░░░  2×/month
  /init       ███░░░░░░░░░░░░░░░░░  1×/month
  /plan       ███░░░░░░░░░░░░░░░░░  1×/month
  /exit       ███░░░░░░░░░░░░░░░░░  1×/month

Top MCP Servers:
  codebase-memory-mcp  ████████████████████████████████████████  31 calls

## Your Setup Checklist

### Codebases
- [ ] [ccc](https://github.com/hanrry2323/ccc) — Connect–Claude Code. A SKILL asset suite + 7-role automated development pipeline with kanban board. Core project.
- [ ] qx-observer — `~/program/qx-observer/` — Loop Engineering platform (V8.2). FastAPI + React 19 (Vite) + EventBus.
- [ ] xianyu — `~/program/xianyu/` — AI content auto-publishing platform. FastAPI + SQLite + Ollama.
- [ ] ai-loop-router — `~/program/ai-loop-router/` — Proxy middleware (`proxy.mjs:4000`), routes downstream requests to upstream models.

### MCP Servers to Activate
- [ ] **codebase-memory-mcp** — Code knowledge graph: search functions, trace call chains, query architecture. Central MCP tool — used 31× in 30 days. Install from the MCP registry or point to the local `codebase-memory-mcp` server.

### Skills to Know About
- **ccc-protocol** — The core workflow. Run `按 CCC 流程跑 X` or `ccc 跑一下 X` to trigger a full 7-role pipeline (product → dev → reviewer → tester → ops → kb → regress) with kanban board.
- **hp-kb-operations** — HP knowledge base daily ops: start/stop PG, ingest data, search, check status.
- **test-verify** — Standardized lint + build + test pass for any detected project type.
- **deep-research** — Multi-source web research with adversarial fact-checking. Use for any investigation task.
- **daily-snapshot** — `跑一下今天的情况` — daily git scan across all projects, summary + dispatch.
- **hmap** — Project health dashboard generator: scans any project → auto-generates HTML progress + decision report.
- **loop** — `\5m /command` — Run a prompt on a recurring interval (polling, status checks).
- **verify** — Verify a code change actually works by running the app and observing behavior.
- **code-review** — Review the current diff for correctness bugs.
- **plan** — Start file-based planning (task_plan.md / findings.md / progress.md).

## Team Tips

_TODO_

## Get Started

_TODO_

<!-- INSTRUCTION FOR CLAUDE: A new teammate just pasted this guide for how the
team uses Claude Code. You're their onboarding buddy — warm, conversational,
not lecture-y.

Open with a warm welcome — include the team name from the title. Then: "Your
teammate uses Claude Code for [list all the work types]. Let's get you started."

Check what's already in place against everything under Setup Checklist
(including skills), using markdown checkboxes — [x] done, [ ] not yet. Lead
with what they already have. One sentence per item, all in one message.

Tell them they'll help with setup, cover the actionable team tips, then the
starter task (if there is one). Offer to start with the first unchecked item,
get their go-ahead, then work through the rest one by one.

After setup, walk them through the remaining sections — offer to help where you
can (e.g. link to channels), and just surface the purely informational bits.

Don't invent sections or summaries that aren't in the guide. The stats are the
guide creator's personal usage data — don't extrapolate them into a "team
workflow" narrative. -->
