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

/// 流式大脑事件（/conversation stream SSE 归一化），对齐 server/web/brain.py 协议：
/// meta / thinking / text / tool_use / tool_result / done / error。
enum BrainStreamEvent: Equatable {
    case meta([String: Any])
    case thinking(String)
    case text(String)
    case toolUse(id: String, name: String, input: [String: Any])
    case toolResult(toolUseID: String, content: String)
    case done(isError: Bool, text: String, error: String)
    case error(status: Int, message: String)

    static func == (lhs: BrainStreamEvent, rhs: BrainStreamEvent) -> Bool {
        switch (lhs, rhs) {
        case (.meta(let a), .meta(let b)):
            return NSDictionary(dictionary: a).isEqual(to: b)
        case (.thinking(let a), .thinking(let b)): return a == b
        case (.text(let a), .text(let b)): return a == b
        case (.toolUse(let ai, let an, let aIn), .toolUse(let bi, let bn, let bIn)):
            return ai == bi && an == bn && NSDictionary(dictionary: aIn).isEqual(to: bIn)
        case (.toolResult(let a, let b), .toolResult(let c, let d)): return a == c && b == d
        case (.done(let a1, let a2, let a3), .done(let b1, let b2, let b3)):
            return a1 == b1 && a2 == b2 && a3 == b3
        case (.error(let a, let b), .error(let c, let d)): return a == c && b == d
        default: return false
        }
    }
}

