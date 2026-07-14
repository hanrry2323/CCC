# Plan: patrol-alert-webhook — Patrol 异常告警 webhook

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-patrol-v4.py`（1141 行）、`scripts/_config.py`（273 行）、`scripts/ccc-notify.sh`（90 行）、`scripts/ccc-engine.py`（~2300 行）
- **当前结构要点**：
  1. `ccc-patrol-v4.py` — `_notify_engine_restart(status)`（L851-884）在 Engine RESTARTED/DEAD 时调用 `ccc-notify.sh` 发桌面通知；`main()`（L1037-1133）在 Step 0 检测到 DEAD 或 RESTARTED 时调用通知
  2. `ccc-patrol-v4.py` — `detect_stagnation()`（L741-769）检测连续 6 轮状态无变化，返回警告字符串，但只输出到报告，**不触发任何通知**
  3. `_config.py` — `Config` dataclass（L90-175）+ `__post_init__`（L188-212）环境变量覆盖，是 CCC 配置集中点；当前无 webhook 相关配置
  4. 代码库中**没有任何 webhook 发送基础设施**——`_webhook.py` 不存在，`ccc-notify.sh` 第 7 行有 `"飞书置顶（v0.8 未接）"` 的注释，但从未实现
  5. `ccc-engine.py` — `_quarantine_with_notify()`（L220-248）也发桌面通知，但本次任务仅聚焦 patrol，不改造 engine
- **待改动点**：
  - `scripts/_config.py` — 新增 `webhook_url` 配置项，环境变量 `CCC_WEBHOOK_URL`
  - `scripts/_webhook.py` — **新建** webhook 发送模块（标准库 `urllib.request`，无外部依赖）
  - `scripts/ccc-patrol-v4.py` — `_notify_engine_restart()` 追加 webhook 发送 + stagnation 检测触发 webhook

---

## 范围

- **目标**：Patrol 检测到 Engine DEAD / RESTARTED / 持续停滞时发送 webhook 通知（支持通用 JSON、飞书、钉钉格式），替代目前仅桌面通知
- **只改文件**：`["scripts/_config.py", "scripts/_webhook.py", "scripts/ccc-patrol-v4.py"]`
- **不改文件**：`["scripts/ccc-notify.sh", "scripts/ccc-engine.py", "scripts/ccc-board.py", "scripts/_lessons.py", "tests/"]`
- **执行方式**：`manual`
- **Phase 数**：2

---

## 改动 1（Phase 1）：Webhook 基础设施 — `_webhook.py` + `_config.py` 配置

### 做什么

新建 `scripts/_webhook.py` 作为集中 webhook 发送模块，在 `_config.py` 中添加 `webhook_url` 配置项。`_webhook.py` 使用 Python 标准库 `urllib.request` 发送 HTTP POST，不引入外部依赖。

支持 3 种 webhook 格式自动识别：
1. **通用 JSON**（默认）：POST `{"title": "...", "message": "...", "level": "L2/L3", "source": "patrol-v4", "timestamp": "..."}`
2. **飞书格式**（URL 含 `feishu` 或 `open.feishu.cn`）：POST 飞书卡片消息
3. **钉钉格式**（URL 含 `dingtalk` 或 `oapi.dingtalk.com`）：POST 钉钉 Markdown 消息

所有 HTTP 调用有 10 秒超时，异常静默处理，不阻塞主流程。

### 怎么做

**1a. `scripts/_config.py`** — 在 Config dataclass 的 `# ── HTTP 服务 ──` 段落后（L186 后）新增 webhook_url 字段，并在 `__post_init__` 中添加环境变量覆盖：

```python
    # ── Webhook（v0.32+）──
    webhook_url: str = ""  # Patrol webhook URL，留空禁用；优先级 CCC_WEBHOOK_URL 环境变量
```

`__post_init__` 中新增：
```python
        _env_override_str(self, "webhook_url", "CCC_WEBHOOK_URL")
```

