#!/usr/bin/env bash
# traj-digest.sh · DSH 执行轨迹坑清单一键抽取器（ccc084 固化）
#
# 基线：/tmp/dsh-traj-extract.py（环节②交接指令 S116-01 附带的临时取证脚本，重启即失）。
# 本脚本将其逻辑固化为仓内常备巡检工具：对指定卡的执行轨迹一键输出
# 五类坑清单（A 并发架构 / B 派发生命周期 / C macOS 环境 / D 测试基线 / E git 工作流），
# 每条含 类别 / 证据行 / 时间戳，条目编号与环节②指令第二节取证表（A1…E3）对齐。
#
# 用法：
#   scripts/traj-digest.sh <卡号|exec日志路径> [卡号2 ...] [--json] [--out FILE] [--stderr PATH]
#   例：scripts/traj-digest.sh ccc076 ccc077 ccc078 ccc079
#
# 数据源（全部只读，绝不改写任何数据源）：
#   1. 会话轨迹   ~/.dsh/sessions/<worktree>-<卡号>--/*/session.jsonl.zstd（基线脚本主输入）
#   2. exec 日志  $TRAJ_DIGEST_LOG_DIR/exec/<卡号>*.log（runN 重启序列 / 审计标记 / 终报证据行）
#   3. 派发事件  $TRAJ_DIGEST_LOG_DIR/exec/worker-events.jsonl
#   4. 引擎指标  $TRAJ_DIGEST_LOG_DIR/exec/engine-metrics.jsonl（并发水位 + stderr 无时间戳时的对时锚）
#   5. 引擎stderr $TRAJ_DIGEST_LOG_DIR/engine.stderr.log（无时间戳，按行序+metrics 时间窗线性内插，≈标注）
#
# 平台纪律：macOS 优先——不使用 sha256sum/stat -c 等 GNU 专属命令；set -euo pipefail；
#          grep 计数为零返回 1 属已知坑（C5），一律 `|| true` 兜底。
#
# 退出码：0=正常出清单；2=用法错误/卡无任何轨迹数据。

set -euo pipefail

PROG_NAME="$(basename "$0")"

usage() {
    cat <<EOF
用法: ${PROG_NAME} <卡号|exec日志路径> [卡号2 ...] [--json] [--out FILE] [--stderr PATH]

参数:
  卡号            如 ccc076（大小写不敏感）；或 exec 日志路径（自动剥离 .runN/.audit 后缀得卡号）
  --json          输出机器可读 JSON（默认人读文本）
  --out FILE      结果另存文件（默认仅 stdout）
  --stderr PATH   引擎 stderr 路径覆盖（默认 \$TRAJ_DIGEST_LOG_DIR/engine.stderr.log）

环境变量:
  TRAJ_DIGEST_SESSIONS_DIR  会话轨迹根目录（默认 ~/.dsh/sessions）
  TRAJ_DIGEST_LOG_DIR       CCC 运行日志根目录（默认 ~/.ccc/logs）
  TRAJ_DIGEST_STDERR_T0/T1  stderr 对时锚覆盖（ISO8601；缺省用 engine-metrics.jsonl 首末样本时间内插）
EOF
}

if [[ $# -lt 1 ]]; then
    usage >&2
    exit 2
fi

JSON_OUT=0
OUT_FILE=""
STDERR_PATH_ARG=""
CARDS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --json)    JSON_OUT=1; shift ;;
        --out)     OUT_FILE="${2:-}"; shift 2 ;;
        --stderr)  STDERR_PATH_ARG="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        -*)        echo "[traj-digest] 未知参数: $1" >&2; usage >&2; exit 2 ;;
        *)         CARDS+=("$1"); shift ;;
    esac
done

export TRAJ_DIGEST_JSON_OUT="$JSON_OUT"
export TRAJ_DIGEST_OUT_FILE="$OUT_FILE"
export TRAJ_DIGEST_STDERR_PATH_ARG="$STDERR_PATH_ARG"
export TRAJ_DIGEST_CARDS_INPUT="${CARDS[*]}"

