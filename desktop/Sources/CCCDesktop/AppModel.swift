import AppKit
import Foundation
import SwiftUI

@MainActor
final class AppModel: ObservableObject {
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
    @Published var messages: [ChatMessage] = []
    @Published var draft: String = ""
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

    @Published var flowEmptyMessage = "聊透后转任务，编排将在此展开"
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

    // Board
    @Published var boardColumns: [String: [BoardTask]] = [:]
    @Published var boardBusy = false
    @Published var boardError: String?
    @Published var boardWorkspaceLabel: String?

    // Ops
    @Published var opsOverview: OpsOverview?
    @Published var opsRisks: [OpsRisk] = []
    @Published var opsRisksCount: Int?
    @Published var opsRisksHigh: Int?
    @Published var opsBusy = false
    @Published var opsError: String?

    private var flowTask: Task<Void, Never>?
    private var flowBackoffNs: UInt64 = 3_000_000_000
    private var flowRefreshTask: Task<Void, Never>?
    private var flowSSEBoundProjectId: String?
    private var flowSnapshotPaused = false
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
    /// 本机落盘节流
    private var diskSaveTask: Task<Void, Never>?
    private var pendingDiskThreadId: String?

    /// 兼容旧 UI 命名：仅反映「当前会话」是否在生成
    var isStreaming: Bool { currentThreadStreaming }

    init() {
        let fallback = URL(string: "http://192.168.3.116:7777/")!
        client = APIClient(baseURL: fallback, user: "ccc", password: "ccc")
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
        let agentStr = (agentRaw?.isEmpty == false ? agentRaw! : agentURLString)
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
            await warmLocalAgentNow(base: candidate)
            startWarmLoopIfNeeded()
            return candidate
        }

