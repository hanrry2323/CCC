import XCTest
@testable import CCCDesktop

/// 每个测试捕获的 7788 侧状态（URLProtocol handler 后台线程执行，用 class 引用共享）
final class MockAgentState {
    var loginCalls = 0
    var outboxCalls = 0
    var outboxAuthHeaders: [String] = []
    var loginBodies: [String] = []
}

/// 行为锁 · 7788 Agent 账号密码登录（APIClient × URLProtocol mock）
/// 锁定：配置凭证→登录换 Bearer（一次）、缓存复用、401→重登一次（有界）、恒 401 报错不无限循环、
/// 未配置→降级共享密钥（兼容窗口）、两者皆无→明确报错、已配置登录被拒→报错不降级、换凭证失效
final class AgentLoginTests: XCTestCase {

    private let hub = URL(string: "http://127.0.0.1:17777/")!
    private let agent = URL(string: "http://127.0.0.1:7788/")!

    private var isoFormatter: ISO8601DateFormatter {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withColonSeparatorInTimeZone]
        return f
    }

    private func loginJSON(_ token: String, expiresIn: TimeInterval = 3600) -> [String: Any] {
        [
            "token": token,
            "expires_at": isoFormatter.string(from: Date().addingTimeInterval(expiresIn)),
            "ttl_s": 3600,
            "scheme": "bearer",
        ]
    }

    private func resp(_ code: Int, for request: URLRequest) -> HTTPURLResponse {
        HTTPURLResponse(url: request.url!, statusCode: code, httpVersion: nil, headerFields: nil)!
    }

    private func json(_ code: Int, _ obj: [String: Any], for request: URLRequest) throws -> (HTTPURLResponse, Data) {
        (resp(code, for: request), try JSONSerialization.data(withJSONObject: obj))
    }

    /// URLSession 经 URLProtocol 时把 httpBody 转成 httpBodyStream，需两者都读
    private func requestBody(_ req: URLRequest) -> String {
        if let body = req.httpBody {
            return String(data: body, encoding: .utf8) ?? ""
        }
        guard let stream = req.httpBodyStream else { return "" }
        stream.open()
        defer { stream.close() }
        var data = Data()
        let bufSize = 4096
        let buf = UnsafeMutablePointer<UInt8>.allocate(capacity: bufSize)
        defer { buf.deallocate() }
        while stream.hasBytesAvailable {
            let read = stream.read(buf, maxLength: bufSize)
            if read <= 0 { break }
            data.append(buf, count: read)
        }
        return String(data: data, encoding: .utf8) ?? ""
    }

    private func makeClient(
        agentUser: String = "alice",
        agentPassword: String = "s3cret",
        agentSharedSecret: String? = nil
    ) async -> APIClient {
        let c = APIClient(
            baseURL: hub,
            user: "ccc",
            password: "ccc",
            urlProtocolClasses: [MockURLProtocol.self],
            agentUser: agentUser,
            agentPassword: agentPassword,
            agentSharedSecret: agentSharedSecret
        )
        await c.update(
            baseURL: hub, user: "ccc", password: "ccc",
            chatBaseURL: agent,
            agentUser: agentUser,
            agentPassword: agentPassword
        )
        return c
    }

    private func agentHandler(
        _ state: MockAgentState,
        loginStatus: @escaping (Int) -> Int = { _ in 200 },
        outboxStatus: @escaping (Int) -> Int = { _ in 200 }
    ) -> (URLRequest) throws -> (HTTPURLResponse, Data) {
        { req in
            let path = req.url?.path ?? ""
            let auth = req.value(forHTTPHeaderField: "Authorization") ?? ""
            if path.hasSuffix("/api/auth/agent-login") {
                state.loginCalls += 1
                state.loginBodies.append(self.requestBody(req))
                let code = loginStatus(state.loginCalls)
                if code == 200 {
                    return try self.json(200, self.loginJSON("agent-tok\(state.loginCalls)"), for: req)
                }
                return try self.json(code, ["detail": "bad credentials"], for: req)
            }
            if path.hasSuffix("/api/outbox/flush") {
                state.outboxCalls += 1
                state.outboxAuthHeaders.append(auth)
                return try self.json(outboxStatus(state.outboxCalls), ["ok": true], for: req)
            }
            return try self.json(404, ["error": "unexpected \(path)"], for: req)
        }
    }

    // MARK: - 登录换 Bearer

    func testAgentLoginExchangedForBearer() async throws {
        let state = MockAgentState()
        MockURLProtocol.handler = agentHandler(state)
        defer { MockURLProtocol.handler = nil }

        _ = try await makeClient().nudgeOutboxFlush()

        XCTAssertEqual(state.loginCalls, 1)
        XCTAssertEqual(state.outboxCalls, 1)
        XCTAssertEqual(state.outboxAuthHeaders, ["Bearer agent-tok1"])
        // 账号密码走 body（不是默认弱口令）
        XCTAssertTrue(state.loginBodies[0].contains("alice"))
        XCTAssertTrue(state.loginBodies[0].contains("s3cret"))
    }

    func testAgentLoginCachedNoRelogin() async throws {
        let state = MockAgentState()
        MockURLProtocol.handler = agentHandler(state)
        defer { MockURLProtocol.handler = nil }

        let c = await makeClient()
        _ = try await c.nudgeOutboxFlush()
        _ = try await c.nudgeOutboxFlush()

        XCTAssertEqual(state.loginCalls, 1)  // 会话 token 缓存复用
        XCTAssertEqual(state.outboxCalls, 2)
        XCTAssertEqual(state.outboxAuthHeaders, ["Bearer agent-tok1", "Bearer agent-tok1"])
    }

    // MARK: - 401 重登一次（有界）

    func test401OnceThenReloginSucceeds() async throws {
        let state = MockAgentState()
        MockURLProtocol.handler = agentHandler(state, outboxStatus: { $0 == 1 ? 401 : 200 })
        defer { MockURLProtocol.handler = nil }

        _ = try await makeClient().nudgeOutboxFlush()

        XCTAssertEqual(state.loginCalls, 2)    // 初次 + 401 后重登
        XCTAssertEqual(state.outboxCalls, 2)   // 401 + 重试
        XCTAssertEqual(state.outboxAuthHeaders, ["Bearer agent-tok1", "Bearer agent-tok2"])
    }

    func test401TwiceThrowsNoInfiniteLoop() async throws {
        let state = MockAgentState()
        MockURLProtocol.handler = agentHandler(state, outboxStatus: { _ in 401 })
        defer { MockURLProtocol.handler = nil }

        do {
            _ = try await makeClient().nudgeOutboxFlush()
            XCTFail("应抛出 401")
        } catch let e as APIError {
            guard case .http(let code, let body) = e else {
                return XCTFail("应为 http(401)，got \(e)")
            }
            XCTAssertEqual(code, 401)
            XCTAssertTrue(body.contains("请在设置"), "应引导重新配置，got: \(body)")
        }
        // 有界：重登一次后仍 401 → 报错，不无限循环
        XCTAssertEqual(state.loginCalls, 2)
        XCTAssertEqual(state.outboxCalls, 2)
    }

    // MARK: - 未配置降级共享密钥（兼容窗口）

    func testNoCredsFallsBackToSharedSecret() async throws {
        let state = MockAgentState()
        MockURLProtocol.handler = agentHandler(state)
        defer { MockURLProtocol.handler = nil }

        let c = await makeClient(agentUser: "", agentPassword: "", agentSharedSecret: "shared-secret")
        _ = try await c.nudgeOutboxFlush()

        XCTAssertEqual(state.loginCalls, 0)  // 未配置凭证 → 不尝试登录
        XCTAssertEqual(state.outboxAuthHeaders, ["Bearer shared-secret"])
    }

    func testNoCredsNoSecretThrowsClearError() async throws {
        let state = MockAgentState()
        MockURLProtocol.handler = agentHandler(state, outboxStatus: { _ in 401 })
        defer { MockURLProtocol.handler = nil }

        // 空串 = 显式禁用共享密钥（避免读到测试机真实 ~/.ccc/agent-token）
        let c = await makeClient(agentUser: "", agentPassword: "", agentSharedSecret: "")
        do {
            _ = try await c.nudgeOutboxFlush()
            XCTFail("应抛出 401")
        } catch let e as APIError {
            guard case .http(let code, let body) = e else {
                return XCTFail("应为 http(401)，got \(e)")
            }
            XCTAssertEqual(code, 401)
            XCTAssertTrue(body.contains("未配置"), "应提示未配置凭证，got: \(body)")
        }
        XCTAssertEqual(state.loginCalls, 0)
    }

    // MARK: - 已配置但登录被拒 → 报错不降级

    func testCredsConfiguredLogin401ThrowsNotSilent() async throws {
        let state = MockAgentState()
        MockURLProtocol.handler = agentHandler(state, loginStatus: { _ in 401 }, outboxStatus: { _ in 401 })
        defer { MockURLProtocol.handler = nil }

        // 密码错误 + 有共享密钥：绝不能静默降级共享密钥（掩盖配置错误）
        let c = await makeClient(agentUser: "alice", agentPassword: "wrong", agentSharedSecret: "shared-secret")
        do {
            _ = try await c.nudgeOutboxFlush()
            XCTFail("应抛出 401")
        } catch let e as APIError {
            guard case .http(let code, let body) = e else {
                return XCTFail("应为 http(401)，got \(e)")
            }
            XCTAssertEqual(code, 401)
            XCTAssertTrue(
                body.contains("登录失败") || body.contains("账号或密码错误"),
                "应提示登录被拒，got: \(body)"
            )
        }
        XCTAssertEqual(state.loginCalls, 2)  // 初次 + 401 后重登一次（有界）
        XCTAssertFalse(
            state.outboxAuthHeaders.contains("Bearer shared-secret"),
            "已配置凭证登录失败不应降级共享密钥"
        )
    }

    // MARK: - 换凭证失效

    func testCredentialChangeInvalidatesAgentToken() async throws {
        let state = MockAgentState()
        MockURLProtocol.handler = agentHandler(state)
        defer { MockURLProtocol.handler = nil }

        let c = await makeClient()
        _ = try await c.nudgeOutboxFlush()  // tok1

        await c.update(
            baseURL: hub, user: "ccc", password: "ccc",
            chatBaseURL: agent,
            agentUser: "alice", agentPassword: "changed"
        )
        _ = try await c.nudgeOutboxFlush()  // 换密码 → 旧会话 token 作废，重登

        XCTAssertEqual(state.loginCalls, 2)
        XCTAssertEqual(state.outboxAuthHeaders, ["Bearer agent-tok1", "Bearer agent-tok2"])
    }
}
