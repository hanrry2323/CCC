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
    var baseURL: URL
    var user: String
    var password: String

    init(baseURL: URL, user: String = "ccc", password: String = "ccc") {
        self.baseURL = baseURL
        self.user = user
        self.password = password
    }

    private func authedRequest(_ path: String, method: String = "GET", body: Data? = nil) throws -> URLRequest {
        guard let url = URL(string: path, relativeTo: baseURL) else {
            throw APIError.badURL
        }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let token = Data("\(user):\(password)".utf8).base64EncodedString()
        req.setValue("Basic \(token)", forHTTPHeaderField: "Authorization")
        req.httpBody = body
        return req
    }

    private func send<T: Decodable>(_ req: URLRequest, as type: T.Type) async throws -> T {
        let (data, resp) = try await URLSession.shared.data(for: req)
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
        let path = "api/desktop/threads?project_id=\(projectId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? projectId)"
        let resp = try await send(try authedRequest(path), as: ThreadsResp.self)
        return resp.threads
    }

    func createThread(projectId: String, title: String?) async throws -> CreateThreadResp {
        var payload: [String: String] = ["project_id": projectId]
        if let title, !title.isEmpty { payload["title"] = title }
        let data = try JSONEncoder().encode(payload)
        return try await send(try authedRequest("api/desktop/threads", method: "POST", body: data), as: CreateThreadResp.self)
    }

    func fetchThread(projectId: String, threadId: String) async throws -> ThreadDetail {
        let path = "api/desktop/threads/\(threadId)?project_id=\(projectId)"
        return try await send(try authedRequest(path), as: ThreadDetail.self)
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
        // 复用 Hub 对话 API（loop-code 在 Server）；响应可能是 SSE，取非流式 JSON 或文本
        let req = try authedRequest("api/chat", method: "POST", body: data)
        let (respData, resp) = try await URLSession.shared.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if !(200..<300).contains(code) {
            let text = String(data: respData, encoding: .utf8) ?? ""
            throw APIError.http(code, String(text.prefix(400)))
        }
        if let decoded = try? JSONDecoder().decode(ChatResp.self, from: respData) {
            return decoded
        }
        // SSE / 纯文本回落
        let text = String(data: respData, encoding: .utf8) ?? ""
        let reply = Self.extractSSEReply(text) ?? text
        return ChatResp(reply: reply, session_id: sessionId, messages: nil)
    }

    private static func extractSSEReply(_ text: String) -> String? {
        var chunks: [String] = []
        for line in text.split(separator: "\n") {
            if line.hasPrefix("data: ") {
                let payload = String(line.dropFirst(6))
                if payload == "[DONE]" { continue }
                if let data = payload.data(using: .utf8),
                   let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    if let c = obj["content"] as? String { chunks.append(c) }
                    else if let c = obj["delta"] as? String { chunks.append(c) }
                    else if let c = obj["text"] as? String { chunks.append(c) }
                }
            }
        }
        let joined = chunks.joined()
        return joined.isEmpty ? nil : joined
    }

    func transfer(_ req: TransferRequest) async throws -> TransferResponse {
        let data = try JSONEncoder().encode(req)
        let urlReq = try authedRequest("api/desktop/transfer", method: "POST", body: data)
        let (respData, resp) = try await URLSession.shared.data(for: urlReq)
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
        var path = "api/desktop/flow/snapshot?project_id=\(projectId)"
        if let epicId, !epicId.isEmpty {
            path += "&epic_id=\(epicId)"
        }
        return try await send(try authedRequest(path), as: FlowSnapshot.self)
    }
}
