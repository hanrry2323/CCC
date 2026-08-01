import Foundation

enum APIError: LocalizedError {
    case badURL
    case http(Int, String)
    /// SSE `type=error`（带 sidecar `code`）或客户端进展超时
    case stream(code: String?, message: String)
    case decode(String)
    case gate([GateError])
    /// Hub 返回 ok 但缺少 epic_id（空响应/半截 JSON 等）— 可重试
    case emptyEpicId

    var errorDescription: String? {
        switch self {
        case .badURL: return "无效 Server 地址"
        case .http(let code, let body): return "HTTP \(code): \(body)"
        case .stream(_, let message): return message
        case .decode(let m): return "解析失败: \(m)"
        case .gate(let errs):
            return errs.map(\.localized).joined(separator: "；")
        case .emptyEpicId: return "transfer 空 epic_id（可重试）"
        }
    }

    /// sidecar / 客户端稳定性错误码（无则 nil）
    var streamCode: String? {
        switch self {
        case .stream(let code, _): return code
        default: return nil
        }
    }

    var httpStatus: Int? {
        switch self {
        case .http(let code, _): return code
        default: return nil
        }
    }

    /// 鉴权 / 路径 / 过长：禁止自动重试
    var isNonRetryableAuthOrClient: Bool {
        switch self {
        case .http(let code, let body):
            if code == 401 || code == 403 || code == 503 || code == 413 { return true }
            let b = body.lowercased()
            return b.contains("unauthorized")
                || b.contains("project_path not allowed")
                || b.contains("鉴权")
        case .stream(let code, let message):
            let c = (code ?? "").lowercased()
            if c == "unauthorized" { return true }
            let m = message.lowercased()
            return m.contains("鉴权") || m.contains("unauthorized")
        default:
            return false
        }
    }

    /// 同会话可自动重试的中断类错误
    var isRetryableStreamFailure: Bool {
        if isNonRetryableAuthOrClient { return false }
        switch self {
        case .stream(let code, let message):
            let c = (code ?? "").lowercased()
            if ["first_event_timeout", "tool_stall", "idle_timeout", "max_timeout",
                "lock_timeout", "client_progress_stall", "empty_stub",
                "hang", "connect_failed"].contains(c) {
                return true
            }
            let m = message
            return m.contains("中断") || m.contains("无进展") || m.contains("首事件")
                || m.contains("首包") || m.contains("挂死") || m.contains("工具")
                || m.contains("超时") || m.contains("空占位") || m.contains("连接")
        case .decode(let m):
            return m.contains("中断") || m.contains("空回复") || m.contains("无进展")
        case .http(let code, let body):
            if code == 401 || code == 403 || code == 503 || code == 413 { return false }
            // 5xx 且非鉴权文案时允许重试一次
            if code >= 500 {
                return !body.contains("鉴权")
            }
            return false
        default:
            return false
        }
    }

    /// 重试前是否 drop live slot；empty_stub 额外清 resume id
    var shouldDropLiveSlotBeforeRetry: Bool {
        switch self {
        case .stream(let code, _):
            let c = (code ?? "").lowercased()
            return ["first_event_timeout", "tool_stall", "lock_timeout",
                    "client_progress_stall", "empty_stub", "hang", "connect_failed",
                    "idle_timeout", "max_timeout"].contains(c)
        case .decode(let m):
            return m.contains("无进展") || m.contains("中断") || m.contains("空回复")
        default:
            return false
        }
    }

