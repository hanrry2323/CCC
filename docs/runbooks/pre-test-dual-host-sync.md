# 测前双机对齐与清扰（Runbook）

> **目的**：开测前让 M1 / Mac2017 / Desktop / sidecar 跑同一 commit，并清掉会污染右栏、Engine、绑定态的残留。  
> **权威**：平台改仓只在 Cursor（M1）；2017 用 **`git pull --ff-only`**，禁止整仓 rsync 当 SSOT（见 [`../product/dev-channel.md`](../product/dev-channel.md)）。  
> **核对命令**：[`../deploy/dual-host-version-check.md`](../deploy/dual-host-version-check.md) · `bash scripts/ccc-dual-host-check.sh`

## 0. 测前不要做什么

- 不要在 2017 上手改 `scripts/` 后不提交（会与 `origin/main` 分叉，下次 pull 冲突）。
- 不要把 `routers/desktop.py` rsync 进 `services/`（会留下假模块，干扰 import）。
- 不要在 `invent` / 非队列消费模式下开测（现网默认 `invent_hard_disabled=true`，保持即可）。
- 不要假设「Hub API 已新 = Desktop 已新」——Desktop 必须重装二进制。

## 1. M1：落盘 → 推远程

```bash
cd ~/program/CCC
git status -sb
# 确认只含本次意图改动后：
git add -A && git commit -m "…" && git push origin main
git rev-parse --short HEAD   # 记下目标 sha
```

## 2. Mac2017：丢掉脏树 → 对齐 main → 重启编排面

```bash
ssh mac2017 'bash -s' <<'BASH'
set -euo pipefail
cd ~/program/CCC
git fetch origin
# 丢弃未提交热补丁 / 误同步文件（以 origin/main 为准）
git reset --hard origin/main
git clean -fd -- scripts/chat_server/services/desktop.py 2>/dev/null || true
git pull --ff-only origin main
git rev-parse --short HEAD
# 编排面：Hub 必重启；Board/Engine 有脚本改动才重启
launchctl kickstart -k "gui/$(id -u)/com.ccc.chat-server"
launchctl kickstart -k "gui/$(id -u)/com.ccc.board"
launchctl kickstart -k "gui/$(id -u)/com.ccc.engine"
BASH
```

## 3. M1：重装 Desktop + 踢 sidecar / 隧道

```bash
cd ~/program/CCC/desktop
bash scripts/package-baseline.sh
rm -rf /Applications/CCCDesktop.app
cp -R .build/CCCDesktop.app /Applications/
launchctl kickstart -k "gui/$(id -u)/com.ccc.agent-sidecar"
launchctl kickstart -k "gui/$(id -u)/com.ccc.hub-tunnel" 2>/dev/null || true
# 关掉旧 Desktop 再开，避免仍跑旧二进制
```

## 4. 清测试干扰（按项目）

### 4.1 Hub 右栏绑定（沉底 epic 幽灵轨）

```bash
# 在 2017：清空项目 last_epic / epic_history（示例 qb）
ssh mac2017 'python3 -' <<'PY'
from pathlib import Path
d = Path.home() / "program/CCC/.ccc/chat/_desktop/qb"
d.mkdir(parents=True, exist_ok=True)
(d / "last_epic.json").write_text("{}\n", encoding="utf-8")
(d / "epic_history.json").write_text("[]\n", encoding="utf-8")
print("cleared", d)
PY
```

Hub ≥ 本 runbook 对应版本后：`ui_hidden` 终态 epic 不会再进 `/flow/epics` 的 `bound_hint`；snapshot 对沉底卡返回 `empty` + `sunk`，Desktop 清轨。

### 4.2 Desktop 本机 flow 缓存

```bash
# 清指定项目会话 flow（不删对话正文时可只把 flow 置 null）
python3 - <<'PY'
from pathlib import Path
import json
root = Path.home() / "Library/Application Support/CCCDesktop/sessions/qb"
for p in root.rglob("*.json"):
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    if isinstance(data, dict) and data.get("flow"):
        data["flow"] = None
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("cleared flow", p)
PY
rm -f "$HOME/Library/Application Support/CCCDesktop/board-cache-qb.json"
```

### 4.3 Engine 孤儿 active_tasks

看板已无对应卡、但 `~/.ccc/engine-active-tasks.json` 仍挂 tid 时，Engine 会误占槽：

```bash
ssh mac2017 'python3 -' <<'PY'
import json
from pathlib import Path
p = Path.home() / ".ccc/engine-active-tasks.json"
data = json.loads(p.read_text()) if p.is_file() else {}
# 例：删掉已 quarantine / 板上已无的 qb 孤儿
drop = [k for k in data if "091fa83b-w1" in k or "606b5bb8-w1" in k]
for k in drop:
    data.pop(k, None)
    print("dropped", k)
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
PY
launchctl kickstart -k "gui/$(id -u)/com.ccc.engine"
```

### 4.4 控制面

```bash
# 只读核对；勿在测中擅自降到 ui/disabled
ssh mac2017 'python3 -c "import json;c=json.load(open(\"$HOME/.ccc/control.json\"));print(c.get(\"mode\"), c.get(\"policy\",{}).get(\"invent_hard_disabled\"), c.get(\"policy\",{}).get(\"queue_consumer_only\"))"'
# 期望：enabled / True / True
```

## 5. 验收门（开测前必绿）

```bash
# 双机 VERSION + commit
CCC_SERVER=http://127.0.0.1:17777 bash scripts/ccc-dual-host-check.sh

# Hub 右栏对空闲仓（例 qb）
curl -sS -u ccc:ccc "http://127.0.0.1:17777/api/desktop/flow/epics?project_id=qb&limit=5"
# 期望：epics=[] 且 bound_hint=null（若该仓无在飞任务）

curl -sS -u ccc:ccc "http://127.0.0.1:17777/api/desktop/lens/qb/board"
# 期望：inflight_total=0；活跃 counts 与意图一致

# Desktop 二进制晚于源码
stat -f '%Sm %N' -t '%Y-%m-%d %H:%M' \
  desktop/Sources/CCCDesktop/AppModel.swift \
  /Applications/CCCDesktop.app/Contents/MacOS/CCCDesktop
```

## 相关

- Desktop 部署清单：[`../deploy/desktop.md`](../deploy/desktop.md)
- 开发通道：[`../product/dev-channel.md`](../product/dev-channel.md)
- 右栏绑定契约：[`../product/flow-events.md`](../product/flow-events.md)（沉底 / `sunk` / `missing_on_board`）
