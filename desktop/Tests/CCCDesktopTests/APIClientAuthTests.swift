import XCTest
@testable import CCCDesktop

/// URLProtocol mock：拦截全部请求，按 URL + Authorization 头返回可编程响应
final class MockURLProtocol: URLProtocol {
    static var handler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler = MockURLProtocol.handler else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        do {
            let (resp, data) = try handler(request)
            client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}

/// 每个测试捕获的请求序列状态（URLProtocol handler 在后台线程执行，用 class 引用共享）
final class MockHubState {
    var tokenCalls = 0
    var projectCalls = 0
    var projectAuthHeaders: [String] = []
}

/// 行为锁 · 认证层（APIClient × URLProtocol mock）
/// 锁定：Basic 只在 token 换取出现、后续请求带 Bearer、缓存复用、
/// 401→重取一次、401 两次报错（不无限循环）、token 端点 404 降级 Basic、TTL 前刷新、换凭证失效
final class APIClientAuthTests: XCTestCase {

    private var isoFormatter: ISO8601DateFormatter {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withColonSeparatorInTimeZone]
        return f
    }

    private func tokenJSON(_ token: String, expiresIn: TimeInterval = 3600) -> [String: Any] {
        [
            "token": token,
            "role": "operator",
            "scheme": "bearer",
            "expires_at": isoFormatter.string(from: Date().addingTimeInterval(expiresIn)),
            "ttl_s": 3600,
        ]
    }

    private func resp(_ code: Int, for request: URLRequest) -> HTTPURLResponse {
        HTTPURLResponse(url: request.url!, statusCode: code, httpVersion: nil, headerFields: nil)!
    }

    private func json(_ code: Int, _ obj: [String: Any], for request: URLRequest) throws -> (HTTPURLResponse, Data) {
        (resp(code, for: request), try JSONSerialization.data(withJSONObject: obj))
    }

    private func client(_ state: MockHubState) -> APIClient {
        APIClient(
            baseURL: URL(string: "http://127.0.0.1:17777/")!,
            user: "ccc",
            password: "ccc",
            urlProtocolClasses: [MockURLProtocol.self]
        )
    }

    private func standardHandler(
        _ state: MockHubState,
        projectStatus: @escaping (Int) -> Int = { _ in 200 }
    ) -> (URLRequest) throws -> (HTTPURLResponse, Data) {
        { req in
            let path = req.url?.path ?? ""
            let auth = req.value(forHTTPHeaderField: "Authorization") ?? ""
            if path.hasSuffix("/api/auth/token") {
                state.tokenCalls += 1
                return try self.json(200, self.tokenJSON("tok\(state.tokenCalls)"), for: req)
            }
            if path.hasSuffix("/api/desktop/projects") {
                state.projectCalls += 1
                state.projectAuthHeaders.append(auth)
                return try self.json(projectStatus(state.projectCalls), ["projects": [], "default_project": NSNull()], for: req)
            }
            return try self.json(404, ["error": "unexpected \(path)"], for: req)
        }
    }

    // MARK: - token 获取 + Bearer 使用

    func testTokenFetchedWithBasicThenBearer() async throws {
        let state = MockHubState()
        MockURLProtocol.handler = standardHandler(state)
        defer { MockURLProtocol.handler = nil }

        _ = try await client(state).fetchProjects()

        XCTAssertEqual(state.tokenCalls, 1)
        XCTAssertEqual(state.projectCalls, 1)
        // Basic 只出现在 token 换取（ccc:ccc）
        XCTAssertTrue(state.tokenCalls == 1)
        XCTAssertEqual(state.projectAuthHeaders, ["Bearer tok1"])
    }

    func testTokenCachedNoRefetch() async throws {
        let state = MockHubState()
        MockURLProtocol.handler = standardHandler(state)
        defer { MockURLProtocol.handler = nil }

        let c = client(state)
        _ = try await c.fetchProjects()
        _ = try await c.fetchProjects()

        XCTAssertEqual(state.tokenCalls, 1)  // 缓存复用，不重复换取
        XCTAssertEqual(state.projectCalls, 2)
        XCTAssertEqual(state.projectAuthHeaders, ["Bearer tok1", "Bearer tok1"])
    }

    // MARK: - 401 重取一次

    func test401RefetchOnceAndSucceed() async throws {
        let state = MockHubState()
        MockURLProtocol.handler = standardHandler(state) { call in
            call == 1 ? 401 : 200  // 第一次 401（模拟服务端重启），重试成功
        }
        defer { MockURLProtocol.handler = nil }

        _ = try await client(state).fetchProjects()

        XCTAssertEqual(state.tokenCalls, 2)   // 初次 + 401 后重取
        XCTAssertEqual(state.projectCalls, 2) // 401 + 重试
        XCTAssertEqual(state.projectAuthHeaders, ["Bearer tok1", "Bearer tok2"])
    }

    func test401TwiceThrowsNoInfiniteLoop() async throws {
        let state = MockHubState()
        MockURLProtocol.handler = standardHandler(state) { _ in 401 }  // 恒 401
        defer { MockURLProtocol.handler = nil }

        do {
            _ = try await client(state).fetchProjects()
            XCTFail("应抛出 401")
        } catch let e as APIError {
            if case .http(let code, _) = e {
                XCTAssertEqual(code, 401)
            } else {
                XCTFail("应为 http(401)，got \(e)")
            }
        }
        // 有界：token 重取一次后仍 401 → 报错，不无限循环
        XCTAssertEqual(state.tokenCalls, 2)
        XCTAssertEqual(state.projectCalls, 2)
    }

