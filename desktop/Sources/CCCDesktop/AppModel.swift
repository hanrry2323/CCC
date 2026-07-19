import AppKit
import Foundation
import SwiftUI

// MARK: - ChatState：隔离流式 delta 通知到消息列表区
// 消息列表用 @ObservedObject 订阅本对象；侧栏/右栏只看 AppModel
@MainActor
final class ChatState: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var draft: String = ""
    /// 流式局部状态文案（连接中/生成中）；避免每 token 刷 AppModel.statusText
    @Published var streamStatus: String = ""

    /// 就地改 struct 字段时强制触发 @Published（下标 mutate 不一定发 willSet）
    func replaceMessage(id: UUID, _ update: (inout ChatMessage) -> Void) {
        guard let idx = messages.firstIndex(where: { $0.id == id }) else { return }
        var copy = messages
        update(&copy[idx])
        messages = copy
    }
}

@MainActor
final class AppModel: ObservableObject {
    /// 现网默认：M1 Desktop → Mac2017 Hub（可用设置 / CCC_SERVER 覆盖）
    @AppStorage("ccc.server") var serverURLString: String = "http://192.168.3.116:7777"
    @AppStorage("ccc.user") var authUser: String = "ccc"
    @AppStorage("ccc.pass") var authPass: String = "ccc"
    @AppStorage("ccc.selectedProject") var persistedProjectId: String = ""
    /// 本机 Agent Sidecar（loop-code 热路径）；空则只用 Hub
    @AppStorage("ccc.agent") var agentURLString: String = "http://127.0.0.1:7788"
    /// 全局本机工作区 fallback（sidecar cwd）
    @AppStorage("ccc.localWorkspace") var localWorkspacePath: String = ""
    /// JSON: projectId → 本机绝对路径
    @AppStorage("ccc.localWorkspaceMap") var localWorkspaceMapJSON: String = "{}"
    /// CCC 仓根（拉起 sidecar）；空则自动探测
    @AppStorage("ccc.home") var cccHomePath: String = ""

    @Published var projects: [DesktopProject] = []
    @Published var threads: [DesktopThread] = []
    @Published var selectedProjectId: String?
    @Published var selectedThreadId: String?
    /// 对话状态（messages + draft），独立 ObservableObject 隔离 delta 通知
    @Published var chat = ChatState()
    @Published var statusText: String = "未连接"
    /// "local" = 本机 sidecar 可聊；"none" = 本机 Agent 未就绪（禁止 Hub 聊天回退）
    @Published var agentMode: String = "none"
    /// 状态栏：本机 Agent / 本机 Agent 未就绪
    @Published var agentBadge: String = "本机 Agent 未就绪"
    /// 可聊 = sidecar 健康（与 hubReachable 独立）
    var canChat: Bool { agentMode == "local" }
    /// 可转任务 = Hub 可达 + 业务仓可下达
    var canTransfer: Bool {
        hubReachable && (selectedProject?.isDispatchable == true)
    }
    @Published var busy = false
    /// 界面可用：本机可聊或有项目缓存（≠ 可聊；可聊看 canChat）
    @Published var connected = false
    /// Hub projects/API 是否刚探测成功（转任务/flow 需要）
    @Published var hubReachable = false
    @Published var destination: SidebarDestination = .chat
    @Published var toast: String?
    @Published var showSettingsHint = false

    @Published var transferTitle = ""
    @Published var transferGoal = ""
    @Published var transferAcceptance = ""
    @Published var transferPipeline = "dev"
    @Published var transferExecutor = "opencode"
    @Published var transferFeasibility = "ok"
    @Published var transferFeasibilityReason = ""
    @Published var transferPlanMd = ""
    @Published var showTransferSheet = false
    @Published var transferError: String?
    /// 解析到的定稿条（消息下「确认转任务」）
    @Published var pendingTransferDraft: TransferDraft?
    /// 右栏拆分动画世代（works 0→N 时递增；切会话重置）
    @Published var flowSplitGeneration: UInt64 = 0
    private var lastAnimatedEpicId: String?

    @Published var flowEmptyMessage = "编排空闲·等定稿下达（与对话故障无关）"
    @Published var flowWorks: [FlowWork] = []
    @Published var flowEpic: FlowEpic?
    @Published var flowHeadline: String = ""
    @Published var currentEpicId: String?
    @Published var recentEpics: [FlowEpicRef] = []
    @Published var selectedNodeDetail: FlowNodeDetail?
    @Published var lastError: String?
    @Published var expandedProjectIds: Set<String> = []
    @Published var renameThreadId: String?
    @Published var renameDraft: String = ""

    /// 转任务后扇出超时提示（右栏）
    @Published var flowFanoutHint: String?
    /// 当前选中会话是否正在生成（按会话，非全局）
    @Published var currentThreadStreaming = false
    /// 发送失败时回填输入框（一次性）
    @Published var composerBounce: String?
    /// 消息「预览」全文（对齐旧 Hub）
    @Published var previewMarkdown: String?
    /// 当前会话累计 token（cost 事件累加；用于触发显示压缩）
    @Published var sessionTokens: Int = 0
    /// 显示压缩阈值（token）；超此触发 agent session 重置注入摘要
    static let agentCompactTokenThreshold = 80_000
    /// 项目后台任务态（卡片灯用）：projectId → 状态键（idle/pending/in_progress/testing/done/failed）
    @Published var projectTaskState: [String: String] = [:]
    /// 项目对话流式态：projectId → "idle"/"text"/"tool"
    @Published var projectConvState: [String: String] = [:]
    /// 项目卡片轮询 task
    private var projectPollTask: Task<Void, Never>?

    // Board
    @Published var boardColumns: [String: [BoardTask]] = [:]
    @Published var boardBusy = false
    @Published var boardError: String?
    @Published var boardWorkspaceLabel: String?
    /// 与 Web Hub「显示已隐藏」对齐：true 时带 include_hidden=1
    @Published var boardShowHidden = false

    // Ops
    @Published var opsOverview: OpsOverview?
    @Published var opsRisks: [OpsRisk] = []
    @Published var opsRisksCount: Int?
    @Published var opsRisksHigh: Int?
    @Published var opsBusy = false
    @Published var opsError: String?
    @Published var opsSummary: OpsSummary?
    @Published var opsAdoptBusy = false
    @Published var opsAdoptError: String?
    /// 顶栏：中转站 flash/code/pro 今日调用
    @Published var routerUsage: RouterUsageResp?
    /// 上一轮拉取的今日总量，用于算「近一轮窗口」增量
    private var routerLastTotals: [String: Int] = [:]
    /// 近 5 秒窗口内新增（与轮询周期对齐；+ 号后展示）
    @Published private(set) var routerWindowDelta: [String: Int] = [
        "flash": 0, "code": 0, "pro": 0,
    ]

    private var flowTask: Task<Void, Never>?
    private var flowBackoffNs: UInt64 = 3_000_000_000
    private var flowRefreshTask: Task<Void, Never>?
    private var flowSSEBoundProjectId: String?
    private var flowSnapshotPaused = false
    private var routerUsageTask: Task<Void, Never>?
    /// 本机 sidecar 可多路并行（对话面；无 Hub chat）
    private var activeChatThreadId: String?
    /// 每会话独立对话流 task
    private var chatTasks: [String: Task<Void, Never>] = [:]
    private var streamingThreadIds: Set<String> = []
    /// 供侧栏观察多路生成状态（与 streamingThreadIds 同步）
    @Published private(set) var liveStreamingThreadIds: Set<String> = []
    private static let maxParallelLocalChats = 3
    /// 会话消息本地缓存（切会话秒开，不堵 HTTP）
    private var threadMessages: [String: [ChatMessage]] = [:]
    /// 会话右栏编排缓存（与对话隔离）
    private var threadFlow: [String: FlowThreadSnapshot] = [:]
    /// 防止慢 HTTP 回写错会话
    private var threadSwitchGeneration: UInt64 = 0
    private var fanoutWatchTask: Task<Void, Never>?
    private var client: APIClient
    /// UI smoke 写入路径（仅 CCC_DESKTOP_UI_SMOKE=1）
    private(set) var uiSmokeOutPath: String?
    /// sidecar 探测成功缓存（30s）
    private var agentProbeOKUntil: Date?
    private var cachedAgentBaseURL: URL?
    private var didToastHubFallback = false
    /// keep-warm
    private var warmLoopTask: Task<Void, Never>?
    /// sidecar 未就绪时自动重探（避免启动竞态卡死「未就绪」）
    private var agentRecoverTask: Task<Void, Never>?
    private var lastWarmAt: Date?
    /// 本机落盘节流：按 threadId 独立，避免多会话互相取消丢落盘
    private var diskSaveTasks: [String: Task<Void, Never>] = [:]

    /// 兼容旧 UI 命名：仅反映「当前会话」是否在生成
    var isStreaming: Bool { currentThreadStreaming }

    init() {
        // 与 @AppStorage 默认一致：现网 Hub 在 2017；本机仅作 fallback
        let raw = UserDefaults.standard.string(forKey: "ccc.server")
            ?? "http://192.168.3.116:7777"
        let url = APIClient.makeBaseURL(from: raw)
            ?? URL(string: "http://192.168.3.116:7777")!
        let user = UserDefaults.standard.string(forKey: "ccc.user") ?? "ccc"
        let pass = UserDefaults.standard.string(forKey: "ccc.pass") ?? "ccc"
        client = APIClient(baseURL: url, user: user, password: pass)
    }

    // MARK: - Workspace map