# ---- 主逻辑：bash 只做装配，分析全部交给内嵌 python3 ----
python3 <<'PYEOF'
import glob, json, os, re, shutil, subprocess, sys
from collections import Counter, defaultdict
from datetime import datetime

SESSIONS_ROOT = os.environ.get("TRAJ_DIGEST_SESSIONS_DIR") or os.path.expanduser("~/.dsh/sessions")
LOG_ROOT      = os.environ.get("TRAJ_DIGEST_LOG_DIR") or os.path.expanduser("~/.ccc/logs")
EXEC_DIR      = os.path.join(LOG_ROOT, "exec")
WORKER_EVENTS = os.path.join(EXEC_DIR, "worker-events.jsonl")
ENGINE_METRICS= os.path.join(EXEC_DIR, "engine-metrics.jsonl")
STDERR_PATH   = os.environ.get("TRAJ_DIGEST_STDERR_PATH_ARG") or os.path.join(LOG_ROOT, "engine.stderr.log")
JSON_MODE     = os.environ.get("TRAJ_DIGEST_JSON_OUT") == "1"
OUT_FILE      = os.environ.get("TRAJ_DIGEST_OUT_FILE") or ""

ZSTD = shutil.which("zstd")
if not ZSTD:
    print("[traj-digest][FATAL] 未找到 zstd 命令（macOS 可 brew install zstd），无法解压会话轨迹", file=sys.stderr)
    sys.exit(2)

CARD_RE = re.compile(r"^([a-z]+)(\d+)$", re.I)

def norm_card(tok):
    """'ccc076' / '/path/ccc078.run3.log' -> ('ccc078', None|原路径)"""
    tok = tok.strip()
    if os.path.isfile(tok):
        base = os.path.splitext(os.path.basename(tok))[0]
        base = re.sub(r"\.(run\d+|audit|audit\.pre\-rebase|test\-evidence|log)$", "", base)
        m = CARD_RE.match(base)
        return (m.group(0).lower() if m else None), tok
    m = CARD_RE.match(tok)
    return (m.group(0).lower() if m else None), None

def trunc(s, n=280):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s[:n] + ("…[%d chars]" % len(s) if len(s) > n else "")

def fmt_ts(v):
    """毫秒/秒 epoch 或 ISO 字符串 → 'MM-DD HH:MM:SS'；解析失败原样加?"""
    if v is None or v == "":
        return "?"
    try:
        if isinstance(v, (int, float)):
            n = float(v)
            if n >= 1e12:      # 毫秒
                n /= 1000.0
            elif n < 1e9:      # 过小视为脏数据
                return "?" + str(v)[:24]
            return datetime.fromtimestamp(n).strftime("%m-%d %H:%M:%S")
        s = str(v).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo:
            dt = dt.astimezone()
        return dt.strftime("%m-%d %H:%M:%S")
    except Exception:
        return "?" + str(v)[:24]

def iso_to_epoch(v):
    if v in (None, ""):
        return None
    try:
        if isinstance(v, (int, float)):
            return float(v) / 1000.0
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return None

