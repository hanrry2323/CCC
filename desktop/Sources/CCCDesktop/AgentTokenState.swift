import Foundation

/// 7788 Agent 会话 token 生命周期（纯逻辑，可测）。
/// 对齐窗口 1 `POST /api/auth/agent-login` 契约（task-K）：账号密码 → 内存 TTL 会话 token，
/// TTL 1h，内存缓存，服务端重启失效。report-K 回后按实际契约校准字段。
///
/// 状态：
/// - token / expiresAt：内存缓存（非持久化凭据）
/// - refreshLead：TTL 前刷新提前量（剩余 < 此值即视为需刷新）
///
/// 注：刻意比 HubTokenState 少 degrade 窗口——Hub 有 Basic 降级兜底，
/// Agent 侧无 Basic；401 有界重登一次即是最坏上限，无需冷却窗口。
struct AgentTokenState {
    var token: String?
    var expiresAt: Date?

    /// TTL 前刷新提前量：剩余 < refreshLead 即需换新 token
    var refreshLead: TimeInterval = 120

    /// 有有效会话 token：存在、未过期、且未进入刷新窗口。
    /// 无过期时间（解析失败）→ 视为有效，靠 401 重登兜底。
    func isValid(now: Date) -> Bool {
        guard let token, !token.isEmpty else { return false }
        guard let expiresAt else { return true }
        return now < expiresAt.addingTimeInterval(-refreshLead)
    }

    mutating func store(token: String, expiresAt: Date?) {
        self.token = token
        self.expiresAt = expiresAt
    }

    mutating func invalidate() {
        token = nil
        expiresAt = nil
    }

    /// 收到 401：token 吊销 / 过期 / 服务端重启 → 清 token（强制下轮重登）
    mutating func recordBearer401() {
        invalidate()
    }
}

/// POST /api/auth/agent-login 响应（窗口 K 契约：`{token, role, expires_in}`，report-K §四）
struct AgentLoginResponse: Decodable {
    let token: String
    /// 会话 TTL 秒（sidecar `CCC_AGENT_SESSION_TTL` 默认 3600）
    let expires_in: Int?
    let scheme: String?
}
