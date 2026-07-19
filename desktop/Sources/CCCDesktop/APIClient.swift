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
        // 本机 sidecar 可多路并行；Hub 回退时 AppModel 仍限 1 路
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
            let (data, resp) = try await self.session.data(for: req)
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            if !(200..<300).contains(code) {
                if let err = try? JSONDecoder().decode(APIErrorBody.self, from: data),
                   let gates = err.errors, !gates.isEmpty {
                    throw APIError.gate(gates)
                }
                let text = String(data: data, encoding: .utf8) ?? ""
                throw APIError.http(code, String(text.prefix(400)))
            }
            do {
                return try JSONDecoder().decode(T.self, from: data)
            } catch {
                throw APIError.decode(error.localizedDescription)
            }
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

    /// 流式聊天：优先本机 Agent Sidecar，否则 Hub；回调保证在 MainActor
    func streamChat(
        projectId: String,
        sessionId: String,
        messages: [ChatMessage],
        onEvent: @escaping @MainActor @Sendable (ChatStreamEvent) -> Void
    ) async throws {
        struct Body: Encodable {
            let project: String
            let session_id: String
            let messages: [ChatMessage]
            let mode: String
            let project_path: String?
        }
        let data = try JSONEncoder().encode(
            Body(
                project: projectId,
                session_id: sessionId,
                messages: messages,
                mode: "chat",
                project_path: localProjectPath
            )
        )
        let req: URLRequest
        if let chatBase = chatBaseURL {
            guard let url = URL(string: "api/chat", relativeTo: chatBase) else {
                throw APIError.badURL
            }
            var r = URLRequest(url: url)
            r.httpMethod = "POST"
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
            r.setValue("text/event-stream, application/json", forHTTPHeaderField: "Accept")
            r.httpBody = data
            req = r
        } else {
            req = try authedRequest("api/chat", method: "POST", body: data)
        }
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
        for try await line in bytes.lines {
            try Task.checkCancellation()
            let raw = line
            guard raw.hasPrefix("data:") else { continue }
            var payload = String(raw.dropFirst(5))
            if payload.hasPrefix(" ") { payload = String(payload.dropFirst()) }
            if payload == "[DONE]" || payload.isEmpty { continue }
            guard let pdata = payload.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: pdata) as? [String: Any]
            else { continue }
            let type = obj["type"] as? String
            if type == "ping" { continue }
            if type == "error" {
                let msg = (obj["content"] as? String) ?? (obj["message"] as? String) ?? "chat error"
                throw APIError.http(500, msg)
            }
            if type == "tool_use" {
                gotTool = true
                let name = (obj["name"] as? String) ?? "tool"
                var inputStr: [String: String] = [:]
                if let inp = obj["input"] as? [String: Any] {
                    for (k, v) in inp {
                        inputStr[k] = "\(v)"
                    }
                }
                await onEvent(.toolUse(name: name, input: inputStr))
                continue
            }
            if type == "tool_result" {
                await onEvent(.toolResult(ok: true))
                continue
            }
            if type == "cost" {
                let tokens = obj["tokens"] as? Int
                let usd = obj["usd"] as? Double
                await onEvent(.cost(tokens: tokens, usd: usd))
                continue
            }
            if type == "done" {
                gotDone = true
                donePartial = (obj["partial"] as? Bool) ?? false
                await onEvent(.done(partial: donePartial))
                continue
            }
            let chunk: String? = {
                if let c = obj["content"] as? String, !c.isEmpty { return c }
                if let c = obj["delta"] as? String, !c.isEmpty { return c }
                if let c = obj["text"] as? String, !c.isEmpty { return c }
                return nil
            }()
            if let chunk, type == "delta" || type == "text" || type == nil || type == "content" {
                gotDelta = true
                await onEvent(.delta(chunk))
            }
        }
        if !gotDelta && !gotTool {
            throw APIError.decode("空回复（SSE 未解析到内容）")
        }
        // 流被掐断却没 done → 半截；有 done.partial → 半截
        if !gotDone || donePartial {
            throw APIError.decode("回复中断（连接或生成未完整结束）")
        }
    }

    /// 本地聊完后把消息落到 Hub（转任务 / 历史）
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

    /// Hub 过渡预热（本地 sidecar 可用时可不调）
    func warmHubAgent(projectId: String, threadId: String) async {
        struct Body: Encodable {
            let project_id: String
            let thread_id: String
        }
        do {
            let data = try JSONEncoder().encode(Body(project_id: projectId, thread_id: threadId))
            let req = try authedRequest("api/desktop/agent/warm", method: "POST", body: data)
            struct Ok: Decodable { let ok: Bool? }
            _ = try await send(req, as: Ok.self)
        } catch {
            // 预热失败不阻断聊天
        }
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