**1b. `scripts/_webhook.py`** — 新建文件，内容：

```python
"""ccc — Webhook 通知发送器（v0.32+）

纯标准库，零外部依赖。支持通用 JSON / 飞书卡片 / 钉钉 Markdown 三种格式。

用法:
    from _webhook import send_webhook
    send_webhook(cfg.webhook_url, "L3", "Engine 重启失败", "需人工介入")
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone

_log = logging.getLogger("webhook")

_TIMEOUT = 10  # HTTP 超时（秒）


def _guess_format(url: str) -> str:
    """根据 URL 推断 webhook 格式：generic / feishu / dingtalk"""
    u = url.lower()
    if "feishu" in u or "open.feishu.cn" in u:
        return "feishu"
    if "dingtalk" in u or "oapi.dingtalk.com" in u:
        return "dingtalk"
    return "generic"


def _build_payload(level: str, title: str, message: str, fmt: str) -> dict:
    """按格式构建请求体"""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if fmt == "feishu":
        return {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": f"[CCC {level}] {title}",
                        "content": [
                            [{"tag": "text", "text": f"{message}\n时间: {ts}"}]
                        ],
                    }
                }
            },
        }
    if fmt == "dingtalk":
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": f"[CCC {level}] {title}",
                "text": f"### [CCC {level}] {title}\n\n{message}\n\n---\n {ts}",
            },
        }
    # generic
    return {
        "title": title,
        "message": message,
        "level": level,
        "source": "patrol-v4",
        "timestamp": ts,
    }


def send_webhook(url: str, level: str, title: str, message: str) -> bool:
    """发送 webhook 通知。异常静默处理，返回 True=成功/False=失败/跳过。

    Args:
        url: webhook URL（空串或空白 = 跳过）
        level: "L1" / "L2" / "L3"
        title: 通知标题
        message: 通知正文

    Returns:
        True 表示发送成功（或 url 为空被跳过），False 表示 HTTP 错误
    """
    url = url.strip()
    if not url:
        return True  # 未配置 = 跳过，不算失败

    fmt = _guess_format(url)
    payload = _build_payload(level, title, message, fmt)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status == 200:
                _log.info("webhook ok (%s, %s)", level, title)
                return True
            _log.warning("webhook HTTP %d: %s", resp.status, body[:200])
            return False
    except (urllib.error.URLError, OSError, ValueError) as exc:
        _log.warning("webhook failed (%s): %s", title, exc)
        return False
```

### 验收清单

- [ ] `_webhook.py` 模块存在，import 不报错
- [ ] `_config.py` `Config` 含 `webhook_url` 字段
- [ ] `_config.py` `__post_init__` 含 `_env_override_str(self, "webhook_url", "CCC_WEBHOOK_URL")`
- [ ] `send_webhook()` 空 URL 时直接返回 True，不发请求
- [ ] `send_webhook()` 通用格式正确 POST JSON `{"title","message","level","source","timestamp"}`
- [ ] `send_webhook()` 飞书格式正确构建 `{"msg_type":"post","content":{"post":{"zh_cn":{...}}}}`
- [ ] `send_webhook()` 钉钉格式正确构建 `{"msgtype":"markdown","markdown":{"title","text"}}`
- [ ] HTTP 超时 10 秒，网络错误静默处理不抛异常
- [ ] URL 格式识别：含 `feishu` → feishu / 含 `dingtalk` → dingtalk / 其他 → generic

### 验收

