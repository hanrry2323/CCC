import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# v0.51.0 P2-3: sys.path 注入由 chat_server/__init__.py 统一处理（chat_server 包被
# import 时 __init__.py 会先执行注入，config 模块加载时 scripts/ 已在 sys.path 中）
from _claude_cli import ClaudeCliMissing, resolve_claude_cli  # noqa: E402

HOST = os.environ.get("CCC_CHAT_HOST", "0.0.0.0")
# Hub 对外端口：7777（用户习惯口）；Board API 内网默认 7775
PORT = int(os.environ.get("CCC_CHAT_PORT", "7777"))
# Hub 约定账密：用户名与密码均为 ccc（可用环境变量覆盖）
AUTH_USER = os.environ.get("CCC_CHAT_USER", "ccc")
AUTH_PASS = os.environ.get("CCC_CHAT_PASS", "ccc").strip()
BOARD_URL = os.environ.get("CCC_BOARD_URL", "http://127.0.0.1:7775")
BOARD_TOKEN = os.environ.get("QX_BOARD_TOKEN", "").strip()
# CCC_PROXY_URL / :4002 已随 ai-loop-router 退役；Hub 对话走 Desktop sidecar，勿再默认中转。

# Hub 对话超时（空闲 / 硬上限）。有工具调用时墙钟 180s 极易误杀。
# idle：距上次收到 Claude 输出的静默秒数；max：整轮硬上限。
CHAT_IDLE_TIMEOUT = int(os.environ.get("CCC_CHAT_IDLE_TIMEOUT", "600"))
CHAT_MAX_TIMEOUT = int(os.environ.get("CCC_CHAT_MAX_TIMEOUT", "1800"))
CHAT_IDLE_TIMEOUT = max(60, min(CHAT_IDLE_TIMEOUT, 3600))
CHAT_MAX_TIMEOUT = max(CHAT_IDLE_TIMEOUT, min(CHAT_MAX_TIMEOUT, 7200))
# 持续会话：live ClaudeSDKClient 空闲回收 / 并发上限
CHAT_SESSION_IDLE_TTL = int(os.environ.get("CCC_CHAT_SESSION_IDLE_TTL", "900"))
CHAT_SESSION_IDLE_TTL = max(60, min(CHAT_SESSION_IDLE_TTL, 7200))
CHAT_SESSION_MAX_LIVE = int(os.environ.get("CCC_CHAT_SESSION_MAX_LIVE", "4"))
CHAT_SESSION_MAX_LIVE = max(1, min(CHAT_SESSION_MAX_LIVE, 16))
# 热路径防挂死：拿 slot 锁 / connect / 超时后 drain 的硬上限（秒）
CHAT_LOCK_WAIT = int(os.environ.get("CCC_CHAT_LOCK_WAIT", "15"))
CHAT_LOCK_WAIT = max(3, min(CHAT_LOCK_WAIT, 120))
CHAT_CONNECT_TIMEOUT = int(os.environ.get("CCC_CHAT_CONNECT_TIMEOUT", "30"))
CHAT_CONNECT_TIMEOUT = max(5, min(CHAT_CONNECT_TIMEOUT, 120))
CHAT_DRAIN_TIMEOUT = int(os.environ.get("CCC_CHAT_DRAIN_TIMEOUT", "8"))
CHAT_DRAIN_TIMEOUT = max(2, min(CHAT_DRAIN_TIMEOUT, 60))
# warm 抢锁失败快返回（勿阻塞后续 chat）
CHAT_WARM_LOCK_WAIT = int(os.environ.get("CCC_CHAT_WARM_LOCK_WAIT", "3"))
CHAT_WARM_LOCK_WAIT = max(1, min(CHAT_WARM_LOCK_WAIT, 30))
# 可靠性契约：有心跳 ≠ 有进展。query 后无任何可映射事件 / 工具无结果 → 中断并回收 slot。
# Plan/长提示 + MiniMax 首包常 >60s；默认 120s（可用 CCC_CHAT_FIRST_EVENT_TIMEOUT 覆盖，上限 300）。
CHAT_FIRST_EVENT_TIMEOUT = int(os.environ.get("CCC_CHAT_FIRST_EVENT_TIMEOUT", "120"))
CHAT_FIRST_EVENT_TIMEOUT = max(10, min(CHAT_FIRST_EVENT_TIMEOUT, 300))
CHAT_TOOL_STALL_TIMEOUT = int(os.environ.get("CCC_CHAT_TOOL_STALL_TIMEOUT", "90"))
CHAT_TOOL_STALL_TIMEOUT = max(15, min(CHAT_TOOL_STALL_TIMEOUT, 600))
# 会话存储目录（测试可设 CCC_CHAT_DIR 指到临时目录，避免污染真实列表）
CHAT_DIR = Path(os.environ.get("CCC_CHAT_DIR", str(PROJECT_ROOT / ".ccc" / "chat")))
CHAT_DIR.mkdir(parents=True, exist_ok=True)
# LAN / localhost CORS regex（SPA；原生 Desktop 不依赖 CORS）
# 默认仅本机，避免 RFC1918 + credentials 被同网段网页滥用；扩网段请设 CCC_CHAT_CORS_ORIGIN_REGEX
CORS_ORIGIN_REGEX = os.environ.get(
    "CCC_CHAT_CORS_ORIGIN_REGEX",
    # 本机 + 内网 LAN（M1 对话 SPA :7788 → Hub :7777）
    r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?$",
)