    // MARK: - 降级 Basic（开关 off 期间不断链）

    func testTokenEndpoint404FallsBackToBasic() async throws {
        let state = MockHubState()
        MockURLProtocol.handler = { req in
            let path = req.url?.path ?? ""
            let auth = req.value(forHTTPHeaderField: "Authorization") ?? ""
            if path.hasSuffix("/api/auth/token") {
                state.tokenCalls += 1
                return try self.json(404, ["error": "not found"], for: req)  // 旧服务端无 token 端点
            }
            if path.hasSuffix("/api/desktop/projects") {
                state.projectCalls += 1
                state.projectAuthHeaders.append(auth)
                return try self.json(200, ["projects": [], "default_project": NSNull()], for: req)
            }
            return try self.json(404, ["error": "unexpected"], for: req)
        }
        defer { MockURLProtocol.handler = nil }

        _ = try await client(state).fetchProjects()

        XCTAssertEqual(state.tokenCalls, 1)
        XCTAssertEqual(state.projectAuthHeaders, ["Basic Y2NjOmNjYw=="])  // 降级 Basic
    }

    func testDegradeWindowUsesBasicWithoutRefetch() async throws {
        let state = MockHubState()
        MockURLProtocol.handler = { req in
            let path = req.url?.path ?? ""
            let auth = req.value(forHTTPHeaderField: "Authorization") ?? ""
            if path.hasSuffix("/api/auth/token") {
                state.tokenCalls += 1
                return try self.json(404, ["error": "not found"], for: req)
            }
            if path.hasSuffix("/api/desktop/projects") {
                state.projectAuthHeaders.append(auth)
                return try self.json(200, ["projects": [], "default_project": NSNull()], for: req)
            }
            return try self.json(404, ["error": "unexpected"], for: req)
        }
        defer { MockURLProtocol.handler = nil }

        let c = client(state)
        _ = try await c.fetchProjects()  // 触发降级窗口
        _ = try await c.fetchProjects()  // 窗口内：直走 Basic，不再打 token 端点

        XCTAssertEqual(state.tokenCalls, 1)
        XCTAssertEqual(state.projectAuthHeaders, ["Basic Y2NjOmNjYw==", "Basic Y2NjOmNjYw=="])
    }

    // MARK: - TTL 前刷新

    func testRefreshNearExpiry() async throws {
        let state = MockHubState()
        MockURLProtocol.handler = { req in
            let path = req.url?.path ?? ""
            if path.hasSuffix("/api/auth/token") {
                state.tokenCalls += 1
                let expireIn: TimeInterval = state.tokenCalls == 1 ? 60 : 3600  // 首个 token 剩余 60s < refreshLead
                return try self.json(200, self.tokenJSON("tok\(state.tokenCalls)", expiresIn: expireIn), for: req)
            }
            if path.hasSuffix("/api/desktop/projects") {
                state.projectAuthHeaders.append(req.value(forHTTPHeaderField: "Authorization") ?? "")
                return try self.json(200, ["projects": [], "default_project": NSNull()], for: req)
            }
            return try self.json(404, ["error": "unexpected"], for: req)
        }
        defer { MockURLProtocol.handler = nil }

        let c = client(state)
        _ = try await c.fetchProjects()  // tok1
        _ = try await c.fetchProjects()  // 近 TTL → 刷新 → tok2

        XCTAssertEqual(state.tokenCalls, 2)
        XCTAssertEqual(state.projectAuthHeaders, ["Bearer tok1", "Bearer tok2"])
    }

    // MARK: - 换凭证失效

    func testCredentialChangeInvalidatesToken() async throws {
        let state = MockHubState()
        MockURLProtocol.handler = standardHandler(state)
        defer { MockURLProtocol.handler = nil }

        let url = URL(string: "http://127.0.0.1:17777/")!
        let c = client(state)
        _ = try await c.fetchProjects()  // tok1

        await c.update(baseURL: url, user: "ccc", password: "other")  // 换密码 → 旧 token 失效
        _ = try await c.fetchProjects()  // 应重取
        XCTAssertEqual(state.tokenCalls, 2)

        await c.update(baseURL: url, user: "ccc", password: "other")  // 同凭证 → 不失效
        _ = try await c.fetchProjects()  // 缓存 tok2 复用
        XCTAssertEqual(state.tokenCalls, 2)
        XCTAssertEqual(state.projectAuthHeaders, ["Bearer tok1", "Bearer tok2", "Bearer tok2"])
    }

    // MARK: - sendVoid 写路径同样走 Bearer

    func testSendVoidUsesBearer() async throws {
        let state = MockHubState()
        MockURLProtocol.handler = { req in
            let path = req.url?.path ?? ""
            let auth = req.value(forHTTPHeaderField: "Authorization") ?? ""
            if path.hasSuffix("/api/auth/token") {
                state.tokenCalls += 1
                return try self.json(200, self.tokenJSON("tok1"), for: req)
            }
            if path.hasSuffix("/api/desktop/threads/proj") {
                state.projectAuthHeaders.append(auth)
                return try self.json(200, ["ok": true], for: req)
            }
            return try self.json(404, ["error": "unexpected"], for: req)
        }
        defer { MockURLProtocol.handler = nil }

        let (_, code) = try await client(state).genericPOST("api/desktop/threads/proj")

        XCTAssertEqual(code, 200)
        XCTAssertEqual(state.projectAuthHeaders, ["Bearer tok1"])
    }
}
