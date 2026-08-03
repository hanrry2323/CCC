import Foundation

enum APIError: LocalizedError {
    case badURL
    case http(Int, String)
    case decode(String)

    var errorDescription: String? {
        switch self {
        case .badURL: return "无效 Server 地址"
        case .http(let code, let body): return "HTTP \(code): \(body)"
        case .decode(let m): return "解析失败: \(m)"
        }
    }

    var httpStatus: Int? {
        switch self {
        case .http(let code, _): return code
        default: return nil
        }
    }
}

actor APIClient {
    private(set) var baseURL: URL
    private(set) var user: String
    private(set) var password: String
    /// 短请求
    private let session: URLSession

    /// 新服务端 base URL
    private var newServerBaseURL: URL?
    /// 新服务端会话 token（内存缓存）
    private var newServerToken: String?
    /// 新服务端 token 过期时刻
    private var newServerTokenExpiresAt: Date?

    init(
        baseURL: URL,
        user: String = "ccc",
        password: String = "ccc",
        /// 测试注入：自定义 URLProtocol（默认空 → 生产行为不变）
        urlProtocolClasses: [URLProtocol.Type] = []
    ) {
        self.baseURL = baseURL
        self.user = user
        self.password = password
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = 45
        cfg.timeoutIntervalForResource = 120
        cfg.waitsForConnectivity = false
        cfg.httpMaximumConnectionsPerHost = 4
        if !urlProtocolClasses.isEmpty {
            cfg.protocolClasses = urlProtocolClasses + (cfg.protocolClasses ?? [])
        }
        self.session = URLSession(configuration: cfg)
    }

    func update(baseURL: URL, user: String, password: String) {
        self.baseURL = baseURL
        self.user = user
        self.password = password
    }

    static func makeBaseURL(from raw: String) -> URL? {
        var s = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !s.isEmpty else { return nil }
        if !s.contains("://") { s = "http://" + s }
        if !s.hasSuffix("/") { s += "/" }
        return URL(string: s)
    }

    // MARK: - 新服务端（server/web/server.py）对接：POST /session + POST /conversation

    /// 新服务端会话 token 响应
    struct NewServerSessionResponse: Decodable {
        let token: String
        let expires_at: String?
        let ttl_s: Int?
    }

    /// 新服务端对话响应
    struct NewServerConversationResponse: Decodable {
        let reply: String
    }

    /// 新服务端对话历史消息条目
    struct NewServerMessage: Decodable, Sendable {
        let role: String
        let message: String
        let timestamp: String
    }

    /// 配置新服务端地址（nil = 禁用）
    func configureNewServer(url: URL?) {
        newServerBaseURL = url
        if url == nil {
            newServerToken = nil
            newServerTokenExpiresAt = nil
        }
    }

    /// 是否启用了新服务端
    var hasNewServer: Bool { newServerBaseURL != nil }

    /// 登录新服务端：POST /session → 换取 Bearer token
    func loginToNewServer(username: String, password: String) async throws -> String {
        guard let base = newServerBaseURL else {
            throw APIError.badURL
        }
        guard let url = URL(string: "session", relativeTo: base) else {
            throw APIError.badURL
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: String] = ["username": username, "password": password]
        req.httpBody = try JSONEncoder().encode(body)
        req.timeoutInterval = 15

        let (data, resp) = try await session.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0

        guard (200..<300).contains(code) else {
            if code == 401 {
                throw APIError.http(code, "新服务端登录失败：账号或密码错误")
            }
            let text = String(data: data, encoding: .utf8) ?? ""
            throw APIError.http(code, text)
        }
        let decoded = try JSONDecoder().decode(NewServerSessionResponse.self, from: data)
        newServerToken = decoded.token
        if let ttl = decoded.ttl_s {
            newServerTokenExpiresAt = Date().addingTimeInterval(TimeInterval(ttl))
        } else {
            newServerTokenExpiresAt = nil
        }
        return decoded.token
    }

    /// 新服务端 token 是否有效（未过期）
    private func isNewServerTokenValid() -> Bool {
        guard let token = newServerToken, !token.isEmpty else { return false }
        guard let expiresAt = newServerTokenExpiresAt else { return true }
        return Date() < expiresAt
    }

    /// 新服务端鉴权头（有效 token → Bearer；否则 nil）
    private func newServerAuthHeader() -> String? {
        guard isNewServerTokenValid(), let token = newServerToken else { return nil }
        return "Bearer \(token)"
    }

    /// 带新服务端鉴权的请求构造
    private func newServerAuthedRequest(path: String, method: String = "GET", body: Data? = nil) throws -> URLRequest {
        guard let base = newServerBaseURL else { throw APIError.badURL }
        guard let url = URL(string: path, relativeTo: base) else { throw APIError.badURL }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let auth = newServerAuthHeader() {
            req.setValue(auth, forHTTPHeaderField: "Authorization")
        }
        req.httpBody = body
        req.timeoutInterval = 15
        return req
    }

    /// 新服务端对话：POST /conversation
    func sendConversation(message: String) async throws -> String {
        let body = try JSONEncoder().encode(["message": message])
        let req = try newServerAuthedRequest(path: "conversation", method: "POST", body: body)
        let (data, resp) = try await session.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if code == 401 {
            newServerToken = nil
            throw APIError.http(401, "新服务端会话 token 过期，请重新登录")
        }
        guard (200..<300).contains(code) else {
            let text = String(data: data, encoding: .utf8) ?? ""
            throw APIError.http(code, text)
        }
        let decoded = try JSONDecoder().decode(NewServerConversationResponse.self, from: data)
        return decoded.reply
    }

    /// 新服务端对话历史：GET /conversation
    func fetchNewServerConversationHistory() async throws -> [NewServerMessage] {
        let req = try newServerAuthedRequest(path: "conversation")
        let (data, resp) = try await session.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(code) else {
            let text = String(data: data, encoding: .utf8) ?? ""
            throw APIError.http(code, text)
        }
        struct HistoryWrapper: Decodable {
            let messages: [NewServerMessage]
        }
        let decoded = try JSONDecoder().decode(HistoryWrapper.self, from: data)
        return decoded.messages
    }

    /// 通用发送 + 解码（带重试）
    private func send<T: Decodable>(
        _ req: URLRequest,
        as type: T.Type,
        maxAttempts: Int = 3
    ) async throws -> T {
        let attempts = max(1, min(maxAttempts, 3))
        let req = req
        var lastError: Error?
        for attempt in 1...attempts {
            do {
                let (data, resp) = try await self.session.data(for: req)
                let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
                if !(200..<300).contains(code) {
                    let text = String(data: data, encoding: .utf8) ?? ""
                    if code >= 500 || code == 0, attempt < attempts {
                        try await Task.sleep(nanoseconds: UInt64(attempt) * 400_000_000)
                        continue
                    }
                    throw APIError.http(code, String(text.prefix(400)))
                }
                do {
                    return try JSONDecoder().decode(T.self, from: data)
                } catch {
                    throw APIError.decode(error.localizedDescription)
                }
            } catch let e as APIError {
                throw e
            } catch {
                lastError = error
                if attempt < attempts {
                    try await Task.sleep(nanoseconds: UInt64(attempt) * 400_000_000)
                    continue
                }
                throw error
            }
        }
        throw lastError ?? APIError.decode("请求失败")
    }

    // MARK: - 新服务端协议端点

    struct ProjectsResp: Decodable {
        let projects: [DesktopProject]
        let default_project: String?
    }

    struct ThreadsResp: Decodable {
        let threads: [DesktopThread]
        let project_id: String?
    }

    struct ThreadDetail: Decodable {
        let thread_id: String?
        let title: String?
        let messages: [ChatMessage]?
    }

    /// 探活新服务端：GET /health（免鉴权）
    func probeNewServerHealth() async -> Bool {
        guard let base = newServerBaseURL else { return false }
        guard let url = URL(string: "health", relativeTo: base) else { return false }
        var req = URLRequest(url: url)
        req.timeoutInterval = 3
        do {
            let (_, resp) = try await session.data(for: req)
            return (resp as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    /// 新服务端项目列表：GET /board/summaries → 派生 DesktopProject 列表
    func fetchProjectsNewServer() async throws -> ProjectsResp {
        var req = try newServerAuthedRequest(path: "board/summaries")
        req.timeoutInterval = 10
        struct SummariesResp: Decodable {
            let summaries: [String: DecodableStub]
        }
        struct DecodableStub: Decodable {}
        let resp = try await send(req, as: SummariesResp.self, maxAttempts: 2)
        let names = resp.summaries.keys.sorted()
        let projects: [DesktopProject] = names.map { name in
            DesktopProject(
                id: name,
                name: name,
                path: "",
                workspace: name,
                role: "app",
                engine_eligible: true
            )
        }
        return ProjectsResp(projects: projects, default_project: names.first)
    }

    /// 新服务端线程列表：单会话壳，返回固定一条 thread
    func fetchThreadsNewServer(projectId: String) async throws -> ThreadsResp {
        return ThreadsResp(
            threads: [DesktopThread(
                thread_id: "main",
                title: "对话",
                updated_at: nil,
                project_id: projectId
            )],
            project_id: projectId
        )
    }

    /// 新服务端线程详情：GET /conversation 历史 → ThreadDetail
    func fetchThreadNewServer(projectId: String, threadId: String) async throws -> ThreadDetail {
        let history = try await fetchNewServerConversationHistory()
        let messages: [ChatMessage] = history.map { m in
            ChatMessage(
                id: UUID(),
                role: m.role,
                content: m.message,
                isStreaming: false
            )
        }
        return ThreadDetail(
            thread_id: "main",
            title: "对话",
            messages: messages
        )
    }

    /// 新服务端看板快照：GET /board/snapshot?workspace=X
    func fetchBoardNewServer(workspace: String, includeHidden: Bool = false) async throws -> BoardSnapshot {
        let enc = workspace.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? workspace
        var path = "board/snapshot?workspace=\(enc)"
        if includeHidden { path += "&include_hidden=1" }
        var req = try newServerAuthedRequest(path: path)
        req.timeoutInterval = 12
        return try await send(req, as: BoardSnapshot.self, maxAttempts: 2)
    }

    /// 新服务端多项目汇总：GET /board/summaries?workspaces=a,b
    func fetchBoardSummariesNewServer(workspaces: [String]) async throws -> BoardSummariesResp {
        let joined = workspaces.joined(separator: ",")
        let enc = joined.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? joined
        var req = try newServerAuthedRequest(path: "board/summaries?workspaces=\(enc)")
        req.timeoutInterval = 12
        return try await send(req, as: BoardSummariesResp.self, maxAttempts: 2)
    }

    /// 新服务端任务详情：GET /tasks/{id}?workspace=X
    func fetchTaskDetailNewServer(taskId: String, workspace: String) async throws -> BoardTaskDetail {
        let t = taskId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? taskId
        let w = workspace.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? workspace
        let req = try newServerAuthedRequest(path: "tasks/\(t)?workspace=\(w)")
        return try await send(req, as: BoardTaskDetail.self)
    }

    /// 新服务端运维汇总：GET /ops/summary
    func fetchOpsSummaryNewServer() async throws -> OpsSummary {
        var req = try newServerAuthedRequest(path: "ops/summary")
        req.timeoutInterval = 15
        return try await send(req, as: OpsSummary.self, maxAttempts: 2)
    }
}