        // 尝试自启
        statusText = "连接 Agent…"
        let homeHint = cccHomePath.trimmingCharacters(in: .whitespacesAndNewlines)
        let launch = AgentSidecarLauncher.ensureRunning(
            cccHomeHint: homeHint.isEmpty ? nil : homeHint
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
                await warmLocalAgentNow(base: candidate)
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

    private func warmLocalAgentNow(base: URL? = nil) async {
        let ok = await client.warmLocalAgent(base: base ?? cachedAgentBaseURL)
        if ok { lastWarmAt = Date() }
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

    /// 发送前：距上次 warm >120s 则补暖
    private func warmBeforeSendIfNeeded() async {
        guard agentMode == "local" else { return }
        if let last = lastWarmAt, Date().timeIntervalSince(last) < 120 { return }
        await warmLocalAgentNow()
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
        draft = "UI自检：请只回复四个字「自检OK」"
        await sendMessage()
        let assistant = messages.last(where: { $0.role == "assistant" && !$0.isStreaming })?.content ?? ""
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
        if let tid = selectedThreadId {
            persistCurrentThreadSnapshot(threadId: tid)
        }
        selectedProjectId = id
        persistedProjectId = id
        expandedProjectIds.insert(id)
        if switching {
            selectedThreadId = nil
            messages = []
            applyFlowSnapshot(nil)
            refreshCurrentThreadStreaming()
            selectedNodeDetail = nil
            // 项目变了才重建 flow SSE；会话切换绝不重连
            ensureFlowSSE()
        }
        await refreshThreads(projectId: id)
        // 不自动绑旧 flow；等用户点会话
    }

    func toggleProjectExpanded(_ id: String) {
        if expandedProjectIds.contains(id) {
            expandedProjectIds.remove(id)
        } else {
            expandedProjectIds.insert(id)
        }
    }

    func refreshThreads(projectId: String) async {
        let local = LocalSessionStore.threadsAsDesktop(projectId: projectId)
        do {
            try await prepareClient()
            let remote = try await client.fetchThreads(projectId: projectId)
            threads = mergeThreadLists(remote: remote, local: local)
            hubReachable = true
        } catch {
            // Hub 不可达：只用本机索引
            if !local.isEmpty {
                threads = local
            } else if threads.isEmpty {
                showToast("会话列表暂不可用（Hub 不可达）")
            }
        }
        // 预热最近会话进 RAM，切会话秒开
        prefetchRecentThreads(projectId: projectId, limit: 12)
    }

    private func prefetchRecentThreads(projectId: String, limit: Int) {
        let ids = threads.prefix(limit).map(\.thread_id)
        for tid in ids {
            hydrateThreadFromDisk(projectId: projectId, threadId: tid)
        }
    }

    private func mergeThreadLists(remote: [DesktopThread], local: [DesktopThread]) -> [DesktopThread] {
        var byId: [String: DesktopThread] = [:]
        for t in remote { byId[t.thread_id] = t }
        for t in local {
            if byId[t.thread_id] == nil {
                byId[t.thread_id] = t
            } else if let r = byId[t.thread_id],
                      (t.updated_at ?? "") > (r.updated_at ?? "") {
                byId[t.thread_id] = DesktopThread(
                    thread_id: t.thread_id,
                    title: t.title ?? r.title,
                    updated_at: t.updated_at ?? r.updated_at,
                    project_id: t.project_id ?? r.project_id
                )
            }
        }
        return byId.values.sorted { ($0.updated_at ?? "") > ($1.updated_at ?? "") }
    }

    func newThread() async {
        guard let pid = selectedProjectId else {
            showToast("请先选择项目")
            return
        }
        if let old = selectedThreadId {
            persistCurrentThreadSnapshot(threadId: old)
        }
        busy = true
        defer { busy = false }
        let title = "方案讨论"
        let tid: String
        do {
            try await prepareClient()
            let resp = try await client.createThread(projectId: pid, title: title)
            tid = resp.thread_id
            hubReachable = true
        } catch {
            // 本机会话，Hub 稍后镜像
            tid = "local-\(UUID().uuidString.prefix(8).lowercased())"
            showToast("Hub 暂不可达，已建本机会话")
        }
        activateNewThread(projectId: pid, threadId: tid, title: title)
        await refreshThreads(projectId: pid)
        destination = .chat
        ensureFlowSSE()
    }

    private func activateNewThread(projectId: String, threadId: String, title: String) {
        threadSwitchGeneration &+= 1
        selectedThreadId = threadId
        messages = []
        threadMessages[threadId] = []
        pendingTransferDraft = nil
        lastAnimatedEpicId = nil
        flowSplitGeneration &+= 1
        applyFlowSnapshot(nil)
        flowEmptyMessage = "在本对话中转任务后，编排会出现在这里"
        let snap = FlowThreadSnapshot(
            epicId: nil, epic: nil, works: [], headline: "",
            recentEpics: [], emptyMessage: flowEmptyMessage, fanoutHint: nil
        )
        threadFlow[threadId] = snap
        LocalSessionStore.saveMessages(
            projectId: projectId,
            threadId: threadId,
            messages: [],
            title: title,
            flow: snap,
            needsHubSync: threadId.hasPrefix("local-")
        )
        if threadId.hasPrefix("local-") {
            LocalSessionStore.enqueueSync(projectId: projectId, threadId: threadId)
        }
        refreshCurrentThreadStreaming()
    }

    func openThread(_ id: String) async {
        guard let pid = selectedProjectId else { return }

        // 1) 落盘当前会话（消息 + 右栏）— 先刷盘再切，避免节流丢写
        if let old = selectedThreadId, old != id {
            pendingDiskThreadId = old
            flushDiskSave()
            persistCurrentThreadSnapshot(threadId: old)
        }

        // 2) 秒切：磁盘优先（含 RAM 已空被 Hub 冲掉的情况）
        threadSwitchGeneration &+= 1
        let gen = threadSwitchGeneration
        selectedThreadId = id
        destination = .chat

        hydrateThreadFromDisk(projectId: pid, threadId: id)
        messages = threadMessages[id] ?? []
        pendingTransferDraft = nil
        if let cached = threadMessages[id],
           let lastAsst = cached.last(where: { $0.role == "assistant" && !$0.isStreaming }) {
            refreshTransferDraft(from: lastAsst.content)
        }
        lastAnimatedEpicId = nil
        flowSplitGeneration &+= 1
        applyFlowSnapshot(threadFlow[id])
        refreshCurrentThreadStreaming()
        updateFlowSnapshotPause()
        lastError = nil

        // 3) 后台同步 Hub（不得用更空结果盖掉本机）
        Task { [weak self] in
            guard let self else { return }
            await self.syncThreadFromServer(projectId: pid, threadId: id, generation: gen)
            await self.syncFlowFromServer(projectId: pid, threadId: id, generation: gen)
            try? await self.prepareClient()
            // 对话预热只走本机 sidecar；编排暖槽与可聊无关
        }
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
        threadMessages[threadId] = messages
        let snap = FlowThreadSnapshot(
            epicId: currentEpicId,
            epic: flowEpic,
            works: flowWorks,
            headline: flowHeadline,
            recentEpics: recentEpics,
            emptyMessage: flowEmptyMessage,
            fanoutHint: flowFanoutHint
        )
        threadFlow[threadId] = snap
        if let pid = selectedProjectId {
            let title = threads.first(where: { $0.thread_id == threadId })?.title
            LocalSessionStore.saveMessages(
                projectId: pid,
                threadId: threadId,
                messages: messages,
                title: title,
                flow: snap
            )
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
            flowEmptyMessage = "本对话尚未转任务；聊透后点「转任务」"
            flowFanoutHint = nil
            selectedNodeDetail = nil
        }
    }

    /// 后台拉消息；Hub 更空时保留本机；生成中禁止覆盖
    private func syncThreadFromServer(projectId: String, threadId: String, generation: UInt64) async {
        if streamingThreadIds.contains(threadId) { return }
        // 同步前再灌一次盘，避免 RAM 已被冲空
        hydrateThreadFromDisk(projectId: projectId, threadId: threadId)
        do {
            try await prepareClient()
            let detail = try await client.fetchThread(projectId: projectId, threadId: threadId)
            guard threadSwitchGeneration == generation, selectedThreadId == threadId else { return }
            var loaded = detail.messages ?? []
            let cached = threadMessages[threadId]
                ?? LocalSessionStore.load(projectId: projectId, threadId: threadId)?.messages
                ?? []

            // Hub 空 / 明显更短：本机优先，禁止回写空盘
            let hubScore = LocalSessionStore.messageScore(loaded)
            let localScore = LocalSessionStore.messageScore(cached)
            if hubScore == 0 && localScore > 0 {
                return
            }
            if localScore > hubScore {
                // 仍合并 tool_steps，但不丢本地正文
                loaded = mergeMessagesPreservingTools(server: loaded, local: cached)
                if LocalSessionStore.messageScore(loaded) < localScore {
                    loaded = cached
                }
            } else if !cached.isEmpty {
                loaded = mergeMessagesPreservingTools(server: loaded, local: cached)
            }

            // 流式尾巴
            if let live = cached.last(where: \.isStreaming) {
                if !loaded.contains(where: { $0.id == live.id }) {
                    if let u = cached.last(where: { $0.role == "user" }),
                       loaded.last?.role != "user" {
                        loaded.append(u)
                    }
                    loaded.append(live)
                }
            }
            threadMessages[threadId] = loaded
            if selectedThreadId == threadId {
                messages = loaded
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
            // Hub 失败：强制本机盘回填 UI
            hydrateThreadFromDisk(projectId: projectId, threadId: threadId)
            if selectedThreadId == threadId {
                messages = threadMessages[threadId] ?? []
            }
        }
    }

    /// Hub 有 steps 用 Hub；Hub 无而本地有则保留本地 steps
    private func mergeMessagesPreservingTools(server: [ChatMessage], local: [ChatMessage]) -> [ChatMessage] {
        var result = server
        for (i, sm) in result.enumerated() where sm.role == "assistant" {
            if !sm.toolSteps.isEmpty { continue }
            if let lm = local.last(where: {
                $0.role == "assistant"
                    && !$0.toolSteps.isEmpty
                    && ($0.content == sm.content || sm.content.isEmpty || $0.content.hasPrefix(String(sm.content.prefix(40))))
            }) {
                result[i].toolSteps = lm.toolSteps
                result[i].filesChanged = max(sm.filesChanged, lm.filesChanged)
                result[i].toolsFinished = lm.toolsFinished || sm.toolsFinished
            }
        }
        // 本地助手条数更多时，补上尚未落盘的尾部
        if local.filter({ $0.role == "assistant" }).count > result.filter({ $0.role == "assistant" }).count,
           let lastLocal = local.last(where: { $0.role == "assistant" && !$0.toolSteps.isEmpty }),
           !(result.last?.toolSteps.isEmpty == false) {
            if result.last?.role == "assistant" {
                result[result.count - 1].toolSteps = lastLocal.toolSteps
                result[result.count - 1].filesChanged = lastLocal.filesChanged
                result[result.count - 1].toolsFinished = lastLocal.toolsFinished
            }
        }
        return result
    }

    private func syncFlowFromServer(projectId: String, threadId: String, generation: UInt64) async {
        do {
            try await prepareClient()
            let epics = try await client.fetchRecentEpics(projectId: projectId, threadId: threadId)
            guard threadSwitchGeneration == generation, selectedThreadId == threadId else { return }
            // 右栏只投影「本 thread」：以该会话 epic 为准，禁止沿用上一会话 currentEpicId
            recentEpics = epics
            let bound = epics.first?.epic_id
            currentEpicId = bound
            if bound == nil {
                flowEpic = nil
                flowWorks = []
                flowHeadline = ""
                flowEmptyMessage = "本对话尚未转任务；聊透后点「转任务」"
                flowFanoutHint = nil
            } else {
                await refreshFlowNow()
            }
            persistCurrentThreadSnapshot(threadId: threadId)
            ensureFlowSSE()
        } catch {
            if selectedThreadId == threadId, threadFlow[threadId] == nil {
                flowEmptyMessage = "流程加载失败"
            }
        }
    }

    func beginRenameThread(_ thread: DesktopThread) {
        renameThreadId = thread.thread_id
        renameDraft = thread.title ?? "新对话"
    }

    func commitRenameThread() async {
        guard let pid = selectedProjectId, let tid = renameThreadId else { return }
        let title = renameDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !title.isEmpty else {
            renameThreadId = nil
            return
        }
        LocalSessionStore.rename(projectId: pid, threadId: tid, title: title)
        renameThreadId = nil
        do {
            try await prepareClient()
            try await client.renameThread(projectId: pid, threadId: tid, title: title)
        } catch {
            showToast("已改本机标题；Hub 同步失败")
        }
        await refreshThreads(projectId: pid)
    }

    func deleteThread(_ threadId: String) async {
        guard let pid = selectedProjectId else { return }
        chatTasks[threadId]?.cancel()
        chatTasks[threadId] = nil
        streamingThreadIds.remove(threadId)
        threadMessages[threadId] = nil
        threadFlow[threadId] = nil
        LocalSessionStore.delete(projectId: pid, threadId: threadId)
        if selectedThreadId == threadId {
            selectedThreadId = nil
            messages = []
            currentEpicId = nil
            flowEpic = nil
            flowWorks = []
            recentEpics = []
        }
        refreshCurrentThreadStreaming()
        do {
            try await prepareClient()
            try await client.deleteThread(projectId: pid, threadId: threadId)
        } catch {
            // 本机已删；Hub 失败可忽略
        }
        await refreshThreads(projectId: pid)
        await bindFlowToCurrentThread()
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
            messages = msgs
        }
        scheduleDiskSave(threadId: threadId)
    }

    /// 本机落盘节流 ~300ms
    private func scheduleDiskSave(threadId: String) {
        pendingDiskThreadId = threadId
        diskSaveTask?.cancel()
        diskSaveTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 300_000_000)
            guard !Task.isCancelled, let self else { return }
            await MainActor.run {
                self.flushDiskSave()
            }
        }
    }

