import Foundation

enum APIError: LocalizedError {
    case badURL
    case http(Int, String)
    case decode(String)
    case gate([GateError])

    var errorDescription: String? {
        switch self {
        case .badURL: return "无效 Server 地址"
        case .http(let code, let body): return "HTTP \(code): \(body)"
        case .decode(let m): return "解析失败: \(m)"
        case .gate(let errs):
            return errs.map(\.localized).joined(separator: "；")
        }
    }
}

actor APIClient {
    private(set) var baseURL: URL
    private(set) var user: String
    private(set) var password: String
    /// 本机 Agent Sidecar（有则 chat 热路径走 localhost，不经 Hub）
    private(set) var chatBaseURL: URL?
    /// 本机业务仓路径（sidecar cwd）；空则 sidecar 用默认
    private(set) var localProjectPath: String?
    /// 短请求（列表/看板）
    private let session: URLSession
    /// 对话 SSE（可多路；与 flow 分离，避免抢同一连接池）
    private let chatSession: URLSession
    /// 流程 SSE（全 App 1 条）
    private let flowSession: URLSession

    init(baseURL: URL, user: String = "ccc", password: String = "ccc") {
        self.baseURL = baseURL
        self.user = user
        self.password = password
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = 30
        cfg.timeoutIntervalForResource = 90
        cfg.waitsForConnectivity = true
        // 短请求严控：防止 Desktop 并发打满 Hub
        cfg.httpMaximumConnectionsPerHost = 2
        self.session = URLSession(configuration: cfg)

        let chatCfg = URLSessionConfiguration.default
        chatCfg.timeoutIntervalForRequest = 600
        chatCfg.timeoutIntervalForResource = 1800
        chatCfg.waitsForConnectivity = true
        // 本机 sidecar 可多路并行（对话面禁止 Hub chat）
        chatCfg.httpMaximumConnectionsPerHost = 4
        chatCfg.requestCachePolicy = .reloadIgnoringLocalCacheData
        self.chatSession = URLSession(configuration: chatCfg)

        let flowCfg = URLSessionConfiguration.default
        flowCfg.timeoutIntervalForRequest = 600
        flowCfg.timeoutIntervalForResource = 1800
        flowCfg.waitsForConnectivity = true
        flowCfg.httpMaximumConnectionsPerHost = 1
        flowCfg.requestCachePolicy = .reloadIgnoringLocalCacheData
        self.flowSession = URLSession(configuration: flowCfg)
    }

    func update(
        baseURL: URL,
        user: String,
        password: String,
        chatBaseURL: URL? = nil,
        localProjectPath: String? = nil
    ) {
        self.baseURL = baseURL
        self.user = user
        self.password = password
        self.chatBaseURL = chatBaseURL
        self.localProjectPath = localProjectPath
    }

    var usesLocalAgent: Bool { chatBaseURL != nil }

    /// 探测本机 sidecar `/health`
    func probeLocalAgent(base: URL) async -> Bool {
        guard var health = URL(string: "health", relativeTo: base) else { return false }
        if health.absoluteString.hasSuffix("health") == false {
            health = base.appendingPathComponent("health")
        }
        var req = URLRequest(url: health)
        req.timeoutInterval = 1.5
        do {
            let (data, resp) = try await session.data(for: req)
            guard (resp as? HTTPURLResponse)?.statusCode == 200 else { return false }
            if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                return (obj["ok"] as? Bool) == true
            }
            return true
        } catch {
            return false
        }
    }

    /// Sidecar keep-warm：`POST /warm`
    @discardableResult
    func warmLocalAgent(base: URL? = nil) async -> Bool {
        let root = base ?? chatBaseURL
        guard let root else { return false }
        guard let url = URL(string: "warm", relativeTo: root) else { return false }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = Data("{}".utf8)
        req.timeoutInterval = 8
        do {
            let (data, resp) = try await session.data(for: req)
            guard (resp as? HTTPURLResponse)?.statusCode == 200 else { return false }
            if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                return (obj["ok"] as? Bool) == true
            }
            return true
        } catch {
            return false
        }
    }

    static func makeBaseURL(from raw: String) -> URL? {
        var s = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !s.isEmpty else { return nil }
        if !s.contains("://") { s = "http://" + s }
        if !s.hasSuffix("/") { s += "/" }
        return URL(string: s)
    }

    private func authedRequest(_ path: String, method: String = "GET", body: Data? = nil) throws -> URLRequest {
        guard let url = URL(string: path, relativeTo: baseURL) else {
            throw APIError.badURL
        }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("text/event-stream, application/json", forHTTPHeaderField: "Accept")
        let token = Data("\(user):\(password)".utf8).base64EncodedString()
        req.setValue("Basic \(token)", forHTTPHeaderField: "Authorization")
        req.httpBody = body
        return req
    }

    private func send<T: Decodable>(_ req: URLRequest, as type: T.Type) async throws -> T {
        try await HubRequestGate.shared.withPermit {
            var lastError: Error?
            for attempt in 1...3 {
                do {
                    let (data, resp) = try await self.session.data(for: req)
                    let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
                    if !(200..<300).contains(code) {
                        if let err = try? JSONDecoder().decode(APIErrorBody.self, from: data),
                           let gates = err.errors, !gates.isEmpty {
                            throw APIError.gate(gates)
                        }
                        let text = String(data: data, encoding: .utf8) ?? ""
                        // 5xx / 0 可重试；4xx 不重试
                        if code >= 500 || code == 0, attempt < 3 {
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
                    if attempt < 3 {
                        try await Task.sleep(nanoseconds: UInt64(attempt) * 400_000_000)
                        continue
                    }
                    throw error
                }
            }
            throw lastError ?? APIError.decode("请求失败")
        }
    }

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

    struct CreateThreadResp: Decodable {
        let thread_id: String
        let title: String?
    }

    struct EpicsResp: Decodable {
        let ok: Bool?
        let epics: [FlowEpicRef]
    }

    func fetchProjects() async throws -> ProjectsResp {
        try await send(try authedRequest("api/desktop/projects"), as: ProjectsResp.self)
    }

    func fetchThreads(projectId: String) async throws -> [DesktopThread] {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? projectId
        let resp = try await send(try authedRequest("api/desktop/threads?project_id=\(enc)"), as: ThreadsResp.self)
        return resp.threads
    }

    func createThread(projectId: String, title: String?) async throws -> CreateThreadResp {
        var payload: [String: String] = ["project_id": projectId]
        if let title, !title.isEmpty { payload["title"] = title }
        let data = try JSONEncoder().encode(payload)
        return try await send(try authedRequest("api/desktop/threads", method: "POST", body: data), as: CreateThreadResp.self)
    }

    func fetchThread(projectId: String, threadId: String) async throws -> ThreadDetail {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? projectId
        return try await send(
            try authedRequest("api/desktop/threads/\(threadId)?project_id=\(enc)"),
            as: ThreadDetail.self
        )
    }

    func renameThread(projectId: String, threadId: String, title: String) async throws {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? projectId
        let data = try JSONEncoder().encode(["title": title])
        struct Ok: Decodable { let ok: Bool?; let thread_id: String? }
        _ = try await send(
            try authedRequest("api/desktop/threads/\(threadId)?project_id=\(enc)", method: "PATCH", body: data),
            as: Ok.self
        )
    }

    func deleteThread(projectId: String, threadId: String) async throws {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? projectId
        struct Ok: Decodable { let ok: Bool? }
        _ = try await send(
            try authedRequest("api/desktop/threads/\(threadId)?project_id=\(enc)", method: "DELETE"),
            as: Ok.self
        )
    }

    func fetchRecentEpics(projectId: String, threadId: String? = nil) async throws -> [FlowEpicRef] {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? projectId
        var path = "api/desktop/flow/epics?project_id=\(enc)"
        if let threadId, !threadId.isEmpty {
            let t = threadId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? threadId
            path += "&thread_id=\(t)"
        }
        let resp = try await send(try authedRequest(path), as: EpicsResp.self)
        return resp.epics
    }

    /// 流式聊天：仅本机 Agent Sidecar（对话面基线；禁止 Hub /api/chat 回退）
    /// onEvent 由调用方切 MainActor（避免 actor↔MainActor 死锁导致 tool 事件攒到结束）
    func streamChat(
        projectId: String,
        sessionId: String,
        messages: [ChatMessage],
        promptMode: String = "full",
        onEvent: @escaping @Sendable (ChatStreamEvent) async -> Void
    ) async throws {
        guard let chatBase = chatBaseURL else {
            throw APIError.decode("本机 Agent 未就绪（对话只走本机 sidecar，不回退 Hub）")
        }
        struct Body: Encodable {
            let project: String
            let session_id: String
            let messages: [ChatMessage]
            let mode: String
            let project_path: String?
            let prompt_mode: String
        }
        let data = try JSONEncoder().encode(
            Body(
                project: projectId,
                session_id: sessionId,
                messages: messages,
                mode: "chat",
                project_path: localProjectPath,
                prompt_mode: promptMode
            )
        )
        guard let url = URL(string: "api/chat", relativeTo: chatBase) else {
            throw APIError.badURL
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("text/event-stream, application/json", forHTTPHeaderField: "Accept")
        req.httpBody = data
        let (bytes, resp) = try await chatSession.bytes(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if !(200..<300).contains(code) {
            var errBody = ""
            for try await line in bytes.lines { errBody += line; if errBody.count > 400 { break } }
            throw APIError.http(code, errBody)
        }

        var gotDelta = false
        var gotTool = false
        var gotDone = false
        var donePartial = false
        // Phase 1.6: 按行切片但用 cursor 一次性丢前缀，避免 removeSubrange 每行 O(n) 共 O(n²)
        let nlByte = Data([UInt8(ascii: "\n")])
        var buffer = Data()
        for try await chunk in bytes {
            try Task.checkCancellation()
            buffer.append(chunk)
            var cursor = buffer.startIndex
            while let r = buffer.range(of: nlByte, in: cursor..<buffer.endIndex) {
                let lineData = buffer.subdata(in: cursor..<r.lowerBound)
                cursor = r.upperBound
                var line = String(data: lineData, encoding: .utf8) ?? ""
                if line.hasSuffix("\r") { line.removeLast() }
                guard line.hasPrefix("data:") else { continue }
                var payload = String(line.dropFirst(5))
                if payload.hasPrefix(" ") { payload = String(payload.dropFirst()) }
                if payload == "[DONE]" || payload.isEmpty { continue }
                guard let pdata = payload.data(using: .utf8),
                      let obj = try? JSONSerialization.jsonObject(with: pdata) as? [String: Any]
                else { continue }
                let type = (obj["type"] as? String)?.lowercased()
                if type == "ping" { continue }
                if type == "error" {
                    let msg = (obj["content"] as? String) ?? (obj["message"] as? String) ?? "chat error"
                    throw APIError.http(500, msg)
                }
                if type == "tool_use" || type == "tool-use" || type == "tooluse" {
                    gotTool = true
                    let name = (obj["name"] as? String)
                        ?? (obj["tool"] as? String)
                        ?? (obj["tool_name"] as? String)
                        ?? "tool"
                    var inputStr: [String: String] = [:]
                    if let inp = obj["input"] as? [String: Any] {
                        for (k, v) in inp { inputStr[k] = "\(v)" }
                    } else if let inp = obj["input"] as? [String: String] {
                        inputStr = inp
                    } else if let ns = obj["input"] as? NSDictionary {
                        for (k, v) in ns {
                            if let ks = k as? String { inputStr[ks] = "\(v)" }
                        }
                    }
                    await onEvent(.toolUse(name: name, input: inputStr))
                    continue
                }
                if type == "tool_result" || type == "tool-result" {
                    let isErr = (obj["is_error"] as? Bool) == true
                        || (obj["error"] as? Bool) == true
                    await onEvent(.toolResult(ok: !isErr))
                    continue
                }
                if type == "cost" {
                    await onEvent(.cost(
                        tokens: obj["tokens"] as? Int,
                        usd: obj["usd"] as? Double
                    ))
                    continue
                }
                if type == "done" {
                    gotDone = true
                    donePartial = (obj["partial"] as? Bool) ?? false
                    await onEvent(.done(partial: donePartial))
                    continue
                }
                let textChunk: String? = {
                    if let c = obj["content"] as? String, !c.isEmpty { return c }
                    if let c = obj["delta"] as? String, !c.isEmpty { return c }
                    if let c = obj["text"] as? String, !c.isEmpty { return c }
                    return nil
                }()
                if let textChunk, type == "delta" || type == "text" || type == nil || type == "content" {
                    gotDelta = true
                    await onEvent(.delta(textChunk))
                }
            }
            // Phase 1.6: 一次性丢掉已处理前缀，保留未结束的尾巴给下一个 chunk
            if cursor > buffer.startIndex {
                buffer = buffer.subdata(in: cursor..<buffer.endIndex)
            }
        }
        if !gotDelta && !gotTool {
            throw APIError.decode("空回复（SSE 未解析到内容）")
        }
        if !gotDone || donePartial {
            throw APIError.decode("回复中断（连接或生成未完整结束）")
        }
    }

    /// 会话镜像备份到 Hub（非权威；Engine 不读；本机 Application Support 为准）
    func syncThreadMessages(
        projectId: String,
        threadId: String,
        messages: [ChatMessage]
    ) async throws {
        struct Body: Encodable {
            let project_id: String
            let messages: [ChatMessage]
        }
        let enc = threadId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? threadId
        let data = try JSONEncoder().encode(Body(project_id: projectId, messages: messages))
        let req = try authedRequest(
            "api/desktop/threads/\(enc)/messages",
            method: "PUT",
            body: data
        )
        struct Ok: Decodable { let ok: Bool? }
        _ = try await send(req, as: Ok.self)
    }

    func transfer(_ req: TransferRequest) async throws -> TransferResponse {
        let data = try JSONEncoder().encode(req)
        let urlReq = try authedRequest("api/desktop/transfer", method: "POST", body: data)
        return try await HubRequestGate.shared.withPermit {
            let (respData, resp) = try await self.session.data(for: urlReq)
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            let decoded = try JSONDecoder().decode(TransferResponse.self, from: respData)
            if !(200..<300).contains(code) || decoded.ok == false {
                if let errs = decoded.errors, !errs.isEmpty {
                    throw APIError.gate(errs)
                }
                throw APIError.http(code, decoded.error ?? "transfer failed")
            }
            return decoded
        }
    }

    func fetchBoard(workspace: String) async throws -> BoardSnapshot {
        let enc = workspace.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? workspace
        return try await send(try authedRequest("api/board?workspace=\(enc)"), as: BoardSnapshot.self)
    }

    func fetchOpsOverview() async throws -> OpsOverview {
        try await send(try authedRequest("api/ops/overview"), as: OpsOverview.self)
    }

    func fetchOpsRisks() async throws -> OpsRisksResp {
        try await send(try authedRequest("api/ops/risks"), as: OpsRisksResp.self)
    }

    func fetchProjectBaseline(projectId: String) async throws -> ProjectBaselineResp {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? projectId
        return try await send(try authedRequest("api/projects/\(enc)/baseline"), as: ProjectBaselineResp.self)
    }

    func flowSnapshot(projectId: String, epicId: String? = nil) async throws -> FlowSnapshot {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? projectId
        var path = "api/desktop/flow/snapshot?project_id=\(enc)"
        if let epicId, !epicId.isEmpty {
            let e = epicId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? epicId
            path += "&epic_id=\(e)"
        }
        return try await send(try authedRequest(path), as: FlowSnapshot.self)
    }

    /// 消费 flow SSE；每次 fanout/work_status 回调刷新建议
    func streamFlowEvents(
        projectId: String,
        epicId: String?,
        onEvent: @escaping @Sendable (String, [String: Any]) -> Void
    ) async throws {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? projectId
        var path = "api/desktop/flow/events?project_id=\(enc)"
        if let epicId, !epicId.isEmpty {
            let e = epicId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? epicId
            path += "&epic_id=\(e)"
        }
        let req = try authedRequest(path)
        let (bytes, resp) = try await flowSession.bytes(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if !(200..<300).contains(code) {
            throw APIError.http(code, "flow events failed")
        }
        var eventName = "message"
        for try await line in bytes.lines {
            if line.hasPrefix("event:") {
                eventName = line.dropFirst(6).trimmingCharacters(in: .whitespaces)
                continue
            }
            if line.hasPrefix("data:") {
                var payload = String(line.dropFirst(5))
                if payload.hasPrefix(" ") { payload = String(payload.dropFirst()) }
                if let data = payload.data(using: .utf8),
                   let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    onEvent(eventName, obj)
                }
                eventName = "message"
            }
        }
    }
}