# 禁止历史泄漏 / 空口令；产品约定口令 "ccc" 明确允许
_FORBIDDEN_PASSWORDS = frozenset({
    "", "claude2026", "password", "admin", "123456", "changeme",
})

# F-SEC-03: 辅助拦截（主防线=工具 allowlist + cwd jail）；覆盖常见变形，避免裸 \brm\b 误伤
DANGEROUS_PATTERN = re.compile(
    r"(?i)("
    r"\brm\s+(-[a-zA-Z0-9]*[rf][a-zA-Z0-9]*[rf]?[a-zA-Z0-9]*|-r\s+-f|-f\s+-r|--force)\b|"
    r"\brm\s+/"
    r"|/bin/rm\b"
    r"|\bsudo\b"
    r"|\bdd\s+if="
    r"|\bmkfs\b"
    r"|\bformat\s+[A-Za-z]:"  # format C: / format d:
    r"|>\s*/dev/"
    r"|\bchmod\s+777\b"
    r"|\b(curl|wget)\b[^\n]*\|\s*(ba)?sh\b"
    r"|\bshred\b"
    r")"
)

# F-SEC-03: Claude CLI 允许的工具（allowlist）；未列出的工具名应被拒绝
# discuss = Plan 模式（全智力只读：可子代理/检索，禁止写业务仓）；engineer = 显式解锁本机改文件
# Bash 在 discuss 中保留：对齐基线/定稿等关键路径需要 `git status` / `git log`（纪律限制为只读命令）。
# Task/Agent：只读调研/审查/代码地图类子代理（子代理同样禁写）。
# 外网工具允许；挂死由 CHAT_FIRST_EVENT_TIMEOUT / CHAT_TOOL_STALL_TIMEOUT 回收，禁止靠删能力「止血」。
CLAUDE_TOOL_ALLOWLIST_DISCUSS = frozenset({
    "Read", "Glob", "Grep", "LS", "Bash", "TodoWrite", "WebFetch", "WebSearch",
    "Task", "Agent",
})
CLAUDE_TOOL_ALLOWLIST_ENGINEER = frozenset({
    "Read", "Write", "Edit", "MultiEdit", "Glob", "Grep",
    "LS", "Bash", "NotebookEdit", "TodoWrite", "WebFetch", "WebSearch",
    "Task", "Agent",
})
# 硬闸：discuss 非空 allowlist 时显式 disallowed（不靠自觉）
CLAUDE_TOOL_DISALLOW_DISCUSS = frozenset({
    "Write", "Edit", "MultiEdit", "NotebookEdit",
})
# 兼容旧引用：全量 = 工程师模式
CLAUDE_TOOL_ALLOWLIST = CLAUDE_TOOL_ALLOWLIST_ENGINEER

_ENGINEER_PHRASES = ("工程师模式", "直接改本机")