    var shouldClearResumeIdBeforeRetry: Bool {
        if case .stream(let code, _) = self {
            return (code ?? "").lowercased() == "empty_stub"
        }
        return false
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
    /// 本机 Agent 登录账号（默认空 → 无默认弱口令；未配置时降级共享密钥或明确报错）
    private(set) var agentUser: String
    /// 本机 Agent 登录密码（默认空；只进内存，不落盘）
    private(set) var agentPassword: String
    /// 测试注入的共享密钥（非 nil 时覆盖 `CCC_AGENT_TOKEN`/`~/.ccc/agent-token` 读取）
    private var agentSharedSecret: String?
    /// 短请求（列表/看板）
    private let session: URLSession
    /// 对话 SSE（可多路；与 flow 分离，避免抢同一连接池）
    private let chatSession: URLSession
    /// 流程 SSE（全 App 1 条）
    private let flowSession: URLSession
    /// Hub 会话 token 生命周期（Bearer 收敛；内存缓存，服务端重启失效）
    private var hubToken = HubTokenState()
    /// in-flight token 获取去重（并发请求只打一次 /api/auth/token）
    private var tokenFetchTask: Task<String?, Never>?
    /// 7788 Agent 会话 token 生命周期（账号密码 → 会话 token）
    private var agentTokenState = AgentTokenState()
    /// in-flight agent-login 去重（并发 7788 请求只打一次登录）
    private var agentLoginTask: Task<AgentLoginResult, Never>?
    /// 最近一次 Agent 鉴权失败原因（最终 401 报错文案用）
    private var agentLastAuthFailure: AgentAuthFailure?

    init(
        baseURL: URL,
        user: String = "ccc",
        password: String = "ccc",
        /// 测试注入：自定义 URLProtocol（默认空 → 生产行为不变）
        urlProtocolClasses: [URLProtocol.Type] = [],
        /// 本机 Agent 登录账号（默认空 → 无默认弱口令）
        agentUser: String = "",
        /// 本机 Agent 登录密码（默认空）
        agentPassword: String = "",
        /// 测试注入：共享密钥覆盖（默认 nil → 生产读 `CCC_AGENT_TOKEN`/`~/.ccc/agent-token`）
        agentSharedSecret: String? = nil
    ) {
        self.baseURL = baseURL
        self.user = user
        self.password = password
        self.agentUser = agentUser
        self.agentPassword = agentPassword
        self.agentSharedSecret = agentSharedSecret
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = 45
        cfg.timeoutIntervalForResource = 120
        // Hub 短请求：禁止等系统「连通」——Wi‑Fi/路由抖时会拖死远超 timeout
        cfg.waitsForConnectivity = false
        // 短请求：列表/看板/用量；与 flow SSE 分 session，避免互相堵
        cfg.httpMaximumConnectionsPerHost = 4
        if !urlProtocolClasses.isEmpty {
            cfg.protocolClasses = urlProtocolClasses + (cfg.protocolClasses ?? [])
        }
        self.session = URLSession(configuration: cfg)

        let chatCfg = URLSessionConfiguration.default
        chatCfg.timeoutIntervalForRequest = 600
        chatCfg.timeoutIntervalForResource = 1800
        chatCfg.waitsForConnectivity = false
        // 本机 sidecar 可多路并行（对话面禁止 Hub chat）
        chatCfg.httpMaximumConnectionsPerHost = 4
        chatCfg.requestCachePolicy = .reloadIgnoringLocalCacheData
        if !urlProtocolClasses.isEmpty {
            chatCfg.protocolClasses = urlProtocolClasses + (chatCfg.protocolClasses ?? [])
        }
        self.chatSession = URLSession(configuration: chatCfg)

        let flowCfg = URLSessionConfiguration.default
        flowCfg.timeoutIntervalForRequest = 600
        flowCfg.timeoutIntervalForResource = 1800
        // Flow SSE 重连勿挂系统连通等待
        flowCfg.waitsForConnectivity = false
        flowCfg.httpMaximumConnectionsPerHost = 1
        flowCfg.requestCachePolicy = .reloadIgnoringLocalCacheData
        if !urlProtocolClasses.isEmpty {
            flowCfg.protocolClasses = urlProtocolClasses + (flowCfg.protocolClasses ?? [])
        }
        self.flowSession = URLSession(configuration: flowCfg)
    }

    func update(
        baseURL: URL,
        user: String,
        password: String,
        chatBaseURL: URL? = nil,
        localProjectPath: String? = nil,
        agentUser: String? = nil,
        agentPassword: String? = nil
    ) {
        let credChanged = baseURL != self.baseURL || user != self.user || password != self.password
        self.baseURL = baseURL
        self.user = user
        self.password = password
        if credChanged {
            // 换 Hub / 换账密 → 旧 token 作废，下个请求用新凭证换 token
            hubToken.invalidate()
        }
        let agentBaseChanged = chatBaseURL != self.chatBaseURL
        // 在赋值前比对凭证变化（换地址/账号/密码 → 旧会话 token 作废，下轮请求用新凭证重登）
        let agentUserChanged = (agentUser != nil) && (agentUser != self.agentUser)
        let agentPassChanged = (agentPassword != nil) && (agentPassword != self.agentPassword)
        self.chatBaseURL = chatBaseURL
        self.localProjectPath = localProjectPath
        if let agentUser { self.agentUser = agentUser }
        if let agentPassword { self.agentPassword = agentPassword }
        if agentBaseChanged || agentUserChanged || agentPassChanged {
            agentTokenState.invalidate()
        }
    }

    /// 仅刷新 Hub 地址/账密（顶栏用量轮询）；不碰 sidecar cwd
    func updateHubEndpoint(baseURL: URL, user: String, password: String) {
        let credChanged = baseURL != self.baseURL || user != self.user || password != self.password
        self.baseURL = baseURL
        self.user = user
        self.password = password
        if credChanged {
            hubToken.invalidate()
        }
    }

    var usesLocalAgent: Bool { chatBaseURL != nil }

    /// 本机 sidecar 共享密钥：`CCC_AGENT_TOKEN` 或 `~/.ccc/agent-token`（兼容窗口降级用）。
    /// 非 nil 即显式覆盖（含空串 = 禁用共享密钥；测试注入用），生产默认 nil 走环境/文件。
    private var agentToken: String {
        if let override = agentSharedSecret {
            return override
        }
        if let env = ProcessInfo.processInfo.environment["CCC_AGENT_TOKEN"]?
            .trimmingCharacters(in: .whitespacesAndNewlines), !env.isEmpty
        {
            return env
        }
        let url = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".ccc/agent-token")
        guard let raw = try? String(contentsOf: url, encoding: .utf8) else { return "" }
        return raw.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // MARK: - 7788 Agent 鉴权（账号密码 → 会话 token；401 重登一次有界）

    /// Agent 鉴权失败原因（最终 401 报错文案用）
    enum AgentAuthFailure {
        /// 未配置凭证 且 无共享密钥
        case notConfigured
        /// 已配置凭证但 agent-login 被拒（账号/密码错误；不降级掩盖配置错误）
        case loginFailed
    }

    /// agent-login 结果（区分「被拒」与「端点不可用」，决定是否降级共享密钥）
    private enum AgentLoginResult {
        case token(String)
        /// 服务端拒绝登录（401/403：账号或密码错误）
        case rejected
        /// 端点不存在 / 超时 / 传输失败（旧 sidecar 未实现登录 或 网络抖）→ 兼容窗口降级
        case unavailable
    }

    private func hasAgentCredentials() -> Bool {
        !agentUser.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !agentPassword.isEmpty
    }

    /// 决策本次 7788 请求用的 Agent 鉴权头。
    /// - 有效会话 token → Bearer
    /// - 凭证已配置 → `POST /api/auth/agent-login` 换 token；被拒 → `.loginFailed`（不降级）
    /// - 端点不可用（旧 sidecar）→ 降级共享密钥（兼容窗口）；无共享密钥 → `.loginFailed`
    /// - 凭证未配置 → 降级共享密钥；无共享密钥 → `.notConfigured`
    private func resolveAgentAuthHeader(forceReauth: Bool = false) async -> (header: String?, failure: AgentAuthFailure?) {
        if !forceReauth, agentTokenState.isValid(now: Date()), let token = agentTokenState.token {
            return (header: "Bearer \(token)", failure: nil)
        }
        if hasAgentCredentials() {
            switch await performAgentLogin() {
            case .token(let token):
                return (header: "Bearer \(token)", failure: nil)
            case .rejected:
                agentLastAuthFailure = .loginFailed
                return (header: nil, failure: .loginFailed)
            case .unavailable:
                // 兼容窗口：旧 sidecar 无 agent-login → 共享密钥；无密钥则明确报错
                let secret = agentToken
                if !secret.isEmpty {
                    return (header: "Bearer \(secret)", failure: nil)
                }
                agentLastAuthFailure = .loginFailed
                return (header: nil, failure: .loginFailed)
            }
        }
        // 未配置凭证：降级共享密钥（兼容窗口，不断链）；无共享密钥 → 明确报错
        let secret = agentToken
        if !secret.isEmpty {
            return (header: "Bearer \(secret)", failure: nil)
        }
        agentLastAuthFailure = .notConfigured
        return (header: nil, failure: .notConfigured)
    }

    /// POST /api/auth/agent-login（账号密码 → 会话 token）；in-flight 去重
    private func performAgentLogin() async -> AgentLoginResult {
        if let task = agentLoginTask {
            return await task.value
        }
        let task = Task { [weak self] in await self?.performAgentLoginInner() ?? .unavailable }
        agentLoginTask = task
        defer { agentLoginTask = nil }
        return await task.value
    }

    private func performAgentLoginInner() async -> AgentLoginResult {
        guard let base = chatBaseURL else { return .unavailable }
        guard let url = URL(string: "api/auth/agent-login", relativeTo: base) else {
            return .unavailable
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = [
            // 契约 key：user（report-K §四；非 username）
            "user": agentUser.trimmingCharacters(in: .whitespacesAndNewlines),
            "password": agentPassword,
        ]
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        req.timeoutInterval = 15
        do {
            let (data, resp) = try await session.data(for: req)
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            if (200..<300).contains(code) {
                guard let obj = try? JSONDecoder().decode(AgentLoginResponse.self, from: data) else {
                    return .unavailable
                }
                agentTokenState.store(
                    token: obj.token,
                    // expires_in = 相对秒（不是 ISO 时间戳）；无则 nil → 靠 401 重登兜底
                    expiresAt: obj.expires_in.map { Date().addingTimeInterval(TimeInterval($0)) }
                )
                return .token(obj.token)
            }
            if code == 401 || code == 403 { return .rejected }
            return .unavailable
        } catch {
            return .unavailable
        }
    }

    /// 401 → 清会话 token → 强制重登/降级 → 新 Bearer；失败 nil（调用方报错，不无限重试）
    private func freshAgentBearerHeader() async -> String? {
        agentTokenState.recordBearer401()
        let (header, _) = await resolveAgentAuthHeader(forceReauth: true)
        return header
    }

    /// 为请求注入 Agent 鉴权头（Bearer + 兼容 X-CCC-Agent-Token）
    private func setAgentAuth(_ req: inout URLRequest, _ header: String?) {
        guard let header, header.hasPrefix("Bearer ") else { return }
        req.setValue(header, forHTTPHeaderField: "Authorization")
        req.setValue(String(header.dropFirst(7)), forHTTPHeaderField: "X-CCC-Agent-Token")
    }

    /// 为 7788 请求注入 Agent 鉴权头（执行点调用；无可用头则不发，交由调用方处理 401）
    private func applyAgentAuth(_ req: inout URLRequest) async {
        let (header, _) = await resolveAgentAuthHeader()
        setAgentAuth(&req, header)
    }

    /// 最终 401 的清晰报错文案（区分未配置 / 登录被拒 / 通用失效）
    private func agentAuthErrorMessage(code: Int) -> String {
        switch agentLastAuthFailure {
        case .notConfigured:
            return "本机 Agent 未配置登录凭证（\(code)）。请在设置中填写「本机对话 Agent → 登录账号/密码」"
        case .loginFailed:
            return "本机 Agent 登录失败（\(code)）：账号或密码错误。请在设置中重新配置"
        case nil:
            return "本机 Agent 鉴权失败（\(code)）：会话 token 失效。请在设置中检查账号密码"
        }
    }

    /// 执行带 Agent 鉴权的 7788 短请求；401 → 重登一次 → 重试一次（有界）。
    /// 返回 (data, statusCode)；传输错误抛给调用方（fire-and-forget 路径 catch 即可）。
    private func agentData(for req: URLRequest) async throws -> (Data, Int) {
        var active = req
        await applyAgentAuth(&active)
        var (data, resp) = try await session.data(for: active)
        var code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if code == 401, let header = await freshAgentBearerHeader() {
            setAgentAuth(&active, header)
            (data, resp) = try await session.data(for: active)
            code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        }
        return (data, code)
    }

    /// 探测本机 sidecar `/health`；可选回填 capabilities
    func probeLocalAgent(base: URL) async -> Bool {
        let info = await fetchAgentHealth(base: base)
        return info?.ok == true
    }

    struct AgentHealthInfo: Sendable {
        var ok: Bool
        var model: String?
        var models: [String]
        var toolModes: [String]
        var compact: Bool
        var supportsAttachments: Bool
        var agentRuntime: String?
        var configDir: String?
        var loopCodeVersion: String?
    }

    func fetchAgentHealth(base: URL) async -> AgentHealthInfo? {
        guard var health = URL(string: "health", relativeTo: base) else { return nil }
        if health.absoluteString.hasSuffix("health") == false {
            health = base.appendingPathComponent("health")
        }
        var req = URLRequest(url: health)
        req.timeoutInterval = 1.5
        do {
            let (data, resp) = try await session.data(for: req)
            guard (resp as? HTTPURLResponse)?.statusCode == 200 else { return nil }
            guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                return AgentHealthInfo(
                    ok: true, model: nil, models: [], toolModes: [],
                    compact: false, supportsAttachments: false,
                    agentRuntime: nil, configDir: nil, loopCodeVersion: nil
                )
            }
            let caps = obj["capabilities"] as? [String: Any]
            return AgentHealthInfo(
                ok: (obj["ok"] as? Bool) == true,
                model: obj["model"] as? String,
                models: (obj["models"] as? [String]) ?? [],
                toolModes: (obj["tool_modes"] as? [String]) ?? [],
                compact: (obj["compact"] as? Bool) ?? (caps?["compact"] as? Bool) ?? false,
                supportsAttachments: (obj["supports_attachments"] as? Bool)
                    ?? (caps?["attachments"] as? Bool) ?? false,
                agentRuntime: obj["agent_runtime"] as? String,
                configDir: obj["config_dir"] as? String,
                loopCodeVersion: obj["loop_code_version"] as? String
            )
        } catch {
            return nil
        }
    }

    /// Sidecar keep-warm 结果：仅 `slotConnected` 才算真暖（cli-only warm 不算）
    struct WarmResult: Sendable {
        let httpOk: Bool
        let slotConnected: Bool
    }

    /// Sidecar keep-warm：`POST /warm`（带 project_path 时真正预连 SDK slot）
    @discardableResult
    func warmLocalAgent(
        base: URL? = nil,
        projectPath: String? = nil,
        sessionId: String? = nil,
        toolMode: String = "discuss",
        claudeSessionId: String? = nil
    ) async -> WarmResult {
        let root = base ?? chatBaseURL
        guard let root else { return WarmResult(httpOk: false, slotConnected: false) }
        guard let url = URL(string: "warm", relativeTo: root) else {
            return WarmResult(httpOk: false, slotConnected: false)
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        var body: [String: Any] = [:]
        if let projectPath, !projectPath.isEmpty {
            body["project_path"] = projectPath
        }
        if let sessionId, !sessionId.isEmpty {
            body["session_id"] = sessionId
        }
        let mode = toolMode.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        body["tool_mode"] = (mode == "engineer") ? "engineer" : "discuss"
        body["model"] = "flash"
        if let claudeSessionId {
            let sid = claudeSessionId.trimmingCharacters(in: .whitespacesAndNewlines)
            if !sid.isEmpty {
                body["claude_session_id"] = sid
            }
        }
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        // 真预连可能 15–40s；失败不阻塞发消息
        req.timeoutInterval = projectPath == nil ? 8 : 45
        do {
            let (data, code) = try await agentData(for: req)
            guard code == 200 else {
                return WarmResult(httpOk: false, slotConnected: false)
            }
            guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                return WarmResult(httpOk: true, slotConnected: false)
            }
            let httpOk = (obj["ok"] as? Bool) == true
            var slotConnected = false
            if let slot = obj["slot"] as? [String: Any] {
                slotConnected = (slot["connected"] as? Bool) == true
                    || ((slot["ok"] as? Bool) == true && (slot["connected"] as? Bool) != false)
            }
            // 无 project_path 时 sidecar 只查 CLI，slot=null → 不算真暖
            if projectPath == nil || projectPath?.isEmpty == true {
                slotConnected = false
            }
            return WarmResult(httpOk: httpOk, slotConnected: slotConnected)
        } catch {
            return WarmResult(httpOk: false, slotConnected: false)
        }
    }

    /// 通知 sidecar 丢弃 ClaudeSDKClient live slot。
    /// - Parameter reason: 写入 sidecar 日志（cancel / reset / heal）
    func dropSidecarSession(
        projectPath: String,
        sessionId: String,
        reason: String = "user-reset"
    ) async {
        guard let root = chatBaseURL else { return }
        guard let url = URL(string: "api/session/drop", relativeTo: root) else { return }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = [
            "project_path": projectPath,
            "session_id": sessionId,
            "reason": reason,
        ]
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        req.timeoutInterval = 5
        _ = try? await agentData(for: req)
    }

    /// 通知 sidecar 压缩 agent session：drop slot + 新 slot 注入摘要
    func compactSidecarSession(projectPath: String, sessionId: String, summary: String) async {
        guard let root = chatBaseURL else { return }
        guard let url = URL(string: "api/session/compact", relativeTo: root) else { return }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = [
            "project_path": projectPath,
            "session_id": sessionId,
            "summary": summary,
        ]
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)
        req.timeoutInterval = 30
        _ = try? await agentData(for: req)
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
        // 认证由执行点注入（Bearer 收敛）：见 injectHubAuth / resolveHubAuthHeader
        req.httpBody = body
        return req
    }