actor APIClient {
    private(set) var baseURL: URL
    private(set) var user: String
    private(set) var password: String
    /// 短请求
    private let session: URLSession
    /// 流式请求（长尾）：资源超时放大到 10 分钟（> 大脑 120s 超时），空闲读超时 60s
    private let streamSession: URLSession

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
        let scfg = URLSessionConfiguration.default
        scfg.timeoutIntervalForRequest = 60
        scfg.timeoutIntervalForResource = 600
        scfg.waitsForConnectivity = false
        scfg.httpMaximumConnectionsPerHost = 4
        if !urlProtocolClasses.isEmpty {
            scfg.protocolClasses = urlProtocolClasses + (scfg.protocolClasses ?? [])
        }
        self.streamSession = URLSession(configuration: scfg)
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

    /// 流式对话请求体（stream:true）
    struct StreamBody: Encodable {
        let message: String
        let stream: Bool
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

    /// 流式请求构造：走 streamSession 长尾超时（不放宽 15s 短请求）
    private func newServerStreamingRequest(path: String, body: Data?) throws -> URLRequest {
        guard let base = newServerBaseURL else { throw APIError.badURL }
        guard let url = URL(string: path, relativeTo: base) else { throw APIError.badURL }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let auth = newServerAuthHeader() {
            req.setValue(auth, forHTTPHeaderField: "Authorization")
        }
        req.httpBody = body
        req.timeoutInterval = 60
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

    /// 新服务端流式对话：POST /conversation {stream:true} → SSE 逐事件产出
    ///
    /// 事件归一化为 BrainStreamEvent（meta / thinking / text / tool_use /
    /// tool_result / done / error）。401 → 抛 APIError 并清除 token；
    /// 客户端断连/取消 → 正常 finish（不抛错）。与 server/web/brain.py 协议对齐。
    func streamConversation(message: String) -> AsyncThrowingStream<BrainStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                await self.runStreamConversation(message: message, continuation: continuation)
            }
            continuation.onTermination = { @Sendable _ in
                task.cancel()
            }
        }
    }

    private func runStreamConversation(
        message: String,
        continuation: AsyncThrowingStream<BrainStreamEvent, Error>.Continuation
    ) async {
        do {
            let body = try JSONEncoder().encode(StreamBody(message: message, stream: true))
            let req = try newServerStreamingRequest(path: "conversation", body: body)
            let (bytes, resp) = try await streamSession.bytes(for: req)
            guard let http = resp as? HTTPURLResponse else {
                continuation.finish(throwing: APIError.http(0, "非 HTTP 响应"))
                return
            }
            let code = http.statusCode
            if code == 401 {
                newServerToken = nil
                continuation.finish(throwing: APIError.http(401, "新服务端会话 token 过期，请重新登录"))
                return
            }
            guard (200..<300).contains(code) else {
                var text = ""
                for try await line in bytes.lines { text += line + "\n" }
                continuation.finish(
                    throwing: APIError.http(code, text.trimmingCharacters(in: .whitespacesAndNewlines))
                )
                return
            }

            // SSE 块解析：每事件 = 一条 `event:` 行 + 一条 `data:` 行。
            // 逐行累积，遇新 `event:` 行、空行或 EOF 时派发前一事件。注意
            // bytes.lines 会丢弃空行（omittingEmptySubsequences），不能依赖
            // \n\n 做分隔 → 以 `event:` 行为块边界，天然兼容网络分块边界
            // （半个 JSON 不会被解析）。
            var eventName = ""
            var dataLines: [String] = []
            func flushBlock() {
                guard !eventName.isEmpty || !dataLines.isEmpty else { return }
                let raw = dataLines.joined(separator: "\n")
                let name = eventName
                eventName = ""
                dataLines = []
                guard !raw.isEmpty,
                      let obj = try? JSONSerialization.jsonObject(with: Data(raw.utf8))
                            as? [String: Any] else { return }
                if let event = Self.parseStreamEvent(name: name, payload: obj) {
                    continuation.yield(event)
                }
            }
            for try await rawLine in bytes.lines {
                let line = rawLine.hasSuffix("\r") ? String(rawLine.dropLast()) : rawLine
                if line.isEmpty {
                    flushBlock()
                } else if line.hasPrefix("event:") {
                    flushBlock()
                    eventName = String(line.dropFirst(6)).trimmingCharacters(in: .whitespaces)
                } else if line.hasPrefix("data:") {
                    let d = String(line.dropFirst(5))
                    dataLines.append(d.hasPrefix(" ") ? String(d.dropFirst()) : d)
                }
            }
            flushBlock()
            continuation.finish()
        } catch is CancellationError {
            continuation.finish()
        } catch {
            continuation.finish(throwing: error)
        }
    }

    /// SSE data payload → BrainStreamEvent（未知事件跳过）
    private static func parseStreamEvent(name: String, payload: [String: Any]) -> BrainStreamEvent? {
        switch name {
        case "meta":
            return .meta(payload)
        case "thinking":
            return .thinking(payload["data"] as? String ?? "")
        case "text":
            return .text(payload["text"] as? String ?? "")
        case "tool_use":
            return .toolUse(
                id: payload["id"] as? String ?? "",
                name: payload["name"] as? String ?? "",
                input: payload["input"] as? [String: Any] ?? [:]
            )
        case "tool_result":
            return .toolResult(
                toolUseID: payload["tool_use_id"] as? String ?? "",
                content: payload["content"] as? String ?? ""
            )
        case "done":
            return .done(
                isError: payload["is_error"] as? Bool ?? false,
                text: payload["text"] as? String ?? "",
                error: payload["error"] as? String ?? ""
            )
        case "error":
            return .error(
                status: payload["status"] as? Int ?? 0,
                message: payload["message"] as? String ?? ""
            )
        default:
            return nil
        }
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

    /// 新服务端看板快照：GET /board/snapshot?workspace=X
    func fetchBoardNewServer(workspace: String, includeHidden: Bool = false) async throws -> BoardSnapshot {
        let enc = workspace.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? workspace
        var path = "board/snapshot?workspace=\(enc)"
        if includeHidden { path += "&include_hidden=1" }
        var req = try newServerAuthedRequest(path: path)
        req.timeoutInterval = 12
        return try await send(req, as: BoardSnapshot.self, maxAttempts: 2)
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