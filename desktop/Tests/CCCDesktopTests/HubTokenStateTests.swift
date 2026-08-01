import XCTest
@testable import CCCDesktop

/// 行为锁 · 认证层（纯逻辑）：HubTokenState / HubTokenStateSupport
/// 锁定 token 缓存、TTL 前刷新、降级窗口、401 强制重取、过期时间解析
final class HubTokenStateTests: XCTestCase {

    private let now = Date(timeIntervalSince1970: 1_000_000)

    // MARK: - isValid（缓存 + 过期 + TTL 前刷新）

    func testNoTokenInvalid() {
        var s = HubTokenState()
        XCTAssertFalse(s.isValid(now: now))
    }

    func testValidWithinTTL() {
        var s = HubTokenState()
        s.store(token: "t", role: "operator", expiresAt: now.addingTimeInterval(3600))
        XCTAssertTrue(s.isValid(now: now))
    }

    func testExpiredInvalid() {
        var s = HubTokenState()
        s.store(token: "t", role: nil, expiresAt: now.addingTimeInterval(-1))
        XCTAssertFalse(s.isValid(now: now))
    }

    func testRefreshLeadRefreshesBeforeTTL() {
        // TTL 前刷新：剩余 < refreshLead(120s) 即视为需刷新
        var s = HubTokenState()
        s.store(token: "t", role: nil, expiresAt: now.addingTimeInterval(119))
        XCTAssertFalse(s.isValid(now: now))
        s.store(token: "t", role: nil, expiresAt: now.addingTimeInterval(120))
        XCTAssertFalse(s.isValid(now: now)) // 恰好 = 提前量 → 刷新
        s.store(token: "t", role: nil, expiresAt: now.addingTimeInterval(121))
        XCTAssertTrue(s.isValid(now: now))
    }

    func testNilExpiryTreatedValid() {
        // 过期时间解析失败 → 视为有效，靠 401 重取兜底
        var s = HubTokenState()
        s.store(token: "t", role: nil, expiresAt: nil)
        XCTAssertTrue(s.isValid(now: now))
    }

    func testInvalidateClears() {
        var s = HubTokenState()
        s.store(token: "t", role: "operator", expiresAt: now.addingTimeInterval(3600))
        s.invalidate()
        XCTAssertFalse(s.isValid(now: now))
        XCTAssertNil(s.token)
        XCTAssertNil(s.role)
    }

    // MARK: - 降级窗口

    func testDegradeWindow() {
        var s = HubTokenState()
        XCTAssertFalse(s.isDegrading(now: now))
        s.recordFetchFailure(now: now)
        XCTAssertTrue(s.isDegrading(now: now))
        XCTAssertTrue(s.isDegrading(now: now.addingTimeInterval(29)))
        XCTAssertFalse(s.isDegrading(now: now.addingTimeInterval(31)))
        XCTAssertFalse(s.isDegrading(now: now.addingTimeInterval(100)))
    }

    func testStoreClearsDegradeWindow() {
        var s = HubTokenState()
        s.recordFetchFailure(now: now)
        XCTAssertTrue(s.isDegrading(now: now))
        s.store(token: "t", role: nil, expiresAt: now.addingTimeInterval(3600))
        XCTAssertFalse(s.isDegrading(now: now))
        XCTAssertTrue(s.isValid(now: now))
    }

    func testBearer401ClearsTokenAndDegrade() {
        // 服务端 401：清 token + 清降级窗口（强制下轮重取 Bearer，不继续走 Basic）
        var s = HubTokenState()
        s.recordFetchFailure(now: now)
        s.store(token: "t", role: nil, expiresAt: now.addingTimeInterval(3600))
        s.recordBearer401(now: now)
        XCTAssertFalse(s.isValid(now: now))
        XCTAssertFalse(s.isDegrading(now: now))
    }

    // MARK: - 过期时间解析

    func testParseExpiryValidFormats() {
        let expected = ISO8601DateFormatter().date(from: "2026-08-01T23:59:59Z")
        XCTAssertEqual(HubTokenStateSupport.parseExpiry("2026-08-01T23:59:59+00:00"), expected)
        XCTAssertEqual(HubTokenStateSupport.parseExpiry("2026-08-01T23:59:59Z"), expected)
        XCTAssertNotNil(HubTokenStateSupport.parseExpiry("2026-08-01T23:59:59.123+00:00"))
    }

    func testParseExpiryInvalidReturnsNil() {
        XCTAssertNil(HubTokenStateSupport.parseExpiry(nil))
        XCTAssertNil(HubTokenStateSupport.parseExpiry(""))
        XCTAssertNil(HubTokenStateSupport.parseExpiry("not-a-date"))
    }
}