    // MARK: - Hub 认证（Bearer 收敛；Basic 仅在换取 token / 降级回退）

    /// 唯一 Basic 头构造点（白名单：token 换取 + 降级回退）
    private func basicAuthHeader() -> String {
        let token = Data("\(user):\(password)".utf8).base64EncodedString()
        return "Basic \(token)"
    }

    /// 供 AppModel 等外部构造带认证的请求头（探活等轻量路径）
    func hubAuthorizationHeader() async -> String? {
        await resolveHubAuthHeader()
    }

    /// 为请求注入 Hub 认证头（actor 内部执行点调用）
    func injectHubAuth(_ req: inout URLRequest) async {
        guard let header = await resolveHubAuthHeader() else { return }
        req.setValue(header, forHTTPHeaderField: "Authorization")
    }

    /// 决策本次用哪个凭证：有效 Bearer → 近 TTL 刷新 → Basic 换 token → 失败降级 Basic
    private func resolveHubAuthHeader() async -> String? {
        if hubToken.isValid(now: Date()) {
            guard let token = hubToken.token else { return basicAuthHeader() }
            return "Bearer \(token)"
        }
        if hubToken.isDegrading(now: Date()) {
            return basicAuthHeader()
        }
        if let token = await fetchAndStoreToken() {
            return "Bearer \(token)"
        }
        // 获取失败：进降级窗口，本次回退 Basic（服务端 CCC_AUTH_REQUIRE_BEARER 未开时仍放行 → 不断链）
        hubToken.recordFetchFailure(now: Date())
        return basicAuthHeader()
    }

