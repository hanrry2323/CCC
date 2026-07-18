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
            return errs.map { $0.message ?? $0.code ?? "?" }.joined(separator: "；")
        }
    }
}

actor APIClient {
    private(set) var baseURL: URL
    private(set) var user: String
    private(set) var password: String
    private let session: URLSession

    init(baseURL: URL, user: String = "ccc", password: String = "ccc") {
        self.baseURL = baseURL
        self.user = user
        self.password = password
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = 600
        cfg.timeoutIntervalForResource = 1800
        cfg.waitsForConnectivity = true
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
        let (data, resp) = try await session.data(for: req)
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

    struct ChatResp: Decodable {
        let reply: String?
        let session_id: String?
        let messages: [ChatMessage]?
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

    func chat(projectId: String, sessionId: String, messages: [ChatMessage]) async throws -> ChatResp {
        struct Body: Encodable {
            let project: String
            let session_id: String
            let messages: [ChatMessage]
            let mode: String
        }
        let data = try JSONEncoder().encode(
            Body(project: projectId, session_id: sessionId, messages: messages, mode: "chat")
        )
        let req = try authedRequest("api/chat", method: "POST", body: data)
        let (respData, resp) = try await session.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if !(200..<300).contains(code) {
            let text = String(data: respData, encoding: .utf8) ?? ""
            throw APIError.http(code, String(text.prefix(400)))
        }
        if let decoded = try? JSONDecoder().decode(ChatResp.self, from: respData) {
            return decoded
        }
        let text = String(data: respData, encoding: .utf8) ?? ""
        let reply = Self.extractSSEReply(text)
        if reply.isEmpty {
            throw APIError.decode("空回复（SSE 未解析到 delta）")
        }
        return ChatResp(reply: reply, session_id: sessionId, messages: nil)
    }

    /// Hub SSE：`{"type":"delta","content":"..."}` 等
    private static func extractSSEReply(_ text: String) -> String {
        var chunks: [String] = []
        let normalized = text.replacingOccurrences(of: "\r\n", with: "\n")
        for line in normalized.split(separator: "\n", omittingEmptySubsequences: false) {
            let raw = String(line)
            guard raw.hasPrefix("data:") else { continue }
            var payload = String(raw.dropFirst(5))
            if payload.hasPrefix(" ") { payload = String(payload.dropFirst()) }
            if payload == "[DONE]" || payload.isEmpty { continue }
            guard let data = payload.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { continue }
            let type = obj["type"] as? String
            if type == "error" {
                let msg = (obj["content"] as? String) ?? (obj["message"] as? String) ?? "chat error"
                chunks.append("\n[错误] \(msg)")
                continue
            }
            if type == "delta" || type == nil {
                if let c = obj["content"] as? String, !c.isEmpty {
                    chunks.append(c)
                }
            }
        }
        return chunks.joined()
    }

    func transfer(_ req: TransferRequest) async throws -> TransferResponse {
        let data = try JSONEncoder().encode(req)
        let urlReq = try authedRequest("api/desktop/transfer", method: "POST", body: data)
        let (respData, resp) = try await session.data(for: urlReq)
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

    func flowSnapshot(projectId: String, epicId: String? = nil) async throws -> FlowSnapshot {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? projectId
        var path = "api/desktop/flow/snapshot?project_id=\(enc)"
        if let epicId, !epicId.isEmpty {
            let e = epicId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? epicId
            path += "&epic_id=\(e)"
        }
        return try await send(try authedRequest(path), as: FlowSnapshot.self)
    }
}