    private func flushDiskSave() {
        guard let tid = pendingDiskThreadId ?? selectedThreadId,
              let pid = selectedProjectId
        else { return }
        let msgs = threadMessages[tid] ?? messages
        let title = threads.first(where: { $0.thread_id == tid })?.title
        let flow = threadFlow[tid]
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
        var msgs = threadMessages[threadId] ?? (selectedThreadId == threadId ? messages : [])
        body(&msgs)
        persistMessages(for: threadId, msgs)
    }

    /// Phase 1.4: delta 热路径专用——直接下标改 messages[i].content，避免整数组重赋值。
    /// 仍触发 @Published willSet（subscript setter），但 SwiftUI 可按 row diff，不重建 LazyVStack。
    private func applyDeltaInPlace(threadId: String, assistantId: UUID, chunk: String) {
        if var msgs = threadMessages[threadId],
           let idx = msgs.firstIndex(where: { $0.id == assistantId }) {
            msgs[idx].content += chunk
            threadMessages[threadId] = msgs
        }
        if selectedThreadId == threadId,
           let mIdx = messages.firstIndex(where: { $0.id == assistantId }) {
            messages[mIdx].content += chunk
        } else if selectedThreadId == threadId, let msgs = threadMessages[threadId] {
            // 兜底：messages 与 threadMessages 不同步时整表对齐一次
            messages = msgs
        }
        scheduleDiskSave(threadId: threadId)
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
            if item.attempts >= LocalSessionStore.maxSyncAttempts { continue }
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
        refreshCurrentThreadStreaming()
        updateFlowSnapshotPause()
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
        var tid = selectedThreadId
        if tid == nil {
            let title = String(trimmed.prefix(40))
            do {
                try await prepareClient()
                let t = try await client.createThread(projectId: pid, title: title)
                tid = t.thread_id
                activateNewThread(projectId: pid, threadId: t.thread_id, title: title)
                await refreshThreads(projectId: pid)
            } catch {
                // Hub 抖：本机会话仍可发
                let localId = "local-\(UUID().uuidString.prefix(8).lowercased())"
                tid = localId
                activateNewThread(projectId: pid, threadId: localId, title: title)
                await refreshThreads(projectId: pid)
                showToast("Hub 暂不可达，已用本机会话继续")
            }
        }
        guard let threadId = tid else { return false }
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
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        draft = ""
        sendUserMessage(text, stopAndSend: stopAndSend)
    }