    /// POST /api/auth/token（Basic 换取）；in-flight 去重
    private func fetchAndStoreToken() async -> String? {
        if let task = tokenFetchTask {
            return await task.value
        }
        let task = Task { [weak self] in await self?.performTokenFetch() }
        tokenFetchTask = task
        defer { tokenFetchTask = nil }
        return await task.value
    }

    private func performTokenFetch() async -> String? {
        guard let url = URL(string: "api/auth/token", relativeTo: baseURL) else { return nil }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        // Basic 只在此换取 token 时出现（B2 契约）
        req.setValue(basicAuthHeader(), forHTTPHeaderField: "Authorization")
        req.timeoutInterval = 15
        do {
            let (data, resp) = try await session.data(for: req)
            guard (resp as? HTTPURLResponse)?.statusCode == 200 else { return nil }
            guard let obj = try? JSONDecoder().decode(HubTokenResponse.self, from: data) else {
                return nil
            }
            hubToken.store(token: obj.token, role: obj.role, expiresAt: HubTokenStateSupport.parseExpiry(obj.expires_at))
            return obj.token
        } catch {
            return nil
        }
    }

    /// 401 → 清 token → 重取 Bearer；成功返回新 Bearer 头，无则 nil（调用方报错，不无限重试）
    private func freshBearerHeader() async -> String? {
        hubToken.recordBearer401(now: Date())
        guard let header = await resolveHubAuthHeader(), header.hasPrefix("Bearer ") else {
            return nil
        }
        return header
    }