# ---------------- 五类坑检测器（编号对齐环节②指令第二节） ----------------
# (id, 说明, 编译正则)
KW_DETECTORS = [
    # C 类 · macOS 环境层
    ("C1", "sha256sum 缺失/命令不存在(exit 127)", re.compile(r"sha256sum|command not found|exit code: 127", re.I)),
    ("C2", "/var→/private/var symlink 解析差异",   re.compile(r"private/var|symlink.*resolve|符号链接.*解析", re.I)),
    ("C3", "残留进程占端口(Address already in use)", re.compile(r"Address already in use|EADDRINUSE|端口.{0,12}(占用|in use)", re.I)),
    ("C4", "docgate 直跑 No module named 'server'", re.compile(r"No module named ['\"]?server|No module named", re.I)),
    ("C5", "bash 语法坑(括号未引用/unbound/grep -c 空计数)", re.compile(r"(?i:unbound variable|syntax error near|unexpected token)|TERMINAL\(", 0)),
    # D 类 · 测试与基线层
    ("D1", "main 带红测试进分支(断言翻转)", re.compile(r"断言翻转|Red 测试|TestSubdirScan|test_board_loader", re.I)),
    ("D2", "测试隔离缺陷/环境依赖(relay·真实仓写入)", re.compile(r"pre-existing|存量失败|同样失败|conversation 族|:6100|relay 负载|真实.{0,6}(roadmap|仓)|stash 掉本次改动", re.I)),
    ("D3", "API 签名漂移(TypeError)", re.compile(r"TypeError|签名漂移|verify_maintenance\(\) ?(新增|missing)|missing \d? required positional", re.I)),
    # E 类 · git 工作流层
    ("E1", "unstaged 下 rebase 失败", re.compile(r"cannot rebase|rebase.{0,30}(失败|error|cannot|abort)|error: (cannot|your local changes)|unstaged changes", re.I)),
    ("E2", "push 未设 upstream(exit 128)", re.compile(r"exit code: 128|no upstream|autoSetupMerge|set upstream", re.I)),
    ("E3", "nothing to commit 竞态", re.compile(r"nothing to commit|nothing added to commit", re.I)),
    # A 类 · 并发架构层（轨迹可见部分）
    ("A2", "写卡竞态(file changed/写入者不可归因)", re.compile(r"file changed since it was read|写入者不可归因|并发实例下写入", re.I)),
]
# A 类会话级判定（非关键词）：A1 机审风暴=同卡「被审分支副本」提示词会话聚集；见 analyze_sessions。
ERR_PAT = re.compile(r"\[exit code: [1-9]|sandbox: |\[status: (failed|killed|timeout)|Traceback|error:", re.I)

def iter_strings(obj):
    """递归抽出 JSON 结构里所有字符串值。"""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from iter_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from iter_strings(v)

def zread_lines(path):
    p = subprocess.run([ZSTD, "-dc", path], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"zstd 解压失败: {path}: {p.stderr.decode('utf-8', 'replace')[:120]}")
    return p.stdout.decode("utf-8", "replace").splitlines()

def session_files_for(card):
    pat_exact = os.path.join(SESSIONS_ROOT, f"*-{card}--", "*", "session.jsonl.zstd")
    return sorted(glob.glob(pat_exact))