# discuss = Plan：方案智力拉满，执行权（改码）为零；交付物是定稿/plan_md/转任务
# 工具：SDK 默认全开 + 硬禁 Write/Edit…；MCP/Skill/子代理可用
DISCUSS_TOOL_DISCIPLINE = (
    "【工具纪律 · Plan · Desktop 规划面】你是 Desktop 方案搭档（不是 Cursor 平台助手）：智力拉满、执行权为零。"
    "工具默认全开（含 Read/Bash/Web/Task/Agent/Skill/MCP）；"
    "硬禁：Write / Edit / MultiEdit / NotebookEdit、装包、推远程、删文件、重定向写盘、擅自 commit。"
    "可用子代理做代码定位、调研、审查草案，结果汇总进方案，禁止落盘改文件。"
    "Bash 可跑只读探查与 `ccc-hub-lens.py`；禁止写盘/改仓命令。"
    "业务仓事实必须经 Hub 只读透镜（禁止写死 2017 绝对路径、禁止 ssh/rsync）："
    "`python3 scripts/ccc-hub-lens.py board|locate|grep|tree|file|git <project_id> …`；"
    "优先透镜 / 本机只读 ccc；业务仓禁止假装有第二树。"
    "【扫风险 / 定稿】禁止只读文档交差。必须：① board live；"
    "② locate 或 grep 按意图符号/关键词定点收窄（禁止全仓无脑扫）；"
    "③ 抽 1～3 个相对路径 file 核实；④ 需要时 git summary；再给风险与定稿。"
    "续查只用透镜返回的相对路径；禁止把 2017 绝对路径抄回本机 Read。"
    "仅当当前对话是 CCC 平台仓（project_id=ccc）且本机映射存在时，才允许对本机 git status/log/diff/show。"
    "输出方案与风险、定稿契约；交付物不是仓库 diff。"
    "对齐基线快照只作开场，不作终局。Hub 不可达 → 明说不可达 + 快照时刻，禁止瞎编。"
    "短确认、闲聊可直接答（仍有工具可用，不必强开）。工程师模式仅用于平台仓 ccc。"
)


def resolve_tool_mode(
    explicit: str | None = None,
    *,
    user_text: str = "",
    project_id: str = "",
) -> str:
    """返回 discuss | engineer。缺省 discuss；显式或口令解锁 engineer。

    业务仓（project_id != ccc）一律 discuss，口令无效。
    """
    t = (explicit or "").strip().lower()
    if t in ("engineer", "discuss"):
        mode = t
    elif any(p in (user_text or "") for p in _ENGINEER_PHRASES):
        mode = "engineer"
    else:
        mode = "discuss"
    pid = (project_id or "").strip().lower()
    if mode == "engineer" and pid and pid != "ccc":
        return "discuss"
    return mode


def tools_for_mode(
    mode: str,
    *,
    user_text: str = "",
    prompt_mode: str | None = None,
) -> frozenset:
    """discuss = 只读全集（SDK 侧空 allowlist + 硬禁写）；engineer = 含写工具。

    已取消 light 零工具 / 剥 Web：短闲聊靠纪律「直接答」，不靠掏空 allowlist。
    discuss 不再用正向 allowlist 卡死 MCP/Skill 等动态工具名——只禁 Write/Edit。
    user_text / prompt_mode 保留参数兼容旧调用方。
    """
    _ = (user_text, prompt_mode)
    if (mode or "").strip().lower() == "engineer":
        return CLAUDE_TOOL_ALLOWLIST_ENGINEER
    # 兼容测试/观测：名义全集；真正下发给 SDK 见 ClaudeSessionManager._build_options
    return CLAUDE_TOOL_ALLOWLIST_DISCUSS


# 兼容旧测试/调用：critical / plan 判定仍可用于观测，不再驱动剥工具
_CRITICAL_FLOW_RE = re.compile(
    r"(对齐基线|对齐项目基线|下一步|定稿|扫风险|转任务|下达|可以转了|"
    r"方案|规划|plan|透镜|看板|审查|核实|静默探测|静默功课|ccc-transfer)",
    re.I,
)


def is_critical_flow(user_text: str = "") -> bool:
    """对齐基线 / 定稿 / 扫风险 / 透镜 等主路径（观测用）。"""
    return bool(_CRITICAL_FLOW_RE.search(user_text or ""))


def is_plan_turn(*, user_text: str = "", prompt_mode: str | None = None) -> bool:
    """兼容旧名：discuss 已恒全工具；此函数恒 True（或仍识别关键词）。"""
    _ = (user_text, prompt_mode)
    return True