- [编译检查] `python3 -m compileall -q scripts/_webhook.py scripts/_config.py` → 0 errors
- [语法] `python3 -c "import ast; ast.parse(open('scripts/_webhook.py').read())"` → 无异常
- [模块导入] `python3 -c "from _webhook import send_webhook, _guess_format; print('ok')"` → ok
- [URL 识别] `python3 -c "
from _webhook import _guess_format
assert _guess_format('https://open.feishu.cn/...') == 'feishu'
assert _guess_format('https://oapi.dingtalk.com/...') == 'dingtalk'
assert _guess_format('https://hooks.example.com') == 'generic'
print('url detection: ok')
"`
- [空 URL 跳过] `python3 -c "
from _webhook import send_webhook
assert send_webhook('', 'L3', 't', 'm') == True
assert send_webhook('  ', 'L3', 't', 'm') == True
print('empty url skip: ok')
"`
- [通用格式 payload] `python3 -c "
from _webhook import _build_payload
p = _build_payload('L3', 'Test', 'Msg', 'generic')
assert p['title'] == 'Test' and p['level'] == 'L3' and p['source'] == 'patrol-v4'
print('generic payload: ok')
"`
- [config 存在] `python3 -c "
import sys; sys.path.insert(0, 'scripts')
from _config import Config
c = Config()
assert hasattr(c, 'webhook_url')
print('config.webhook_url exists: ok')
"`

---

## 改动 2（Phase 2）：Patrol 集成 — `_notify_engine_restart()` + stagnation webhook

### 做什么

在 patrol 的两个触发点发送 webhook：
1. **`_notify_engine_restart(status)`**（L851）—— Engine DEAD / RESTARTED 时，在现有桌面通知后追加 webhook 发送。读取 `_config.py` 的 `webhook_url`（或环境变量 `CCC_WEBHOOK_URL`），传给 `send_webhook()`。
2. **`main()` stagnation 检测块**（L1101-1105）—— 当 `detect_stagnation()` 返回非空警告时，发送 stagnation webhook（level=L2）。目前在 `main()` 内直接处理。

两者均通过 `try/except` 保护，不影响主巡检流程。

### 怎么做

**2a. `scripts/ccc-patrol-v4.py`** — 在 `_notify_engine_restart()` 函数体内（L883 的 `except OSError: pass` 之前）追加 webhook 调用。需在函数顶部或外部导入 `_config` 和 `_webhook`：

```python
def _notify_engine_restart(status: str) -> None:
    """Engine 重启/死亡时发桌面通知 + webhook。非阻塞，不抛异常。"""
    notify_script = CCC_HOME / "scripts" / "ccc-notify.sh"
    if not notify_script.is_file():
        return
    try:
        if status == "RESTARTED":
            subprocess.Popen(
                [
                    "bash",
                    str(notify_script),
                    "L2",
                    "Engine 自动重启",
                    "Patrol-v4 检测到 Engine 已停止，已自动重启完成",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        elif status == "DEAD":
            subprocess.Popen(
                [
                    "bash",
                    str(notify_script),
                    "L3",
                    "Engine 重启失败",
                    "Patrol-v4 尝试自动重启 Engine 失败，需人工介入",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except OSError:
        pass

    # v0.32: webhook 通知（无论 RESTARTED 还是 DEAD）
    try:
        from _config import Config
        from _webhook import send_webhook

        cfg = Config()
        if cfg.webhook_url:
            level = "L3" if status == "DEAD" else "L2"
            title = "Engine 自动重启" if status == "RESTARTED" else "Engine 重启失败"
            msg = (
                "Patrol-v4 检测到 Engine 已停止，已自动重启完成"
                if status == "RESTARTED"
                else "Patrol-v4 尝试自动重启 Engine 失败，需人工介入"
            )
            send_webhook(cfg.webhook_url, level, title, msg)
    except Exception:
        pass
```

**2b. `scripts/ccc-patrol-v4.py`** — 在 `main()` 中 Step 4 的 stagnation 检测块（L1101-1105）追加 webhook。现有代码：

```python
    # ── Step 4: 状态持久化 ──
    warn = detect_stagnation(ws_stats)
    if warn:
        warnings.append(warn)
    save_patrol_state(ws_stats, engine_status, all_fix_ops, len(all_stuck_ops), warn)
```