    private var workspaceMap: [String: String] {
        get {
            guard let data = localWorkspaceMapJSON.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: String]
            else { return [:] }
            return obj
        }
        set {
            if let data = try? JSONSerialization.data(withJSONObject: newValue),
               let s = String(data: data, encoding: .utf8) {
                localWorkspaceMapJSON = s
            }
        }
    }

    /// 当前选中项目的本机路径（Settings 绑定）
    var selectedProjectLocalPath: String {
        get {
            guard let pid = selectedProjectId else { return "" }
            return workspaceMap[pid] ?? ""
        }
        set {
            guard let pid = selectedProjectId else { return }
            var m = workspaceMap
            let trimmed = newValue.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty {
                m.removeValue(forKey: pid)
            } else {
                m[pid] = trimmed
            }
            workspaceMap = m
        }
    }

    /// map → 全局 fallback → Hub path 若本机存在
    func localPath(for projectId: String?) -> String? {
        guard let projectId, !projectId.isEmpty else {
            let g = localWorkspacePath.trimmingCharacters(in: .whitespacesAndNewlines)
            return g.isEmpty ? nil : g
        }
        if let mapped = workspaceMap[projectId]?.trimmingCharacters(in: .whitespacesAndNewlines),
           !mapped.isEmpty {
            return mapped
        }
        let global = localWorkspacePath.trimmingCharacters(in: .whitespacesAndNewlines)
        if !global.isEmpty { return global }
        if let hubPath = projects.first(where: { $0.id == projectId })?.path,
           !hubPath.isEmpty,
           FileManager.default.fileExists(atPath: hubPath) {
            return hubPath
        }
        return nil
    }

    private func prepareClient() async throws {
        guard let url = APIClient.makeBaseURL(from: serverURLString) else {
            throw APIError.badURL
        }
        let chatURL = await ensureLocalAgent()
        let localPath = localPath(for: selectedProjectId)
        await client.update(
            baseURL: url,
            user: authUser,
            password: authPass,
            chatBaseURL: chatURL,
            localProjectPath: localPath
        )
    }

    /// 探测（30s 缓存）→ 失败则拉起 sidecar → 再探测；失败标「未就绪」并后台重探
    @discardableResult
    private func ensureLocalAgent() async -> URL? {
        let agentRaw = ProcessInfo.processInfo.environment["CCC_AGENT"]?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let agentStr = (
            (agentRaw?.isEmpty == false) ? (agentRaw ?? agentURLString) : agentURLString
        )
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard let candidate = APIClient.makeBaseURL(from: agentStr) else {
            setAgentModeNone(reason: "Agent URL 无效")
            return nil
        }

        if let until = agentProbeOKUntil, until > Date(),
           let cached = cachedAgentBaseURL, cached == candidate {
            agentMode = "local"
            agentBadge = "本机 Agent"
            return candidate
        }

        if await client.probeLocalAgent(base: candidate) {
            agentProbeOKUntil = Date().addingTimeInterval(30)
            cachedAgentBaseURL = candidate
            agentMode = "local"
            agentBadge = "本机 Agent"
            didToastHubFallback = false
            // fire-and-forget：不阻塞 ensureLocalAgent 返回
            Task { await warmLocalAgentNow(base: candidate) }
            startWarmLoopIfNeeded()
            return candidate
        }

        // 尝试自启
        statusText = "连接 Agent…"
        let homeHint = cccHomePath.trimmingCharacters(in: .whitespacesAndNewlines)
        let agentBase = agentURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        let launch = AgentSidecarLauncher.ensureRunning(
            cccHomeHint: homeHint.isEmpty ? nil : homeHint,
            agentBase: agentBase.isEmpty ? AgentSidecarLauncher.defaultAgentBase : agentBase
        )
        if launch.launched, let home = launch.cccHome, cccHomePath.isEmpty {
            cccHomePath = home
        }

        let deadline = Date().addingTimeInterval(8)
        while Date() < deadline {
            if await client.probeLocalAgent(base: candidate) {
                agentProbeOKUntil = Date().addingTimeInterval(30)
                cachedAgentBaseURL = candidate
                agentMode = "local"
                agentBadge = "本机 Agent"
                didToastHubFallback = false
                // fire-and-forget：不阻塞 ensureLocalAgent 返回
                Task { await warmLocalAgentNow(base: candidate) }
                startWarmLoopIfNeeded()
                if connected { statusText = "已连接 · 本机 Agent" }
                return candidate
            }
            try? await Task.sleep(nanoseconds: 400_000_000)
        }

        agentProbeOKUntil = nil
        cachedAgentBaseURL = nil
        setAgentModeNone(reason: launch.detail)
        return nil
    }

    private func warmLocalAgentNow(base: URL? = nil, toolMode: String = "discuss") async {
        // 已在流式时勿抢 slot 锁
        if currentThreadStreaming || !liveStreamingThreadIds.isEmpty { return }
        let pid = selectedProjectId
        let path = localPath(for: pid)
        let sid = pid.map { LocalSessionStore.conversationThreadId(for: $0) }
        let result = await client.warmLocalAgent(
            base: base ?? cachedAgentBaseURL,
            projectPath: path,
            sessionId: sid,
            toolMode: toolMode
        )
        // 仅真暖（slot.connected）才记 lastWarmAt；cli-only 不算
        if result.slotConnected {
            lastWarmAt = Date()
        }
    }

    private func startWarmLoopIfNeeded() {
        guard agentMode == "local" else { return }
        if warmLoopTask != nil { return }
        warmLoopTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 240_000_000_000) // 240s
                guard let self, !Task.isCancelled else { break }
                guard self.agentMode == "local" else { continue }
                await self.warmLocalAgentNow()
            }
        }
    }

    /// 本机 Agent 未就绪时每 3s 重探，sidecar 拉起后自动恢复可聊
    private func startAgentRecoverLoopIfNeeded() {
        guard agentMode != "local" else { return }
        if agentRecoverTask != nil { return }
        agentRecoverTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 3_000_000_000)
                guard let self, !Task.isCancelled else { break }
                if self.agentMode == "local" {
                    self.agentRecoverTask = nil
                    break
                }
                _ = await self.ensureLocalAgent()
                if self.agentMode == "local" {
                    self.connected = true
                    self.updateConnectionStatusText(localOK: true, hubOK: self.hubReachable)
                    self.startWarmLoopIfNeeded()
                    self.agentRecoverTask = nil
                    self.showToast("本机 Agent 已恢复")
                    break
                }
            }
        }
    }

    /// 发送前：距上次真暖 >90s 则补暖；流式中跳过（避免抢锁）
    private func warmBeforeSendIfNeeded(toolMode: String) {
        guard agentMode == "local" else { return }
        if currentThreadStreaming || !liveStreamingThreadIds.isEmpty { return }
        if let last = lastWarmAt, Date().timeIntervalSince(last) < 90 { return }
        Task { await warmLocalAgentNow(toolMode: toolMode) }
    }

    private func setAgentModeNone(reason: String) {
        agentMode = "none"
        agentBadge = "本机 Agent 未就绪"
        startAgentRecoverLoopIfNeeded()
        if !didToastHubFallback {
            didToastHubFallback = true
            showToast("本机 Agent 未就绪：\(reason)。请执行 bash scripts/install-agent-sidecar-plist.sh --start")
        }
    }

    var selectedProject: DesktopProject? {
        projects.first { $0.id == selectedProjectId }
    }

    func bootstrap() async {
        // 环境变量优先，便于启动时强制指到 Mac2017
        if let env = ProcessInfo.processInfo.environment["CCC_SERVER"]?.trimmingCharacters(in: .whitespacesAndNewlines),
           !env.isEmpty {
            serverURLString = env
        } else if serverURLString.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            serverURLString = "http://192.168.3.116:7777"
        }
        // 先灌本机 projects 缓存，避免 Hub 抖时空白
        if let cache = LocalSessionStore.loadProjects(), !cache.projects.isEmpty {
            projects = cache.projects
            if selectedProjectId == nil {
                selectedProjectId = cache.default_project ?? cache.projects.first(where: \.isDispatchable)?.id
            }
        }
        await refreshProjects()
        if agentMode != "local" {
            startAgentRecoverLoopIfNeeded()
        }
        await flushPendingHubSync()
        startProjectTaskPolling()
        startRouterUsagePolling()
        if ProcessInfo.processInfo.environment["CCC_DESKTOP_UI_SMOKE"] == "1" {
            await runUISmoke()
        }
    }

    /// 无人值守：连接 → 发一条 → 断言助手气泡 → 写 JSON → 退出
    private func runUISmoke() async {
        let out = ProcessInfo.processInfo.environment["CCC_DESKTOP_UI_SMOKE_OUT"]
            ?? "/tmp/ccc-desktop-ui-smoke.json"
        uiSmokeOutPath = out
        func writeResult(ok: Bool, assistant: String?, error: String?) {
            let payload: [String: Any] = [
                "ok": ok,
                "assistant": assistant ?? "",
                "error": error ?? "",
                "server": serverURLString,
                "project": selectedProjectId ?? "",
            ]
            if let data = try? JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted]),
               let s = String(data: data, encoding: .utf8) {
                try? s.write(toFile: out, atomically: true, encoding: .utf8)
            }
        }
        guard connected else {
            writeResult(ok: false, assistant: nil, error: lastError ?? "未连接")
            NSApplication.shared.terminate(nil)
            return
        }
        // 优先业务仓
        if let demo = projects.first(where: { $0.id == "ccc-demo" && $0.isDispatchable }) {
            await selectProject(demo.id)
        } else if let p = projects.first(where: \.isDispatchable) {
            await selectProject(p.id)
        }
        chat.draft = "UI自检：请只回复四个字「自检OK」"
        await sendMessage()
        let assistant = chat.messages.last(where: { $0.role == "assistant" && !$0.isStreaming })?.content ?? ""
        let ok = !assistant.isEmpty
        writeResult(ok: ok, assistant: assistant, error: ok ? nil : (lastError ?? toast ?? "无助手回复"))
        try? await Task.sleep(nanoseconds: 400_000_000)
        NSApplication.shared.terminate(nil)
    }

    func reconnect() async {
        statusText = "连接中…"
        await refreshProjects()
    }

    func dismissToast() { toast = nil }

    func showToast(_ msg: String) {
        toast = msg
        Task {
            try? await Task.sleep(nanoseconds: 5_000_000_000)
            if toast == msg { toast = nil }
        }
    }

    func refreshProjects() async {
        busy = true
        defer { busy = false }
        // 先确保本机 Agent（可聊不依赖 Hub）
        _ = await ensureLocalAgent()
        let localOK = agentMode == "local"

        do {
            try await prepareClient()
            let resp = try await client.fetchProjects()
            projects = resp.projects
            hubReachable = true
            LocalSessionStore.saveProjects(resp.projects, defaultProject: resp.default_project)
            showSettingsHint = false
            let preferred = persistedProjectId.isEmpty ? nil : persistedProjectId
            let preferredProject = preferred.flatMap { id in projects.first { $0.id == id } }
            if let preferredProject, preferredProject.isDispatchable {
                selectedProjectId = preferredProject.id
            } else if selectedProjectId == nil
                || !projects.contains(where: { $0.id == selectedProjectId })
                || (selectedProject?.isOrch == true && projects.contains(where: \.isDispatchable)) {
                selectedProjectId = resp.default_project
                    ?? resp.projects.first(where: \.isDispatchable)?.id
                    ?? preferred
                    ?? resp.projects.first?.id
            } else if let preferred, projects.contains(where: { $0.id == preferred }) {
                selectedProjectId = preferred
            }
            if let pid = selectedProjectId {
                persistedProjectId = pid
                expandedProjectIds.insert(pid)
                await refreshThreads(projectId: pid)
                await bindFlowToCurrentThread()
            }
            // 可聊只看 sidecar；connected 表示「界面可用」（本机可聊或至少有项目缓存）
            connected = localOK || !projects.isEmpty
            lastError = nil
            updateConnectionStatusText(localOK: localOK, hubOK: true)
            startWarmLoopIfNeeded()
            await flushPendingHubSync()
        } catch {
            hubReachable = false
            lastError = error.localizedDescription
            // Hub 失败：保留缓存 projects，本机 Agent 仍可聊
            if let cache = LocalSessionStore.loadProjects(), !cache.projects.isEmpty {
                projects = cache.projects
                if selectedProjectId == nil {
                    selectedProjectId = cache.default_project
                        ?? cache.projects.first(where: \.isDispatchable)?.id
                }
            }
            if let pid = selectedProjectId {
                await refreshThreads(projectId: pid)
            }
            connected = localOK || !projects.isEmpty
            showSettingsHint = !localOK && !hubReachable
            updateConnectionStatusText(localOK: localOK, hubOK: false)
            if !localOK {
                showToast("本机 Agent 未就绪（对话不可用）。Hub：\(error.localizedDescription)")
            } else {
                showToast("Hub 暂不可达（可聊；转任务暂不可用）")
            }
            if localOK { startWarmLoopIfNeeded() }
        }
    }

    private func updateConnectionStatusText(localOK: Bool, hubOK: Bool) {
        if localOK && hubOK {
            statusText = "已连接 · 本机 Agent"
            agentBadge = "本机 Agent"
        } else if localOK && !hubOK {
            statusText = "本机 Agent · Hub 暂不可达（可聊）"
            agentBadge = "本机 Agent"
        } else if !localOK && hubOK {
            statusText = "Hub 可达 · 可转任务 · 本机 Agent 未就绪"
            agentBadge = "本机 Agent 未就绪"
        } else {
            statusText = "本机 Agent 未就绪 · Hub 不可达"
            agentBadge = "本机 Agent 未就绪"
        }
    }

    func selectProject(_ id: String) async {
        let switching = id != selectedProjectId
        if let tid = selectedThreadId, switching {
            persistCurrentThreadSnapshot(threadId: tid)
        }
        selectedProjectId = id
        persistedProjectId = id
        expandedProjectIds.insert(id)
        // 单对话模型：每项目恰好一个会话 "<projectId>::main"
        selectedThreadId = LocalSessionStore.conversationThreadId(for: id)
        if switching {
            // 禁止先清空再加载（会闪空对话/右栏）；直接 hydrate
            selectedNodeDetail = nil
            ensureFlowSSE()
            await loadConversation(projectId: id)
            // 切项目即预连该项目的 agent slot（后台，不挡 UI）；带 generation 防过期写回
            let warmGen = threadSwitchGeneration
            Task { [warmGen] in
                guard self.threadSwitchGeneration == warmGen else { return }
                await self.warmLocalAgentNow()
            }
        } else {
            // 同项目再点（从看板/运维回对话）：只恢复缓存，不踢 Hub 同步，避免闪空
            let tid = LocalSessionStore.conversationThreadId(for: id)
            hydrateThreadFromDisk(projectId: id, threadId: tid)
            if let cached = threadMessages[tid], !cached.isEmpty {
                chat.messages = cached
            }
            if let snap = threadFlow[tid] {
                applyFlowSnapshot(snap)
            }
            refreshCurrentThreadStreaming()
        }
    }

    /// 侧栏点项目卡：切项目 + 强制回对话面（看板/运维里点项目也能回对话）
    func openProjectConversation(_ id: String) async {
        destination = .chat
        await selectProject(id)
    }

    /// 加载项目的唯一会话（磁盘 SSOT；Hub 仅在本机为空时可选补种，禁止回写覆盖）
    private func loadConversation(projectId: String) async {
        let tid = ConversationStore.conversationId(for: projectId)
        threadSwitchGeneration &+= 1
        let gen = threadSwitchGeneration
        selectedThreadId = tid
        let state = ConversationStore.load(projectId: projectId)
        threadMessages[tid] = state.messages
        if let flow = state.flow {
            threadFlow[tid] = flow
        } else if let bound = state.boundEpicId {
            let snap = FlowThreadSnapshot(
                epicId: bound, epic: nil, works: [], headline: "",
                recentEpics: [], emptyMessage: "编排空闲·等定稿下达（与对话故障无关）", fanoutHint: nil            )
            threadFlow[tid] = snap
        }
        chat.messages = state.messages
        pendingTransferDraft = nil
        if let lastAsst = state.messages.last(where: { $0.role == "assistant" && !$0.isStreaming }) {
            refreshTransferDraft(from: lastAsst.content)
        }
        lastAnimatedEpicId = nil
        flowSplitGeneration &+= 1
        applyFlowSnapshot(threadFlow[tid])
        refreshCurrentThreadStreaming()
        updateFlowSnapshotPause()
        lastError = nil
        // 后台：本机空才从 Hub 补种消息；flow 以本地 boundEpicId 为先
        Task { [weak self] in
            guard let self else { return }
            await self.syncThreadFromServer(projectId: projectId, threadId: tid, generation: gen)
            await self.syncFlowFromServer(projectId: projectId, threadId: tid, generation: gen)
        }
    }

    /// 重置当前项目的对话：清盘 + drop sidecar slot + 清 UI
    func resetConversation() async {
        guard let pid = selectedProjectId else {
            showToast("请先选择项目")
            return
        }
        if let tid = selectedThreadId {
            cancelChat(threadId: tid, silent: true)
        }
        LocalSessionStore.reset(projectId: pid)
        let convId = LocalSessionStore.conversationThreadId(for: pid)
        threadMessages[convId] = nil
        threadFlow[convId] = nil
        // 通知 sidecar 丢弃 live slot
        await dropSidecarSession(projectId: pid)
        selectedThreadId = convId
        chat.messages = []
        applyFlowSnapshot(nil)
        flowSplitGeneration &+= 1
        refreshCurrentThreadStreaming()
        showToast("对话已重置")
        destination = .chat
    }

    /// 通知 sidecar 丢弃项目的 ClaudeSDKClient live slot
    private func dropSidecarSession(projectId: String) async {
        guard canChat else { return }
        let path = localPath(for: projectId) ?? ""
        await client.dropSidecarSession(
            projectPath: path,
            sessionId: LocalSessionStore.conversationThreadId(for: projectId)
        )
    }

    /// 显示压缩：消息超阈值时把最早 N 轮替换为摘要卡；token 超阈值时触发 agent session 重置
    func compactConversationIfNeeded(projectId: String, threadId: String) async {
        let current = threadMessages[threadId] ?? (selectedThreadId == threadId ? chat.messages : [])
        let (compacted, didCompact, rounds) = LocalSessionStore.compactIfNeeded(current)
        guard didCompact else { return }
        threadMessages[threadId] = compacted
        if selectedThreadId == threadId {
            chat.messages = compacted
        }
        flushDiskSave(threadId: threadId)
        // agent session token 超阈值 → 重置注入摘要（节约 token）
        if sessionTokens >= Self.agentCompactTokenThreshold {
            await resetAgentSessionWithSummary(projectId: projectId, threadId: threadId, rounds: rounds)
            sessionTokens = 0
        }
    }

    /// 调 sidecar /api/session/compact：drop slot + 新 slot 注入摘要
    private func resetAgentSessionWithSummary(projectId: String, threadId: String, rounds: Int) async {
        guard canChat else { return }
        let path = localPath(for: projectId) ?? ""
        let summary = "已压缩 \(rounds) 轮对话，请基于本机磁盘历史继续。"
        await client.compactSidecarSession(
            projectPath: path,
            sessionId: threadId,
            summary: summary
        )
    }

    func toggleProjectExpanded(_ id: String) {
        if expandedProjectIds.contains(id) {
            expandedProjectIds.remove(id)
        } else {
            expandedProjectIds.insert(id)
        }
    }

    func refreshThreads(projectId: String) async {
        // 单对话模型：确保 "<projectId>::main" 会话在索引中
        let tid = LocalSessionStore.conversationThreadId(for: projectId)
        let local = LocalSessionStore.threadsAsDesktop(projectId: projectId)
        if !local.contains(where: { $0.thread_id == tid }) {
            LocalSessionStore.saveMessages(
                projectId: projectId,
                threadId: tid,
                messages: [],
                title: "对话",
                allowDowngrade: true
            )
        }
        threads = LocalSessionStore.threadsAsDesktop(projectId: projectId)
        hydrateThreadFromDisk(projectId: projectId, threadId: tid)
    }

    func newThread() async {
        await resetConversation()
    }

    /// 项目即对话：忽略任意 thread id，只加载当前项目唯一会话
    func openThread(_ id: String) async {
        _ = id
        guard let pid = selectedProjectId else { return }
        destination = .chat
        await loadConversation(projectId: pid)
    }

    /// 从本机盘灌 RAM；若盘比 RAM 更丰富则覆盖空/残缺缓存
    private func hydrateThreadFromDisk(projectId: String, threadId: String) {
        guard let disk = LocalSessionStore.load(projectId: projectId, threadId: threadId) else { return }
        let ram = threadMessages[threadId] ?? []
        let diskScore = LocalSessionStore.messageScore(disk.messages)
        let ramScore = LocalSessionStore.messageScore(ram)
        if ram.isEmpty || diskScore > ramScore {
            threadMessages[threadId] = disk.messages
        }
        if let flow = disk.flow, threadFlow[threadId] == nil || (threadFlow[threadId]?.works.isEmpty == true && !flow.works.isEmpty) {
            threadFlow[threadId] = flow
        } else if threadFlow[threadId] == nil, disk.flow != nil {
            threadFlow[threadId] = disk.flow
        }
    }

    private func persistCurrentThreadSnapshot(threadId: String) {
        let cached = threadMessages[threadId] ?? []
        let outgoing = chat.messages
        // 禁止空 messages 冲掉更丰富的缓存（切看板/运维竞态）
        let best: [ChatMessage]
        if LocalSessionStore.messageScore(outgoing) >= LocalSessionStore.messageScore(cached) {
            best = outgoing
        } else {
            best = cached
        }
        threadMessages[threadId] = best
        let snap = FlowThreadSnapshot(
            epicId: currentEpicId,
            epic: flowEpic,
            works: flowWorks,
            headline: flowHeadline,
            recentEpics: recentEpics,
            emptyMessage: flowEmptyMessage,
            fanoutHint: flowFanoutHint
        )
        // 空右栏不覆盖已有 works
        if let prev = threadFlow[threadId],
           snap.works.isEmpty, snap.epic == nil,
           (!prev.works.isEmpty || prev.epic != nil) {
            // 只更新消息；保留旧 flow
        } else {
            threadFlow[threadId] = snap
        }
        if selectedProjectId != nil {
            // 统一落盘路径：取消节流后立即写，避免旧 flush 覆盖
            flushDiskSave(threadId: threadId)
        }
    }

    private func applyFlowSnapshot(_ snap: FlowThreadSnapshot?) {
        if let snap {
            currentEpicId = snap.epicId
            flowEpic = snap.epic
            flowWorks = snap.works
            flowHeadline = snap.headline
            recentEpics = snap.recentEpics
            flowEmptyMessage = snap.emptyMessage
            flowFanoutHint = snap.fanoutHint
        } else {
            currentEpicId = nil
            flowEpic = nil
            flowWorks = []
            flowHeadline = ""
            recentEpics = []
            flowEmptyMessage = "编排空闲·等定稿下达（与对话故障无关）"
            flowFanoutHint = nil
            selectedNodeDetail = nil
        }
    }

    /// 本机有消息则禁止 Hub GET 回写；仅本机为空时可选补种备份
    private func syncThreadFromServer(projectId: String, threadId: String, generation: UInt64) async {
        if streamingThreadIds.contains(threadId) { return }
        hydrateThreadFromDisk(projectId: projectId, threadId: threadId)
        let cached = threadMessages[threadId]
            ?? LocalSessionStore.load(projectId: projectId, threadId: threadId)?.messages
            ?? []
        // 契约：本机 SSOT — 有内容绝不让 Hub 覆盖 UI
        if LocalSessionStore.messageScore(cached) > 0 {
            if selectedThreadId == threadId, destination == .chat, chat.messages.isEmpty {
                chat.messages = cached
            }
            return
        }
        do {
            try await prepareClient()
            let detail = try await client.fetchThread(projectId: projectId, threadId: threadId)
            guard threadSwitchGeneration == generation, selectedThreadId == threadId else { return }
            let loaded = detail.messages ?? []
            guard LocalSessionStore.messageScore(loaded) > 0 else { return }
            threadMessages[threadId] = loaded
            if selectedThreadId == threadId, destination == .chat {
                chat.messages = loaded
            }
            let title = threads.first(where: { $0.thread_id == threadId })?.title
                ?? detail.title
            LocalSessionStore.saveMessages(
                projectId: projectId,
                threadId: threadId,
                messages: loaded,
                title: title,
                flow: threadFlow[threadId],
                allowDowngrade: false
            )
            hubReachable = true
        } catch {
            hydrateThreadFromDisk(projectId: projectId, threadId: threadId)
            if selectedThreadId == threadId {
                chat.messages = threadMessages[threadId] ?? []
            }
        }
    }

    /// 右栏：本地 boundEpicId 为 SSOT；Hub 列表只作 enrichment，空列表不冲本地
    private func syncFlowFromServer(projectId: String, threadId: String, generation: UInt64) async {
        do {
            try await prepareClient()
            // 始终传 ::main，由 Hub 做项目会话视图（刀 2）；过渡期也兼容省略 filter
            let epicsResp = try await client.fetchRecentEpicsDetailed(
                projectId: projectId,
                threadId: threadId
            )
            guard threadSwitchGeneration == generation, selectedThreadId == threadId else { return }
            let epics = epicsResp.epics
            recentEpics = epics
            let localSnap = threadFlow[threadId]
            let localBound = localSnap?.epicId ?? currentEpicId
            let hasLocalFlow =
                (localBound?.isEmpty == false)
                || (localSnap?.epic != nil)
                || !(localSnap?.works.isEmpty ?? true)
                || !flowWorks.isEmpty

            if let bound = localBound, !bound.isEmpty {
                // 本机绑定优先：不因 Hub「第一条」抢绑
                currentEpicId = bound
                await refreshFlowNow()
            } else if let hint = epicsResp.boundHint, !hint.isEmpty {
                currentEpicId = hint
                await refreshFlowNow()
            } else if let match = epics.first(where: { ($0.thread_id ?? "") == threadId })?.epic_id {
                currentEpicId = match
                await refreshFlowNow()
            } else if let first = epics.first?.epic_id {
                currentEpicId = first
                await refreshFlowNow()
            } else if hasLocalFlow {
                return
            } else {
                currentEpicId = nil
                flowEpic = nil
                flowWorks = []
                flowHeadline = ""
                flowEmptyMessage = "编排空闲·等定稿下达（与对话故障无关）"
                flowFanoutHint = nil
            }
            persistCurrentThreadSnapshot(threadId: threadId)
            ensureFlowSSE()
        } catch {
            if selectedThreadId == threadId, threadFlow[threadId] == nil {
                flowEmptyMessage = "流程加载失败"
            }
        }
    }

    /// 多会话改名已退役；项目即对话无独立 thread 标题 UI
    func beginRenameThread(_ thread: DesktopThread) {
        _ = thread
    }

    func commitRenameThread() async {
        renameThreadId = nil
    }

    /// 删除会话 = 重置当前项目唯一对话（不再支持按 UUID 删多会话）
    func deleteThread(_ threadId: String) async {
        _ = threadId
        await resetConversation()
    }

    private func refreshCurrentThreadStreaming() {
        if let tid = selectedThreadId {
            currentThreadStreaming = streamingThreadIds.contains(tid)
            if currentThreadStreaming, canChat {
                setStatusImmediate("本机生成中…")
            } else if canChat, statusText.contains("生成中") || statusText.hasPrefix("本条失败") {
                updateConnectionStatusText(localOK: true, hubOK: hubReachable)
            }
        } else {
            currentThreadStreaming = false
        }
    }

    /// 95+：聊天不再暂停右栏 flow；只挡「覆盖当前 messages」的 HTTP 同步（见 syncThreadFromServer）
    private func updateFlowSnapshotPause() {
        flowSnapshotPaused = false
    }

    private func persistMessages(for threadId: String, _ msgs: [ChatMessage]) {
        threadMessages[threadId] = msgs
        if selectedThreadId == threadId {
            chat.messages = msgs
        }
        scheduleDiskSave(threadId: threadId)
    }

    /// 本机落盘节流 ~300ms；按 threadId 独立任务，禁止互相 cancel
    private func scheduleDiskSave(threadId: String) {
        let pid = Self.projectId(fromThreadId: threadId)
        let projectId = pid.isEmpty ? (selectedProjectId ?? "") : pid
        guard !projectId.isEmpty else { return }
        diskSaveTasks[threadId]?.cancel()
        diskSaveTasks[threadId] = Task { [weak self, threadId, projectId] in
            try? await Task.sleep(nanoseconds: 300_000_000)
            guard !Task.isCancelled, let self else { return }
            await MainActor.run {
                self.writeDiskSave(threadId: threadId, projectId: projectId)
                self.diskSaveTasks[threadId] = nil
            }
        }
    }

    /// 立即落盘指定会话（切项目 / compact）；取消该 tid 的节流任务
    private func flushDiskSave(threadId: String? = nil) {
        if let tid = threadId {
            diskSaveTasks[tid]?.cancel()
            diskSaveTasks[tid] = nil
            let pid = Self.projectId(fromThreadId: tid)
            let projectId = pid.isEmpty ? (selectedProjectId ?? "") : pid
            guard !projectId.isEmpty else { return }
            writeDiskSave(threadId: tid, projectId: projectId)
            return
        }
        // 刷全部 pending
        let keys = Array(diskSaveTasks.keys)
        for tid in keys {
            flushDiskSave(threadId: tid)
        }
    }

    private func writeDiskSave(threadId tid: String, projectId pid: String) {
        let msgs = (threadMessages[tid] ?? (selectedThreadId == tid ? chat.messages : []))
            .filter { !$0.isStreaming || !$0.content.isEmpty }
        let title = threads.first(where: { $0.thread_id == tid })?.title
        var flow = threadFlow[tid]
        if flow?.epicId == nil, let eid = currentEpicId, selectedThreadId == tid {
            flow?.epicId = eid
        }
        LocalSessionStore.saveMessages(
            projectId: pid,
            threadId: tid,
            messages: msgs,
            title: title,
            flow: flow,
            needsHubSync: false
        )
    }

    private func mutateThreadMessages(threadId: String, _ body: (inout [ChatMessage]) -> Void) {
        var msgs = threadMessages[threadId] ?? (selectedThreadId == threadId ? chat.messages : [])
        body(&msgs)
        persistMessages(for: threadId, msgs)
    }

    /// Phase 1.4: delta 热路径专用——直接下标改 messages[i].content，避免整数组重赋值。
    /// 仍触发 @Published willSet（subscript setter），但 SwiftUI 可按 row diff，不重建 LazyVStack。
    private func applyDeltaInPlace(threadId: String, assistantId: UUID, chunk: String) {
        if var msgs = threadMessages[threadId],
           let idx = msgs.firstIndex(where: { $0.id == assistantId }) {
            msgs[idx].content += chunk
            // 新 delta 到达 → 清掉阶段性短句
            if msgs[idx].transientNote != nil {
                msgs[idx].transientNote = nil
            }
            threadMessages[threadId] = msgs
        }
        if selectedThreadId == threadId {
            chat.replaceMessage(id: assistantId) { m in
                m.content += chunk
                if m.transientNote != nil {
                    m.transientNote = nil
                }
            }
            // 兜底：messages 与 threadMessages 不同步时整表对齐一次
            if !chat.messages.contains(where: { $0.id == assistantId }),
               let msgs = threadMessages[threadId] {
                chat.messages = msgs
            }
        }
        scheduleDiskSave(threadId: threadId)
    }

    /// 末段长 result 分片：~20 字/帧、50ms 间隔，避免一次性弹出
    private func applyDeltaInChunks(threadId: String, assistantId: UUID, chunk: String) {
        let chars = Array(chunk)
        let sliceSize = 20
        var pos = 0
        // 先喂第一片，立刻有内容显示
        let first = String(chars.prefix(sliceSize))
        applyDeltaInPlace(threadId: threadId, assistantId: assistantId, chunk: first)
        pos = sliceSize
        Task { [weak self] in
            while pos < chars.count {
                try? await Task.sleep(nanoseconds: 50_000_000)
                guard let self, !Task.isCancelled else { return }
                let end = min(pos + sliceSize, chars.count)
                let piece = String(chars[pos..<end])
                await MainActor.run {
                    self.applyDeltaInPlace(threadId: threadId, assistantId: assistantId, chunk: piece)
                }
                pos = end
            }
        }
    }

    /// Phase 1.4: statusText 250ms 节流，避免每个 delta 都重绘状态栏
    private var pendingStatusText: String?
    private var statusThrottleTask: Task<Void, Never>?
    private func setStatusThrottled(_ text: String) {
        pendingStatusText = text
        if statusThrottleTask != nil { return }
        statusThrottleTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 250_000_000)
            guard let self else { return }
            self.statusThrottleTask = nil
            if let pending = self.pendingStatusText {
                self.pendingStatusText = nil
                self.statusText = pending
            }
        }
    }
    private func setStatusImmediate(_ text: String) {
        pendingStatusText = nil
        statusThrottleTask?.cancel()
        statusThrottleTask = nil
        statusText = text
    }

    /// Hub PUT 会话备份（非权威；Engine 不读；失败入重试队列，本机磁盘为准）
    private func syncMessagesToHub(projectId: String, threadId: String, messages synced: [ChatMessage]) async {
        do {
            try await prepareClient()
            try await client.syncThreadMessages(
                projectId: projectId,
                threadId: threadId,
                messages: synced
            )
            LocalSessionStore.dequeueSync(projectId: projectId, threadId: threadId)
        } catch {
            LocalSessionStore.enqueueSync(projectId: projectId, threadId: threadId)
        }
    }

    private func flushPendingHubSync() async {
        guard hubReachable else { return }
        let pending = LocalSessionStore.loadPendingSync()
        for item in pending {
            if item.attempts >= LocalSessionStore.maxSyncAttempts {
                // 耗尽重试：出队，避免僵尸项永久膨胀 pending-sync.json
                LocalSessionStore.dequeueSync(
                    projectId: item.project_id, threadId: item.thread_id
                )
                continue
            }
            guard let rec = LocalSessionStore.load(projectId: item.project_id, threadId: item.thread_id)
            else {
                LocalSessionStore.dequeueSync(projectId: item.project_id, threadId: item.thread_id)
                continue
            }
            do {
                try await prepareClient()
                try await client.syncThreadMessages(
                    projectId: item.project_id,
                    threadId: item.thread_id,
                    messages: rec.messages
                )
                LocalSessionStore.dequeueSync(projectId: item.project_id, threadId: item.thread_id)
            } catch {
                _ = LocalSessionStore.bumpAttempt(projectId: item.project_id, threadId: item.thread_id)
            }
        }
    }

    static func promptMode(forUserText text: String) -> String {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let forceFull = ["定稿", "转任务", "下达", "可以转了"].contains { t.contains($0) }
        if forceFull || t.count > 80 { return "full" }
        return "light"
    }

    /// discuss = 只读探查（默认）；engineer = 允许本机写文件（口令解锁）
    static func toolMode(forUserText text: String) -> String {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.contains("工程师模式") || t.contains("直接改本机") { return "engineer" }
        return "discuss"
    }

    /// 同会话 stop-and-send；仅本机 sidecar，可多路并行
    func sendUserMessage(_ text: String, stopAndSend: Bool = true) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        Task { await self.sendUserMessageAndWait(trimmed, stopAndSend: stopAndSend) }
    }

    func isThreadStreaming(_ threadId: String) -> Bool {
        liveStreamingThreadIds.contains(threadId) || streamingThreadIds.contains(threadId)
    }

    private func setThreadStreaming(_ threadId: String, _ on: Bool) {
        if on {
            streamingThreadIds.insert(threadId)
        } else {
            streamingThreadIds.remove(threadId)
        }
        liveStreamingThreadIds = streamingThreadIds
        // 同步项目对话灯：threadId = "<projectId>::main"
        let pid = Self.projectId(fromThreadId: threadId)
        if on {
            // 必须覆盖 "idle"；不可用 ??（非 nil 的 idle 会卡住）
            projectConvState[pid] = "text"
        } else {
            projectConvState[pid] = "idle"
        }
        refreshCurrentThreadStreaming()
        updateFlowSnapshotPause()
    }

    /// 从 threadId "<projectId>::main" 反解 projectId
    static func projectId(fromThreadId threadId: String) -> String {
        if let range = threadId.range(of: "::") {
            return String(threadId[..<range.lowerBound])
        }
        return threadId
    }

    /// 工具调用期间设项目对话灯为 "tool"
    private func setProjectConvToolState(threadId: String) {
        let pid = Self.projectId(fromThreadId: threadId)
        if streamingThreadIds.contains(threadId) {
            projectConvState[pid] = "tool"
        }
    }

    /// delta 期间回退为 "text"（若当前是 "tool" 则保留工具态）
    /// 节流：避免每个 token 刷侧栏 projectConvState
    private var pendingConvTextThreadId: String?
    private var convTextThrottleTask: Task<Void, Never>?
    private func setProjectConvTextState(threadId: String) {
        pendingConvTextThreadId = threadId
        if convTextThrottleTask != nil { return }
        convTextThrottleTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 250_000_000)
            guard let self else { return }
            self.convTextThrottleTask = nil
            guard let tid = self.pendingConvTextThreadId else { return }
            self.pendingConvTextThreadId = nil
            let pid = Self.projectId(fromThreadId: tid)
            if self.streamingThreadIds.contains(tid), self.projectConvState[pid] != "tool" {
                self.projectConvState[pid] = "text"
            }
        }
    }

    /// 启动项目卡片后台任务态轮询（10s）
    func startProjectTaskPolling() {
        guard projectPollTask == nil else { return }
        projectPollTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { break }
                await self.refreshProjectTaskState()
                try? await Task.sleep(nanoseconds: 10_000_000_000)
            }
        }
    }

    func stopProjectTaskPolling() {
        projectPollTask?.cancel()
        projectPollTask = nil
    }

    private func refreshProjectTaskState() async {
        guard hubReachable, !projects.isEmpty else { return }
        let workspaces = projects.compactMap { $0.workspace ?? $0.id }
        do {
            try await prepareClient()
            let resp = try await client.fetchBoardSummaries(workspaces: workspaces)
            var newState: [String: String] = [:]
            for proj in projects {
                let ws = proj.workspace ?? proj.id
                if let snap = resp.summaries[ws] {
                    newState[proj.id] = Self.deriveTaskState(from: snap.counts ?? [:])
                }
            }
            projectTaskState = newState
        } catch {
            // 静默失败；卡片灯不是关键路径
        }
    }

    /// 从 board 列计数推导项目级任务态（只关心「有活」；纯 released 视为空闲）
    static func deriveTaskState(from counts: [String: Int]) -> String {
        let failed = counts["abnormal"] ?? 0
        let inProgress = counts["in_progress"] ?? 0
        let testing = counts["testing"] ?? 0
        let planned = counts["planned"] ?? 0
        let backlog = counts["backlog"] ?? 0
        if failed > 0 { return "failed" }
        if inProgress > 0 { return "in_progress" }
        if testing > 0 { return "testing" }
        if planned > 0 || backlog > 0 { return "pending" }
        return "idle"
    }

    /// 可等待版本：smoke / 自动化必须等整轮 SSE（含 done）结束
    @discardableResult
    func sendUserMessageAndWait(_ text: String, stopAndSend: Bool = true) async -> Bool {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return false }
        guard let pid = selectedProjectId else {
            showToast("请先选择项目")
            composerBounce = trimmed
            return false
        }
        // 编排仓可聊方案；仅转任务/下达仍禁（isDispatchable）
        let tid = ConversationStore.conversationId(for: pid)
        if selectedThreadId != tid {
            selectedThreadId = tid
            hydrateThreadFromDisk(projectId: pid, threadId: tid)
            if chat.messages.isEmpty, let cached = threadMessages[tid] {
                chat.messages = cached
            }
        }
        let threadId = tid
        // 对话面：必须本机 Agent；禁止 Hub /api/chat
        if !canChat {
            showToast("本机 Agent 未就绪。请执行 bash scripts/install-agent-sidecar-plist.sh --start")
            composerBounce = trimmed
            return false
        }

        if streamingThreadIds.contains(threadId) {
            if stopAndSend {
                let previous = chatTasks[threadId]
                cancelChat(threadId: threadId, silent: true)
                await previous?.value
            } else {
                showToast("正在生成，请先点停止")
                composerBounce = trimmed
                return false
            }
        }

        let others = streamingThreadIds.filter { $0 != threadId }.count
        if others >= Self.maxParallelLocalChats {
            showToast("已有 \(Self.maxParallelLocalChats) 路在生成，请先停止一路再发")
            composerBounce = trimmed
            return false
        }

        let task = Task { [weak self] in
            guard let self else { return }
            await self.runChatStream(projectId: pid, threadId: threadId, text: trimmed)
        }
        chatTasks[threadId] = task
        await task.value
        return true
    }

    func sendMessageCancellable(stopAndSend: Bool = true) {
        let text = chat.draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        chat.draft = ""
        sendUserMessage(text, stopAndSend: stopAndSend)
    }

    func sendMessage() async {
        let text = chat.draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        chat.draft = ""
        _ = await sendUserMessageAndWait(text, stopAndSend: true)
    }

    private func runChatStream(projectId: String, threadId: String, text: String) async {
        setThreadStreaming(threadId, true)
        activeChatThreadId = threadId
        defer {
            setThreadStreaming(threadId, false)
            if activeChatThreadId == threadId {
                activeChatThreadId = streamingThreadIds.first
            }
            chatTasks[threadId] = nil
            // 当前会话聊完再追赶右栏
            if selectedThreadId == threadId {
                let flowGen = threadSwitchGeneration
                Task { [flowGen, threadId] in
                    guard self.threadSwitchGeneration == flowGen,
                          self.selectedThreadId == threadId else { return }
                    await self.refreshFlow()
                }
            }
        }

        let userMsg = ChatMessage(role: "user", content: text)
        let assistantId = UUID()
        mutateThreadMessages(threadId: threadId) { msgs in
            msgs.append(userMsg)
            msgs.append(ChatMessage(id: assistantId, role: "assistant", content: "", isStreaming: true))
        }

        do {
            if selectedThreadId == threadId {
                setStatusImmediate("连接本机 Agent…")
                chat.streamStatus = "连接本机 Agent…"
            }
            try await prepareClient()
            // 业务仓未绑本机路径时提示一次（不阻断）
            if localPath(for: projectId) == nil,
               let p = projects.first(where: { $0.id == projectId }), p.isDispatchable {
                showToast("未绑定本机工作区，sidecar 可能扫错目录 — 设置里为当前项目填写路径")
            }
            let mode = Self.promptMode(forUserText: text)
            let tools = Self.toolMode(forUserText: text)
            warmBeforeSendIfNeeded(toolMode: tools)
            if selectedThreadId == threadId {
                setStatusImmediate("本机生成中…")
                chat.streamStatus = "本机生成中…"
            }
            let outbound = (threadMessages[threadId] ?? []).filter { $0.id != assistantId }

            // 同会话自动重试 1 次（保留已生成的本地内容，清空半截助手再流）
            var streamError: Error?
            for attempt in 1...2 {
                do {
                    if attempt == 2 {
                        if selectedThreadId == threadId {
                            setStatusImmediate("重连中…")
                            chat.streamStatus = "重连中…"
                        }
                        mutateThreadMessages(threadId: threadId) { msgs in
                            guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                            msgs[idx].content = ""
                            msgs[idx].toolSteps = []
                            msgs[idx].filesChanged = 0
                            msgs[idx].toolsFinished = false
                            msgs[idx].isStreaming = true
                        }
                        try await prepareClient()
                    }
                    let outboundAttempt = (threadMessages[threadId] ?? []).filter { $0.id != assistantId }
                    try await client.streamChat(
                        projectId: projectId,
                        sessionId: threadId,
                        messages: attempt == 1 ? outbound : outboundAttempt,
                        promptMode: mode,
                        toolMode: tools
                    ) { [weak self] event in
                        guard let model = self else { return }
                        await MainActor.run {
                            model.applyChatEvent(threadId: threadId, assistantId: assistantId, event: event)
                        }
                    }
                    streamError = nil
                    break
                } catch is CancellationError {
                    throw CancellationError()
                } catch {
                    streamError = error
                    let cancelled = (error as NSError).code == NSURLErrorCancelled
                        || error.localizedDescription.lowercased().contains("cancel")
                    if cancelled { throw error }
                    // 仅网络/半截可重试
                    let retryable = error.localizedDescription.contains("中断")
                        || error.localizedDescription.contains("partial")
                        || error.localizedDescription.contains("timed out")
                        || error.localizedDescription.contains("Timeout")
                        || error.localizedDescription.contains("连接")
                        || error.localizedDescription.contains("无响应")
                        || error.localizedDescription.contains("挂死")
                        || (error as? APIError).map { if case .http = $0 { return true }; return false } ?? false
                        || (error as NSError).domain == NSURLErrorDomain
                    if attempt == 1 && retryable {
                        continue
                    }
                    throw error
                }
            }
            if let streamError { throw streamError }

            var failedEmpty = false
            mutateThreadMessages(threadId: threadId) { msgs in
                guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                msgs[idx].isStreaming = false
                for i in msgs[idx].toolSteps.indices where msgs[idx].toolSteps[i].status == .running {
                    msgs[idx].toolSteps[i].status = .done
                }
                if !msgs[idx].toolSteps.isEmpty {
                    msgs[idx].toolsFinished = true
                }
                if msgs[idx].content.isEmpty && msgs[idx].toolSteps.isEmpty {
                    msgs.remove(at: idx)
                    failedEmpty = true
                }
            }
            if failedEmpty {
                throw APIError.decode("模型无有效回复")
            }
            if selectedThreadId == threadId {
                chat.streamStatus = ""
                updateConnectionStatusText(localOK: canChat, hubOK: hubReachable)
            }
            // 解析定稿块
            if let asst = (threadMessages[threadId] ?? []).last(where: { $0.id == assistantId }) {
                refreshTransferDraft(from: asst.content)
            }
            // 本机立即落盘 + Hub 异步镜像
            flushDiskSave()
            // 显示压缩（异步，不打断当前流）
            await compactConversationIfNeeded(projectId: projectId, threadId: threadId)
            let synced = (threadMessages[threadId] ?? chat.messages)
                .filter { $0.role == "user" || $0.role == "assistant" }
                .map {
                    ChatMessage(
                        role: $0.role,
                        content: $0.content,
                        toolSteps: $0.toolSteps,
                        filesChanged: $0.filesChanged,
                        toolsFinished: $0.toolsFinished
                    )
                }
            await syncMessagesToHub(projectId: projectId, threadId: threadId, messages: synced)
            await refreshThreads(projectId: projectId)
        } catch is CancellationError {
            if selectedThreadId == threadId {
                chat.streamStatus = ""
            }
            mutateThreadMessages(threadId: threadId) { msgs in
                guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                msgs[idx].isStreaming = false
                msgs[idx].toolsFinished = true
                if msgs[idx].content.isEmpty {
                    msgs.remove(at: idx)
                } else if !msgs[idx].content.contains("（已取消）") {
                    msgs[idx].content += "\n\n（已取消）"
                }
            }
        } catch {
            let cancelled = (error as NSError).code == NSURLErrorCancelled
                || error.localizedDescription.lowercased().contains("cancel")
            mutateThreadMessages(threadId: threadId) { msgs in
                guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                msgs[idx].isStreaming = false
                msgs[idx].toolsFinished = true
                if cancelled {
                    if msgs[idx].content.isEmpty { msgs.remove(at: idx) }
                } else if msgs[idx].content.isEmpty && msgs[idx].toolSteps.isEmpty {
                    msgs.remove(at: idx)
                    if msgs.last?.id == userMsg.id {
                        msgs.removeLast()
                    }
                } else if !msgs[idx].content.isEmpty {
                    msgs[idx].content += "\n\n（回复中断）"
                }
            }
            if !cancelled {
                if selectedThreadId == threadId {
                    chat.streamStatus = ""
                    setStatusImmediate("本条失败")
                }
                showToast("对话失败：\(error.localizedDescription)")
                if selectedThreadId == threadId {
                    composerBounce = text
                }
            }
        }
    }

    private func applyChatEvent(threadId: String, assistantId: UUID, event: ChatStreamEvent) {
        switch event {
        case .ping:
            if selectedThreadId == threadId {
                // 首包前 / idle：明确「连接中」，勿空泡假死
                if chat.streamStatus.isEmpty
                    || chat.streamStatus.contains("连接")
                    || chat.streamStatus.contains("重连") {
                    chat.streamStatus = "连接本机 Agent…"
                    setStatusThrottled("连接本机 Agent…")
                }
            }
            return
        case .delta(let chunk):
            // 末段长 result 分片喂入（去「弹出」）：> 500 字按 ~20 字/帧、50ms 间隔
            if chunk.count > 500 {
                applyDeltaInChunks(threadId: threadId, assistantId: assistantId, chunk: chunk)
            } else {
                applyDeltaInPlace(threadId: threadId, assistantId: assistantId, chunk: chunk)
            }
            if selectedThreadId == threadId, chat.streamStatus != "本机生成中…" {
                chat.streamStatus = "本机生成中…"
                setStatusThrottled("本机生成中…")
            }
            setProjectConvTextState(threadId: threadId)
            return
        case .status(let note):
            mutateThreadMessages(threadId: threadId) { msgs in
                guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                msgs[idx].transientNote = note
            }
            // mutateThreadMessages → messages= 已触发 @Published；勿再 objectWillChange
            return
        case .toolUse, .toolResult, .cost, .done:
            break
        }
        if case .toolUse = event {
            setProjectConvToolState(threadId: threadId)
        }
        mutateThreadMessages(threadId: threadId) { msgs in
            guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
            switch event {
            case .ping, .delta, .status:
                break
            case .toolUse(let name, let input):
                let anyInput: [String: Any] = input
                let step = ToolStep(
                    name: name,
                    label: ToolProgressHelper.humanLabel(name: name, input: anyInput),
                    icon: ToolProgressHelper.icon(for: name),
                    status: .running
                )
                msgs[idx].toolSteps.append(step)
                msgs[idx].toolsFinished = false
                if ToolProgressHelper.isWrite(name) {
                    msgs[idx].filesChanged += 1
                }
                if selectedThreadId == threadId {
                    chat.streamStatus = "工具执行中…"
                    setStatusThrottled("工具执行中…")
                }
            case .toolResult(let ok):
                if let ri = msgs[idx].toolSteps.lastIndex(where: { $0.status == .running }) {
                    msgs[idx].toolSteps[ri].status = ok ? .done : .error
                } else if let last = msgs[idx].toolSteps.indices.last {
                    msgs[idx].toolSteps[last].status = ok ? .done : .error
                }
                let allDone = !msgs[idx].toolSteps.isEmpty
                    && msgs[idx].toolSteps.allSatisfy { $0.status != .running }
                if allDone {
                    msgs[idx].toolsFinished = true
                }
            case .cost(let tokens, _):
                if let t = tokens, t > 0 {
                    sessionTokens += t
                }
            case .done:
                for i in msgs[idx].toolSteps.indices where msgs[idx].toolSteps[i].status == .running {
                    msgs[idx].toolSteps[i].status = .done
                }
                if !msgs[idx].toolSteps.isEmpty {
                    msgs[idx].toolsFinished = true
                }
                if selectedThreadId == threadId {
                    chat.streamStatus = ""
                }
            }
        }
    }

    func cancelChat(threadId: String? = nil, silent: Bool = false) {
        let tid = threadId ?? selectedThreadId
        guard let tid else { return }
        chatTasks[tid]?.cancel()
        chatTasks[tid] = nil
        setThreadStreaming(tid, false)
        if selectedThreadId == tid {
            chat.streamStatus = ""
        }
        if activeChatThreadId == tid {
            activeChatThreadId = streamingThreadIds.first
        }
        mutateThreadMessages(threadId: tid) { msgs in
            if let idx = msgs.lastIndex(where: { $0.isStreaming }) {
                msgs[idx].isStreaming = false
                msgs[idx].toolsFinished = true
                if msgs[idx].content.isEmpty {
                    msgs.remove(at: idx)
                } else if !msgs[idx].content.contains("（已取消）") {
                    msgs[idx].content += "\n\n（已取消）"
                }
            }
        }
        if !silent {
            showToast("已取消生成")
        }
    }

    func applyQuickPrompt(_ prompt: String, uiLabel: String) {
        destination = .chat
        showToast(uiLabel)
        sendUserMessage(prompt, stopAndSend: true)
    }

    func alignBaseline() async {
        guard let pid = selectedProjectId else {
            showToast("请先选择项目")
            return
        }
        destination = .chat
        do {
            try await prepareClient()
            let resp = try await client.fetchProjectBaseline(projectId: pid)
            let prompt = (resp.prompt ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            guard !prompt.isEmpty else {
                showToast("基线为空")
                return
            }
            showToast("已注入对齐基线")
            sendUserMessage(prompt, stopAndSend: true)
        } catch {
            showToast(error.localizedDescription)
        }
    }

    func exportThreadMarkdown() -> String {
        chat.messages
            .filter { !$0.isStreaming || !$0.content.isEmpty }
            .map { msg in
                let role = msg.role == "user" ? "用户" : "助手"
                return "## \(role)\n\n\(msg.content)\n"
            }
            .joined(separator: "\n")
    }

    func copyMessage(_ text: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        showToast("已复制")
    }

    func exportThreadToPasteboard() {
        let md = exportThreadMarkdown()
        guard !md.isEmpty else {
            showToast("无可导出内容")
            return
        }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(md, forType: .string)
        showToast("会话已复制为 Markdown")
    }

    /// 用户消息 → 填回输入框（对齐 Hub「编辑」）
    func editUserMessage(_ message: ChatMessage) {
        guard message.role == "user" else { return }
        composerBounce = message.content
        destination = .chat
        showToast("已填入输入框，改完再发送")
    }

    /// 助手消息 → 重发紧邻的上一条用户消息（对齐 Hub「重新生成」）
    func regenerateAssistant(after message: ChatMessage) {
        guard message.role == "assistant", let tid = selectedThreadId else { return }
        let msgs = threadMessages[tid] ?? chat.messages
        guard let idx = msgs.firstIndex(where: { $0.id == message.id }) else { return }
        var userText: String?
        var i = idx - 1
        while i >= 0 {
            if msgs[i].role == "user" {
                userText = msgs[i].content
                break
            }
            i -= 1
        }
        guard let text = userText?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty else {
            showToast("没有可重新生成的用户消息")
            return
        }
        sendUserMessage(text, stopAndSend: true)
    }

    /// 从某条助手消息打开预览
    func previewMessage(_ text: String) {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty else {
            showToast("无可预览内容")
            return
        }
        previewMarkdown = t
    }

    /// 从某条助手消息打开转任务（预填）
    func openTransfer(fromAssistantContent content: String) {
        transferError = nil
        applyTransferDraft(TransferDraftParser.parse(from: content), fallbackContent: content)
        showTransferSheet = true
    }

    func openTransferSheet() {
        transferError = nil
        if let d = pendingTransferDraft {
            applyTransferDraft(d, fallbackContent: nil)
        } else {
            prefillTransferFromChat()
        }
        showTransferSheet = true
    }

    /// 一键确认定稿条 → 直接提交（字段已齐）
    func confirmPendingTransfer() {
        guard let d = pendingTransferDraft else {
            openTransferSheet()
            return
        }
        applyTransferDraft(d, fallbackContent: nil)
        if d.isGateReady {
            Task { await submitTransfer() }
        } else {
            showTransferSheet = true
        }
    }

    func dismissPendingTransfer() {
        pendingTransferDraft = nil
    }

    /// 助手回复结束后刷新定稿条
    func refreshTransferDraft(from content: String) {
        if let d = TransferDraftParser.parse(from: content), d.isGateReady || !d.title.isEmpty {
            pendingTransferDraft = d
            applyTransferDraft(d, fallbackContent: nil)
        }
    }

    private func applyTransferDraft(_ draft: TransferDraft?, fallbackContent: String?) {
        if let d = draft {
            if !d.title.isEmpty { transferTitle = d.title }
            if !d.goal.isEmpty { transferGoal = d.goal }
            if !d.acceptance.isEmpty { transferAcceptance = d.acceptance }
            if !d.pipeline.isEmpty { transferPipeline = d.pipeline }
            if !d.feasibility.isEmpty { transferFeasibility = d.feasibility }
            transferFeasibilityReason = d.feasibilityReason
            if !d.executorIntent.isEmpty { transferExecutor = d.executorIntent }
            if !d.planMd.isEmpty { transferPlanMd = d.planMd }
            return
        }
        guard let t = fallbackContent?.trimmingCharacters(in: .whitespacesAndNewlines), !t.isEmpty else {
            return
        }
        if transferGoal.isEmpty { transferGoal = String(t.prefix(2000)) }
        if transferTitle.isEmpty {
            transferTitle = String(t.replacingOccurrences(of: "\n", with: " ").prefix(40))
        }
        if transferAcceptance.isEmpty {
            transferAcceptance = "按对话结论验收；现象符合描述即通过"
        }
    }

    /// 从对话启发式预填门禁字段（无 ccc-transfer 时）
    func prefillTransferFromChat() {
        let assistants = chat.messages.filter { $0.role == "assistant" && !$0.isStreaming }.map(\.content)
        if let last = assistants.last, let d = TransferDraftParser.parse(from: last) {
            applyTransferDraft(d, fallbackContent: nil)
            pendingTransferDraft = d
            return
        }
        let users = chat.messages.filter { $0.role == "user" }.map(\.content)
        let lastUser = users.last ?? ""
        let blob = (users.suffix(3) + assistants.suffix(2)).joined(separator: "\n")
        let lastAssistant = assistants.last ?? ""

        if transferTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            if let t = extractSection(blob, names: ["标题", "title"]) {
                transferTitle = String(t.replacingOccurrences(of: "\n", with: " ").prefix(80))
            } else {
                transferTitle = String(lastUser.replacingOccurrences(of: "\n", with: " ").prefix(40))
            }
        }
        if transferGoal.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            if let g = extractSection(blob, names: ["目标", "goal"]) {
                transferGoal = g
            } else {
                transferGoal = String(lastUser.prefix(200))
            }
        }
        if transferAcceptance.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            if let a = extractSection(blob, names: ["验收", "验证", "acceptance"]) {
                transferAcceptance = normalizeAcceptance(a)
            } else if !lastUser.isEmpty {
                transferAcceptance = "按对话约定完成，并可复查结果"
            }
        }
        if transferPipeline.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            if let p = extractSection(blob, names: ["产线", "pipeline"]) {
                transferPipeline = String(p.split(separator: "\n").first ?? Substring("dev"))
            } else {
                transferPipeline = "dev"
            }
        }
        if transferPlanMd.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            if lastAssistant.count > 80 {
                transferPlanMd = lastAssistant
            }
        }
        if transferFeasibility.isEmpty {
            transferFeasibility = "ok"
        }
    }

    private func normalizeAcceptance(_ text: String) -> String {
        text
            .split(separator: "\n")
            .map { line -> String in
                var s = String(line).trimmingCharacters(in: .whitespaces)
                while s.hasPrefix("-") || s.hasPrefix("*") {
                    s = String(s.dropFirst()).trimmingCharacters(in: .whitespaces)
                }
                return s
            }
            .filter { !$0.isEmpty }
            .joined(separator: "\n")
    }

    private func extractSection(_ text: String, names: [String]) -> String? {
        for name in names {
            let patterns = ["## \(name)", "**\(name)**", "\(name)：", "\(name):"]
            for p in patterns {
                if let r = text.range(of: p, options: .caseInsensitive) {
                    var rest = String(text[r.upperBound...])
                    if let next = rest.range(of: #"\n#{1,3}\s|\n\*\*"#, options: .regularExpression) {
                        rest = String(rest[..<next.lowerBound])
                    }
                    let cleaned = rest.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !cleaned.isEmpty { return String(cleaned.prefix(1200)) }
                }
            }
        }
        return nil
    }

    private func resetTransferForm() {
        transferTitle = ""
        transferGoal = ""
        transferAcceptance = ""
        transferPipeline = "dev"
        transferExecutor = "opencode"
        transferFeasibility = "ok"
        transferFeasibilityReason = ""
        transferPlanMd = ""
        transferError = nil
        pendingTransferDraft = nil
    }

    func submitTransfer() async {
        guard let pid = selectedProjectId else {
            transferError = "缺少项目"
            showToast("转任务失败：缺少项目")
            return
        }
        if !hubReachable {
            transferError = "Hub 暂不可达"
            showToast("转任务需要 Hub，当前暂不可达")
            return
        }
        if let p = selectedProject, !p.isDispatchable {
            transferError = "当前项目不可下达"
            showToast("转任务失败：当前项目不可下达（请切业务仓）")
            return
        }
        let title = transferTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        let goal = transferGoal.trimmingCharacters(in: .whitespacesAndNewlines)
        let pipeline = transferPipeline.trimmingCharacters(in: .whitespacesAndNewlines)
        let accLines = transferAcceptance
            .split(separator: "\n")
            .map { String($0).trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        if title.isEmpty || goal.isEmpty || pipeline.isEmpty || accLines.isEmpty {
            transferError = "请填齐：标题、目标、产线、至少一条验收"
            showToast("转任务失败：请填齐标题、目标、产线与验收")
            return
        }
        if transferFeasibility == "blocked",
           transferFeasibilityReason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            transferError = "可行性为 blocked 时必须填写原因"
            showToast("转任务失败：标记为阻塞时需写原因")
            return
        }
        if transferFeasibility != "ok" {
            transferError = "可行性非 ok，无法转任务"
            showToast("转任务失败：方案评估为不可执行")
            return
        }
        let chatDigest = chat.messages
            .suffix(8)
            .map { "\($0.role): \(String($0.content.prefix(200)))" }
            .joined(separator: "\n")
        let planBody: String = {
            let custom = transferPlanMd.trimmingCharacters(in: .whitespacesAndNewlines)
            if !custom.isEmpty { return custom }
            return """
            # Plan: \(title)

            ## 目标
            \(goal)

            ## 验收
            \(accLines.map { "- \($0)" }.joined(separator: "\n"))

            ## 对话摘要
            \(chatDigest)
            """
        }()
        busy = true
        defer { busy = false }
        let req = TransferRequest(
            project_id: pid,
            thread_id: ConversationStore.conversationId(for: pid),
            title: title,
            goal: goal,
            acceptance: accLines,
            pipeline: pipeline,
            feasibility: transferFeasibility,
            feasibility_reason: transferFeasibility == "blocked" ? transferFeasibilityReason : nil,
            executor_intent: transferExecutor,
            skills_hint: [],
            plan_md: planBody,
            complexity: "medium"
        )
        do {
            try await prepareClient()
            let resp = try await client.transfer(req)
            let convId = ConversationStore.conversationId(for: pid)
            selectedThreadId = convId
            currentEpicId = resp.epic_id
            // 本机 boundEpicId 立即落盘（右栏 SSOT）
            var snap = threadFlow[convId] ?? FlowThreadSnapshot(
                epicId: resp.epic_id, epic: nil, works: [], headline: "",
                recentEpics: recentEpics, emptyMessage: "", fanoutHint: nil
            )
            snap.epicId = resp.epic_id
            threadFlow[convId] = snap
            persistCurrentThreadSnapshot(threadId: convId)
            showTransferSheet = false
            pendingTransferDraft = nil
            resetTransferForm()
            statusText = "已转任务"
            var toastMsg = "已创建待办 \(resp.epic_id ?? "")"
            if resp.engine_wake?.ok == true {
                toastMsg += " · Engine 已唤醒"
            }
            showToast(toastMsg)
            lastAnimatedEpicId = nil
            flowSplitGeneration &+= 1
            await bindFlowToCurrentThread(preferEpicId: resp.epic_id)
            startFanoutWatchdog(epicId: resp.epic_id)
        } catch {
            let plain = plainTransferError(error)
            transferError = plain
            showToast("转任务失败：\(plain)")
        }
    }

    private func plainTransferError(_ error: Error) -> String {
        let raw = error.localizedDescription
        if raw.contains("missing_title") { return "缺标题" }
        if raw.contains("missing_goal") { return "缺目标" }
        if raw.contains("missing_acceptance") { return "缺验收" }
        if raw.contains("missing_pipeline") { return "缺产线" }
        if raw.contains("feasibility_blocked") { return "方案评估不可执行" }
        if raw.contains("project_not_dispatchable") { return "项目不可下达" }
        if raw.contains("invalid_executor") { return "执行面无效" }
        return raw
    }

    /// 转任务后若 15s 仍无 works，右栏明示原因
    func startFanoutWatchdog(epicId: String?) {
        fanoutWatchTask?.cancel()
        flowFanoutHint = nil
        guard let epicId, !epicId.isEmpty else { return }
        fanoutWatchTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 15_000_000_000)
            guard !Task.isCancelled, let self else { return }
            await MainActor.run {
                guard self.currentEpicId == epicId else { return }
                if self.flowWorks.isEmpty {
                    let stage = self.flowHeadline.isEmpty
                        ? (self.flowEpic?.user_stage ?? self.flowEpic?.headline ?? "待拆解")
                        : self.flowHeadline
                    self.flowFanoutHint =
                        "15 秒内未见拆分（\(stage)）。Engine 可能未扇出，可开运维查看。"
                }
            }
        }
    }

    func clearFanoutHint() {
        flowFanoutHint = nil
        fanoutWatchTask?.cancel()
        fanoutWatchTask = nil
    }

    /// 右栏与当前项目对话绑定：本机 boundEpicId 优先
    func bindFlowToCurrentThread(preferEpicId: String? = nil) async {
        guard let pid = selectedProjectId else { return }
        selectedNodeDetail = nil
        let tid = ConversationStore.conversationId(for: pid)
        selectedThreadId = tid
        do {
            try await prepareClient()
            let epicsResp = try await client.fetchRecentEpicsDetailed(
                projectId: pid,
                threadId: tid
            )
            recentEpics = epicsResp.epics
            let localSnap = threadFlow[tid]
            let localBound = localSnap?.epicId ?? currentEpicId
            let hasLocalFlow =
                (localBound?.isEmpty == false)
                || (localSnap?.epic != nil)
                || !(localSnap?.works.isEmpty ?? true)
                || !flowWorks.isEmpty
            if let prefer = preferEpicId, !prefer.isEmpty {
                currentEpicId = prefer
            } else if let bound = localBound, !bound.isEmpty {
                currentEpicId = bound
            } else if let hint = epicsResp.boundHint, !hint.isEmpty {
                currentEpicId = hint
            } else if let match = epicsResp.epics.first(where: { ($0.thread_id ?? "") == tid })?.epic_id {
                currentEpicId = match
            } else if let first = epicsResp.epics.first?.epic_id {
                currentEpicId = first
            } else if hasLocalFlow {
                await refreshFlow()
                restartFlowSSE()
                return
            } else {
                currentEpicId = nil
                flowEpic = nil
                flowWorks = []
                flowHeadline = ""
                flowEmptyMessage = "编排空闲·等定稿下达（与对话故障无关）"
            }
            persistCurrentThreadSnapshot(threadId: tid)
            await refreshFlow()
            restartFlowSSE()
        } catch {
            flowEmptyMessage = "流程加载失败"
        }
    }

    func refreshEpicList() async {
        await bindFlowToCurrentThread()
    }

    func selectEpic(_ epicId: String) async {
        currentEpicId = epicId
        selectedNodeDetail = nil
        await refreshFlow()
        restartFlowSSE()
    }

    func refreshFlow() async {
        // 合并短时间内的多次刷新，避免 snapshot 风暴打挂 Hub
        flowRefreshTask?.cancel()
        flowRefreshTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 500_000_000)
            guard !Task.isCancelled, let self else { return }
            await self.refreshFlowNow()
        }
    }

    private func refreshFlowNow() async {
        guard let pid = selectedProjectId else { return }
        guard !flowSnapshotPaused else { return }
        do {
            try await prepareClient()
            let snap = try await client.flowSnapshot(projectId: pid, epicId: currentEpicId)
            applySnapshot(snap)
        } catch {
            // SSE 为主；snapshot 失败不刷屏、不改 connected
        }
    }

    private func applySnapshot(_ snap: FlowSnapshot) {
        if snap.empty == true {
            if currentEpicId == nil {
                if !flowWorks.isEmpty { flowWorks = [] }
                if flowEpic != nil { flowEpic = nil }
                if !flowHeadline.isEmpty { flowHeadline = "" }
                let msg = snap.message
                    ?? "编排空闲·等定稿下达（与对话故障无关）"
                if flowEmptyMessage != msg { flowEmptyMessage = msg }
            }
            return
        }
        let works = snap.works ?? []
        let eid = snap.epic_id ?? currentEpicId
        let headline = snap.headline
            ?? snap.epic?.headline
            ?? (works.first(where: \.isActive).map { "正在：\($0.title)" } ?? "")
        let prevEmpty = flowWorks.isEmpty
        let epicChanged = (currentEpicId ?? "") != (eid ?? "")
        // 仅在变化时写入，避免 SSE 重绘冲掉中栏输入焦点
        if flowWorks != works { flowWorks = works }
        if currentEpicId != eid { currentEpicId = eid }
        if flowEpic != snap.epic { flowEpic = snap.epic }
        if flowHeadline != headline { flowHeadline = headline }
        if !flowEmptyMessage.isEmpty { flowEmptyMessage = "" }
        if !works.isEmpty {
            flowFanoutHint = nil
            fanoutWatchTask?.cancel()
            fanoutWatchTask = nil
            // 当前对话 epic：works 首次出现 → 触发拆分动画
            if (prevEmpty || epicChanged), lastAnimatedEpicId != eid {
                lastAnimatedEpicId = eid
                flowSplitGeneration &+= 1
            }
        }
        // 写回当前会话编排缓存
        if let tid = selectedThreadId {
            threadFlow[tid] = FlowThreadSnapshot(
                epicId: currentEpicId,
                epic: flowEpic,
                works: flowWorks,
                headline: flowHeadline,
                recentEpics: recentEpics,
                emptyMessage: flowEmptyMessage,
                fanoutHint: flowFanoutHint
            )
        }
    }

    func openNodeDetail(id: String) {
        if let epic = flowEpic, (epic.id ?? currentEpicId) == id {
            let body = [
                epic.goal_summary.map { "目标：\($0)" },
                epic.pipeline.map { "产线：\($0)" },
                epic.user_stage.map { "阶段：\($0)" },
                epic.description.map { String($0.prefix(1200)) },
            ]
            .compactMap { $0 }
            .joined(separator: "\n\n")
            selectedNodeDetail = FlowNodeDetail(
                id: id,
                kind: "epic",
                title: epic.title ?? id,
                status: epic.user_stage ?? epic.column ?? "",
                body: body.isEmpty ? "暂无详情" : body
            )
            return
        }
        if let work = flowWorks.first(where: { $0.workId == id }) {
            var parts: [String] = [
                "状态：\(work.displayStatus)",
                "执行面：\(work.displayExecutor)",
            ]
            if let deps = work.dependsOnTitles, !deps.isEmpty {
                parts.append("依赖：\(deps.joined(separator: "、"))")
            }
            if let note = work.note, !note.isEmpty {
                parts.append(note)
            }
            if let fail = work.failureNote, !fail.isEmpty {
                parts.append("失败：\(fail)")
            }
            selectedNodeDetail = FlowNodeDetail(
                id: id,
                kind: "work",
                title: work.title,
                status: work.displayStatus,
                body: parts.joined(separator: "\n")
            )
        }
    }

    func dismissNodeDetail() {
        selectedNodeDetail = nil
    }

    func restartFlowSSE() {
        ensureFlowSSE()
    }

    /// 全 App 仅 1 条 flow SSE；仅项目变化时重建，切会话绝不重连
    func ensureFlowSSE() {
        guard let pid = selectedProjectId else {
            flowTask?.cancel()
            flowTask = nil
            flowSSEBoundProjectId = nil
            return
        }
        if flowTask != nil, flowSSEBoundProjectId == pid {
            return
        }
        startProjectFlowSSE(projectId: pid)
    }

    private func startProjectFlowSSE(projectId: String) {
        flowTask?.cancel()
        flowSSEBoundProjectId = projectId
        flowBackoffNs = 3_000_000_000
        flowTask = Task { [weak self] in
            while !Task.isCancelled {
                do {
                    try await self?.prepareClient()
                    await MainActor.run { self?.flowBackoffNs = 3_000_000_000 }
                    try await self?.client.streamFlowEvents(
                        projectId: projectId,
                        epicId: nil
                    ) { event, _ in
                        if ["fanout", "work_status", "epic_created", "executor"].contains(event) {
                            Task { @MainActor in
                                guard let self else { return }
                                guard !self.flowSnapshotPaused else { return }
                                guard self.selectedProjectId == projectId else { return }
                                await self.refreshFlow()
                            }
                        }
                    }
                    try? await Task.sleep(nanoseconds: 2_000_000_000)
                } catch {
                    if Task.isCancelled { break }
                    let delay = await MainActor.run { () -> UInt64 in
                        let d = self?.flowBackoffNs ?? 3_000_000_000
                        self?.flowBackoffNs = min(d + 2_000_000_000, 12_000_000_000)
                        return d
                    }
                    try? await Task.sleep(nanoseconds: delay)
                }
            }
        }
    }


    func openHubInBrowser(route: String = "") {
        var base = serverURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        while base.hasSuffix("/") { base.removeLast() }
        let urlStr: String
        if route.isEmpty {
            urlStr = base
        } else if route.hasPrefix("#") {
            urlStr = base + "/" + route
        } else {
            urlStr = base + "/#/" + route
        }
        if let url = URL(string: urlStr) {
            NSWorkspace.shared.open(url)
        }
    }

    func selectDestination(_ dest: SidebarDestination) {
        let prev = destination
        destination = dest
        switch dest {
        case .chat:
            // 从看板/运维回对话：用本机缓存恢复，禁止空闪、禁止 Hub 空结果冲掉
            if prev != .chat, let pid = selectedProjectId {
                let tid = LocalSessionStore.conversationThreadId(for: pid)
                selectedThreadId = tid
                hydrateThreadFromDisk(projectId: pid, threadId: tid)
                if let cached = threadMessages[tid], !cached.isEmpty {
                    chat.messages = cached
                }
                if let snap = threadFlow[tid] {
                    applyFlowSnapshot(snap)
                }
                refreshCurrentThreadStreaming()
            }
        case .board:
            // 离开对话前落盘，避免回来丢消息/右栏
            if let tid = selectedThreadId {
                persistCurrentThreadSnapshot(threadId: tid)
            }
            let destGen = threadSwitchGeneration
            Task { [destGen] in
                guard self.threadSwitchGeneration == destGen else { return }
                await self.refreshBoard()
            }
        case .ops:
            if let tid = selectedThreadId {
                persistCurrentThreadSnapshot(threadId: tid)
            }
            let destGen = threadSwitchGeneration
            Task { [destGen] in
                guard self.threadSwitchGeneration == destGen else { return }
                await self.refreshOps()
            }
        }
    }

    func refreshBoard() async {
        boardBusy = true
        boardError = nil
        defer { boardBusy = false }
        let ws = selectedProject?.workspace
            ?? selectedProjectId
            ?? "CCC"
        boardWorkspaceLabel = ws
        do {
            try await prepareClient()
            let snap = try await client.fetchBoard(workspace: ws, includeHidden: boardShowHidden)
            boardColumns = snap.columns ?? [:]
        } catch {
            boardError = error.localizedDescription
            boardColumns = [:]
        }
    }

    func setBoardShowHidden(_ show: Bool) async {
        boardShowHidden = show
        await refreshBoard()
    }

    func moveBoardTask(_ task: BoardTask, to: String) async {
        let ws = boardWorkspaceLabel ?? selectedProject?.workspace ?? "CCC"
        do {
            try await prepareClient()
            try await client.moveTask(taskId: task.id, to: to, workspace: ws)
            await refreshBoard()
        } catch {
            boardError = "移动失败: \(error.localizedDescription)"
        }
    }

    func hideCompletedEpics() async {
        let ws = boardWorkspaceLabel ?? selectedProject?.workspace ?? "CCC"
        do {
            try await prepareClient()
            try await client.hideCompletedEpics(workspace: ws)
            // 隐藏后若未开「显示已隐藏」，列表会变少——符合预期
            await refreshBoard()
        } catch {
            boardError = "隐藏失败: \(error.localizedDescription)"
        }
    }

    func reopenBoardTask(_ task: BoardTask, to: String = "planned") async {
        let ws = boardWorkspaceLabel ?? selectedProject?.workspace ?? "CCC"
        do {
            try await prepareClient()
            try await client.reopenTask(taskId: task.id, to: to, workspace: ws)
            await refreshBoard()
        } catch {
            boardError = "重开失败: \(error.localizedDescription)"
        }
    }

    func fetchTaskDetail(_ task: BoardTask) async throws -> BoardTaskDetail {
        try await prepareClient()
        let ws = boardWorkspaceLabel ?? selectedProject?.workspace ?? "CCC"
        return try await client.fetchTaskDetail(taskId: task.id, workspace: ws)
    }

    func refreshOps() async {
        opsBusy = true
        opsError = nil
        defer { opsBusy = false }
        do {
            try await prepareClient()
            // 优先用聚合端点（一次拉全）；回退到分立端点
            if let summary = try? await client.fetchOpsSummary() {
                opsSummary = summary
                opsOverview = summary.overview
                opsRisks = summary.risks?.risks ?? []
                opsRisksCount = summary.risks?.count
                opsRisksHigh = summary.risks?.high
                if let router = summary.router {
                    applyRouterUsage(router)
                }
                return
            }
            async let overview = client.fetchOpsOverview()
            async let risksResp = client.fetchOpsRisks()
            opsOverview = try await overview
            let risks = try await risksResp
            opsRisks = risks.risks ?? []
            opsRisksCount = risks.count
            opsRisksHigh = risks.high
        } catch {
            opsError = error.localizedDescription
        }
    }

    func runDailyReview(workspace: String) async {
        opsAdoptBusy = true
        opsAdoptError = nil
        defer { opsAdoptBusy = false }
        do {
            try await prepareClient()
            try await client.runDailyReview(workspace: workspace)
            await refreshOps()
        } catch {
            opsAdoptError = "日审失败: \(error.localizedDescription)"
        }
    }

    func adoptSuggestion(workspace: String, title: String, description: String, tags: [String] = ["ops-auto"]) async {
        opsAdoptBusy = true
        opsAdoptError = nil
        defer { opsAdoptBusy = false }
        do {
            try await prepareClient()
            try await client.adoptSuggestion(workspace: workspace, title: title, description: description, tags: tags)
        } catch {
            opsAdoptError = "采纳失败: \(error.localizedDescription)"
        }
    }

    // MARK: - Router usage (toolbar)

    func startRouterUsagePolling() {
        routerUsageTask?.cancel()
        routerUsageTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { break }
                // 流式对话中降频：避免顶栏轮询加重「全家在忙」假死感
                let streaming = !self.liveStreamingThreadIds.isEmpty || self.currentThreadStreaming
                if !streaming {
                    await self.refreshRouterUsage()
                }
                let sleepNs: UInt64 = streaming ? 15_000_000_000 : 5_000_000_000
                try? await Task.sleep(nanoseconds: sleepNs)
            }
        }
    }

    func refreshRouterUsage() async {
        do {
            // 轻量拉取：不走 prepareClient/ensureLocalAgent，避免每 5s 挤占 Hub/Agent
            let resp = try await client.fetchRouterUsage()
            applyRouterUsage(resp)
            if resp.ok == true || resp.tiers != nil {
                if !hubReachable {
                    hubReachable = true
                    updateConnectionStatusText(localOK: agentMode == "local", hubOK: true)
                }
            }
        } catch {
            // fail-soft：保留上次总量；窗口增量归零；不把整 App 打成离线
            if routerUsage == nil {
                applyRouterUsage(
                    RouterUsageResp(
                        ok: false,
                        tiers: RouterUsageTiers(
                            flash: RouterTierCount(requests_today: 0, tokens_today: 0),
                            code: RouterTierCount(requests_today: 0, tokens_today: 0),
                            pro: RouterTierCount(requests_today: 0, tokens_today: 0)
                        ),
                        source: nil,
                        error: error.localizedDescription
                    )
                )
            } else {
                routerWindowDelta = ["flash": 0, "code": 0, "pro": 0]
            }
        }
    }

    /// 今日总量（中转站 requests_today）
    func routerRequestCount(_ tier: String) -> Int {
        guard let t = routerUsage?.tiers else { return 0 }
        switch tier {
        case "flash": return t.flash?.requests ?? 0
        case "code": return t.code?.requests ?? 0
        case "pro": return t.pro?.requests ?? 0
        default: return 0
        }
    }

    /// 近 5 秒窗口内新增（+ 号后；无调用则为 0）
    func routerLiveCount(_ tier: String) -> Int {
        routerWindowDelta[tier] ?? 0
    }

    private func applyRouterUsage(_ resp: RouterUsageResp) {
        routerUsage = resp
        var window: [String: Int] = [:]
        for tier in ["flash", "code", "pro"] {
            let total = routerRequestCount(from: resp, tier: tier)
            if let prev = routerLastTotals[tier] {
                window[tier] = max(0, total - prev)
            } else {
                // 首轮只定基线，不把全日累计当成「实时」
                window[tier] = 0
            }
            routerLastTotals[tier] = total
        }
        routerWindowDelta = window
    }

    private func routerRequestCount(from resp: RouterUsageResp, tier: String) -> Int {
        guard let t = resp.tiers else { return 0 }
        switch tier {
        case "flash": return t.flash?.requests ?? 0
        case "code": return t.code?.requests ?? 0
        case "pro": return t.pro?.requests ?? 0
        default: return 0
        }
    }
}
