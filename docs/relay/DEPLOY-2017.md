# CCC Relay · 2017 部署 Runbook（Flash 单通道）

> **目标**：Mac2017 部署 / 热更 CCC Relay；Engine / OpenCode 走 **flash** 同池。  
> **权威**：[`docs/product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「CCC Relay」· [`KEY-POOL.md`](KEY-POOL.md)  
> **约束**：2017 `git pull --ff-only`；单实例 `:4000`/`:4002`；**fail-open 不可协商**；密钥不进 git。

---

## 0. 前置

```bash
node --version   # >= 18
lsof -nP -iTCP:4000 -sTCP:LISTEN || true
```

---

## 1. 拉码 + 编译

```bash
cd /Users/fan/program/CCC
git pull --ff-only origin main
cd relay && npm ci && npm run build
# 验证: ls dist/
```

---

## 2. upstreams（Flash-only）

```bash
mkdir -p ~/.ccc/relay && chmod 700 ~/.ccc/relay
cp ~/program/CCC/templates/relay-upstreams.example.json ~/.ccc/relay/upstreams.json
chmod 600 ~/.ccc/relay/upstreams.json
# 编辑真 key：
# 免费：zen/v1 + *-free/GLM · billing=zen-free|zhipu-failover · free=true · 直连（禁止 proxy）
# 收费：zen/go/v1 + deepseek-v4-flash · billing=opencode-go · free=false · tier_priority=80
#        恰好 2 把启用；request_overrides.thinking.type=disabled
# Pro/code：enabled:false（轮空）
$EDITOR ~/.ccc/relay/upstreams.json
# 同步刷新本机 KEY-INVENTORY.md（0600）
```

**Flash 契约检查**（只需启用 flash；Pro/code 可轮空）：

```bash
python3 -c "
import json
cfg = json.load(open('$HOME/.ccc/relay/upstreams.json'))
ups = cfg if isinstance(cfg, list) else cfg.get('upstreams') or []
flash = [u for u in ups if u.get('enabled', True) is not False and (u.get('tier') or '').lower()=='flash']
paid = [u for u in flash if not u.get('free', False)]
proxy = [u['name'] for u in flash if u.get('proxy')]
print('flash_n', len(flash), 'paid_n', len(paid), 'proxy_flash', proxy or 'none')
assert flash, 'need enabled flash'
assert len(paid) == 2, 'need exactly 2 paid Go flash'
assert not proxy, 'flash must not set proxy'
print('OK')
"
```

---

## 3. 装 plist + 启动

```bash
cd /Users/fan/program/CCC
bash scripts/install-relay-plist.sh --start --host 2017
launchctl list | grep ccc.relay
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:4000/admin/status
```

可选看门狗：`bash scripts/install-relay-flash-watchdog-plist.sh`

---

## 4. Engine / OpenCode → flash

```bash
bash scripts/ccc-autostart-guard.sh enable --start
# Engine 默认 OPENCODE_MODEL=loop/flash（scripts/ccc-engine.sh）

cp ~/program/CCC/templates/opencode.relay.example.json ~/.config/opencode/opencode.json
chmod 600 ~/.config/opencode/opencode.json
# model 应为 loop/flash；provider loop → http://127.0.0.1:4002/v1

# 直连兜底（fail-open）可选：
# cp templates/opencode.direct.example.json ~/.config/opencode/opencode.direct.json
```

---

## 5. 烟测

```bash
curl -sS -m 30 -D - -o /dev/null http://127.0.0.1:4000/v1/messages \
  -H 'content-type: application/json' \
  -d '{"model":"flash","max_tokens":16,"messages":[{"role":"user","content":"ping"}]}' \
  | grep -iE 'HTTP/|X-Routed'

curl -sS 'http://127.0.0.1:4000/admin/usage?period=1h' | python3 -m json.tool | head
# 勿用 GET /health 判 Anthropic 口（易 404）
```

PaidGuarantee / cache：见 KEY-POOL §2.1；证据 [`../briefs/2026-07-28-relay-flash-seal.md`](../briefs/2026-07-28-relay-flash-seal.md)。

---

## 6. fail-open（摘要）

杀 `com.ccc.relay.2017` 后客户端须能降级直连（`CCC_RELAY_DIRECT_URL` / `~/.ccc/relay-direct.url`），任务不 block。详见 authority fail-open 红线。

---

## 7. 回滚

```bash
launchctl kickstart -k "gui/$(id -u)/com.ccc.relay.2017"
# 或 bootout + 移走 plist（见历史归档步骤）
```

---

## 8. 排障

| 现象 | 排查 |
|------|------|
| 503 / 慢 | cooldown：`GET/POST /admin/cooldowns`；付费是否试到（PaidGuarantee） |
| Go 401 | 钥误打 `zen/v1` → 改 `zen/go/v1` |
| OpenCode 空转 | thinking 未关；确认 `thinking.type=disabled` |
| 假红 | 勿用 `/health`；改 `POST /v1/messages` |
| cache 低 | 检查 pinPaid / 禁 flash `proxy`（打冷缓存） |

**SSOT**：authority「CCC Relay（硬 · 2026-07-28 · Flash 单通道）」。