    func sendMessage() async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        draft = ""
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
                Task { await self.refreshFlow() }
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
                setStatusImmediate("连接 Agent…")
            }
            try await prepareClient()
            // 业务仓未绑本机路径时提示一次（不阻断）
            if localPath(for: projectId) == nil,
               let p = projects.first(where: { $0.id == projectId }), p.isDispatchable {
                showToast("未绑定本机工作区，sidecar 可能扫错目录 — 设置里为当前项目填写路径")
            }
            await warmBeforeSendIfNeeded()
            if selectedThreadId == threadId {
                setStatusImmediate("本机生成中…")
            }
            let outbound = (threadMessages[threadId] ?? []).filter { $0.id != assistantId }
            let mode = Self.promptMode(forUserText: text)

            // 同会话自动重试 1 次（保留已生成的本地内容，清空半截助手再流）
            var streamError: Error?
            for attempt in 1...2 {
                do {
                    if attempt == 2 {
                        if selectedThreadId == threadId {
                            setStatusImmediate("重连中…")
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
                        promptMode: mode
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
                updateConnectionStatusText(localOK: canChat, hubOK: hubReachable)
            }
            // 解析定稿块
            if let asst = (threadMessages[threadId] ?? []).last(where: { $0.id == assistantId }) {
                refreshTransferDraft(from: asst.content)
            }
            // 本机立即落盘 + Hub 异步镜像
            flushDiskSave()
            let synced = (threadMessages[threadId] ?? messages)
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
        case .delta(let chunk):
            applyDeltaInPlace(threadId: threadId, assistantId: assistantId, chunk: chunk)
            return
        case .toolUse, .toolResult, .cost, .done:
            break
        }
        mutateThreadMessages(threadId: threadId) { msgs in
            guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
            switch event {
            case .delta:
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
            case .cost:
                break
            case .done:
                for i in msgs[idx].toolSteps.indices where msgs[idx].toolSteps[i].status == .running {
                    msgs[idx].toolSteps[i].status = .done
                }
                if !msgs[idx].toolSteps.isEmpty {
                    msgs[idx].toolsFinished = true
                }
            }
        }
        if case .toolUse = event {
            objectWillChange.send()
        } else if case .toolResult = event {
            objectWillChange.send()
        }
    }

    func cancelChat(threadId: String? = nil, silent: Bool = false) {
        let tid = threadId ?? selectedThreadId
        guard let tid else { return }
        chatTasks[tid]?.cancel()
        chatTasks[tid] = nil
        setThreadStreaming(tid, false)
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
        messages
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
        let msgs = threadMessages[tid] ?? messages
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
        let assistants = messages.filter { $0.role == "assistant" && !$0.isStreaming }.map(\.content)
        if let last = assistants.last, let d = TransferDraftParser.parse(from: last) {
            applyTransferDraft(d, fallbackContent: nil)
            pendingTransferDraft = d
            return
        }
        let users = messages.filter { $0.role == "user" }.map(\.content)
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
        let chatDigest = messages
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
            thread_id: selectedThreadId,
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
            currentEpicId = resp.epic_id
            showTransferSheet = false
            pendingTransferDraft = nil
            resetTransferForm()
            statusText = "已转任务"
            var toastMsg = "已创建待办 \(resp.epic_id ?? "")"
            if resp.engine_wake?.ok == true {
                toastMsg += " · Engine 已唤醒"
            }
            showToast(toastMsg)
            // 拆解中：先脉冲空 works，等 fanout
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

    /// 右栏与当前对话深度绑定：只展示本 thread 转出的任务
    func bindFlowToCurrentThread(preferEpicId: String? = nil) async {
        guard let pid = selectedProjectId else { return }
        selectedNodeDetail = nil
        guard let tid = selectedThreadId, !tid.isEmpty else {
            currentEpicId = nil
            recentEpics = []
            flowEpic = nil
            flowWorks = []
            flowHeadline = ""
            flowEmptyMessage = "选择或新建对话后，转任务会出现在这里"
            restartFlowSSE()
            return
        }
        do {
            try await prepareClient()
            recentEpics = try await client.fetchRecentEpics(projectId: pid, threadId: tid)
            if let prefer = preferEpicId, !prefer.isEmpty {
                currentEpicId = prefer
            } else if let first = recentEpics.first?.epic_id {
                currentEpicId = first
            } else {
                currentEpicId = nil
                flowEpic = nil
                flowWorks = []
                flowHeadline = ""
                flowEmptyMessage = "本对话尚未转任务；聊透后点「转任务」"
            }
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
                let msg = snap.message ?? "聊透后转任务，编排将在此展开"
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
        destination = dest
        switch dest {
        case .chat:
            break
        case .board:
            Task { await refreshBoard() }
        case .ops:
            Task { await refreshOps() }
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
            let snap = try await client.fetchBoard(workspace: ws)
            boardColumns = snap.columns ?? [:]
        } catch {
            boardError = error.localizedDescription
            boardColumns = [:]
        }
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
}