改为：

```python
    # ── Step 4: 状态持久化 ──
    warn = detect_stagnation(ws_stats)
    if warn:
        warnings.append(warn)
        # v0.32: stagnation webhook
        try:
            from _config import Config
            from _webhook import send_webhook

            cfg = Config()
            if cfg.webhook_url:
                send_webhook(cfg.webhook_url, "L2", "Patrol 持续停滞", f"连续 6 轮状态无变化: {warn}")
        except Exception:
            pass
    save_patrol_state(ws_stats, engine_status, all_fix_ops, len(all_stuck_ops), warn)
```

### 验收清单

- [ ] Engine RESTARTED 时 webhook 发送（level=L2，title="Engine 自动重启"）
- [ ] Engine DEAD 时 webhook 发送（level=L3，title="Engine 重启失败"）
- [ ] 持续停滞检测触发时 webhook 发送（level=L2，title="Patrol 持续停滞"）
- [ ] `CCC_WEBHOOK_URL` 为空时跳过 webhook，不报错
- [ ] webhook 发送异常不影响 patrol 主流程

### 验收

- [编译检查] `python3 -m compileall -q scripts/ccc-patrol-v4.py` → 0 errors
- [语法] `python3 -c "import ast; ast.parse(open('scripts/ccc-patrol-v4.py').read())"` → 无异常
- [webhook 调用 - notify] `grep -n "send_webhook" scripts/ccc-patrol-v4.py | grep -i "restart\|dead"` → `_notify_engine_restart()` 内匹配（至少 1 处）
- [webhook 调用 - stagnation] `grep -n "send_webhook" scripts/ccc-patrol-v4.py | grep -i "stagnat\|停滞"` → `main()` 内匹配
- [try/except 保护] `grep -n "from _webhook import" scripts/ccc-patrol-v4.py` → 至少 2 处（notify + stagnation），均在 try 块内
- [功能 - 空 URL] `CCC_WEBHOOK_URL="" python3 -c "
import sys; sys.path.insert(0, 'scripts')
from _webhook import send_webhook
assert send_webhook('', 'L2', 't', 'm') == True
print('空 URL skip ok')
"`
- [测试] `python3 -m pytest tests/scripts/ -q --timeout=60` → 全部通过

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 新建 `_webhook.py` + `_config.py` webhook_url 配置 | `feat(webhook): 新增 _webhook.py 发送模块 + webhook_url 配置 (phase 1/2)` |
| 2 | patrol 集成：`_notify_engine_restart()` + stagnation 触发 webhook | `feat(patrol): Engine 重启/停滞时发送 webhook 通知 (phase 2/2)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`python3 -m compileall -q scripts/_webhook.py scripts/_config.py scripts/ccc-patrol-v4.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/scripts/ -q --timeout=60`）
- [ ] diff 范围仅限 `scripts/_webhook.py`、`scripts/_config.py`、`scripts/ccc-patrol-v4.py`
- [ ] 2 个 commit，每个对应一个 phase
- [ ] phases.json phase 数 = 2
- [ ] Plan 中所有验收意图全部达成
- [ ] `CCC_WEBHOOK_URL` 环境变量未设置时 patrol 行为完全不变（webhook 静默跳过）
- [ ] webhook 格式自动识别、通用/飞书/钉钉三种格式均正常工作
- [ ] stagnation webhook 仅在真正检测到停滞时触发，不误报

---

## 后续步骤

- 可考虑在 `ccc-engine.py` 的 `_quarantine_with_notify()` 中也集成 webhook（但本次聚焦 patrol）
- 飞书/钉钉 webhook URL 需要在对应平台申请，用户需设置 `CCC_WEBHOOK_URL` 环境变量
- 后续可增加 webhook 重试机制（当前失败静默跳过）
- 审计脚本（audit_role）可参照此模式加入 webhook