    private func send<T: Decodable>(
        _ req: URLRequest,
        as type: T.Type,
        maxAttempts: Int = 3
    ) async throws -> T {
        let attempts = max(1, min(maxAttempts, 3))
        var req = req
        // Hub 认证注入：Bearer 收敛（含 token 获取/刷新/降级）
        await injectHubAuth(&req)
        return try await HubRequestGate.shared.withPermit {
            var activeReq = req
            var lastError: Error?
            var authRetried = false
            for attempt in 1...attempts {
                do {
                    let (data, resp) = try await self.session.data(for: activeReq)
                    let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
                    if code == 401, !authRetried {
                        // token 过期 / 吊销 / 服务端重启 → 重取一次再试（有界）
                        authRetried = true
                        if let header = await self.freshBearerHeader() {
                            activeReq.setValue(header, forHTTPHeaderField: "Authorization")
                            continue
                        }
                    }
                    if !(200..<300).contains(code) {
                        if let err = try? JSONDecoder().decode(APIErrorBody.self, from: data),
                           let gates = err.errors, !gates.isEmpty {
                            throw APIError.gate(gates)
                        }
                        let text = String(data: data, encoding: .utf8) ?? ""
                        // 5xx / 0 可重试；4xx 不重试
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
    }

    /// POST/PUT 不解 JSON body，只回状态码（用于 move/hide/reopen 等写动作）
    func sendVoid(_ req: URLRequest) async throws -> (Data, Int) {
        var req = req
        await injectHubAuth(&req)
        return try await HubRequestGate.shared.withPermit {
            var activeReq = req
            var authRetried = false
            let (data, resp) = try await self.session.data(for: activeReq)
            var code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            if code == 401, !authRetried {
                authRetried = true
                if let header = await self.freshBearerHeader() {
                    activeReq.setValue(header, forHTTPHeaderField: "Authorization")
                    let (d2, r2) = try await self.session.data(for: activeReq)
                    return (d2, (r2 as? HTTPURLResponse)?.statusCode ?? 0)
                }
            }
            return (data, code)
        }
    }

    /// 通用 GET（返回 Data）
    func genericGET(_ path: String) async throws -> Data {
        let (data, _) = try await sendVoid(authedRequest(path))
        return data
    }

    /// 通用 POST（返回 Data + statusCode）
    func genericPOST(_ path: String, body: Data? = nil) async throws -> (Data, Int) {
        try await sendVoid(authedRequest(path, method: "POST", body: body))
    }

    /// 通用 DELETE（返回 statusCode）
    @discardableResult
    func genericDELETE(_ path: String) async throws -> Int {
        let (_, code) = try await sendVoid(authedRequest(path, method: "DELETE"))
        return code
    }

    /// 通用 PATCH（返回 Data + statusCode）
    func genericPATCH(_ path: String, body: Data? = nil) async throws -> (Data, Int) {
        try await sendVoid(authedRequest(path, method: "PATCH", body: body))
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
        let bound_hint: String?
        let conversation_view: String?
    }

    struct EpicsFetchResult {
        let epics: [FlowEpicRef]
        let boundHint: String?
    }

    func fetchProjects() async throws -> ProjectsResp {
        var req = try authedRequest("api/desktop/projects")
        // 冷启动/再开：短超时 + 少重试，避免 Hub 抖时「同步中」挂很久
        req.timeoutInterval = 10
        return try await send(req, as: ProjectsResp.self, maxAttempts: 2)
    }

    struct HubHealthResp: Decodable {
        let ok: Bool?
        let ts: String?
    }

    /// 轻量探活：优先 `/api/desktop/health`；若 Hub 旧版 404，回退 `/api/desktop/version`（防部署偏斜误判离线）
    @discardableResult
    func probeHubHealth() async throws -> HubHealthResp {
        var req = try authedRequest("api/desktop/health")
        req.timeoutInterval = 3
        do {
            return try await send(req, as: HubHealthResp.self, maxAttempts: 1)
        } catch {
            let code = (error as? APIError)?.httpStatus ?? -1
            // 部署偏斜：新 Desktop + 旧 Hub 无 health → 404；version 仍可达则视为在线
            if code == 404 {
                struct VersionResp: Decodable { let ok: Bool?; let version: String?; let commit: String? }
                var vreq = try authedRequest("api/desktop/version")
                vreq.timeoutInterval = 3
                let v = try await send(vreq, as: VersionResp.self, maxAttempts: 1)
                if v.ok ?? true {
                    return HubHealthResp(ok: true, ts: v.version ?? v.commit)
                }
            }
            throw error
        }
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
        try await fetchRecentEpicsDetailed(projectId: projectId, threadId: threadId).epics
    }

    func fetchRecentEpicsDetailed(projectId: String, threadId: String? = nil) async throws -> EpicsFetchResult {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? projectId
        var path = "api/desktop/flow/epics?project_id=\(enc)"
        if let threadId, !threadId.isEmpty {
            let t = threadId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? threadId
            path += "&thread_id=\(t)"
        }
        var req = try authedRequest(path)
        req.timeoutInterval = 10
        let resp = try await send(req, as: EpicsResp.self, maxAttempts: 2)
        return EpicsFetchResult(epics: resp.epics, boundHint: resp.bound_hint)
    }

    /// 流式聊天：仅本机 Agent Sidecar（对话面基线；禁止 Hub /api/chat 回退）
    /// onEvent 由调用方切 MainActor（避免 actor↔MainActor 死锁导致 tool 事件攒到结束）
    struct ChatStreamResult: Sendable {
        let turnId: String
        let partial: Bool
        let durationMs: Int?
        let eventCounts: [String: Int]
    }

    func streamChat(
        projectId: String,
        sessionId: String,
        turnId: String,
        messages: [ChatMessage],
        promptMode: String = "full",
        toolMode: String = "discuss",
        /// 显式路径优先于 client.localProjectPath（多窗并行时禁止抢全局 cwd）
        projectPath: String? = nil,
        /// loop-code resume：同 thread 持续对话
        claudeSessionId: String? = nil,
        model: String? = nil,
        onEvent: @escaping @Sendable (ChatStreamEvent) async -> Void
    ) async throws -> ChatStreamResult {
        guard let chatBase = chatBaseURL else {
            throw APIError.decode("本机 Agent 未就绪（对话只走本机 sidecar，不回退 Hub）")
        }
        struct Body: Encodable {
            let project: String
            let session_id: String
            let turn_id: String
            let messages: [ChatMessage]
            let prompt: String?
            let mode: String
            let project_path: String?
            let prompt_mode: String
            let tool_mode: String
            let claude_session_id: String?
            let model: String?
        }
        // prompt: 只发最后一条 user；有 prompt 时 messages 发空数组，减首包开销
        let promptHint = messages.last(where: { $0.role == "user" })?.content
        let outboundMessages: [ChatMessage] = (promptHint?.isEmpty == false) ? [] : messages
        let path = projectPath ?? localProjectPath
        let resume = claudeSessionId?.trimmingCharacters(in: .whitespacesAndNewlines)
        let modelResolved = StreamSessionController.resolveModel(model ?? "flash")
        let data = try JSONEncoder().encode(
            Body(
                project: projectId,
                session_id: sessionId,
                turn_id: turnId,
                messages: outboundMessages,
                prompt: promptHint,
                mode: "chat",
                project_path: path,
                prompt_mode: promptMode,
                tool_mode: toolMode,
                claude_session_id: (resume?.isEmpty == false) ? resume : nil,
                model: modelResolved
            )
        )
        guard let url = URL(string: "api/chat", relativeTo: chatBase) else {
            throw APIError.badURL
        }
        // 401 有界重登一次：首轮带当前 token；401 → 清 token → 重登 → 重试一次
        var lastFailure: AgentAuthFailure?
        func startStream(forceReauth: Bool) async throws -> (URLSession.AsyncBytes, URLResponse) {
            var req = URLRequest(url: url)
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.setValue("text/event-stream, application/json", forHTTPHeaderField: "Accept")
            req.httpBody = data
            let (header, failure) = await resolveAgentAuthHeader(forceReauth: forceReauth)
            if let failure { lastFailure = failure }
            setAgentAuth(&req, header)
            return try await chatSession.bytes(for: req)
        }
        var (bytes, resp) = try await startStream(forceReauth: false)
        var code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if code == 401 {
            agentTokenState.recordBearer401()
            (bytes, resp) = try await startStream(forceReauth: true)
            code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        }
        if !(200..<300).contains(code) {
            var errBody = ""
            for try await line in bytes.lines { errBody += line; if errBody.count > 400 { break } }
            if code == 401 {
                throw APIError.http(code, agentAuthErrorMessage(code: code))
            }
            if code == 503 {
                throw APIError.http(
                    code,
                    "本机 Agent 未就绪（503）。请确认 sidecar 已启动，并重装 Desktop：bash desktop/scripts/package-baseline.sh && cp -R desktop/.build/CCCDesktop.app /Applications/"
                )
            }
            throw APIError.http(code, errBody)
        }

        var gotDelta = false
        var gotTool = false
        var gotDone = false
        var donePartial = false
        var doneTurnId = turnId
        var doneMetrics: ChatTurnMetrics?
        var streamErrCode: String?
        var streamErrMsg: String?
        // 可靠性：有心跳 ≠ 有进展。ping 只证明连接活着，不得重置进展时钟。
        // 与 sidecar CHAT_FIRST_EVENT_TIMEOUT（默认 120s）对齐并略宽，避免客户端先误杀。
        let progressLimit: TimeInterval = 150
        var lastProgressAt = Date()
        // Phase 1.6: 按行切片但用 cursor 一次性丢前缀，避免 removeSubrange 每行 O(n) 共 O(n²)
        let nlByte = Data([UInt8(ascii: "\n")])
        var buffer = Data()
        let maxBuffer = 1_048_576 // 1MB：防异常超大单行撑爆内存
        for try await chunk in bytes {
            try Task.checkCancellation()
            if Date().timeIntervalSince(lastProgressAt) > progressLimit {
                throw APIError.stream(
                    code: "client_progress_stall",
                    message: "本机 Agent 无进展（\(Int(progressLimit))s 仅心跳或静默）。可能工具挂死，已中止；请重试"
                )
            }
            buffer.append(chunk)
            if buffer.count > maxBuffer {
                throw APIError.http(413, "SSE line buffer exceeded \(maxBuffer) bytes")
            }
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
                if type == "ping" {
                    // 不刷新 lastProgressAt
                    await onEvent(.ping(turnId: obj["turn_id"] as? String))
                    continue
                }
                if type == "error" {
                    // 记下 code，继续读随后的 done（契约：error 后仍有 done）
                    let msg = (obj["content"] as? String) ?? (obj["message"] as? String) ?? "chat error"
                    let code = (obj["code"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines)
                    streamErrMsg = msg
                    streamErrCode = (code?.isEmpty == false) ? code : streamErrCode
                    lastProgressAt = Date()
                    continue
                }
                if type == "tool_use" || type == "tool-use" || type == "tooluse" {
                    lastProgressAt = Date()
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
                    await onEvent(.toolUse(
                        name: name,
                        input: inputStr,
                        turnId: obj["turn_id"] as? String
                    ))
                    continue
                }
                if type == "tool_result" || type == "tool-result" {
                    lastProgressAt = Date()
                    let isErr = (obj["is_error"] as? Bool) == true
                        || (obj["error"] as? Bool) == true
                    await onEvent(.toolResult(
                        ok: !isErr,
                        turnId: obj["turn_id"] as? String
                    ))
                    continue
                }
                if type == "status" {
                    lastProgressAt = Date()
                    let note = (obj["content"] as? String)
                        ?? (obj["text"] as? String)
                        ?? ""
                    if !note.isEmpty {
                        await onEvent(.status(
                            note,
                            turnId: obj["turn_id"] as? String
                        ))
                    }
                    continue
                }
                if type == "cost" {
                    lastProgressAt = Date()
                    await onEvent(.cost(
                        tokens: obj["tokens"] as? Int,
                        usd: obj["usd"] as? Double,
                        turnId: obj["turn_id"] as? String
                    ))
                    continue
                }
                if type == "done" {
                    lastProgressAt = Date()
                    gotDone = true
                    donePartial = (obj["partial"] as? Bool) ?? false
                    let sid = (obj["claude_session_id"] as? String)?
                        .trimmingCharacters(in: .whitespacesAndNewlines)
                    let rawMetrics = obj["metrics"] as? [String: Any]
                    let rawEvents = rawMetrics?["events"] as? [String: Any]
                    var eventCounts: [String: Int] = [:]
                    for (key, value) in rawEvents ?? [:] {
                        if let count = value as? Int {
                            eventCounts[key] = count
                        } else if let count = value as? NSNumber {
                            eventCounts[key] = count.intValue
                        }
                    }
                    let metrics = rawMetrics.map { raw in
                        ChatTurnMetrics(
                            durationMs: raw["duration_ms"] as? Int,
                            eventCounts: eventCounts
                        )
                    }
                    doneTurnId = (obj["turn_id"] as? String) ?? turnId
                    doneMetrics = metrics
                    await onEvent(.done(
                        partial: donePartial,
                        claudeSessionId: (sid?.isEmpty == false) ? sid : nil,
                        turnId: obj["turn_id"] as? String,
                        metrics: metrics
                    ))
                    continue
                }
                let textChunk: String? = {
                    if let c = obj["content"] as? String, !c.isEmpty { return c }
                    if let c = obj["delta"] as? String, !c.isEmpty { return c }
                    if let c = obj["text"] as? String, !c.isEmpty { return c }
                    return nil
                }()
                if let textChunk, type == "delta" || type == "text" || type == nil || type == "content" {
                    lastProgressAt = Date()
                    gotDelta = true
                    await onEvent(.delta(
                        textChunk,
                        turnId: obj["turn_id"] as? String
                    ))
                }
            }
            // Phase 1.6: 一次性丢掉已处理前缀，保留未结束的尾巴给下一个 chunk
            if cursor > buffer.startIndex {
                buffer = buffer.subdata(in: cursor..<buffer.endIndex)
            }
        }
        if let errMsg = streamErrMsg {
            throw APIError.stream(code: streamErrCode, message: errMsg)
        }
        if !gotDelta && !gotTool {
            throw APIError.stream(code: "empty_reply", message: "空回复（SSE 未解析到内容）")
        }
        if !gotDone || donePartial {
            throw APIError.stream(
                code: donePartial ? "partial_done" : "incomplete",
                message: "回复中断（连接或生成未完整结束）"
            )
        }
        return ChatStreamResult(
            turnId: doneTurnId,
            partial: donePartial,
            durationMs: doneMetrics?.durationMs,
            eventCounts: doneMetrics?.eventCounts ?? [:]
        )
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

    /// 轻推本机 sidecar 冲刷 transfer-outbox（唯一 Hub POST 方）
    @discardableResult
    func nudgeOutboxFlush() async throws -> [String: Any] {
        guard let base = chatBaseURL else { throw APIError.badURL }
        let url = base.appendingPathComponent("api/outbox/flush")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.timeoutInterval = 30
        let (data, code) = try await agentData(for: req)
        guard (200..<300).contains(code) else {
            if code == 401 {
                throw APIError.http(code, agentAuthErrorMessage(code: code))
            }
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIError.http(code, body)
        }
        if data.isEmpty { return [:] }
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    func transfer(_ req: TransferRequest) async throws -> TransferResponse {
        let data = try JSONEncoder().encode(req)
        var urlReq = try authedRequest("api/desktop/transfer", method: "POST", body: data)
        // Hub 抖动时勿用默认 45s×3 把 UI 卡死在「投递中」
        urlReq.timeoutInterval = 25
        await injectHubAuth(&urlReq)
        let maxAttempts = 2
        return try await HubRequestGate.shared.withPermit {
            var activeReq = urlReq
            var attempt = 1
            var authRetried = false
            while true {
                do {
                    let (respData, resp) = try await self.session.data(for: activeReq)
                    let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
                    if code == 401, !authRetried {
                        // token 过期/吊销 → 重取一次再试（有界）
                        authRetried = true
                        if let header = await self.freshBearerHeader() {
                            activeReq.setValue(header, forHTTPHeaderField: "Authorization")
                            continue
                        }
                    }
                    if respData.isEmpty {
                        throw APIError.decode("empty transfer body")
                    }
                    let decoded: TransferResponse
                    do {
                        decoded = try JSONDecoder().decode(TransferResponse.self, from: respData)
                    } catch {
                        throw APIError.decode("transfer decode: \(error.localizedDescription)")
                    }
                    if code >= 500 {
                        throw APIError.http(code, decoded.error ?? "transfer server error")
                    }
                    if !(200..<300).contains(code) || decoded.ok == false {
                        if let errs = decoded.errors, !errs.isEmpty {
                            throw APIError.gate(errs)
                        }
                        throw APIError.http(code, decoded.error ?? "transfer failed")
                    }
                    let eid = (decoded.epic_id ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                    if eid.isEmpty {
                        throw APIError.emptyEpicId
                    }
                    return decoded
                } catch let err as APIError {
                    let retryable: Bool = {
                        switch err {
                        case .emptyEpicId, .decode:
                            return true
                        case .http(let code, _):
                            return code >= 500 || code == 0
                        case .gate:
                            return false
                        default:
                            return false
                        }
                    }()
                    if !retryable || attempt >= maxAttempts {
                        throw err
                    }
                    let ns = UInt64(150_000_000 * attempt) // 150ms, 300ms
                    try? await Task.sleep(nanoseconds: ns)
                    attempt += 1
                } catch {
                    // URLSession / empty / transport — retry
                    if attempt >= maxAttempts { throw error }
                    let ns = UInt64(150_000_000 * attempt)
                    try? await Task.sleep(nanoseconds: ns)
                    attempt += 1
                }
            }
        }
    }

    func fetchBoard(workspace: String, includeHidden: Bool = false) async throws -> BoardSnapshot {
        let enc = workspace.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? workspace
        var path = "api/board?workspace=\(enc)"
        if includeHidden {
            path += "&include_hidden=1"
        }
        var req = try authedRequest(path)
        // 看板读：短超时 + 少重试，避免 Hub 抖动时整页卡死数分钟
        req.timeoutInterval = 12
        return try await send(req, as: BoardSnapshot.self, maxAttempts: 2)
    }

    func fetchBoardSummaries(workspaces: [String]) async throws -> BoardSummariesResp {
        let joined = workspaces.joined(separator: ",")
        let enc = joined.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? joined
        var req = try authedRequest("api/board/summaries?workspaces=\(enc)")
        req.timeoutInterval = 12
        return try await send(req, as: BoardSummariesResp.self, maxAttempts: 2)
    }

    func fetchTaskDetail(taskId: String, workspace: String) async throws -> BoardTaskDetail {
        let t = taskId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? taskId
        let w = workspace.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? workspace
        return try await send(try authedRequest("api/tasks/\(t)?workspace=\(w)"), as: BoardTaskDetail.self)
    }

    func moveTask(taskId: String, to: String, workspace: String) async throws {
        let body = try JSONSerialization.data(withJSONObject: ["id": taskId, "to": to, "workspace": workspace])
        let req = try authedRequest("api/tasks/move", method: "POST", body: body)
        let (_, code) = try await sendVoid(req)
        if !(200..<300).contains(code) {
            throw APIError.http(code, "move failed")
        }
    }

    func hideCompletedEpics(workspace: String) async throws {
        let body = try JSONSerialization.data(withJSONObject: ["workspace": workspace])
        let req = try authedRequest("api/tasks/hide-completed-epics", method: "POST", body: body)
        let (_, code) = try await sendVoid(req)
        if !(200..<300).contains(code) {
            throw APIError.http(code, "hide failed")
        }
    }

    func reopenTask(taskId: String, to: String, workspace: String) async throws {
        let body = try JSONSerialization.data(withJSONObject: ["id": taskId, "to": to, "workspace": workspace])
        let req = try authedRequest("api/tasks/reopen", method: "POST", body: body)
        let (_, code) = try await sendVoid(req)
        if !(200..<300).contains(code) {
            throw APIError.http(code, "reopen failed")
        }
    }

    func fetchOpsOverview() async throws -> OpsOverview {
        try await send(try authedRequest("api/ops/overview"), as: OpsOverview.self)
    }

    func fetchOpsRisks() async throws -> OpsRisksResp {
        try await send(try authedRequest("api/ops/risks"), as: OpsRisksResp.self)
    }

    func fetchOpsSummary() async throws -> OpsSummary {
        try await send(try authedRequest("api/ops/summary"), as: OpsSummary.self)
    }

    func fetchOpsUpstreamDaily() async throws -> OpsUpstreamDailyResp {
        try await send(try authedRequest("api/ops/upstream-daily"), as: OpsUpstreamDailyResp.self)
    }

    func fetchInboxProposals(includeAdopted: Bool = false) async throws -> InboxProposalsResp {
        let q = includeAdopted ? "?include_adopted=1" : ""
        return try await send(try authedRequest("api/desktop/proposals\(q)"), as: InboxProposalsResp.self)
    }

    func adoptInboxProposal(id: String) async throws -> TransferResponse {
        let enc = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        return try await send(
            try authedRequest("api/desktop/proposals/\(enc)/adopt", method: "POST"),
            as: TransferResponse.self
        )
    }

    func runDailyReview(workspace: String) async throws {
        // Dry-run all engine-eligible apps (report-only; apply via schedule / Hub)
        let body = try JSONSerialization.data(withJSONObject: [
            "all_apps": true,
            "apply": false,
            "workspace": workspace,
        ])
        let req = try authedRequest("api/ops/daily-review/run", method: "POST", body: body)
        let (_, code) = try await sendVoid(req)
        if !(200..<300).contains(code) {
            throw APIError.http(code, "daily-review run failed")
        }
    }

    func adoptSuggestion(workspace: String, title: String, description: String, tags: [String]) async throws {
        let body = try JSONSerialization.data(withJSONObject: [
            "workspace": workspace,
            "title": title,
            "description": description,
            "tags": tags,
        ])
        let req = try authedRequest("api/ops/adopt", method: "POST", body: body)
        let (_, code) = try await sendVoid(req)
        if !(200..<300).contains(code) {
            throw APIError.http(code, "adopt failed")
        }
    }

    func fetchProjectBaseline(projectId: String) async throws -> ProjectBaselineResp {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? projectId
        var req = try authedRequest("api/projects/\(enc)/baseline")
        // Hub LAN 偶发抖动：短超时 + 少重试，避免 45s×3 静默挂死
        req.timeoutInterval = 12
        return try await send(req, as: ProjectBaselineResp.self, maxAttempts: 2)
    }

    func flowSnapshot(projectId: String, epicId: String? = nil) async throws -> FlowSnapshot {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? projectId
        var path = "api/desktop/flow/snapshot?project_id=\(enc)"
        if let epicId, !epicId.isEmpty {
            let e = epicId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? epicId
            path += "&epic_id=\(e)"
        }
        var req = try authedRequest(path)
        req.timeoutInterval = 10
        return try await send(req, as: FlowSnapshot.self, maxAttempts: 2)
    }

    /// LPSN · T3: load L1 decided goals
    func fetchMindDecided(projectId: String) async throws -> MindDecidedResp {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? projectId
        var req = try authedRequest("api/desktop/mind/\(enc)/decided")
        req.timeoutInterval = 8
        return try await send(req, as: MindDecidedResp.self, maxAttempts: 2)
    }

    /// LPSN · T3: human mark goal stable / abandoned / probed
    func markMindGoalStatus(projectId: String, goalId: String, status: String) async throws -> MindGoalStatusResp {
        let penc = projectId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? projectId
        let genc = goalId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? goalId
        let body = try JSONSerialization.data(withJSONObject: [
            "status": status,
            "updated_by": "human",
        ])
        var req = try authedRequest(
            "api/desktop/mind/\(penc)/goals/\(genc)/status",
            method: "POST",
            body: body
        )
        req.timeoutInterval = 10
        return try await send(req, as: MindGoalStatusResp.self, maxAttempts: 2)
    }

    /// v0.64: 转意图卡 → 写 L1 planned（不写 backlog）
    @discardableResult
    func upsertIntentCards(projectId: String, cards: [[String: Any]]) async throws -> MindDecidedResp {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? projectId
        let body = try JSONSerialization.data(withJSONObject: [
            "cards": cards,
            "updated_by": "desktop-agent",
        ])
        var req = try authedRequest(
            "api/desktop/mind/\(enc)/intent-cards",
            method: "POST",
            body: body
        )
        req.timeoutInterval = 12
        return try await send(req, as: MindDecidedResp.self, maxAttempts: 2)
    }

    /// 清理僵尸 planned 意图卡（→ abandoned）
    @discardableResult
    func abandonOrphanIntentCards(
        projectId: String,
        goalIds: [String]? = nil,
        allPlanned: Bool = false
    ) async throws -> MindDecidedResp {
        let enc = projectId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? projectId
        var payload: [String: Any] = ["updated_by": "desktop-orphan-clean"]
        if let goalIds, !goalIds.isEmpty {
            payload["goal_ids"] = goalIds
        }
        if allPlanned {
            payload["all_planned"] = true
        }
        let body = try JSONSerialization.data(withJSONObject: payload)
        var req = try authedRequest(
            "api/desktop/mind/\(enc)/intent-cards/abandon-orphans",
            method: "POST",
            body: body
        )
        req.timeoutInterval = 12
        return try await send(req, as: MindDecidedResp.self, maxAttempts: 2)
    }

    /// Dry-run transfer_gate（不写 backlog）
    func validateTransfer(_ payload: [String: Any]) async throws -> TransferValidateResp {
        let body = try JSONSerialization.data(withJSONObject: payload)
        var req = try authedRequest(
            "api/desktop/transfer/validate",
            method: "POST",
            body: body
        )
        req.timeoutInterval = 12
        return try await send(req, as: TransferValidateResp.self, maxAttempts: 2)
    }

    /// 右栏 L1 planned → gate 绿则进代办 + wake Engine（防意图卡停尸）
    func promotePlannedIntentCards(
        projectId: String,
        threadId: String? = nil,
        goalIds: [String]? = nil
    ) async throws -> PromotePlannedResp {
        var payload: [String: Any] = ["project_id": projectId]
        if let threadId, !threadId.isEmpty {
            payload["thread_id"] = threadId
        }
        if let goalIds, !goalIds.isEmpty {
            payload["goal_ids"] = goalIds
        }
        let body = try JSONSerialization.data(withJSONObject: payload)
        var req = try authedRequest(
            "api/desktop/transfer/promote-planned",
            method: "POST",
            body: body
        )
        req.timeoutInterval = 45
        return try await send(req, as: PromotePlannedResp.self, maxAttempts: 2)
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
        var req = try authedRequest(path)
        // Flow SSE 连 Hub：注入 Bearer（含 token 获取/刷新）
        await injectHubAuth(&req)
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
