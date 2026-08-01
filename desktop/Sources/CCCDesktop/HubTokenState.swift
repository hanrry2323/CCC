import Foundation

/// Hub 会话 token 生命周期（纯逻辑，可测）。
/// 对齐后端 `/api/auth/token` 契约（B2）：opaque token，TTL 1h，内存存储，服务端重启失效。
///
/// 状态：
/// - token / expiresAt / role：内存缓存（非持久化凭据）
/// - degradeUntil：token 获取失败后的降级窗口，窗口内请求直接走 Basic
///   （服务端 CCC_AUTH_REQUIRE_BEARER 未开时 Basic 仍放行 → 不断链）
/// - refreshLead：TTL 前刷新提前量（剩余 < 此值即视为需刷新）
struct HubTokenState {
    var token: String?
    var expiresAt: Date?
    var role: String?
    var degradeUntil: Date?

    /// TTL 前刷新提前量：剩余 < refreshLead 即需换新 token
    var refreshLead: TimeInterval = 120
    /// token 获取失败后的降级窗口
    var degradeCooldown: TimeInterval = 30

    /// 有有效 Bearer token：存在、未过期、且未进入刷新窗口。
    /// 无过期时间（解析失败）→ 视为有效，靠 401 重取兜底。
    func isValid(now: Date) -> Bool {
        guard let token, !token.isEmpty else { return false }
        guard let expiresAt else { return true }
        return now < expiresAt.addingTimeInterval(-refreshLead)
    }

    /// 降级窗口内（token 获取失败后）→ 请求直接走 Basic
    func isDegrading(now: Date) -> Bool {
        guard let degradeUntil else { return false }
        return now < degradeUntil
    }

    mutating func store(token: String, role: String?, expiresAt: Date?) {
        self.token = token
        self.role = role
        self.expiresAt = expiresAt
        // 获取成功 → 清降级窗口
        self.degradeUntil = nil
    }

    mutating func invalidate() {
        token = nil
        expiresAt = nil
        role = nil
    }

    /// token 获取失败：进降级窗口（窗口内直接 Basic，避免反复打 token 端点）
    mutating func recordFetchFailure(now: Date) {
        degradeUntil = now.addingTimeInterval(degradeCooldown)
    }

    /// 收到 401：token 可能被吊销 / 过期 / 服务端重启 → 清 token + 清降级窗口（强制下轮重取 Bearer）
    mutating func recordBearer401(now: Date) {
        invalidate()
        degradeUntil = nil
    }
}

/// POST /api/auth/token 响应（B2 契约）
struct HubTokenResponse: Decodable {
    let token: String
    let role: String?
    let scheme: String?
    let expires_at: String?
    let ttl_s: Int?
}

enum HubTokenStateSupport {
    /// 解析后端 ISO 过期时间（`2026-08-01T23:59:59+00:00`；可能带小数秒）。
    /// 解析失败 → nil（token 视为有效，401 兜底）。
    static func parseExpiry(_ iso: String?) -> Date? {
        guard let iso, !iso.isEmpty else { return nil }
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withColonSeparatorInTimeZone, .withFractionalSeconds]
        if let d = f.date(from: iso) { return d }
        f.formatOptions = [.withInternetDateTime, .withColonSeparatorInTimeZone]
        return f.date(from: iso)
    }
}