def analyze_sessions(card):
    """逐会话摘要 + 关键词坑证据。返回 (sessions_meta, kw_hits, err_hits)"""
    files = session_files_for(card)
    sessions, kw_hits, err_hits = [], [], []
    audit_replica_ids = []
    for f in files:
        sid = os.path.basename(os.path.dirname(f))
        ev_count = 0; llm_retry = 0; tool_stats = Counter()
        start_t = None; end_t = None
        user_first = ""; final_txt = ""
        sess_kw = set(); sess_err = []
        for idx, line in enumerate(zread_lines(f)):
            try:
                e = json.loads(line)
            except Exception:
                continue
            ev_count += 1
            t, d = e.get("type"), e.get("data") or {}
            ts = e.get("time")
            if ts:
                start_t = ts if start_t is None else min(start_t, ts)
                end_t = ts if end_t is None else max(end_t, ts)
            if t == "llm/retry":
                llm_retry += 1
            elif t == "tool/call":
                tool_stats[d.get("name")] += 1
            elif t == "user/message":
                texts = [c.get("text", "") for c in d.get("content", []) if isinstance(c, dict) and c.get("type") == "text"]
                joined = "\n".join(texts)
                if not user_first.strip():
                    user_first = joined
                blob = "\n".join(iter_strings(d))
                for did, _, rx in KW_DETECTORS:
                    m = rx.search(blob)
                    if did not in sess_kw and m:
                        sess_kw.add(did)
                        kw_hits.append({"id": did, "src": f"{sid}#ev{idx}", "ts": ts,
                                        "hit": trunc(m.group(0) + " ← " + blob[max(0, m.start()-60):m.end()+120], 200)})
                if ERR_PAT.search(blob):
                    mm = ERR_PAT.search(blob)
                    sess_err.append({"loc": f"{sid}#ev{idx}", "ts": ts,
                                     "hit": trunc(blob[max(0, mm.start()-80):mm.end()+200], 260)})
            elif t == "assistant/message":
                txt = "".join(c.get("text", "") for c in d.get("content", []) if isinstance(c, dict) and c.get("type") == "text")
                if txt.strip():
                    final_txt = txt
                blob = txt
                for did, _, rx in KW_DETECTORS:
                    m = rx.search(blob)
                    if did not in sess_kw and m:
                        sess_kw.add(did)
                        kw_hits.append({"id": did, "src": f"{sid}#ev{idx}", "ts": ts,
                                        "hit": trunc(m.group(0) + " ← " + blob[max(0, m.start()-60):m.end()+120], 200)})
                if ERR_PAT.search(blob):
                    mm = ERR_PAT.search(blob)
                    sess_err.append({"loc": f"{sid}#ev{idx}", "ts": ts,
                                     "hit": trunc(blob[max(0, mm.start()-80):mm.end()+200], 260)})
            else:
                blob = "\n".join(iter_strings(d)) if isinstance(d, dict) else ""
                if blob:
                    for did, _, rx in KW_DETECTORS:
                        m = rx.search(blob)
                        if did not in sess_kw and m:
                            sess_kw.add(did)
                            kw_hits.append({"id": did, "src": f"{sid}#ev{idx}", "ts": ts,
                                            "hit": trunc(m.group(0) + " ← " + blob[max(0, m.start()-60):m.end()+120], 200)})
        # A1 会话级指纹：机审副本提示词
        if user_first.startswith("任务卡（被审分支副本）"):
            audit_replica_ids.append(sid)
        edit_tools = sum(tool_stats[k] for k in ("edit", "write", "str_replace_editor", "Edit", "Write") if k in tool_stats)
        sessions.append({
            "sid": sid, "events": ev_count, "tools": sum(tool_stats.values()),
            "edits": edit_tools, "llm_retry": llm_retry,
            "t0": fmt_ts(start_t), "t1": fmt_ts(end_t),
            "t0_ms": start_t, "t1_ms": end_t,
            "role": "audit-replica" if user_first.startswith("任务卡（被审分支副本）") else ("executor" if user_first.startswith("任务卡") else "other"),
            "user_head": trunc(user_first, 110),
            "final_head": trunc(final_txt, 150),
            "tool_stats": dict(tool_stats),
        })
        err_hits.extend(sess_err)
    return sessions, kw_hits, err_hits, audit_replica_ids

def analyze_exec_logs(card, explicit_path=None):
    """exec 日志扫描：runN 重启序列、审计标记、终报关键词证据。"""
    if explicit_path:
        logs = [explicit_path]
    else:
        logs = sorted(glob.glob(os.path.join(EXEC_DIR, f"{card}*.log")))
    hits, inventory = [], {"files": len(logs), "run_files": 0, "audit_markers": 0}
    run_re = re.compile(re.escape(card) + r"\.run(\d+)\.log$")
    for lp in logs:
        if run_re.search(lp):
            inventory["run_files"] += 1
        short = os.path.basename(lp)
        try:
            with open(lp, encoding="utf-8", errors="replace") as fh:
                for ln, line in enumerate(fh, 1):
                    if "[ccc.engine] start work=" in line and f"work={card}" in line:
                        if "phase=audit" in line:
                            inventory["audit_markers"] += 1
                    for did, _, rx in KW_DETECTORS:
                        m = rx.search(line)
                        if m:
                            hits.append({"id": did, "src": f"exec/{short}:{ln}", "ts": None,
                                         "hit": trunc(m.group(0) + " ← " + line.strip(), 220)})
                    if ERR_PAT.search(line):
                        mm = ERR_PAT.search(line)
                        hits.append({"id": "ERR", "src": f"exec/{short}:{ln}", "ts": None,
                                     "hit": trunc(line[max(0, mm.start()-40):mm.end()+180], 220)})
        except OSError as ex:
            hits.append({"id": "ERR", "src": short, "ts": None, "hit": f"读取失败: {ex}"})
    return inventory, hits