def defer_web_tools_for_turn(
    *,
    tool_mode: str,
    user_text: str = "",
    prompt_mode: str | None = None,
) -> bool:
    """已退役：discuss 不再剥 Web*。保留函数签名兼容旧调用。"""
    _ = (tool_mode, user_text, prompt_mode)
    return False

BOARD_COLUMNS = [
    "backlog", "planned", "in_progress",
    "testing", "verified", "released", "abnormal",
]

def _resolve_hub_claude_bin() -> str:
    try:
        return resolve_claude_cli(require=False) or ""
    except Exception:
        return ""


CLAUDE_BIN = _resolve_hub_claude_bin()

# SDK 子进程 env：白名单（禁止全量继承 shell，避免个人 Claude / 脏变量泄漏进 loop-code）
# 见 docs/product/loop-code-ownership-cut.md Phase1
_CLAUDE_ENV_EXACT = frozenset({
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "TMPDIR",
    "TMP",
    "TEMP",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "LC_MESSAGES",
    "TERM",
    "COLORTERM",
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_PROJECT_DIR",
    "XDG_RUNTIME_DIR",
    "XDG_CONFIG_HOME",
    "NO_COLOR",
    "FORCE_COLOR",
})
_CLAUDE_ENV_PREFIXES = ("ANTHROPIC_", "CCC_", "CLAUDE_CODE_")


def build_claude_env() -> dict[str, str]:
    """构建传给 ClaudeSDKClient / loop-code 的环境变量（调用时快照）。"""
    out: dict[str, str] = {}
    for key, val in os.environ.items():
        if key in _CLAUDE_ENV_EXACT or any(key.startswith(p) for p in _CLAUDE_ENV_PREFIXES):
            out[key] = val
    bin_dir = os.path.dirname(CLAUDE_BIN) if CLAUDE_BIN else ""
    path = out.get("PATH") or os.environ.get("PATH") or ""
    if bin_dir and bin_dir not in path.split(":"):
        path = f"{bin_dir}:{path}" if path else bin_dir
    out["PATH"] = path
    # 确保配置家存在且写入 env（sidecar 应已 setdefault）
    try:
        from _claude_cli import ensure_loop_code_config_dir, default_loop_code_config_dir

        cfg = (out.get("CLAUDE_CONFIG_DIR") or "").strip()
        if not cfg and (os.environ.get("CCC_EXECUTOR") or "").strip().lower() in (
            "loop-code",
            "loopcode",
            "loop_code",
        ):
            cfg = str(default_loop_code_config_dir())
        if cfg:
            ensure_loop_code_config_dir(Path(cfg).expanduser())
            out["CLAUDE_CONFIG_DIR"] = str(Path(cfg).expanduser())
    except Exception:
        pass
    return out


# 兼容旧引用；热路径请用 build_claude_env()（会话连接时再取，含最新 CLAUDE_CONFIG_DIR）
CLAUDE_ENV = build_claude_env()


def validate_auth_config() -> None:
    """Hub 账密门禁：禁止空口令与历史泄漏默认；约定 ccc/ccc 可用。

    监听 0.0.0.0 且仍用默认口令时打印警告（产品允许 ccc:ccc，但全网暴露有风险）。
    """
    if AUTH_PASS.lower() in _FORBIDDEN_PASSWORDS:
        raise SystemExit(
            "CCC_CHAT_PASS is empty or a forbidden default "
            "(e.g. claude2026). Use the Hub password 'ccc', or set another non-forbidden value."
        )
    if HOST in ("0.0.0.0", "::") and AUTH_USER == "ccc" and AUTH_PASS == "ccc":
        print(
            "WARNING: Hub listens on all interfaces with default auth ccc:ccc. "
            "Prefer CCC_CHAT_HOST=127.0.0.1 or a stronger CCC_CHAT_PASS on shared LAN.",
            file=sys.stderr,
        )


def require_claude_bin() -> str:
    """F-SEC-06: 统一走 resolve_claude_cli（支持 CCC_CLAUDE_BIN / loop-code）。"""
    try:
        return resolve_claude_cli(require=True)
    except ClaudeCliMissing as exc:
        raise RuntimeError(str(exc)) from exc

_PROJECTS_FALLBACK = {
    "ccc": {"name": "CCC", "path": str(PROJECT_ROOT)},
}