def analyze_worker_events(card):
    runs, audits, fails, shorts, problems = 0, 0, [], [], []
    audit_tss = []
    if not os.path.isfile(WORKER_EVENTS):
        return None
    with open(WORKER_EVENTS, encoding="utf-8", errors="replace") as fh:
        for ln, line in enumerate(fh, 1):
            try:
                e = json.loads(line)
            except Exception:
                continue
            if str(e.get("work_id", "")).lower() != card:
                continue
            phase = e.get("phase"); dur = e.get("duration_s") or 0
            if phase == "run":
                runs += 1
                if not e.get("ok"):
                    fails.append(f"worker-events:{ln} {fmt_ts(iso_to_epoch(e.get('ts')))} rc={e.get('returncode')} exit_kind={e.get('exit_kind')}")
                if 0 < dur < 300:
                    shorts.append(f"worker-events:{ln} {fmt_ts(iso_to_epoch(e.get('ts')))} duration={dur:.0f}s exit_kind={e.get('exit_kind')}")
            elif phase == "audit":
                audits += 1
                ep = iso_to_epoch(e.get("ts"))
                if ep:
                    audit_tss.append(ep)
            if e.get("problem"):
                problems.append(f"worker-events:{ln} {fmt_ts(iso_to_epoch(e.get('ts')))} {trunc(str(e['problem']),160)}")
    # A1-lite：同卡审计事件短窗聚集（≥2 次/60 分钟）
    a1_lite = None
    audit_tss.sort()
    for i in range(1, len(audit_tss)):
        if audit_tss[i] - audit_tss[i-1] < 3600:
            a1_lite = f"{fmt_ts(audit_tss[i-1]*1000)}→{fmt_ts(audit_tss[i]*1000)} 两次审计间隔<{(audit_tss[i]-audit_tss[i-1])/60:.0f}min"
            break
    return {"runs": runs, "audits": audits, "fails": fails, "shorts": shorts,
            "problems": problems, "a1_lite": a1_lite, "file": WORKER_EVENTS}

def analyze_engine_metrics():
    """全局并发水位：exec/audit 槽位峰值与超订样本（A1 引擎面证据）。"""
    if not os.path.isfile(ENGINE_METRICS):
        return None
    peak_exec = (-1, None); peak_audit = (-1, None)
    over = []; t_first = None; t_last = None
    with open(ENGINE_METRICS, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("kind") != "slots":
                continue
            ts = e.get("ts")
            ep = iso_to_epoch(ts)
            if ep:
                t_first = ep if t_first is None else min(t_first, ep)
                t_last = ep if t_last is None else max(t_last, ep)
            eu, au = e.get("exec_used", 0) or 0, e.get("audit_used", 0) or 0
            amax = e.get("audit_max", 0) or 0
            if eu > peak_exec[0]:
                peak_exec = (eu, ts)
            if au > peak_audit[0]:
                peak_audit = (au, ts)
            if amax and au > amax:
                over.append((ts, au, amax))
    return {"peak_exec": peak_exec, "peak_audit": peak_audit,
            "oversub_samples": len(over),
            "over_first": over[0] if over else None,
            "window": (fmt_ts(t_first * 1000), fmt_ts(t_last * 1000)) if t_first else None,
            "window_epoch": (t_first, t_last) if (t_first and t_last and t_last > t_first) else None}

def stderr_time_anchor(metrics):
    """stderr 无时间戳的对时策略：优先显式 env 锚，其次 metrics 首末样本时间，按行序线性内插（≈近似）。"""
    t0 = iso_to_epoch(os.environ.get("TRAJ_DIGEST_STDERR_T0"))
    t1 = iso_to_epoch(os.environ.get("TRAJ_DIGEST_STDERR_T1"))
    anchor = "env"
    if t0 is None or t1 is None:
        if metrics and metrics.get("window_epoch"):
            e0, e1 = metrics["window_epoch"]
            if e0 and e1 and e1 > e0:
                t0, t1, anchor = e0, e1, "engine-metrics 首末样本(近似)"
    return (t0, t1, anchor) if (t0 and t1 and t1 > t0) else (None, None, None)

STDERR_RX = [
    ("FATAL-config", re.compile(r"\[FATAL\].*config", re.I)),
    ("FATAL-other",  re.compile(r"\[FATAL\]")),
    ("kill/term",    re.compile(r"kill|Terminated|SIGTERM", re.I)),
    ("traceback",    re.compile(r"Traceback")),
    ("storm-kill",   re.compile(r"集体|风暴|批量杀|killed", re.I)),
]

def analyze_stderr(t_anchor):
    if not os.path.isfile(STDERR_PATH):
        return None
    t0, t1, anchor_desc = t_anchor
    groups = defaultdict(lambda: {"n": 0, "first_ln": None, "last_ln": None})
    total = 0
    try:
        with open(STDERR_PATH, encoding="utf-8", errors="replace") as fh:
            for ln, line in enumerate(fh, 1):
                total = ln
                for name, rx in STDERR_RX:
                    if rx.search(line):
                        g = groups[name]
                        g["n"] += 1
                        g["first_ln"] = g["first_ln"] or ln
                        g["last_ln"] = ln
                        break
    except OSError:
        return None
    out = {"file": STDERR_PATH, "lines": total, "anchor": anchor_desc, "groups": []}
    for name, g in groups.items():
        def interp(l):
            if not l or not t0:
                return "?"
            frac = l / max(total, 1)
            return "~" + datetime.fromtimestamp(t0 + (t1 - t0) * frac).strftime("%m-%d %H:%M:%S")
        out["groups"].append({"name": name, "count": g["n"],
                              "ln_range": f"{g['first_ln']}-{g['last_ln']}",
                              "~t_range": f"{interp(g['first_ln'])}→{interp(g['last_ln'])}"})
    out["groups"].sort(key=lambda x: -x["count"])
    return out

DIRECTIVE_MAP = {
    "A1": "A1 engine 双开→机审风暴（33 同指纹审计会话/22 秒内集体被杀）",
    "A2": "A2 写卡竞态（file changed/写入者不可归因）",
    "A3": "A3 根因修复滞后（单实例锁 7c841043b 当晚才提交；已闭环）",
    "B1": "B1 执行体反复重启空转（71 分钟 13 短命会话无一编辑）",
    "B2": "B2 模型通道不稳（llm_retry 最高 5 次/会话）",
    "B3": "B3 watchdog 重派发推断（需 watchdog 日志，不在本工具数据源内）",
    "C1": "C1 sha256sum 不存在 exit 127",
    "C2": "C2 /var→/private/var symlink 差异",
    "C3": "C3 残留进程占端口 7899",
    "C4": "C4 docgate 直跑 No module named 'server'",
    "C5": "C5 bash 语法坑三连（括号/unbound/grep -c 空计数）",
    "D1": "D1 main 带红测试进分支（test_board_loader 断言翻转）",
    "D2": "D2 测试隔离缺陷/relay 环境依赖",
    "D3": "D3 verify_maintenance API 签名漂移 TypeError",
    "E1": "E1 unstaged 下 rebase 失败",
    "E2": "E2 push 未设 upstream exit 128",
    "E3": "E3 nothing to commit 竞态",
}
CATEGORY_OF = {}
for _ids, _cat in [(["A1","A2","A3"], "A 并发架构"), (["B1","B2","B3"], "B 派发生命周期"),
                   (["C1","C2","C3","C4","C5"], "C macOS 环境"),
                   (["D1","D2","D3"], "D 测试基线"), (["E1","E2","E3"], "E git 工作流")]:
    for _i in _ids:
        CATEGORY_OF[_i] = _cat

def digest_card(card, explicit_path=None):
    sessions, kw_hits, err_hits, audit_replicas = analyze_sessions(card)
    inv, exec_hits = analyze_exec_logs(card, explicit_path)
    we = analyze_worker_events(card)
    metrics = analyze_engine_metrics()
    stderr_info = analyze_stderr(stderr_time_anchor(metrics))
    hits = kw_hits + exec_hits
    by_id = defaultdict(list)
    for h in hits:
        by_id[h["id"]].append(h)
    # A1 判定：同指纹审计副本会话聚集（≥10 风暴级；3-9 多实例，是否风暴需结合引擎面/时间聚集）
    a1_ev = []
    n_rep = len(audit_replicas)
    if n_rep >= 10:
        a1_ev.append(f"{n_rep} 个会话共享同一机审提示词指纹「任务卡（被审分支副本）：」→ 风暴级审计实例聚集")
    elif n_rep >= 3:
        a1_ev.append(f"{n_rep} 个会话共享同一机审提示词指纹「任务卡（被审分支副本）：」（多实例机审；风暴判定需结合引擎面超订/集体被杀记录）")
    if we and we.get("a1_lite"):
        a1_ev.append("worker-events 同卡审计事件短窗聚集: " + we["a1_lite"])
    if metrics and metrics.get("oversub_samples"):
        a1_ev.append(f"engine-metrics audit_used>audit_max 样本 {metrics['oversub_samples']} 个"
                     f"（peak_audit={metrics['peak_audit'][0]} @{fmt_ts(iso_to_epoch(metrics['peak_audit'][1]))}）")
    if a1_ev:
        by_id["A1"] = [{"id": "A1", "src": "sessions/metrics", "ts": None, "hit": x} for x in a1_ev]
    # B1 判定：runN 文件数 ≥3 或 空转会话（tools≤8 且 edits==0 且 events≤60 的 executor 会话 ≥2）
    b1_ev = []
    if inv["run_files"] >= 3:
        b1_ev.append(f"exec/{card}.run1..{inv['run_files']}.log 共 {inv['run_files']} 个运行文件 → 反复重派")
    idle = [s for s in sessions if s["role"] == "executor" and s["edits"] == 0 and s["tools"] <= 20]
    if len(idle) >= 3:
        t0s = min([s["t0_ms"] for s in idle if s["t0_ms"]] or [None])
        t1s = max([s["t1_ms"] for s in idle if s["t1_ms"]] or [None])
        span = f"{fmt_ts(t0s)}→{fmt_ts(t1s)}（{(t1s-t0s)/60000:.0f}min）" if (t0s and t1s) else "?"
        b1_ev.append(f"{len(idle)} 个执行体会话零编辑（tools≤20，疑似重启空转/重派）：时间窗 {span}；样本 " +
                     "; ".join(f"{s['sid'][:13]}…({s['t0']},{s['tools']}步)" for s in idle[:6]))
    if we and we.get("shorts") and inv["run_files"] >= 3:
        b1_ev.append("短命运行(<300s): " + "; ".join(we["shorts"][:4]))
    if b1_ev:
        by_id["B1"] = [{"id": "B1", "src": "exec/sessions", "ts": None, "hit": x} for x in b1_ev]
    # B2 判定：单会话 llm_retry ≥3
    for s in sessions:
        if s["llm_retry"] >= 3:
            by_id["B2"].append({"id": "B2", "src": f"session {s['sid'][:16]}…", "ts": s["t0_ms"],
                                "hit": f"llm/retry ×{s['llm_retry']}"})
    # A3/B3：数据源内不可直接取证，如实声明
    note_a3 = "A3 根因修复滞后属 git 提交时序问题，不在轨迹数据源内（指令记录已闭环，单实例锁 7c841043b）"
    note_b3 = "B3 watchdog 重派发为指令中的标注推断；watchdog 日志不在本工具数据源白名单，不出证据"
    result = {
        "card": card,
        "data": {
            "sessions": len(sessions),
            "audit_replica_sessions": len(audit_replicas),
            "exec_logs": inv,
            "worker_events": ({k: we[k] for k in ("runs", "audits")} if we else None),
            "stderr_file": bool(stderr_info),
        },
        "sessions_detail": sessions,
        "findings": {},
        "errors_raw": err_hits[:20],
        "notes": {"A3": note_a3, "B3": note_b3},
        "directive_map": DIRECTIVE_MAP,
        "stderr": stderr_info,
        "metrics_global": metrics,
        "worker_events_detail": we,
    }
    for fid in ["A1", "A2", "B1", "B2", "C1", "C2", "C3", "C4", "C5", "D1", "D2", "D3", "E1", "E2", "E3"]:
        items = by_id.get(fid, [])
        if items:
            result["findings"][fid] = [{"src": h["src"], "ts": fmt_ts(h.get("ts")) if isinstance(h.get("ts"), (int, float)) else (h.get("ts") or "t=?"),
                                        "hit": h["hit"]} for h in items[:12]]
            if len(items) > 12:
                result["findings"][fid].append({"src": "...", "ts": "", "hit": f"另有 {len(items)-12} 条同类证据"})
    return result

def render_text(r):
    L = []
    L.append(f"# traj-digest · {r['card']}")
    d = r["data"]
    L.append(f"数据面: 会话轨迹 {d['sessions']} 个（其中机审副本会话 {d['audit_replica_sessions']}）· "
             f"exec 日志 {d['exec_logs']['files']} 个(run×{d['exec_logs']['run_files']}, audit标记×{d['exec_logs']['audit_markers']}) · "
             f"worker-events {'有'+str(d['worker_events']) if d['worker_events'] else '无记录'} · "
             f"stderr {'在' if d['stderr_file'] else '缺'}")
    L.append("")
    L.append("## 五类坑清单")
    cats = defaultdict(list)
    for fid in r["findings"]:
        cats[CATEGORY_OF.get(fid, "?")].append(fid)
    order = ["A 并发架构", "B 派发生命周期", "C macOS 环境", "D 测试基线", "E git 工作流"]
    any_hit = False
    for cat in order:
        ids = sorted(cats.get(cat, []))
        if not ids:
            continue
        any_hit = True
        L.append(f"### {cat}")
        for fid in ids:
            L.append(f"[{fid}] {DIRECTIVE_MAP[fid]}")
            for ev in r["findings"][fid]:
                ts = ev["ts"] if ev["ts"] else "t=?"
                L.append(f"    · [{ts}] {ev['src']} ｜ {ev['hit']}")
        L.append("")
    if not any_hit:
        L.append("（五类检测器均未命中——不代表无坑，代表白名单数据源内无对应信号）")
        L.append("")
    notes = r.get("notes") or {}
    if notes:
        L.append("## 数据源边界说明")
        for k in sorted(notes):
            L.append(f"- {notes[k]}")
        L.append("")
    st = r.get("stderr")
    if st and st["groups"]:
        L.append(f"## 引擎 stderr（无时间戳 · 对时={st['anchor']} · 行序线性内插≈）")
        for g in st["groups"][:6]:
            L.append(f"- {g['name']} ×{g['count']}  行{g['ln_range']}  ≈{g['~t_range']}")
        L.append("")
    L.append("## 会话明细")
    for s in sorted(r["sessions_detail"], key=lambda x: (x["t0_ms"] or 0)):
        L.append(f"- {s['t0']}→{s['t1']} {s['role']:13s} {s['sid'][:20]} ev={s['events']} tools={s['tools']}"
                 f"(edit {s['edits']}) retry={s['llm_retry']}  {s['user_head']}")
    return "\n".join(L)

cards_in = [c for c in (os.environ.get("TRAJ_DIGEST_CARDS_INPUT") or "").split() if c]
results = []
skipped = []
for tok in cards_in:
    card, path = norm_card(tok)
    if not card:
        skipped.append((tok, "无法识别卡号")); continue
    has_data = session_files_for(card) or glob.glob(os.path.join(EXEC_DIR, f"{card}*.log")) or os.path.isfile(path or "")
    if not has_data:
        skipped.append((tok, "无任何轨迹数据（会话目录与 exec 日志均缺）")); continue
    results.append(digest_card(card, path))

if skipped:
    for tok, why in skipped:
        print(f"[traj-digest][skip] {tok}: {why}", file=sys.stderr)

if not results:
    # 全部入参都无轨迹数据：按用法契约返回 2（部分缺数据但其余可出的情况仍为 0）
    print("(无可出清单的卡)")
    sys.exit(2)

if JSON_MODE:
    out = json.dumps(results, ensure_ascii=False, indent=1)
else:
    out = "\n\n".join(render_text(r) for r in results)

print(out)
if OUT_FILE:
    with open(OUT_FILE, "w", encoding="utf-8") as w:
        w.write(out + ("\n" if not out.endswith("\n") else ""))
    print(f"[traj-digest] 已写出 {OUT_FILE}（{len(out)} 字符）", file=sys.stderr)
sys.exit(0)
PYEOF
