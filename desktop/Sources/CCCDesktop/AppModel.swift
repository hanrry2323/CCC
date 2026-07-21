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
    /// 首启用法横幅是否已关闭
    @AppStorage("ccc.dismissedFirstRunTip") var dismissedFirstRunTip: Bool = false
    /// 对话模型偏好（请求级传 sidecar；flash/code/sonnet/haiku）
    @AppStorage("ccc.preferredModel") var preferredModel: String = "flash"
    /// discuss | engineer
    @AppStorage("ccc.preferredToolMode") var preferredToolMode: String = "discuss"

    @Published var projects: [DesktopProject] = []
    @Published var threads: [DesktopThread] = []
    @Published var selectedProjectId: String?
    @Published var selectedThreadId: String?
    /// Context 面板（本会话用量 / compact）
    @Published var isContextPanelPresented = false
    /// Composer 附件（按当前窗发送时消费）
    @Published var composerAttachments: [ComposerAttachment] = []
    /// 工程师模式切换确认
    @Published var confirmEngineerMode = false
    /// Sidecar 回显模型名（health）
    @Published var sidecarReportedModel: String = ""
    /// 对话状态（messages + draft），独立 ObservableObject 隔离 delta 通知
    @Published var chat = ChatState()
    @Published var statusText: String = "未连接"
    /// "local" = 本机 sidecar 可聊；"none" = 本机 Agent 未就绪（禁止 Hub 聊天回退）
    @Published var agentMode: String = "none"
    /// 状态栏：本机 Agent / 本机 Agent 未就绪
    @Published var agentBadge: String = "本机 Agent 未就绪"
    /// 可聊 = sidecar 健康（与 hubReachable 独立）
    var canChat: Bool { agentMode == "local" }
    /// 可转任务 = Hub 可达 + 业务仓可下达（默认看全局选中；多窗请用 canTransfer(projectId:)）
    var canTransfer: Bool {
        canTransfer(projectId: selectedProjectId)
    }

    func canTransfer(projectId: String?) -> Bool {
        guard hubReachable, let projectId else { return false }
        return projects.first(where: { $0.id == projectId })?.isDispatchable == true
    }

    /// sheet 是否应对某 thread 展示
    func isTransferSheetPresented(for threadId: String?) -> Bool {
        guard let threadId, let open = transferSheetThreadId else { return false }
        return open == threadId
    }
    @Published var busy = false
    /// 界面可用：本机可聊或有项目缓存（≠ 可聊；可聊看 canChat）
    @Published var connected = false
    /// Hub projects/API 是否刚探测成功（转任务/flow 需要）
    @Published var hubReachable = false
    /// 兼容旧路径 / smoke；多窗 UI 用 WindowChatState.destination
    @Published var destination: SidebarDestination = .chat
    @Published var toast: String?
    @Published var showSettingsHint = false

    /// 当前打开的转任务 sheet 所属 thread；nil=未打开（多窗只有匹配 tid 的窗弹 sheet）
    @Published var transferSheetThreadId: String?
    /// 解析到的定稿条（消息下「确认转任务」）——仅镜像「全局选中」线程；多窗请用 threadTransferDraft
    @Published var pendingTransferDraft: TransferDraft?
    /// 按 thread 的投递态（草稿 / 排队 / 已投递 / 已受理）
    @Published private(set) var transferDeliveryByThread: [String: TransferDeliveryPhase] = [:]
    /// OpenCode 式：定稿条按 session/thread 隔离，避免他窗切项目冲掉本窗条
    @Published private(set) var threadTransferDraft: [String: TransferDraft] = [:]
    /// 转任务表单字段按 thread 隔离（不仅是 draft 条）
    @Published private(set) var threadTransferForms: [String: TransferFormState] = [:]
    /// 右栏拆分动画世代（works 0→N 时递增；切会话重置）
    @Published var flowSplitGeneration: UInt64 = 0
    private var lastAnimatedEpicId: String?

    @Published var flowEmptyMessage = "编排空闲 · 下一笔定稿后出现在这里"
    @Published var flowWorks: [FlowWork] = []
    @Published var flowEpic: FlowEpic?
    @Published var flowHeadline: String = ""
    @Published var currentEpicId: String?
    @Published var recentEpics: [FlowEpicRef] = []
    @Published var selectedNodeDetail: FlowNodeDetail?
    @Published var lastError: String?
    /// 最近一次本条对话失败（状态栏可重试/清槽）
    @Published var lastTurnFailure: ChatTurnFailure?
    @Published var expandedProjectIds: Set<String> = []
    @Published var renameThreadId: String?
    @Published var renameDraft: String = ""

    /// 转任务后扇出超时提示（右栏）
    @Published var flowFanoutHint: String?
    /// Phase9：abnormal / failed 止损提示（右栏红条）
    @Published var flowStopLossHint: String?
    /// 避免同一 epic 反复 toast
    private var lastStopLossToastKey: String?
    /// 当前选中会话是否正在生成（按会话，非全局）
    @Published var currentThreadStreaming = false
    /// 发送失败时回填输入框（一次性）
    @Published var composerBounce: String?
    /// 回填目标线程；多窗只吃本窗 tid，避免串到他窗输入框
    @Published var composerBounceThreadId: String?
    /// 消息「预览」全文（对齐旧 Hub）
    @Published var previewMarkdown: String?
    /// 当前选中会话累计 token（由 threadSessionTokens 镜像；UI 显示用）
    @Published var sessionTokens: Int = 0
    /// 每 thread 独立 token，避免 A 会话触发 B 压缩
    private var threadSessionTokens: [String: Int] = [:]

    func sessionTokenCount(for threadId: String) -> Int {
        threadSessionTokens[threadId] ?? (selectedThreadId == threadId ? sessionTokens : 0)
    }
    /// 每 thread 的 loop-code resume id（持续对话 SSOT，与盘上 Record 同步）
    private var threadClaudeSessionIds: [String: String] = [:]

    func hasResume(for threadId: String) -> Bool {
        let sid = threadClaudeSessionIds[threadId]?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return !sid.isEmpty
    }
    /// 显示压缩阈值（token）；超此触发 agent session 重置注入摘要
    static let agentCompactTokenThreshold = 80_000
    /// 项目后台任务态（卡片灯用）：projectId → 状态键（idle/pending/in_progress/testing/done/failed）
    @Published var projectTaskState: [String: String] = [:]
    /// 项目对话流式态：projectId → "idle"/"text"/"tool"
    @Published var projectConvState: [String: String] = [:]
    /// 会话未读（流结束后非焦点窗）
    @Published var threadUnread: Set<String> = []
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
    @Published var inboxProposals: [InboxProposal] = []
    @Published var inboxAdoptBusy = false
    /// 顶栏：本机 Agent 大模型调用（日总量 + 近 5 秒）
    @Published private(set) var agentLLMDailyCount: Int = 0
    @Published private(set) var agentLLMRecent5s: Int = 0
    /// 单调递增 tick：强制 Titlebar accessory 刷新
    @Published private(set) var agentUsageTick: UInt64 = 0
    private var agentLLMCallTimestamps: [Date] = []
    private var agentUsageTask: Task<Void, Never>?
    private static let agentLLMDayKey = "ccc.agentLLM.day"
    private static let agentLLMDailyKey = "ccc.agentLLM.dailyCount"

    /// 每项目一条 Flow SSE（多窗同时盯不同项目时并行订阅）
    private var flowSSETasks: [String: Task<Void, Never>] = [:]
    private var flowBackoffNs: [String: UInt64] = [:]
    private var flowRefreshTasks: [String: Task<Void, Never>] = [:]
    private var flowSnapshotPaused = false
    /// 本机 sidecar 可多路并行（对话面；无 Hub chat）
    private var activeChatThreadId: String?
    /// 每会话独立对话流 task
    private var chatTasks: [String: Task<Void, Never>] = [:]
    /// 每线程当前 turn id：用于拒绝旧 SSE / 重试串流的迟到事件
    private var activeTurnIds: [String: String] = [:]
    private var streamingThreadIds: Set<String> = []
    /// 供侧栏观察多路生成状态（与 streamingThreadIds 同步）
    @Published private(set) var liveStreamingThreadIds: Set<String> = []
    private static let maxParallelLocalChats = 3
    /// 会话消息本地缓存（切会话秒开，不堵 HTTP）——OpenCode `data.message[sessionID]` 同构
    private var threadMessages: [String: [ChatMessage]] = [:]
    /// 每线程消息修订号：仅消息变更时 bump（勿与 flow 共用，否则右栏 SSE 会拖聊天重滚）
    @Published private(set) var threadRevision: [String: UInt64] = [:]
    /// 每线程编排修订号：仅 threadFlow 变更；FlowRail 订阅，聊天区不订阅
    @Published private(set) var threadFlowRevision: [String: UInt64] = [:]
    /// 每线程流式状态文案（连接中/生成中）；禁止单全局 streamStatus 串台
    @Published private(set) var threadStreamStatus: [String: String] = [:]
    /// 会话右栏编排缓存（与对话隔离）——按 threadId 读，不靠全局 flow* 当多窗 SSOT
    private var threadFlow: [String: FlowThreadSnapshot] = [:]
    /// 打开窗焦点项目 refcount（OpenCode：live sync 覆盖所有可见 session/directory）
    private var focusedProjectRefCounts: [String: Int] = [:]
    /// 防止慢 HTTP 回写错会话
    private var threadSwitchGeneration: UInt64 = 0
    private var fanoutWatchTask: Task<Void, Never>?
    private var client: APIClient
    /// UI smoke 写入路径（仅 CCC_DESKTOP_UI_SMOKE=1）
    private(set) var uiSmokeOutPath: String?
    /// sidecar 探测成功缓存（10s；失败立即失效，缩短假健康窗口）
    private var agentProbeOKUntil: Date?
    private var cachedAgentBaseURL: URL?
    private var didToastHubFallback = false

    /// 兼容多会话：从 projectId 推导主线程 id（兼容旧 ::main 迁移）
    private func threadIdForProject(_ projectId: String?) -> String {
        guard let pid = projectId, !pid.isEmpty else { return "" }
        return LocalSessionStore.migrateLegacyThread(projectId: pid)
    }

    /// 解析实际会话：显式 tid（须属 pid）→ 同项目 selectedThreadId → 兼容 ::main
    private func resolveThreadId(projectId: String, preferred: String? = nil) -> String {
        if let preferred, !preferred.isEmpty,
           LocalSessionStore.projectId(fromThreadId: preferred) == projectId {
            return preferred
        }
        if let sel = selectedThreadId, !sel.isEmpty,
           LocalSessionStore.projectId(fromThreadId: sel) == projectId {
            return sel
        }
        return threadIdForProject(projectId)
    }

    /// 多窗焦点线程（warm / slot 按真实 session，不强制 ::main）
    private var focusedThreadRefCounts: [String: Int] = [:]

    /// keep-warm
    private var warmLoopTask: Task<Void, Never>?
    /// sidecar 未就绪时自动重探（避免启动竞态卡死「未就绪」）
    private var agentRecoverTask: Task<Void, Never>?
    /// 每项目上次真暖时间（多窗分别记）
    private var lastWarmAtByProject: [String: Date] = [:]
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

    private func prepareClient(projectId: String? = nil) async throws {
        guard let url = APIClient.makeBaseURL(from: serverURLString) else {
            throw APIError.badURL
        }
        let chatURL = await ensureLocalAgent()
        let pid = projectId ?? selectedProjectId
        let localPath = localPath(for: pid)
        await client.update(
            baseURL: url,
            user: authUser,
            password: authPass,
            chatBaseURL: chatURL,
            localProjectPath: localPath
        )
    }

    /// 探测（10s 缓存）→ 失败则拉起 sidecar → 再探测；失败标「未就绪」并后台重探
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
            agentProbeOKUntil = Date().addingTimeInterval(10)
            cachedAgentBaseURL = candidate
            agentMode = "local"
            agentBadge = "本机 Agent"
            didToastHubFallback = false
            if let info = await client.fetchAgentHealth(base: candidate) {
                sidecarReportedModel = info.model ?? ""
            }
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
                agentProbeOKUntil = Date().addingTimeInterval(10)
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

    /// chat 失败后立刻丢掉健康缓存，避免 10s 假「可聊」
    private func invalidateAgentProbeCache() {
        agentProbeOKUntil = nil
    }

    private func warmLocalAgentNow(
        base: URL? = nil,
        toolMode: String = "discuss",
        projectId: String? = nil,
        threadId: String? = nil
    ) async {
        // 已在流式 / 有在途 chat task 时勿抢 slot 锁
        if shouldSkipWarmForChat() {
            #if DEBUG
            print("[warm] skip: chat in flight")
            #endif
            return
        }
        let pid = projectId ?? selectedProjectId
        guard let pid, !pid.isEmpty else { return }
        let path = localPath(for: pid)
        let sid = resolveThreadId(projectId: pid, preferred: threadId)
        if chatTasks[sid] != nil { return }
        agentWarming = true
        defer { agentWarming = false }
        let result = await client.warmLocalAgent(
            base: base ?? cachedAgentBaseURL,
            projectPath: path,
            sessionId: sid,
            toolMode: toolMode,
            claudeSessionId: threadClaudeSessionIds[sid]
        )
        // await 回来后再确认：若期间已开聊，丢弃 warm 结果、勿记 lastWarmAt
        if shouldSkipWarmForChat() { return }
        if chatTasks[sid] != nil { return }
        // 仅真暖（slot.connected）才记；cli-only 不算
        if result.slotConnected {
            lastWarmAtByProject[pid] = Date()
        }
    }

    private func shouldSkipWarmForChat() -> Bool {
        currentThreadStreaming || !liveStreamingThreadIds.isEmpty || !chatTasks.isEmpty
    }

    /// 暖所有焦点线程（+ 全局选中线程）；按真实 sessionId，不强制 ::main
    private func warmFocusedProjects(toolMode: String = "discuss") async {
        let targets = threadsNeedingWarm()
        for (pid, tid) in targets {
            if Task.isCancelled { break }
            if shouldSkipWarmForChat() { break }
            await warmLocalAgentNow(toolMode: toolMode, projectId: pid, threadId: tid)
        }
    }

    private func threadsNeedingWarm() -> [(String, String)] {
        var ordered: [(String, String)] = []
        var seen = Set<String>()
        for tid in focusedThreadRefCounts.keys.sorted() {
            guard seen.insert(tid).inserted else { continue }
            let pid = LocalSessionStore.projectId(fromThreadId: tid)
            guard !pid.isEmpty else { continue }
            ordered.append((pid, tid))
        }
        if let sel = selectedThreadId, seen.insert(sel).inserted {
            let pid = LocalSessionStore.projectId(fromThreadId: sel)
            if !pid.isEmpty { ordered.append((pid, sel)) }
        } else if let pid = selectedProjectId {
            let tid = threadIdForProject(pid)
            if seen.insert(tid).inserted { ordered.append((pid, tid)) }
        }
        // 仅有项目焦点、尚无线程焦点时，退回项目主会话
        for pid in focusedProjectRefCounts.keys.sorted() {
            let tid = resolveThreadId(projectId: pid)
            if seen.insert(tid).inserted { ordered.append((pid, tid)) }
        }
        return ordered
    }

    private func startWarmLoopIfNeeded() {
        guard agentMode == "local" else { return }
        if warmLoopTask != nil { return }
        warmLoopTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 240_000_000_000) // 240s
                guard let self, !Task.isCancelled else { break }
                guard self.agentMode == "local" else { continue }
                await self.warmFocusedProjects()
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

    /// Phase 1.5: 更新消息内容（就地编辑）
    func updateMessage(threadId: String, messageId: UUID, newContent: String) {
        mutateThreadMessages(threadId: threadId) { msgs in
            guard let idx = msgs.firstIndex(where: { $0.id == messageId }) else { return }
            msgs[idx].content = newContent
            msgs[idx].edited = true
        }
        bumpThreadRevision(threadId)
        syncLegacyChatMirror(from: threadId)
        flushDiskSave(threadId: threadId)
    }

    /// 发送前：距该项目上次真暖 >90s 则补暖；流式中跳过（避免抢锁）
    private func warmBeforeSendIfNeeded(toolMode: String, projectId: String? = nil) {
        guard agentMode == "local" else { return }
        if shouldSkipWarmForChat() { return }
        let pid = projectId ?? selectedProjectId
        if let pid, let last = lastWarmAtByProject[pid], Date().timeIntervalSince(last) < 90 {
            return
        }
        Task { await self.warmLocalAgentNow(toolMode: toolMode, projectId: pid) }
    }

    // MARK: - Window focus（多窗 SSE / warm）

    /// 窗绑定/切换/关闭时调用：维护焦点 refcount，并 reconcile Flow SSE
    func setWindowFocus(from previous: String?, to next: String?) {
        if let prev = previous, !prev.isEmpty {
            let c = (focusedProjectRefCounts[prev] ?? 1) - 1
            if c <= 0 {
                focusedProjectRefCounts.removeValue(forKey: prev)
            } else {
                focusedProjectRefCounts[prev] = c
            }
        }
        if let n = next, !n.isEmpty {
            focusedProjectRefCounts[n, default: 0] += 1
            ensureThreadHydrated(projectId: n)
        }
        reconcileFlowSSE()
        // 新焦点立刻补暖（后台）— 用该项目当前解析出的线程，勿写死 ::main
        if let n = next, !n.isEmpty, agentMode == "local" {
            let tid = resolveThreadId(projectId: n)
            Task { await self.warmLocalAgentNow(projectId: n, threadId: tid) }
        }
    }

    /// 窗级线程焦点：切换/关闭时维护，供 warm 对准真实 session
    func setWindowThreadFocus(from previous: String?, to next: String?) {
        if let prev = previous, !prev.isEmpty {
            let c = (focusedThreadRefCounts[prev] ?? 1) - 1
            if c <= 0 {
                focusedThreadRefCounts.removeValue(forKey: prev)
            } else {
                focusedThreadRefCounts[prev] = c
            }
        }
        if let n = next, !n.isEmpty {
            focusedThreadRefCounts[n, default: 0] += 1
            clearThreadUnread(n)
            ensureThreadHydrated(threadId: n)
            if agentMode == "local" {
                let pid = LocalSessionStore.projectId(fromThreadId: n)
                Task { await self.warmLocalAgentNow(projectId: pid, threadId: n) }
            }
        }
    }

    /// 幂等登记（bootstrap 后）；不重复累加 refcount
    func ensureWindowFocus(projectId: String?) {
        guard let projectId, !projectId.isEmpty else { return }
        if focusedProjectRefCounts[projectId] == nil {
            setWindowFocus(from: nil, to: projectId)
        } else {
            reconcileFlowSSE()
        }
    }

    private var focusedProjectIds: Set<String> {
        Set(focusedProjectRefCounts.keys)
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

    private var bootstrapStarted = false

    func bootstrap() async {
        if bootstrapStarted {
            return
        }
        bootstrapStarted = true
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
        await flushTransferOutbox()
        startProjectTaskPolling()
        startAgentUsageTicker()
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
        let tid = selectedProjectId.map { threadIdForProject( $0) }
        let assistant = (tid.flatMap { threadMessages[$0] } ?? [])
            .last(where: { $0.role == "assistant" && !$0.isStreaming })?.content ?? ""
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
            await flushTransferOutbox()
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
        // 先把「即将离开」的线程钉进 RAM+盘；SSOT 是 threadMessages，不靠 chat.messages
        if let prev = selectedProjectId, switching {
            let prevTid = resolveThreadId(projectId: prev, preferred: selectedThreadId)
            persistCurrentThreadSnapshot(threadId: prevTid)
        }
        // 同步先定 tid + 水合，避免 await refreshThreads 间隙 UI 仍停在旧项目或闪空
        let localRecent = LocalSessionStore.threadsAsDesktop(projectId: id).first?.thread_id
        let eagerTid = localRecent ?? threadIdForProject(id)
        selectedProjectId = id
        persistedProjectId = id
        expandedProjectIds.insert(id)
        ensureThreadHydrated(threadId: eagerTid)
        selectedThreadId = eagerTid
        if switching {
            selectedNodeDetail = nil
            ensureFlowSSE()
            // 右栏先贴本线程缓存，等 load 完成再精修（禁止先清空）
            if let snap = threadFlow[eagerTid] {
                applyFlowSnapshot(snap)
            }
        }
        // 多会话：刷新索引后再对齐最近线程
        await refreshThreads(projectId: id)
        let recent = threads.first(where: {
            LocalSessionStore.projectId(fromThreadId: $0.thread_id) == id
        })?.thread_id
        let tid = recent ?? threadIdForProject(id)
        if tid != selectedThreadId {
            ensureThreadHydrated(threadId: tid)
            selectedThreadId = tid
        }
        if switching {
            await loadConversation(threadId: tid)
            let warmGen = threadSwitchGeneration
            Task { [warmGen] in
                guard self.threadSwitchGeneration == warmGen else { return }
                await self.warmLocalAgentNow(projectId: id, threadId: tid)
            }
        } else {
            // 同项目再点（从看板/运维回对话）：只恢复缓存，不踢 Hub 同步，避免闪空
            syncLegacyChatMirror(from: tid)
            if let snap = threadFlow[tid] {
                applyFlowSnapshot(snap)
            }
            refreshCurrentThreadStreaming()
        }
    }

    /// 侧栏点项目卡：切项目 + 强制回对话面（看板/运维里点项目也能回对话）
    func openProjectConversation(_ id: String) async {
        destination = .chat
        // 点卡瞬间先灌 RAM，保证本窗立刻只显示目标 tid（不等 await）
        ensureThreadHydrated(projectId: id)
        await selectProject(id)
    }

    /// 多窗：保证指定 thread 在 RAM 中已水合。
    func ensureThreadHydrated(threadId: String) {
        guard !threadId.isEmpty else { return }
        if threadMessages[threadId] == nil {
            let pid = LocalSessionStore.projectId(fromThreadId: threadId)
            hydrateThreadFromDisk(projectId: pid, threadId: threadId)
            if threadMessages[threadId] == nil {
                threadMessages[threadId] = []
            }
            bumpThreadRevision(threadId)
        }
    }

    /// 兼容旧 API：从 projectId 保证主线程水合
    func ensureThreadHydrated(projectId: String) {
        ensureThreadHydrated(threadId: threadIdForProject( projectId))
    }

    /// 加载指定线程的会话。流式中或 RAM 更丰富时禁止磁盘盲覆盖。
    func loadConversation(threadId: String) async {
        guard !threadId.isEmpty else { return }
        let tid = threadId
        threadSwitchGeneration &+= 1
        let gen = threadSwitchGeneration
        selectedThreadId = tid
        ensureThreadHydrated(threadId: tid)
        let state = ConversationStore.load(threadId: tid)
        let disk = state.messages
        let ram = threadMessages[tid] ?? []
        let keepRam = streamingThreadIds.contains(tid)
            || chatTasks[tid] != nil
            || (!ram.isEmpty
                && LocalSessionStore.messageScore(ram) >= LocalSessionStore.messageScore(disk))
        if keepRam {
            // 保留 live RAM（含 isStreaming + 原 UUID）；只补 flow
            if threadMessages[tid] == nil {
                threadMessages[tid] = ram
            }
        } else {
            threadMessages[tid] = disk
        }
        if let flow = state.flow {
            if threadFlow[tid] == nil
                || (threadFlow[tid]?.works.isEmpty == true && !flow.works.isEmpty) {
                threadFlow[tid] = flow
            }
        } else if threadFlow[tid] == nil, let bound = state.boundEpicId {
            let snap = FlowThreadSnapshot(
                epicId: bound, epic: nil, works: [], headline: "",
                recentEpics: [], emptyMessage: "编排空闲 · 下一笔定稿后出现在这里", fanoutHint: nil
            )
            threadFlow[tid] = snap
        }
        bumpThreadRevision(tid)
        bumpFlowRevision(tid)
        // chat.messages 仅作「全局选中线程」镜像（smoke/旧路径）；UI 列表读 threadMessages
        syncLegacyChatMirror(from: tid)
        // 只清/刷本线程定稿条；禁止冲掉他窗 threadTransferDraft
        if let lastAsst = (threadMessages[tid] ?? []).last(where: { $0.role == "assistant" && !$0.isStreaming }) {
            refreshTransferDraft(from: lastAsst.content, threadId: tid)
        } else {
            setThreadTransferDraft(tid, nil)
        }
        // 切项目/会话不重启右栏拆解动画（仅真扇出时 bump，见 applyFlowSnapshot）
        applyFlowSnapshot(threadFlow[tid])
        refreshCurrentThreadStreaming()
        updateFlowSnapshotPause()
        lastError = nil
        // 后台：本机空才从 Hub 补种消息；流式中不同步
        let pid = LocalSessionStore.projectId(fromThreadId: tid)
        Task { [weak self] in
            guard let self else { return }
            await self.syncThreadFromServer(projectId: pid, threadId: tid, generation: gen)
            await self.syncFlowFromServer(projectId: pid, threadId: tid, generation: gen)
        }
    }

    /// 重置指定（或全局选中）项目的全部对话：清盘 + drop 各 thread sidecar slot + 清 UI
    func resetConversation(projectId: String? = nil) async {
        guard let pid = projectId ?? selectedProjectId else {
            showToast("请先选择项目")
            return
        }
        let priorThreads = LocalSessionStore.threadsAsDesktop(projectId: pid)
        for t in priorThreads {
            cancelChat(threadId: t.thread_id, silent: true, dropSlot: true)
        }
        // 也清可能未入索引的 ::main
        let mainId = threadIdForProject(pid)
        cancelChat(threadId: mainId, silent: true, dropSlot: true)

        let path = localPath(for: pid) ?? ""
        if !path.isEmpty {
            var dropIds = Set(priorThreads.map(\.thread_id))
            dropIds.insert(mainId)
            for tid in dropIds {
                await client.dropSidecarSession(projectPath: path, sessionId: tid)
                threadMessages.removeValue(forKey: tid)
                threadFlow.removeValue(forKey: tid)
                threadClaudeSessionIds.removeValue(forKey: tid)
                threadSessionTokens.removeValue(forKey: tid)
                setThreadTransferDraft(tid, nil)
                setThreadStreamStatus(tid, "")
            }
        } else {
            for tid in priorThreads.map(\.thread_id) + [mainId] {
                threadMessages.removeValue(forKey: tid)
                threadFlow.removeValue(forKey: tid)
                threadClaudeSessionIds.removeValue(forKey: tid)
                threadSessionTokens.removeValue(forKey: tid)
            }
        }

        LocalSessionStore.reset(projectId: pid)
        // 重建干净主会话
        LocalSessionStore.saveMessages(
            projectId: pid,
            threadId: mainId,
            messages: [],
            title: "对话",
            allowDowngrade: true,
            claudeSessionId: nil
        )
        threadMessages[mainId] = []
        bumpThreadRevision(mainId)
        threads = ConversationStore.listThreads(projectId: pid)
        if selectedProjectId == pid {
            selectedThreadId = mainId
            sessionTokens = 0
            syncLegacyChatMirror(from: mainId)
            applyFlowSnapshot(nil)
            flowSplitGeneration &+= 1
            refreshCurrentThreadStreaming()
        }
        showToast("对话已重置")
        destination = .chat
    }

    /// 旧镜像：仅当全局选中该线程时同步 chat.messages（禁止当多窗显示源）
    private func syncLegacyChatMirror(from threadId: String) {
        guard selectedThreadId == threadId else { return }
        chat.messages = threadMessages[threadId] ?? []
        sessionTokens = threadSessionTokens[threadId] ?? 0
    }

    /// 通知 sidecar 丢弃项目主会话 slot（兼容旧调用）
    private func dropSidecarSession(projectId: String) async {
        guard canChat else { return }
        let path = localPath(for: projectId) ?? ""
        guard !path.isEmpty else { return }
        await client.dropSidecarSession(
            projectPath: path,
            sessionId: threadIdForProject(projectId)
        )
    }

    /// 显示压缩：消息超阈值时把最早 N 轮替换为摘要卡；token 超阈值时触发 agent session 重置
    func compactConversationIfNeeded(projectId: String, threadId: String) async {
        let current = threadMessages[threadId] ?? []
        let (compacted, didCompact, rounds) = LocalSessionStore.compactIfNeeded(current)
        guard didCompact else { return }
        threadMessages[threadId] = compacted
        bumpThreadRevision(threadId)
        syncLegacyChatMirror(from: threadId)
        flushDiskSave(threadId: threadId)
        // agent session token 超阈值 → 重置注入摘要（节约 token）；按 thread 计数
        let tok = threadSessionTokens[threadId] ?? 0
        if tok >= Self.agentCompactTokenThreshold {
            await resetAgentSessionWithSummary(projectId: projectId, threadId: threadId, rounds: rounds)
            threadSessionTokens[threadId] = 0
            threadClaudeSessionIds.removeValue(forKey: threadId)
            if selectedThreadId == threadId {
                sessionTokens = 0
            }
            flushDiskSave(threadId: threadId)
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
        // 多会话：若没有活动线程，才确保 "<projectId>::main"；已存档的 tid 禁止复活
        let tid = threadIdForProject(projectId)
        let local = LocalSessionStore.threadsAsDesktop(projectId: projectId)
        if local.isEmpty,
           !LocalSessionStore.isArchived(projectId: projectId, threadId: tid)
        {
            LocalSessionStore.saveMessages(
                projectId: projectId,
                threadId: tid,
                messages: [],
                title: "对话",
                allowDowngrade: true
            )
        }
        threads = LocalSessionStore.threadsAsDesktop(projectId: projectId)
        if !LocalSessionStore.isArchived(projectId: projectId, threadId: tid) {
            hydrateThreadFromDisk(projectId: projectId, threadId: tid)
        }
    }

    func newThread() async {
        await resetConversation()
    }

    /// 打开指定线程
    func openThread(_ id: String) async {
        guard !id.isEmpty else { return }
        let pid = LocalSessionStore.projectId(fromThreadId: id)
        selectedProjectId = pid
        destination = .chat
        selectedThreadId = id
        clearThreadUnread(id)
        ensureThreadHydrated(threadId: id)
        await loadConversation(threadId: id)
        sessionTokens = threadSessionTokens[id] ?? 0
        ensureFlowSSE()
    }

    func clearThreadUnread(_ threadId: String) {
        guard threadUnread.contains(threadId) else { return }
        var copy = threadUnread
        copy.remove(threadId)
        threadUnread = copy
    }

    func projectHasUnread(_ projectId: String) -> Bool {
        threadUnread.contains { LocalSessionStore.projectId(fromThreadId: $0) == projectId }
    }

    func isThreadUnread(_ threadId: String) -> Bool {
        threadUnread.contains(threadId)
    }

    /// 创建新会话并打开；返回 threadId 供本窗 `window.threadId` 绑定
    @discardableResult
    func createNewThread(projectId: String) async -> String {
        let tid = ConversationStore.createThread(projectId: projectId, title: "新对话")
        threads = ConversationStore.listThreads(projectId: projectId)
        await openThread(tid)
        return tid
    }

    /// Fork：复制消息到新会话（新 resume）
    @discardableResult
    func forkThread(threadId: String) async -> String? {
        flushDiskSave(threadId: threadId)
        guard let newId = ConversationStore.forkThread(threadId: threadId) else {
            showToast("分叉失败")
            return nil
        }
        let pid = LocalSessionStore.projectId(fromThreadId: newId)
        threads = ConversationStore.listThreads(projectId: pid)
        threadClaudeSessionIds.removeValue(forKey: newId)
        await openThread(newId)
        showToast("已分叉会话")
        return newId
    }

    /// 手动 compact（显示压缩 + sidecar 摘要重置）
    func manualCompact(threadId: String) async {
        let pid = LocalSessionStore.projectId(fromThreadId: threadId)
        await compactConversationIfNeeded(projectId: pid, threadId: threadId)
        // 强制再走一遍 sidecar compact（即使显示层未超阈值）
        let msgs = threadMessages[threadId] ?? []
        let summary = msgs.suffix(6).map { "\($0.role): \($0.content.prefix(200))" }.joined(separator: "\n")
        let path = localPath(for: pid) ?? ""
        if !path.isEmpty {
            await client.compactSidecarSession(
                projectPath: path,
                sessionId: threadId,
                summary: summary.isEmpty ? "（用户手动压缩）" : summary
            )
            threadClaudeSessionIds.removeValue(forKey: threadId)
            threadSessionTokens[threadId] = 0
            if selectedThreadId == threadId { sessionTokens = 0 }
        }
        showToast("已压缩上下文")
    }

    func exportThreadJSONToPasteboard(threadId: String? = nil) {
        let tid = threadId ?? selectedThreadId
        guard let tid else { return }
        let pid = LocalSessionStore.projectId(fromThreadId: tid)
        flushDiskSave(threadId: tid)
        guard let data = LocalSessionStore.exportV1JSON(projectId: pid, threadId: tid),
              let str = String(data: data, encoding: .utf8)
        else {
            showToast("导出失败")
            return
        }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(str, forType: .string)
        showToast("已复制会话 JSON")
    }

    func importThreadJSONFromPasteboard(projectId: String?) async {
        guard let pid = projectId ?? selectedProjectId else {
            showToast("请先选择项目")
            return
        }
        guard let str = NSPasteboard.general.string(forType: .string),
              let data = str.data(using: .utf8),
              let newId = LocalSessionStore.importV1(data, projectId: pid)
        else {
            showToast("剪贴板不是有效会话 JSON")
            return
        }
        threads = ConversationStore.listThreads(projectId: pid)
        await openThread(newId)
        showToast("已导入会话")
    }

    func addComposerAttachment(path: String) {
        let p = path.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !p.isEmpty else { return }
        if composerAttachments.contains(where: { $0.path == p }) { return }
        composerAttachments.append(ComposerAttachment(path: p))
    }

    func removeComposerAttachment(id: UUID) {
        composerAttachments.removeAll { $0.id == id }
    }

    func requestEngineerMode() {
        if preferredToolMode == "engineer" {
            preferredToolMode = "discuss"
            showToast("已切回讨论模式")
            return
        }
        confirmEngineerMode = true
    }

    func confirmEnableEngineerMode() {
        preferredToolMode = "engineer"
        confirmEngineerMode = false
        showToast("工程师模式：允许本机改文件")
    }

    func revealChangedFiles(message: ChatMessage, projectId: String?) {
        var paths = message.changedFilePaths
        if paths.isEmpty {
            paths = StreamSessionController.writePaths(from: message.toolSteps)
        }
        if paths.isEmpty {
            if let pid = projectId, let root = localPath(for: pid) {
                NSWorkspace.shared.open(URL(fileURLWithPath: root))
                showToast("已打开项目目录")
            } else {
                showToast("无改动路径可打开")
            }
            return
        }
        for p in paths.prefix(8) {
            let url = URL(fileURLWithPath: p)
            if FileManager.default.fileExists(atPath: p) {
                NSWorkspace.shared.activateFileViewerSelecting([url])
            } else if let pid = projectId, let root = localPath(for: pid) {
                let joined = URL(fileURLWithPath: root).appendingPathComponent(p)
                if FileManager.default.fileExists(atPath: joined.path) {
                    NSWorkspace.shared.activateFileViewerSelecting([joined])
                }
            }
        }
    }

    /// 删除（归档）会话
    func archiveThread(threadId: String) async {
        let pid = LocalSessionStore.projectId(fromThreadId: threadId)
        if streamingThreadIds.contains(threadId) {
            cancelChat(threadId: threadId, silent: true, dropSlot: true)
        } else {
            let path = localPath(for: pid) ?? ""
            if !path.isEmpty {
                await client.dropSidecarSession(projectPath: path, sessionId: threadId)
            }
        }
        ConversationStore.archiveThread(threadId: threadId)
        threadMessages.removeValue(forKey: threadId)
        threadFlow.removeValue(forKey: threadId)
        threadClaudeSessionIds.removeValue(forKey: threadId)
        threadSessionTokens.removeValue(forKey: threadId)
        threads = ConversationStore.listThreads(projectId: pid)
        // 如果删的是当前线程，自动切到最近线程；没有则清本窗焦点
        if selectedThreadId == threadId {
            if let first = threads.first {
                await openThread(first.thread_id)
            } else {
                selectedThreadId = nil
                chat.messages = []
                sessionTokens = 0
            }
        }
        showToast("会话已存档")
    }

    /// 重命名线程
    func renameThread(threadId: String, title: String) {
        let pid = LocalSessionStore.projectId(fromThreadId: threadId)
        LocalSessionStore.rename(projectId: pid, threadId: threadId, title: title)
        threads = ConversationStore.listThreads(projectId: pid)
    }

    /// 从本机盘灌 RAM；流式/在途 task 中禁止磁盘覆盖（防 orphan / 掉会话）
    private func hydrateThreadFromDisk(projectId: String, threadId: String) {
        if streamingThreadIds.contains(threadId) || chatTasks[threadId] != nil {
            return
        }
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
        if let sid = disk.claude_session_id?.trimmingCharacters(in: .whitespacesAndNewlines), !sid.isEmpty {
            threadClaudeSessionIds[threadId] = sid
        }
    }

    private func persistCurrentThreadSnapshot(threadId: String) {
        // SSOT = threadMessages。chat.messages 仅在该线程为全局选中且 RAM 空时补种，禁止反写串台。
        if threadMessages[threadId] == nil,
           selectedThreadId == threadId,
           !chat.messages.isEmpty {
            threadMessages[threadId] = chat.messages
        }
        let snap = FlowThreadSnapshot(
            epicId: currentEpicId,
            epic: flowEpic,
            works: flowWorks,
            headline: flowHeadline,
            recentEpics: recentEpics,
            emptyMessage: flowEmptyMessage,
            fanoutHint: flowFanoutHint,
            stopLossHint: flowStopLossHint
        )
        // 空右栏不覆盖已有 works
        if let prev = threadFlow[threadId],
           snap.works.isEmpty, snap.epic == nil,
           (!prev.works.isEmpty || prev.epic != nil) {
            // 只更新消息；保留旧 flow
        } else if selectedThreadId == threadId {
            threadFlow[threadId] = snap
        }
        flushDiskSave(threadId: threadId)
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
            flowStopLossHint = snap.stopLossHint
        } else {
            currentEpicId = nil
            flowEpic = nil
            flowWorks = []
            flowHeadline = ""
            recentEpics = []
            flowEmptyMessage = "编排空闲 · 下一笔定稿后出现在这里"
            flowFanoutHint = nil
            flowStopLossHint = nil
            selectedNodeDetail = nil
        }
    }

    /// 本机有消息则禁止 Hub GET 回写；仅本机为空时可选补种备份
    private func syncThreadFromServer(projectId: String, threadId: String, generation: UInt64) async {
        if LocalSessionStore.isArchived(projectId: projectId, threadId: threadId) { return }
        if streamingThreadIds.contains(threadId) { return }
        hydrateThreadFromDisk(projectId: projectId, threadId: threadId)
        let cached = threadMessages[threadId]
            ?? LocalSessionStore.load(projectId: projectId, threadId: threadId)?.messages
            ?? []
        // 契约：本机 SSOT — 有内容绝不让 Hub 覆盖 UI
        if LocalSessionStore.messageScore(cached) > 0 {
            if selectedThreadId == threadId, destination == .chat {
                syncLegacyChatMirror(from: threadId)
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
            bumpThreadRevision(threadId)
            syncLegacyChatMirror(from: threadId)
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
            bumpThreadRevision(threadId)
            syncLegacyChatMirror(from: threadId)
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
                if selectedThreadId == threadId {
                    currentEpicId = bound
                }
                await refreshFlowNow(projectId: projectId)
            } else if let hint = epicsResp.boundHint, !hint.isEmpty {
                if selectedThreadId == threadId {
                    currentEpicId = hint
                }
                await refreshFlowNow(projectId: projectId)
            } else if let match = epics.first(where: { ($0.thread_id ?? "") == threadId })?.epic_id {
                if selectedThreadId == threadId {
                    currentEpicId = match
                }
                await refreshFlowNow(projectId: projectId)
            } else if let first = epics.first?.epic_id {
                if selectedThreadId == threadId {
                    currentEpicId = first
                }
                await refreshFlowNow(projectId: projectId)
            } else if hasLocalFlow {
                return
            } else {
                if selectedThreadId == threadId {
                    currentEpicId = nil
                    flowEpic = nil
                    flowWorks = []
                    flowHeadline = ""
                    flowEmptyMessage = "编排空闲 · 下一笔定稿后出现在这里"
                    flowFanoutHint = nil
                }
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
        bumpThreadRevision(threadId)
        syncLegacyChatMirror(from: threadId)
        scheduleDiskSave(threadId: threadId)
    }

    private func bumpThreadRevision(_ threadId: String) {
        // 必须整体赋值：字典下标 in-place 改不会触发 @Published
        var copy = threadRevision
        copy[threadId, default: 0] &+= 1
        threadRevision = copy
    }

    private func bumpFlowRevision(_ threadId: String) {
        var copy = threadFlowRevision
        copy[threadId, default: 0] &+= 1
        threadFlowRevision = copy
    }

    /// 多窗显示 SSOT：只读 threadMessages，绝不回落全局 chat.messages（否则切项目会串台）。
    func messagesForThread(_ threadId: String?) -> [ChatMessage] {
        guard let threadId, !threadId.isEmpty else { return [] }
        return threadMessages[threadId] ?? []
    }

    /// OpenCode 式：右栏按 session/thread 取编排快照（多窗不读全局 flow*）
    func flowSnapshot(for threadId: String?) -> FlowThreadSnapshot? {
        guard let threadId, !threadId.isEmpty else { return nil }
        return threadFlow[threadId]
    }

    /// 本窗流式状态文案
    func streamStatus(for threadId: String?) -> String {
        guard let threadId else { return "" }
        return threadStreamStatus[threadId] ?? ""
    }

    /// 本窗定稿条
    func transferDraft(for threadId: String?) -> TransferDraft? {
        guard let threadId else { return nil }
        return threadTransferDraft[threadId]
    }

    private func setThreadStreamStatus(_ threadId: String, _ status: String) {
        var copy = threadStreamStatus
        if status.isEmpty {
            copy.removeValue(forKey: threadId)
        } else {
            copy[threadId] = status
        }
        threadStreamStatus = copy
        if selectedThreadId == threadId {
            chat.streamStatus = status
        }
    }

    private func setComposerBounce(_ text: String?, threadId: String?) {
        composerBounce = text
        composerBounceThreadId = text == nil ? nil : threadId
    }

    private func setThreadTransferDraft(_ threadId: String, _ draft: TransferDraft?) {
        var copy = threadTransferDraft
        if let draft {
            copy[threadId] = draft
        } else {
            copy.removeValue(forKey: threadId)
        }
        threadTransferDraft = copy
        if selectedThreadId == threadId {
            pendingTransferDraft = draft
        }
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
        let msgs = (threadMessages[tid] ?? [])
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
            needsHubSync: false,
            claudeSessionId: threadClaudeSessionIds[tid]
        )
    }

    private func mutateThreadMessages(threadId: String, _ body: (inout [ChatMessage]) -> Void) {
        var msgs = threadMessages[threadId] ?? []
        body(&msgs)
        persistMessages(for: threadId, msgs)
    }

    /// Phase 1.4: delta 热路径——就地改 content；切回后 UUID 仍在 RAM 时可续写。
    /// 若曾被磁盘 hydrate 弄丢 id：流式中按 assistantId 重建气泡，禁止静默丢字。
    private func applyDeltaInPlace(threadId: String, assistantId: UUID, chunk: String) {
        // 流已结束 / 已取消：拒绝迟到分片（含未取消完的旧 Task）回写，防字乱序与假 streaming
        let live = streamingThreadIds.contains(threadId) || chatTasks[threadId] != nil
        guard live else { return }
        var msgs = threadMessages[threadId] ?? []
        if let idx = msgs.firstIndex(where: { $0.id == assistantId }) {
            msgs[idx].content += chunk
            if msgs[idx].transientNote != nil {
                msgs[idx].transientNote = nil
            }
            msgs[idx].isStreaming = true
        } else {
            msgs.append(
                ChatMessage(
                    id: assistantId,
                    role: "assistant",
                    content: chunk,
                    isStreaming: true
                )
            )
        }
        threadMessages[threadId] = msgs
        bumpThreadRevision(threadId)
        // 仅镜像全局选中线程；他窗靠 threadRevision 刷新，禁止 chat.messages 当显示源
        if selectedThreadId == threadId {
            if chat.messages.contains(where: { $0.id == assistantId }) {
                chat.replaceMessage(id: assistantId) { m in
                    m.content += chunk
                    if m.transientNote != nil {
                        m.transientNote = nil
                    }
                    m.isStreaming = true
                }
            } else {
                chat.messages = msgs
            }
        }
        // 流式中不落盘：避免每 token 写盘 + hydrate 竞态；结束/取消时 flushDiskSave
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

    private func flushTransferOutbox() async {
        guard hubReachable else { return }
        let pending = LocalSessionStore.loadTransferOutbox()
        for item in pending {
            if item.attempts >= LocalSessionStore.maxTransferOutboxAttempts {
                LocalSessionStore.dequeueTransfer(clientRequestId: item.client_request_id)
                setTransferDelivery(item.thread_id, .failed)
                continue
            }
            setTransferDelivery(item.thread_id, .delivering)
            let req = TransferRequest(
                project_id: item.project_id,
                thread_id: item.thread_id,
                title: item.title,
                goal: item.goal,
                acceptance: item.acceptance,
                pipeline: item.pipeline,
                feasibility: item.feasibility,
                feasibility_reason: item.feasibility_reason,
                executor_intent: item.executor_intent,
                skills_hint: [],
                plan_md: item.plan_md,
                complexity: item.complexity,
                client_request_id: item.client_request_id
            )
            do {
                try await prepareClient()
                let resp = try await client.transfer(req)
                LocalSessionStore.dequeueTransfer(clientRequestId: item.client_request_id)
                await applyTransferSuccess(resp: resp, tid: item.thread_id, pid: item.project_id)
            } catch {
                _ = LocalSessionStore.bumpTransferAttempt(clientRequestId: item.client_request_id)
                setTransferDelivery(item.thread_id, .queued)
            }
        }
    }

    func transferDelivery(for threadId: String?) -> TransferDeliveryPhase? {
        guard let threadId else { return nil }
        return transferDeliveryByThread[threadId]
    }

    private func setTransferDelivery(_ threadId: String, _ phase: TransferDeliveryPhase) {
        var copy = transferDeliveryByThread
        copy[threadId] = phase
        transferDeliveryByThread = copy
    }

    private func applyTransferSuccess(resp: TransferResponse, tid: String, pid: String) async {
        let eid = (resp.epic_id ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !eid.isEmpty else {
            // 禁止空 epic_id 驱动 ui / fanout（Phase6：空前缀会误匹配全板）
            setTransferDelivery(tid, .failed)
            showToast("转任务失败：Hub 未返回 epic_id")
            return
        }
        if selectedProjectId == pid {
            selectedThreadId = tid
            currentEpicId = eid
        }
        var snap = threadFlow[tid] ?? FlowThreadSnapshot(
            epicId: eid, epic: nil, works: [], headline: "",
            recentEpics: threadFlow[tid]?.recentEpics ?? recentEpics,
            emptyMessage: "", fanoutHint: nil
        )
        snap.epicId = eid
        threadFlow[tid] = snap
        bumpFlowRevision(tid)
        persistCurrentThreadSnapshot(threadId: tid)
        dismissTransferSheet(threadId: tid)
        resetTransferForm(threadId: tid)
        setTransferDelivery(tid, .delivered)
        statusText = "已转任务"
        var toastMsg = "已创建待办 \(eid)"
        if resp.idempotent_replay == true {
            toastMsg = "已受理（幂等）\(eid)"
        }
        if resp.engine_wake?.ok == true {
            toastMsg += " · Engine 已唤醒"
            setTransferDelivery(tid, .accepted)
        }
        showToast(toastMsg)
        lastAnimatedEpicId = nil
        flowSplitGeneration &+= 1
        await bindFlowToThread(projectId: pid, preferEpicId: eid)
        if transferDeliveryByThread[tid] != .accepted {
            setTransferDelivery(tid, .accepted)
        }
        startFanoutWatchdog(epicId: eid, projectId: pid)
    }

    static func promptMode(forUserText text: String) -> String {
        StreamSessionController.resolvePromptMode(forUserText: text)
    }

    /// discuss = 只读探查（默认）；engineer = 允许本机写文件（偏好或口令）
    static func toolMode(forUserText text: String) -> String {
        // 兼容旧调用：无偏好时只看口令
        StreamSessionController.resolveToolMode(preferred: "discuss", userText: text)
    }

    func resolvedToolMode(forUserText text: String) -> String {
        StreamSessionController.resolveToolMode(preferred: preferredToolMode, userText: text)
    }

    func resolvedModel() -> String {
        StreamSessionController.resolveModel(preferredModel)
    }

    /// 同会话 stop-and-send；仅本机 sidecar，可多路并行（可指定 projectId / threadId 供多窗多会话）
    func sendUserMessage(
        _ text: String,
        projectId: String? = nil,
        threadId: String? = nil,
        stopAndSend: Bool = true,
        attachments: [ComposerAttachment]? = nil
    ) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let atts = attachments ?? composerAttachments
        let composed = StreamSessionController.composeUserText(text: trimmed, attachments: atts)
        guard !composed.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        if attachments == nil { composerAttachments = [] }
        let pid = projectId ?? selectedProjectId
        Task {
            await self.sendUserMessageAndWait(
                composed,
                projectId: pid,
                threadId: threadId,
                stopAndSend: stopAndSend
            )
        }
    }

    func isThreadStreaming(_ threadId: String) -> Bool {
        liveStreamingThreadIds.contains(threadId) || streamingThreadIds.contains(threadId)
    }

    private func setThreadStreaming(_ threadId: String, _ on: Bool) {
        let wasOn = streamingThreadIds.contains(threadId)
        if on {
            streamingThreadIds.insert(threadId)
            clearThreadUnread(threadId)
        } else {
            streamingThreadIds.remove(threadId)
            // 流结束且当前没有窗聚焦该 thread → 未读
            if wasOn, (focusedThreadRefCounts[threadId] ?? 0) == 0 {
                var copy = threadUnread
                copy.insert(threadId)
                threadUnread = copy
            }
        }
        liveStreamingThreadIds = streamingThreadIds
        // 同步项目对话灯：threadId = "<projectId>::main"
        let pid = Self.projectId(fromThreadId: threadId)
        var copy = projectConvState
        copy[pid] = on ? "text" : "idle"
        projectConvState = copy
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
        guard streamingThreadIds.contains(threadId) else { return }
        var copy = projectConvState
        copy[pid] = "tool"
        projectConvState = copy
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
                var copy = self.projectConvState
                copy[pid] = "text"
                self.projectConvState = copy
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

    /// 从 board 列计数推导项目级任务态（只关心「有活」；纯 released / 已隐藏 done 视为空闲）
    static func deriveTaskState(from counts: [String: Int]) -> String {
        let failed = counts["abnormal"] ?? 0
        let inProgress = counts["in_progress"] ?? 0
        let testing = counts["testing"] ?? 0
        let planned = counts["planned"] ?? 0
        let backlog = counts["backlog"] ?? 0
        if failed > 0 { return "failed" }
        if inProgress > 0 { return "in_progress" }
        if testing > 0 { return "testing" }
        // backlog 含 pending/planned/running epic；done 沉底后 ui_hidden，不应再进 counts
        if planned > 0 || backlog > 0 { return "pending" }
        return "idle"
    }

    /// 可等待版本：smoke / 自动化必须等整轮 SSE（含 done）结束
    @discardableResult
    func sendUserMessageAndWait(
        _ text: String,
        projectId: String? = nil,
        threadId preferredThreadId: String? = nil,
        stopAndSend: Bool = true
    ) async -> Bool {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return false }
        guard let pid = projectId ?? selectedProjectId else {
            showToast("请先选择项目")
            setComposerBounce(trimmed, threadId: nil)
            return false
        }
        // 多会话：跟本窗/显式 thread，禁止打回 ::main
        let threadId = resolveThreadId(projectId: pid, preferred: preferredThreadId)
        ensureThreadHydrated(threadId: threadId)
        if selectedProjectId == pid {
            if selectedThreadId != threadId {
                selectedThreadId = threadId
            }
            syncLegacyChatMirror(from: threadId)
        }
        if !canChat {
            showToast("本机 Agent 未就绪。请执行 bash scripts/install-agent-sidecar-plist.sh --start")
            setComposerBounce(trimmed, threadId: threadId)
            return false
        }

        if streamingThreadIds.contains(threadId) {
            if stopAndSend {
                let previous = chatTasks[threadId]
                cancelChat(threadId: threadId, silent: true)
                // BUG fix: 上轮 task 已 null（done 提前清）→ 不再等 previous.value。
                // 否则「第二条发出去但 UI 无反应」会卡到 30+ s。
                if previous != nil {
                    await previous?.value
                }
            } else {
                showToast("正在生成，请先点停止")
                setComposerBounce(trimmed, threadId: threadId)
                return false
            }
        } else if chatTasks[threadId] != nil {
            // BUG fix: streaming=false 但 chatTasks[threadId] 残留（done 提前清 fence，
            // defer 还没跑到 chatTasks[threadId]=nil）→ 直接清掉，避免下一轮 task
            // 被旧 task 顶替后 UI 状态不一致。
            chatTasks[threadId] = nil
        }

        let others = streamingThreadIds.filter { $0 != threadId }.count
        if others >= Self.maxParallelLocalChats {
            showToast("已有 \(Self.maxParallelLocalChats) 路在生成，请先停止一路再发")
            setComposerBounce(trimmed, threadId: threadId)
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
            // 聊完追赶该项目右栏（后台窗也要 live 刷新 threadFlow）
            let flowGen = threadSwitchGeneration
            Task { [flowGen, projectId] in
                guard self.threadSwitchGeneration == flowGen else { return }
                await self.refreshFlow(projectId: projectId)
            }
        }

        let userMsg = ChatMessage(role: "user", content: text)
        let assistantId = UUID()
        mutateThreadMessages(threadId: threadId) { msgs in
            msgs.append(userMsg)
            msgs.append(ChatMessage(id: assistantId, role: "assistant", content: "", isStreaming: true))
        }

        do {
            setThreadStreamStatus(threadId, "连接本机 Agent…")
            if selectedThreadId == threadId {
                setStatusImmediate("连接本机 Agent…")
            }
            try await prepareClient(projectId: projectId)
            // 业务仓未绑本机路径时提示一次（不阻断）
            if localPath(for: projectId) == nil,
               let p = projects.first(where: { $0.id == projectId }), p.isDispatchable {
                showToast("未绑定本机工作区，sidecar 可能扫错目录 — 设置里为当前项目填写路径")
            }
            let mode = Self.promptMode(forUserText: text)
            let tools = resolvedToolMode(forUserText: text)
            let modelName = resolvedModel()
            // 发送前不再 fire-and-forget warm：与 streamChat 抢同一 slot 锁，
            // 取消/杀进程后半残连接更容易表现为「切一下就连不上」。
            setThreadStreamStatus(threadId, "本机生成中…")
            if selectedThreadId == threadId {
                setStatusImmediate("本机生成中…")
            }
            let outbound = (threadMessages[threadId] ?? []).filter { $0.id != assistantId }
            let streamProjectPath = localPath(for: projectId)

            // 同会话自动重试 1 次（保留已生成的本地内容，清空半截助手再流）
            var streamError: Error?
            let turnStarted = Date()
            for attempt in 1...2 {
                do {
                    if attempt == 2 {
                        setThreadStreamStatus(threadId, "重连中…")
                        if selectedThreadId == threadId {
                            setStatusImmediate("重连中…")
                        }
                        mutateThreadMessages(threadId: threadId) { msgs in
                            guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                            msgs[idx].content = ""
                            msgs[idx].toolSteps = []
                            msgs[idx].filesChanged = 0
                            msgs[idx].changedFilePaths = []
                            msgs[idx].toolsFinished = false
                            msgs[idx].isStreaming = true
                        }
                        try await prepareClient(projectId: projectId)
                    }
                    let outboundAttempt = (threadMessages[threadId] ?? []).filter { $0.id != assistantId }
                    recordAgentLLMCall()
                    try await client.streamChat(
                        projectId: projectId,
                        sessionId: threadId,
                        messages: attempt == 1 ? outbound : outboundAttempt,
                        promptMode: mode,
                        toolMode: tools,
                        projectPath: streamProjectPath,
                        claudeSessionId: threadClaudeSessionIds[threadId],
                        model: modelName
                    ) { [weak self] event in
                        guard let model = self else { return }
                        await MainActor.run {
                            model.applyChatEvent(threadId: threadId, assistantId: assistantId, event: event)
                        }
                    }
                    streamError = nil
                    DesktopChatTurnLedger.append([
                        "event": "ok",
                        "threadId": threadId,
                        "projectId": projectId,
                        "attempt": attempt,
                        "duration_ms": Int(Date().timeIntervalSince(turnStarted) * 1000),
                    ])
                    if lastTurnFailure?.threadId == threadId {
                        lastTurnFailure = nil
                    }
                    break
                } catch is CancellationError {
                    throw CancellationError()
                } catch {
                    streamError = error
                    let cancelled = (error as NSError).code == NSURLErrorCancelled
                        || error.localizedDescription.lowercased().contains("cancel")
                    if cancelled { throw error }

                    let apiErr = error as? APIError
                    let retryable: Bool = {
                        if let apiErr {
                            if apiErr.isNonRetryableAuthOrClient { return false }
                            if apiErr.isRetryableStreamFailure { return true }
                        }
                        if (error as NSError).domain == NSURLErrorDomain { return true }
                        let d = error.localizedDescription
                        return d.contains("中断") || d.contains("无进展") || d.contains("timed out")
                            || d.contains("Timeout") || d.contains("连接")
                    }()

                    var didHealDrop = false
                    if attempt == 1, retryable, let apiErr, apiErr.shouldDropLiveSlotBeforeRetry {
                        if let path = streamProjectPath, !path.isEmpty {
                            if apiErr.shouldClearResumeIdBeforeRetry {
                                threadClaudeSessionIds.removeValue(forKey: threadId)
                            }
                            await client.dropSidecarSession(
                                projectPath: path,
                                sessionId: threadId,
                                reason: "heal-\(apiErr.streamCode ?? "retry")"
                            )
                            didHealDrop = true
                        }
                    }

                    DesktopChatTurnLedger.append([
                        "event": "fail_attempt",
                        "threadId": threadId,
                        "projectId": projectId,
                        "attempt": attempt,
                        "code": apiErr?.streamCode ?? "",
                        "http": apiErr?.httpStatus ?? 0,
                        "retryable": retryable,
                        "heal_drop": didHealDrop,
                        "message": String(error.localizedDescription.prefix(200)),
                        "duration_ms": Int(Date().timeIntervalSince(turnStarted) * 1000),
                    ])

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
                throw APIError.stream(code: "empty_reply", message: "模型无有效回复")
            }
            setThreadStreamStatus(threadId, "")
            if selectedThreadId == threadId {
                updateConnectionStatusText(localOK: canChat, hubOK: hubReachable)
            }
            // 解析定稿块（按 thread 写入，多窗各自可见）
            if let asst = (threadMessages[threadId] ?? []).last(where: { $0.id == assistantId }) {
                refreshTransferDraft(from: asst.content, threadId: threadId)
            }
            // 本机立即落盘 + Hub 异步镜像
            flushDiskSave()
            // 显示压缩（异步，不打断当前流）
            await compactConversationIfNeeded(projectId: projectId, threadId: threadId)
            let synced = (threadMessages[threadId] ?? [])
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
            setThreadStreamStatus(threadId, "")
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
                invalidateAgentProbeCache()
                let apiErr = error as? APIError
                let code = apiErr?.streamCode
                let msg = error.localizedDescription
                lastTurnFailure = ChatTurnFailure(
                    threadId: threadId,
                    projectId: projectId,
                    code: code,
                    message: msg,
                    userText: text,
                    at: Date()
                )
                DesktopChatTurnLedger.append([
                    "event": "fail",
                    "threadId": threadId,
                    "projectId": projectId,
                    "code": code ?? "",
                    "http": apiErr?.httpStatus ?? 0,
                    "message": String(msg.prefix(240)),
                ])
                setThreadStreamStatus(threadId, "")
                if selectedThreadId == threadId {
                    setStatusImmediate("本条失败 · \(lastTurnFailure?.shortLabel ?? "错误")")
                }
                if apiErr?.isNonRetryableAuthOrClient == true {
                    showToast("对话失败（鉴权/路径）：\(msg)。请检查 ~/.ccc/agent-token 并执行 bash scripts/install-agent-sidecar-plist.sh --start")
                } else {
                    showToast("对话失败：\(lastTurnFailure?.shortLabel ?? msg)")
                }
                setComposerBounce(text, threadId: threadId)
            }
        }
    }

    private func applyChatEvent(threadId: String, assistantId: UUID, event: ChatStreamEvent) {
        switch event {
        case .ping:
            // 心跳 ≠ 进展：勿把状态锁死在「连接中」；工具进行中保留工具态
            let cur = threadStreamStatus[threadId] ?? ""
            if cur.contains("工具") || cur.contains("生成") {
                return
            }
            if cur.isEmpty || cur.contains("连接") || cur.contains("重连") {
                setThreadStreamStatus(threadId, "等待 Agent 首包…")
                if selectedThreadId == threadId {
                    setStatusThrottled("等待 Agent 首包…")
                }
            }
            return
        case .delta(let chunk):
            // 整段写入；禁止异步分片（与重试/结束竞态）
            applyDeltaInPlace(threadId: threadId, assistantId: assistantId, chunk: chunk)
            if threadStreamStatus[threadId] != "本机生成中…" {
                setThreadStreamStatus(threadId, "本机生成中…")
            }
            if selectedThreadId == threadId {
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
        if case .toolUse(let name, _) = event {
            setProjectConvToolState(threadId: threadId)
            let label = "工具执行中：\(name)…"
            setThreadStreamStatus(threadId, label)
            if selectedThreadId == threadId {
                setStatusThrottled(label)
            }
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
                    let path = input["file_path"]
                        ?? input["path"]
                        ?? input["target_file"]
                        ?? input["file"]
                    if let path, !path.isEmpty, !msgs[idx].changedFilePaths.contains(path) {
                        msgs[idx].changedFilePaths.append(path)
                    }
                }
                // stream status 在 mutate 外按 thread 写
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
                    threadSessionTokens[threadId, default: 0] += t
                    if selectedThreadId == threadId {
                        sessionTokens = threadSessionTokens[threadId] ?? 0
                    }
                }
            case .done(_, let claudeSessionId):
                for i in msgs[idx].toolSteps.indices where msgs[idx].toolSteps[i].status == .running {
                    msgs[idx].toolSteps[i].status = .done
                }
                if !msgs[idx].toolSteps.isEmpty {
                    msgs[idx].toolsFinished = true
                }
                if let sid = claudeSessionId?.trimmingCharacters(in: .whitespacesAndNewlines), !sid.isEmpty {
                    threadClaudeSessionIds[threadId] = sid
                }
            }
        }
        if case .done = event {
            // BUG fix: done 事件到达即同步清 streaming + turn fence，避免「第二条发送时仍
            // 处于 streaming=true」卡住 UI（stopAndSend 误命中 cancelAndWait 路径，UI 无反应）。
            // defer 仍会跑（最终清理），但用户感知的反应不能等 await 链收尾。
            activeTurnIds.removeValue(forKey: threadId)
            if streamingThreadIds.contains(threadId) {
                setThreadStreaming(threadId, false)
            }
            setThreadStreamStatus(threadId, "")
            flushDiskSave(threadId: threadId)
        } else if case .toolResult = event {
            // 工具结束后回到生成态（下一轮 delta 会再写细状态）
            if (threadStreamStatus[threadId] ?? "").contains("工具") {
                setThreadStreamStatus(threadId, "本机生成中…")
                if selectedThreadId == threadId {
                    setStatusThrottled("本机生成中…")
                }
            }
        }
    }

    func cancelChat(threadId: String? = nil, silent: Bool = false, dropSlot: Bool = false) {
        let tid = threadId ?? selectedThreadId
        guard let tid else { return }
        chatTasks[tid]?.cancel()
        chatTasks[tid] = nil
        setThreadStreaming(tid, false)
        setThreadStreamStatus(tid, "")
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
        flushDiskSave(threadId: tid)
        // 总是回收 live slot（防半残 cli → 下一轮 first_event 假死）。
        // 默认保留 claude_session_id 以便 resume；仅显式重置/归档时清 resume id。
        let projectId = LocalSessionStore.projectId(fromThreadId: tid)
        let path = localPath(for: projectId) ?? localPath(for: selectedProjectId)
        if dropSlot {
            threadClaudeSessionIds.removeValue(forKey: tid)
        }
        if let path, !path.isEmpty {
            let reason = dropSlot ? "user-reset" : "cancel"
            Task {
                await client.dropSidecarSession(
                    projectPath: path,
                    sessionId: tid,
                    reason: reason
                )
            }
        }
        if !silent {
            showToast("已取消生成")
        }
    }

    /// 状态栏：重试最近失败的用户消息
    func retryLastFailedTurn(threadId: String? = nil) {
        guard let fail = lastTurnFailure else { return }
        let tid = threadId ?? fail.threadId
        guard tid == fail.threadId else { return }
        let text = fail.userText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        lastTurnFailure = nil
        Task {
            await sendUserMessageAndWait(
                text,
                projectId: fail.projectId,
                threadId: tid
            )
        }
    }

    /// 状态栏：只清本会话 live 槽（保留本地消息与 resume id）
    func healThreadSlot(threadId: String? = nil) {
        let tid = threadId ?? selectedThreadId ?? lastTurnFailure?.threadId
        guard let tid, !tid.isEmpty else {
            showToast("请先选择会话")
            return
        }
        let pid = LocalSessionStore.projectId(fromThreadId: tid)
        guard let path = localPath(for: pid), !path.isEmpty else {
            showToast("未绑定本机工作区，无法清槽")
            return
        }
        Task {
            await client.dropSidecarSession(projectPath: path, sessionId: tid, reason: "heal-ui")
            if lastTurnFailure?.threadId == tid {
                lastTurnFailure = nil
            }
            showToast("已清理本会话 Agent 槽，可再发一条")
            DesktopChatTurnLedger.append([
                "event": "heal_slot",
                "threadId": tid,
                "projectId": pid,
            ])
        }
    }

    func applyQuickPrompt(
        _ prompt: String,
        uiLabel: String,
        projectId: String? = nil,
        threadId: String? = nil
    ) {
        destination = .chat
        showToast(uiLabel)
        sendUserMessage(prompt, projectId: projectId, threadId: threadId, stopAndSend: true)
    }

    func alignBaseline(projectId: String? = nil, threadId: String? = nil) async {
        guard let pid = projectId ?? selectedProjectId else {
            showToast("请先选择项目")
            return
        }
        destination = .chat
        do {
            try await prepareClient(projectId: pid)
            let resp = try await client.fetchProjectBaseline(projectId: pid)
            let prompt = (resp.prompt ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            guard !prompt.isEmpty else {
                showToast("基线为空")
                return
            }
            showToast("已注入对齐基线")
            sendUserMessage(
                prompt,
                projectId: pid,
                threadId: threadId ?? selectedThreadId,
                stopAndSend: true
            )
        } catch {
            showToast(error.localizedDescription)
        }
    }

    func exportThreadMarkdown(threadId: String? = nil) -> String {
        let tid = threadId ?? selectedThreadId
        let msgs = tid.map { threadMessages[$0] ?? [] } ?? []
        return msgs
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

    func exportThreadToPasteboard(threadId: String? = nil) {
        let md = exportThreadMarkdown(threadId: threadId)
        guard !md.isEmpty else {
            showToast("无可导出内容")
            return
        }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(md, forType: .string)
        showToast("会话已复制为 Markdown")
    }

    /// 用户消息 → 填回输入框（对齐 Hub「编辑」）
    func editUserMessage(
        _ message: ChatMessage,
        projectId: String? = nil,
        threadId: String? = nil
    ) {
        guard message.role == "user" else { return }
        let pid = projectId ?? selectedProjectId
        let tid = pid.map { resolveThreadId(projectId: $0, preferred: threadId) } ?? selectedThreadId
        setComposerBounce(message.content, threadId: tid)
        destination = .chat
        showToast("已填入输入框，改完再发送")
    }

    /// 助手消息 → 重发紧邻的上一条用户消息（对齐 Hub「重新生成」）
    func regenerateAssistant(
        after message: ChatMessage,
        projectId: String? = nil,
        threadId: String? = nil
    ) {
        guard message.role == "assistant" else { return }
        let pid = projectId ?? selectedProjectId
        guard let pid else { return }
        let tid = resolveThreadId(projectId: pid, preferred: threadId)
        let msgs = threadMessages[tid] ?? []
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
        guard let text = userText, !text.isEmpty else {
            showToast("找不到上一条用户消息")
            return
        }
        sendUserMessage(text, projectId: pid, threadId: tid, stopAndSend: true)
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

    /// 从某条助手消息打开转任务（预填）；多窗必须带 projectId/threadId
    func openTransfer(
        fromAssistantContent content: String,
        projectId: String? = nil,
        threadId: String? = nil
    ) {
        let pid = projectId ?? selectedProjectId
        let tid = pid.map { resolveThreadId(projectId: $0, preferred: threadId) } ?? selectedThreadId
        guard let tid else {
            showToast("请先选择项目")
            return
        }
        applyTransferDraft(
            TransferDraftParser.parse(from: content),
            fallbackContent: content,
            threadId: tid
        )
        presentTransferSheet(threadId: tid)
    }

    func openTransferSheet(projectId: String? = nil, threadId: String? = nil) {
        let pid = projectId ?? selectedProjectId
        let tid = pid.map { resolveThreadId(projectId: $0, preferred: threadId) } ?? selectedThreadId
        guard let tid else {
            showToast("请先选择项目")
            return
        }
        if let d = threadTransferDraft[tid] {
            applyTransferDraft(d, fallbackContent: nil, threadId: tid)
        } else if selectedThreadId == tid, let d = pendingTransferDraft {
            applyTransferDraft(d, fallbackContent: nil, threadId: tid)
        } else {
            prefillTransferFromChat(threadId: tid)
        }
        presentTransferSheet(threadId: tid)
    }

    func presentTransferSheet(threadId: String) {
        transferSheetThreadId = threadId
    }

    func dismissTransferSheet(threadId: String? = nil) {
        if threadId == nil || transferSheetThreadId == threadId {
            transferSheetThreadId = nil
        }
    }

    /// 一键确认定稿条 → 直接提交（字段已齐）
    func confirmPendingTransfer(threadId: String? = nil) {
        let tid = threadId ?? selectedThreadId
        let draft = tid.flatMap { threadTransferDraft[$0] } ?? pendingTransferDraft
        guard let tid, let d = draft else {
            openTransferSheet()
            return
        }
        applyTransferDraft(d, fallbackContent: nil, threadId: tid)
        if d.isGateReady {
            Task { await submitTransfer(threadId: tid) }
        } else {
            presentTransferSheet(threadId: tid)
        }
    }

    func dismissPendingTransfer(threadId: String? = nil) {
        if let tid = threadId {
            setThreadTransferDraft(tid, nil)
        } else if let tid = selectedThreadId {
            setThreadTransferDraft(tid, nil)
        } else {
            pendingTransferDraft = nil
        }
    }

    /// 助手回复结束后刷新定稿条（按 thread 隔离）
    func refreshTransferDraft(from content: String, threadId: String? = nil) {
        let tid = threadId ?? selectedThreadId
        if let d = TransferDraftParser.parse(from: content), d.isGateReady || !d.title.isEmpty {
            if let tid {
                setThreadTransferDraft(tid, d)
                applyTransferDraft(d, fallbackContent: nil, threadId: tid)
                if d.isGateReady { setTransferDelivery(tid, .draft) }
            } else {
                pendingTransferDraft = d
            }
        }
    }

    func transferForm(for threadId: String?) -> TransferFormState {
        guard let threadId else { return TransferFormState() }
        return threadTransferForms[threadId] ?? TransferFormState()
    }

    func bindingTransferField(
        _ threadId: String,
        _ keyPath: WritableKeyPath<TransferFormState, String>
    ) -> Binding<String> {
        Binding(
            get: {
                self.threadTransferForms[threadId]?[keyPath: keyPath]
                    ?? TransferFormState()[keyPath: keyPath]
            },
            set: { newValue in
                var form = self.threadTransferForms[threadId] ?? TransferFormState()
                form[keyPath: keyPath] = newValue
                var copy = self.threadTransferForms
                copy[threadId] = form
                self.threadTransferForms = copy
            }
        )
    }

    private func setTransferForm(_ threadId: String, _ form: TransferFormState) {
        var copy = threadTransferForms
        copy[threadId] = form
        threadTransferForms = copy
    }

    private func mutateTransferForm(_ threadId: String, _ update: (inout TransferFormState) -> Void) {
        var form = threadTransferForms[threadId] ?? TransferFormState()
        update(&form)
        setTransferForm(threadId, form)
    }

    private func applyTransferDraft(
        _ draft: TransferDraft?,
        fallbackContent: String?,
        threadId: String
    ) {
        var form = threadTransferForms[threadId] ?? TransferFormState()
        form.error = nil
        if let d = draft {
            if !d.title.isEmpty { form.title = d.title }
            if !d.goal.isEmpty { form.goal = d.goal }
            if !d.acceptance.isEmpty { form.acceptance = d.acceptance }
            if !d.pipeline.isEmpty { form.pipeline = d.pipeline }
            if !d.feasibility.isEmpty { form.feasibility = d.feasibility }
            form.feasibilityReason = d.feasibilityReason
            if !d.executorIntent.isEmpty { form.executor = d.executorIntent }
            if !d.planMd.isEmpty { form.planMd = d.planMd }
            setTransferForm(threadId, form)
            return
        }
        guard let t = fallbackContent?.trimmingCharacters(in: .whitespacesAndNewlines), !t.isEmpty else {
            setTransferForm(threadId, form)
            return
        }
        if form.goal.isEmpty { form.goal = String(t.prefix(2000)) }
        if form.title.isEmpty {
            form.title = String(t.replacingOccurrences(of: "\n", with: " ").prefix(40))
        }
        if form.acceptance.isEmpty {
            form.acceptance = "按对话结论验收；现象符合描述即通过"
        }
        setTransferForm(threadId, form)
    }

    /// 从对话启发式预填门禁字段（无 ccc-transfer 时）
    func prefillTransferFromChat(threadId: String? = nil) {
        let tid = threadId ?? transferSheetThreadId ?? selectedThreadId
        guard let tid else { return }
        let msgs = threadMessages[tid] ?? []
        let assistants = msgs.filter { $0.role == "assistant" && !$0.isStreaming }.map(\.content)
        if let last = assistants.last, let d = TransferDraftParser.parse(from: last) {
            applyTransferDraft(d, fallbackContent: nil, threadId: tid)
            setThreadTransferDraft(tid, d)
            return
        }
        let users = msgs.filter { $0.role == "user" }.map(\.content)
        let lastUser = users.last ?? ""
        let blob = (users.suffix(3) + assistants.suffix(2)).joined(separator: "\n")
        let lastAssistant = assistants.last ?? ""

        mutateTransferForm(tid) { form in
            if form.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                if let t = extractSection(blob, names: ["标题", "title"]) {
                    form.title = String(t.replacingOccurrences(of: "\n", with: " ").prefix(80))
                } else {
                    form.title = String(lastUser.replacingOccurrences(of: "\n", with: " ").prefix(40))
                }
            }
            if form.goal.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                if let g = extractSection(blob, names: ["目标", "goal"]) {
                    form.goal = g
                } else {
                    form.goal = String(lastUser.prefix(200))
                }
            }
            if form.acceptance.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                if let a = extractSection(blob, names: ["验收", "验证", "acceptance"]) {
                    form.acceptance = normalizeAcceptance(a)
                } else if !lastUser.isEmpty {
                    form.acceptance = "按对话约定完成，并可复查结果"
                }
            }
            if form.pipeline.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                if let p = extractSection(blob, names: ["产线", "pipeline"]) {
                    form.pipeline = String(p.split(separator: "\n").first ?? Substring("dev"))
                } else {
                    form.pipeline = "dev"
                }
            }
            if form.planMd.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                if lastAssistant.count > 80 {
                    form.planMd = lastAssistant
                }
            }
            if form.feasibility.isEmpty {
                form.feasibility = "ok"
            }
            form.error = nil
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

    private func resetTransferForm(threadId: String) {
        setTransferForm(threadId, TransferFormState())
        setThreadTransferDraft(threadId, nil)
        if selectedThreadId == threadId {
            pendingTransferDraft = nil
        }
    }

    func submitTransfer(threadId: String? = nil) async {
        let tid = threadId ?? transferSheetThreadId ?? selectedThreadId
        guard let tid else {
            showToast("转任务失败：缺少项目")
            return
        }
        let pid = Self.projectId(fromThreadId: tid)
        guard !pid.isEmpty else {
            mutateTransferForm(tid) { $0.error = "缺少项目" }
            showToast("转任务失败：缺少项目")
            return
        }
        if let p = projects.first(where: { $0.id == pid }), !p.isDispatchable {
            mutateTransferForm(tid) { $0.error = "当前项目不可下达" }
            showToast("转任务失败：当前项目不可下达（请切业务仓）")
            return
        }
        let form = transferForm(for: tid)
        let title = form.title.trimmingCharacters(in: .whitespacesAndNewlines)
        let goal = form.goal.trimmingCharacters(in: .whitespacesAndNewlines)
        let pipeline = form.pipeline.trimmingCharacters(in: .whitespacesAndNewlines)
        let accLines = form.acceptance
            .split(separator: "\n")
            .map { String($0).trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        if title.isEmpty || goal.isEmpty || pipeline.isEmpty || accLines.isEmpty {
            mutateTransferForm(tid) { $0.error = "请填齐：标题、目标、产线、至少一条验收" }
            showToast("转任务失败：请填齐标题、目标、产线与验收")
            return
        }
        if form.feasibility == "blocked",
           form.feasibilityReason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            mutateTransferForm(tid) { $0.error = "可行性为 blocked 时必须填写原因" }
            showToast("转任务失败：标记为阻塞时需写原因")
            return
        }
        if form.feasibility != "ok" {
            mutateTransferForm(tid) { $0.error = "可行性非 ok，无法转任务" }
            showToast("转任务失败：方案评估为不可执行")
            return
        }
        let chatDigest = (threadMessages[tid] ?? [])
            .suffix(8)
            .map { "\($0.role): \(String($0.content.prefix(200)))" }
            .joined(separator: "\n")
        let planBody: String = {
            let custom = form.planMd.trimmingCharacters(in: .whitespacesAndNewlines)
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
        if !hubReachable {
            let requestId = UUID().uuidString
            let item = LocalSessionStore.TransferOutboxItem(
                client_request_id: requestId,
                project_id: pid,
                thread_id: tid,
                title: title,
                goal: goal,
                acceptance: accLines,
                pipeline: pipeline,
                feasibility: form.feasibility,
                feasibility_reason: form.feasibility == "blocked" ? form.feasibilityReason : nil,
                executor_intent: form.executor,
                plan_md: planBody,
                complexity: "medium",
                attempts: 0,
                saved_at: ISO8601DateFormatter().string(from: Date())
            )
            LocalSessionStore.enqueueTransfer(item)
            setTransferDelivery(tid, .queued)
            mutateTransferForm(tid) { $0.error = nil }
            dismissTransferSheet(threadId: tid)
            showToast("Hub 暂不可达，已排队待投递")
            return
        }
        busy = true
        defer { busy = false }
        let requestId = UUID().uuidString
        setTransferDelivery(tid, .delivering)
        let req = TransferRequest(
            project_id: pid,
            thread_id: tid,
            title: title,
            goal: goal,
            acceptance: accLines,
            pipeline: pipeline,
            feasibility: form.feasibility,
            feasibility_reason: form.feasibility == "blocked" ? form.feasibilityReason : nil,
            executor_intent: form.executor,
            skills_hint: [],
            plan_md: planBody,
            complexity: "medium",
            client_request_id: requestId
        )
        do {
            try await prepareClient()
            let resp = try await client.transfer(req)
            await applyTransferSuccess(resp: resp, tid: tid, pid: pid)
        } catch {
            let plain = plainTransferError(error)
            // 网络类 / 空响应 / 空 epic_id：入 outbox，Hub 恢复后同 CRID 重试
            let lower = plain.lowercased()
            let transient = lower.contains("timed out") || lower.contains("offline")
                || lower.contains("network") || lower.contains("could not connect")
                || lower.contains("connection") || !hubReachable
                || lower.contains("empty transfer") || lower.contains("empty epic")
                || lower.contains("空 epic") || lower.contains("transfer decode")
                || lower.contains("解析失败")
                || ((error as? APIError).map { err in
                    if case .emptyEpicId = err { return true }
                    if case .decode = err { return true }
                    if case .http(let code, _) = err { return code >= 500 || code == 0 }
                    return false
                } ?? false)
            if transient {
                let item = LocalSessionStore.TransferOutboxItem(
                    client_request_id: requestId,
                    project_id: pid,
                    thread_id: tid,
                    title: title,
                    goal: goal,
                    acceptance: accLines,
                    pipeline: pipeline,
                    feasibility: form.feasibility,
                    feasibility_reason: form.feasibility == "blocked" ? form.feasibilityReason : nil,
                    executor_intent: form.executor,
                    plan_md: planBody,
                    complexity: "medium",
                    attempts: 0,
                    saved_at: ISO8601DateFormatter().string(from: Date())
                )
                LocalSessionStore.enqueueTransfer(item)
                setTransferDelivery(tid, .queued)
                mutateTransferForm(tid) { $0.error = nil }
                dismissTransferSheet(threadId: tid)
                showToast("投递中断，已排队：\(plain)")
            } else {
                setTransferDelivery(tid, .failed)
                mutateTransferForm(tid) { $0.error = plain }
                showToast("转任务失败：\(plain)")
            }
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

    /// 转任务后若 15s 仍无 works，右栏明示原因（按项目写 threadFlow）
    func startFanoutWatchdog(epicId: String?, projectId: String? = nil) {
        fanoutWatchTask?.cancel()
        let pid = projectId ?? selectedProjectId
        guard let epicId, !epicId.isEmpty, let pid else { return }
        let tid = threadIdForProject( pid)
        if selectedProjectId == pid {
            flowFanoutHint = nil
        }
        fanoutWatchTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 15_000_000_000)
            guard !Task.isCancelled, let self else { return }
            await MainActor.run {
                var snap = self.threadFlow[tid] ?? FlowThreadSnapshot(
                    epicId: epicId, epic: nil, works: [], headline: "",
                    recentEpics: [], emptyMessage: "", fanoutHint: nil
                )
                guard (snap.epicId ?? "") == epicId || snap.epicId == nil else { return }
                if snap.works.isEmpty {
                    let stage = snap.headline.isEmpty
                        ? (snap.epic?.user_stage ?? snap.epic?.headline ?? "待拆解")
                        : snap.headline
                    let hint = "15 秒内未见拆分（\(stage)）。Engine 可能未扇出，可开运维查看。"
                    snap.fanoutHint = hint
                    self.threadFlow[tid] = snap
                    self.bumpFlowRevision(tid)
                    if self.selectedProjectId == pid {
                        self.flowFanoutHint = hint
                    }
                }
            }
        }
    }

    func clearFanoutHint(projectId: String? = nil) {
        let pid = projectId ?? selectedProjectId
        if let pid {
            let tid = threadIdForProject( pid)
            if var snap = threadFlow[tid] {
                snap.fanoutHint = nil
                threadFlow[tid] = snap
                bumpFlowRevision(tid)
            }
        }
        if projectId == nil || projectId == selectedProjectId {
            flowFanoutHint = nil
        }
        fanoutWatchTask?.cancel()
        fanoutWatchTask = nil
    }

    func clearStopLossHint(projectId: String? = nil) {
        let pid = projectId ?? selectedProjectId
        if let pid {
            let tid = threadIdForProject(pid)
            if var snap = threadFlow[tid] {
                snap.stopLossHint = nil
                threadFlow[tid] = snap
                bumpFlowRevision(tid)
            }
        }
        if projectId == nil || projectId == selectedProjectId {
            flowStopLossHint = nil
        }
    }

    /// 右栏与项目对话绑定：本机 boundEpicId 优先（默认全局选中）
    func bindFlowToCurrentThread(preferEpicId: String? = nil) async {
        guard let pid = selectedProjectId else { return }
        await bindFlowToThread(projectId: pid, preferEpicId: preferEpicId)
    }

    /// OpenCode 式：按 project 绑定编排，写 threadFlow，不抢他窗全局镜像
    func bindFlowToThread(projectId: String, preferEpicId: String? = nil) async {
        let tid = threadIdForProject( projectId)
        let isSelected = selectedProjectId == projectId
        if isSelected {
            selectedNodeDetail = nil
            selectedThreadId = tid
        }
        do {
            try await prepareClient()
            let epicsResp = try await client.fetchRecentEpicsDetailed(
                projectId: projectId,
                threadId: tid
            )
            var snap = threadFlow[tid] ?? FlowThreadSnapshot(
                epicId: nil, epic: nil, works: [], headline: "",
                recentEpics: [], emptyMessage: "编排空闲 · 下一笔定稿后出现在这里", fanoutHint: nil
            )
            snap.recentEpics = epicsResp.epics
            let localBound = snap.epicId ?? (isSelected ? currentEpicId : nil)
            let hasLocalFlow =
                (localBound?.isEmpty == false)
                || (snap.epic != nil)
                || !snap.works.isEmpty
            let resolvedEpic: String?
            if let prefer = preferEpicId, !prefer.isEmpty {
                resolvedEpic = prefer
            } else if let bound = localBound, !bound.isEmpty {
                resolvedEpic = bound
            } else if let hint = epicsResp.boundHint, !hint.isEmpty {
                resolvedEpic = hint
            } else if let match = epicsResp.epics.first(where: { ($0.thread_id ?? "") == tid })?.epic_id {
                resolvedEpic = match
            } else if let first = epicsResp.epics.first?.epic_id {
                resolvedEpic = first
            } else if hasLocalFlow {
                threadFlow[tid] = snap
                bumpFlowRevision(tid)
                if isSelected {
                    recentEpics = epicsResp.epics
                    applyFlowSnapshot(snap)
                }
                await refreshFlow(projectId: projectId)
                reconcileFlowSSE()
                return
            } else {
                resolvedEpic = nil
                snap.epic = nil
                snap.works = []
                snap.headline = ""
                snap.emptyMessage = "编排空闲 · 下一笔定稿后出现在这里"
            }
            snap.epicId = resolvedEpic
            threadFlow[tid] = snap
            bumpFlowRevision(tid)
            if isSelected {
                recentEpics = epicsResp.epics
                currentEpicId = resolvedEpic
                applyFlowSnapshot(snap)
            }
            persistCurrentThreadSnapshot(threadId: tid)
            await refreshFlow(projectId: projectId)
            reconcileFlowSSE()
        } catch {
            if isSelected {
                flowEmptyMessage = "流程加载失败"
            }
            if var snap = threadFlow[tid] {
                snap.emptyMessage = "流程加载失败"
                threadFlow[tid] = snap
                bumpFlowRevision(tid)
            }
        }
    }

    func refreshEpicList(projectId: String? = nil) async {
        if let pid = projectId ?? selectedProjectId {
            await bindFlowToThread(projectId: pid)
        }
    }

    func selectEpic(_ epicId: String, projectId: String? = nil) async {
        let pid = projectId ?? selectedProjectId
        guard let pid else { return }
        let tid = threadIdForProject( pid)
        var snap = threadFlow[tid] ?? FlowThreadSnapshot(
            epicId: epicId, epic: nil, works: [], headline: "",
            recentEpics: [], emptyMessage: "", fanoutHint: nil
        )
        snap.epicId = epicId
        threadFlow[tid] = snap
        bumpFlowRevision(tid)
        if selectedProjectId == pid {
            currentEpicId = epicId
            selectedNodeDetail = nil
        }
        await refreshFlow(projectId: pid)
        reconcileFlowSSE()
    }

    func refreshFlow(projectId: String? = nil) async {
        let pid = projectId ?? selectedProjectId
        guard let pid else { return }
        // 合并短时间内的多次刷新，避免 snapshot 风暴打挂 Hub
        flowRefreshTasks[pid]?.cancel()
        flowRefreshTasks[pid] = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 500_000_000)
            guard !Task.isCancelled, let self else { return }
            await self.refreshFlowNow(projectId: pid)
        }
    }

    private func refreshFlowNow(projectId: String? = nil) async {
        let pid = projectId ?? selectedProjectId
        guard let pid else { return }
        guard !flowSnapshotPaused else { return }
        let tid = threadIdForProject( pid)
        let epicId = threadFlow[tid]?.epicId ?? (selectedProjectId == pid ? currentEpicId : nil)
        do {
            try await prepareClient()
            let snap = try await client.flowSnapshot(projectId: pid, epicId: epicId)
            applySnapshot(snap, projectId: pid)
        } catch {
            // SSE 为主；snapshot 失败不刷屏、不改 connected
        }
    }

    private func applySnapshot(_ snap: FlowSnapshot, projectId: String) {
        let tid = threadIdForProject( projectId)
        let isSelected = selectedProjectId == projectId
        var cached = threadFlow[tid] ?? FlowThreadSnapshot(
            epicId: nil, epic: nil, works: [], headline: "",
            recentEpics: isSelected ? recentEpics : [],
            emptyMessage: "编排空闲 · 下一笔定稿后出现在这里",
            fanoutHint: nil
        )

        if snap.empty == true {
            if cached.epicId == nil {
                cached.works = []
                cached.epic = nil
                cached.headline = ""
                cached.emptyMessage = snap.message
                    ?? "编排空闲 · 下一笔定稿后出现在这里"
                threadFlow[tid] = cached
                bumpFlowRevision(tid)
                if isSelected {
                    applyFlowSnapshot(cached)
                }
            }
            return
        }
        let stage = (snap.user_stage ?? snap.epic?.user_stage ?? snap.epic?.split_status ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
        // 编排完成：右栏时间线退场（历史在看板）；保留 recentEpics 供「切换本对话任务」
        if stage == "done" {
            let keptRecent = cached.recentEpics
            cached.works = []
            cached.epic = nil
            cached.epicId = nil
            cached.headline = ""
            cached.fanoutHint = nil
            cached.stopLossHint = nil
            cached.recentEpics = keptRecent
            cached.emptyMessage = "编排空闲 · 下一笔定稿后出现在这里"
            threadFlow[tid] = cached
            bumpFlowRevision(tid)
            if isSelected {
                applyFlowSnapshot(cached)
                lastAnimatedEpicId = nil
            }
            flushDiskSave(threadId: tid)
            return
        }
        let works = snap.works ?? []
        let eid = snap.epic_id ?? cached.epicId
        let headline = snap.headline
            ?? snap.epic?.headline
            ?? (works.first(where: \.isActive).map { "正在：\($0.title)" } ?? "")
        let prevEmpty = cached.works.isEmpty
        let epicChanged = (cached.epicId ?? "") != (eid ?? "")
        cached.works = works
        cached.epicId = eid
        cached.epic = snap.epic
        cached.headline = headline
        cached.emptyMessage = ""
        // Phase9：abnormal / failed 止损可见（右栏 + 一次性 toast）
        let hasAbnormal = works.contains(where: \.isFailed)
        let stopLoss = (stage == "failed" || hasAbnormal)
        if stopLoss {
            let title = works.first(where: \.isFailed)?.title
                ?? snap.epic?.title
                ?? eid
                ?? "任务"
            let hint = "编排异常：\(title) · 点开运维或看板止损"
            cached.stopLossHint = hint
            let toastKey = "\(projectId)|\(eid ?? "")|failed"
            if lastStopLossToastKey != toastKey {
                lastStopLossToastKey = toastKey
                if isSelected {
                    showToast(hint)
                }
            }
        } else {
            cached.stopLossHint = nil
            if let eid, lastStopLossToastKey?.hasPrefix("\(projectId)|\(eid)|") == true {
                lastStopLossToastKey = nil
            }
        }
        if !works.isEmpty {
            cached.fanoutHint = nil
            if isSelected {
                fanoutWatchTask?.cancel()
                fanoutWatchTask = nil
                flowFanoutHint = nil
            }
            if (prevEmpty || epicChanged), lastAnimatedEpicId != eid {
                lastAnimatedEpicId = eid
                flowSplitGeneration &+= 1
            }
        }
        threadFlow[tid] = cached
        bumpFlowRevision(tid)
        if isSelected {
            applyFlowSnapshot(cached)
        }
    }

    func openNodeDetail(id: String, projectId: String? = nil) {
        let pid = projectId ?? selectedProjectId
        let tid = pid.map { threadIdForProject( $0) }
        let snap = tid.flatMap { threadFlow[$0] }
        let epic = snap?.epic ?? (pid == selectedProjectId ? flowEpic : nil)
        let works = snap?.works ?? (pid == selectedProjectId ? flowWorks : [])
        let curEpicId = snap?.epicId ?? (pid == selectedProjectId ? currentEpicId : nil)

        if let epic, (epic.id ?? curEpicId) == id {
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
        if let work = works.first(where: { $0.workId == id }) {
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
        reconcileFlowSSE()
    }

    /// 对齐 OpenCode：对所有打开窗项目 + 全局选中维持 Flow SSE
    func ensureFlowSSE() {
        reconcileFlowSSE()
    }

    private func reconcileFlowSSE() {
        var want = focusedProjectIds
        if let sel = selectedProjectId { want.insert(sel) }
        for pid in Array(flowSSETasks.keys) where !want.contains(pid) {
            flowSSETasks[pid]?.cancel()
            flowSSETasks.removeValue(forKey: pid)
            flowBackoffNs.removeValue(forKey: pid)
        }
        for pid in want where flowSSETasks[pid] == nil {
            startProjectFlowSSE(projectId: pid)
        }
        if want.isEmpty {
            // 无焦点时不连
        }
    }

    private func startProjectFlowSSE(projectId: String) {
        flowSSETasks[projectId]?.cancel()
        flowBackoffNs[projectId] = 3_000_000_000
        flowSSETasks[projectId] = Task { [weak self] in
            while !Task.isCancelled {
                do {
                    try await self?.prepareClient()
                    await MainActor.run { self?.flowBackoffNs[projectId] = 3_000_000_000 }
                    try await self?.client.streamFlowEvents(
                        projectId: projectId,
                        epicId: nil
                    ) { event, _ in
                        if ["fanout", "work_status", "epic_created", "executor"].contains(event) {
                            Task { @MainActor in
                                guard let self else { return }
                                guard !self.flowSnapshotPaused else { return }
                                // 只要该项目仍在焦点/选中集合，就刷新 threadFlow（不要求 == selectedProjectId）
                                let stillWanted = self.focusedProjectIds.contains(projectId)
                                    || self.selectedProjectId == projectId
                                guard stillWanted else { return }
                                await self.refreshFlow(projectId: projectId)
                            }
                        }
                    }
                    try? await Task.sleep(nanoseconds: 2_000_000_000)
                } catch {
                    if Task.isCancelled { break }
                    let delay = await MainActor.run { () -> UInt64 in
                        let d = self?.flowBackoffNs[projectId] ?? 3_000_000_000
                        self?.flowBackoffNs[projectId] = min(d + 2_000_000_000, 12_000_000_000)
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

    func selectDestination(_ dest: SidebarDestination, projectId: String? = nil) {
        let prev = destination
        destination = dest
        let pid = projectId ?? selectedProjectId
        switch dest {
        case .chat:
            // 从看板/运维回对话：用本机缓存恢复，禁止空闪、禁止 Hub 空结果冲掉
            if prev != .chat, let pid {
                let tid = threadIdForProject( pid)
                if selectedProjectId == pid {
                    selectedThreadId = tid
                }
                ensureThreadHydrated(projectId: pid)
                if selectedProjectId == pid {
                    syncLegacyChatMirror(from: tid)
                    if let snap = threadFlow[tid] {
                        applyFlowSnapshot(snap)
                    }
                    refreshCurrentThreadStreaming()
                }
            }
        case .board:
            // 离开对话前落盘，避免回来丢消息/右栏
            if let pid {
                let tid = threadIdForProject( pid)
                persistCurrentThreadSnapshot(threadId: tid)
            } else if let tid = selectedThreadId {
                persistCurrentThreadSnapshot(threadId: tid)
            }
            let destGen = threadSwitchGeneration
            Task { [destGen] in
                guard self.threadSwitchGeneration == destGen else { return }
                await self.refreshBoard(projectId: pid)
            }
        case .ops:
            if let pid {
                let tid = threadIdForProject( pid)
                persistCurrentThreadSnapshot(threadId: tid)
            } else if let tid = selectedThreadId {
                persistCurrentThreadSnapshot(threadId: tid)
            }
            let destGen = threadSwitchGeneration
            Task { [destGen] in
                guard self.threadSwitchGeneration == destGen else { return }
                await self.refreshOps()
            }
        }
    }

    func refreshBoard(projectId: String? = nil) async {
        boardBusy = true
        boardError = nil
        defer { boardBusy = false }
        let pid = projectId ?? selectedProjectId
        let proj = projects.first { $0.id == pid }
        let ws = proj?.workspace
            ?? pid
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
                // router-usage 已退役；顶栏改计本机 Agent 调用
            } else {
                async let overview = client.fetchOpsOverview()
                async let risksResp = client.fetchOpsRisks()
                opsOverview = try await overview
                let risks = try await risksResp
                opsRisks = risks.risks ?? []
                opsRisksCount = risks.count
                opsRisksHigh = risks.high
            }
            if let props = try? await client.fetchInboxProposals() {
                inboxProposals = props.proposals ?? []
            }
        } catch {
            opsError = error.localizedDescription
        }
    }

    func adoptInboxProposal(_ id: String) async {
        inboxAdoptBusy = true
        opsAdoptError = nil
        defer { inboxAdoptBusy = false }
        do {
            try await prepareClient()
            let resp = try await client.adoptInboxProposal(id: id)
            if resp.ok != true {
                opsAdoptError = resp.error ?? "采纳失败"
                return
            }
            inboxProposals.removeAll { $0.id == id }
            await refreshOps()
        } catch {
            opsAdoptError = "inbox 采纳失败: \(error.localizedDescription)"
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

    // MARK: - Agent LLM usage (toolbar)

    /// 每次本机 Agent 真正发起一轮上游对话（含自动重试）计 1 次
    func recordAgentLLMCall() {
        let now = Date()
        rollAgentLLMDayIfNeeded(now: now)
        agentLLMDailyCount += 1
        UserDefaults.standard.set(agentLLMDailyCount, forKey: Self.agentLLMDailyKey)
        agentLLMCallTimestamps.append(now)
        refreshAgentLLMRecent5s(now: now)
        bumpAgentUsageTick()
    }

    func startAgentUsageTicker() {
        agentUsageTask?.cancel()
        loadAgentLLMDailyFromDisk()
        refreshAgentLLMRecent5s(now: Date())
        bumpAgentUsageTick()
        agentUsageTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                guard !Task.isCancelled, let self else { break }
                await MainActor.run {
                    self.refreshAgentLLMRecent5s(now: Date())
                    self.bumpAgentUsageTick()
                }
            }
        }
    }

    private func loadAgentLLMDailyFromDisk() {
        let today = Self.agentLLMDayString(Date())
        let storedDay = UserDefaults.standard.string(forKey: Self.agentLLMDayKey) ?? ""
        if storedDay != today {
            UserDefaults.standard.set(today, forKey: Self.agentLLMDayKey)
            UserDefaults.standard.set(0, forKey: Self.agentLLMDailyKey)
            agentLLMDailyCount = 0
        } else {
            agentLLMDailyCount = UserDefaults.standard.integer(forKey: Self.agentLLMDailyKey)
        }
    }

    private func rollAgentLLMDayIfNeeded(now: Date) {
        let today = Self.agentLLMDayString(now)
        let storedDay = UserDefaults.standard.string(forKey: Self.agentLLMDayKey) ?? ""
        if storedDay != today {
            UserDefaults.standard.set(today, forKey: Self.agentLLMDayKey)
            UserDefaults.standard.set(0, forKey: Self.agentLLMDailyKey)
            agentLLMDailyCount = 0
            agentLLMCallTimestamps.removeAll()
        }
    }

    private func refreshAgentLLMRecent5s(now: Date) {
        let cutoff = now.addingTimeInterval(-5)
        agentLLMCallTimestamps = agentLLMCallTimestamps.filter { $0 >= cutoff }
        agentLLMRecent5s = agentLLMCallTimestamps.count
    }

    private func bumpAgentUsageTick() {
        agentUsageTick &+= 1
    }

    private static func agentLLMDayString(_ date: Date) -> String {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = .current
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: date)
    }

    // MARK: - Phase 1.2: Search / Help / Commands

    @Published var searchQuery: String = ""
    @Published var searchResults: [LocalSessionStore.SearchResult] = []
    @Published var isSearching: Bool = false
    /// 点搜索结果后滚动到该消息（UUID string）
    @Published var pendingScrollMessageId: String?
    @Published var isHelpPresented: Bool = false
    /// 菜单 ⌘F：侧栏搜索框抢焦点
    @Published var searchFocusTick: UInt64 = 0
    /// 菜单命令：请求新会话 / 转任务 / 切换目的地（由当前窗消费）
    @Published var commandNewThreadTick: UInt64 = 0
    @Published var commandTransferTick: UInt64 = 0
    @Published var commandDestination: SidebarDestination?
    /// sidecar 预热中（不阻塞发送，仅状态可见）
    @Published var agentWarming: Bool = false

    func performSearch(query: String) {
        guard !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            searchResults = []
            isSearching = false
            return
        }
        isSearching = true
        searchQuery = query
        var results: [LocalSessionStore.SearchResult] = []
        for project in projects {
            let r = LocalSessionStore.searchMessages(projectId: project.id, query: query)
            results.append(contentsOf: r)
        }
        searchResults = results.sorted { ($0.updatedAt ?? "") > ($1.updatedAt ?? "") }
        isSearching = false
    }

    func clearSearch() {
        searchQuery = ""
        searchResults = []
        isSearching = false
    }

    /// 打开搜索命中：灌全局选中 + 待滚消息；调用方还需写 WindowChatState
    func openSearchResult(_ result: LocalSessionStore.SearchResult) async {
        let pid = LocalSessionStore.projectId(fromThreadId: result.threadId)
        pendingScrollMessageId = result.messageId
        clearSearch()
        destination = .chat
        await openThread(result.threadId)
        selectedProjectId = pid
        selectedThreadId = result.threadId
    }

    func requestSearchFocus() {
        destination = .chat
        commandDestination = .chat
        searchFocusTick &+= 1
    }

    func requestNewThread() {
        commandDestination = .chat
        commandNewThreadTick &+= 1
    }

    func requestOpenTransfer() {
        commandDestination = .chat
        commandTransferTick &+= 1
    }

    func requestDestination(_ dest: SidebarDestination) {
        commandDestination = dest
        selectDestination(dest, projectId: selectedProjectId)
    }

    /// 转任务按钮旁人话门禁（nil = 可点）
    func transferGateHint(projectId: String?, threadId: String?) -> String? {
        if !hubReachable {
            return "Hub 未连接，暂不能转任务（可先继续聊方案）"
        }
        guard let projectId else {
            return "先在左侧选择一个业务项目"
        }
        if let p = projects.first(where: { $0.id == projectId }), p.isOrch == true {
            return "当前是编排仓：请切到业务项目再转任务"
        }
        if !canTransfer(projectId: projectId) {
            return "该项目不可下达，请换业务仓或检查 Hub 项目列表"
        }
        if let d = transferDraft(for: threadId), !d.isGateReady {
            return "定稿未过门禁：补全标题、目标与至少一条验收"
        }
        return nil
    }

    func dismissFirstRunTip() {
        dismissedFirstRunTip = true
    }

    // MARK: - Phase 1.3: Token tracking

    @Published var perMessageTokens: [UUID: Int] = [:]
    @Published var totalSessionCost: Double = 0

    private func trackTokenUsage(threadId: String, msgId: UUID, content: String) {
        let tokens = content.count / 4
        threadSessionTokens[threadId, default: 0] += tokens
        if selectedThreadId == threadId {
            sessionTokens = threadSessionTokens[threadId] ?? 0
        }
        totalSessionCost += Double(tokens) * 0.000003 // ~$3/M tokens est
        var copy = perMessageTokens
        copy[msgId] = tokens
        perMessageTokens = copy
    }

    // MARK: - Phase 2.1: Manual epic creation

    @Published var isManualEpicPresented: Bool = false
    @Published var manualEpicForm: ManualEpicForm = ManualEpicForm()

    func createManualEpic(projectId: String, form: ManualEpicForm) async {
        let tid = threadIdForProject( projectId)
        let accLines = form.acceptance
            .split(separator: "\n")
            .map { String($0).trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        guard !form.title.isEmpty, !form.goal.isEmpty, !form.pipeline.isEmpty, !accLines.isEmpty else {
            showToast("请填齐标题、目标、产线与验收")
            return
        }
        busy = true
        defer { busy = false }
        let req = TransferRequest(
            project_id: projectId,
            thread_id: tid,
            title: form.title,
            goal: form.goal,
            acceptance: accLines,
            pipeline: form.pipeline,
            feasibility: "ok",
            feasibility_reason: nil,
            executor_intent: form.executor,
            skills_hint: [],
            plan_md: form.goal,
            complexity: form.complexity,
            client_request_id: UUID().uuidString
        )
        do {
            try await prepareClient()
            let resp = try await client.transfer(req)
            if selectedProjectId == projectId {
                currentEpicId = resp.epic_id
            }
            showToast("任务已创建：\(form.title)")
            isManualEpicPresented = false
        } catch {
            showToast("创建失败：\(error.localizedDescription)")
        }
    }

    // MARK: - Phase 2.2: Task templates

    @Published var templates: [TaskTemplate] = []
    @Published var isTemplatePickerPresented: Bool = false

    func loadTemplates() {
        guard let data = UserDefaults.standard.data(forKey: "ccc.taskTemplates"),
              let items = try? JSONDecoder().decode([TaskTemplate].self, from: data)
        else {
            templates = []
            return
        }
        templates = items
    }

    func saveTemplate(_ template: TaskTemplate) {
        loadTemplates()
        templates.append(template)
        guard let data = try? JSONEncoder().encode(templates) else { return }
        UserDefaults.standard.set(data, forKey: "ccc.taskTemplates")
    }

    func deleteTemplate(title: String) {
        loadTemplates()
        templates.removeAll { $0.title == title }
        guard let data = try? JSONEncoder().encode(templates) else { return }
        UserDefaults.standard.set(data, forKey: "ccc.taskTemplates")
    }

    func applyTemplate(_ template: TaskTemplate) {
        manualEpicForm = ManualEpicForm(
            title: template.title,
            goal: template.goal,
            acceptance: template.acceptance,
            pipeline: template.pipeline,
            executor: template.executor,
            complexity: template.complexity,
            priority: template.priority
        )
    }

    // MARK: - Phase 2.3: Board task CRUD

    func createBoardTask(workspace: String, title: String, description: String,
                         pipeline: String = "dev", executor: String = "opencode",
                         parentId: String? = nil) async {
        do {
            try await prepareClient()
            var body: [String: Any] = [
                "title": title,
                "description": description,
                "status": "backlog",
                "workspace": workspace,
                "executor": executor,
                "tags": pipeline.components(separatedBy: ",").map { $0.trimmingCharacters(in: .whitespaces) },
            ]
            if let parentId {
                body["parent_id"] = parentId
                body["card_kind"] = "work"
            }
            let w = workspace.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? workspace
            let data = try JSONSerialization.data(withJSONObject: body)
            let (_, code) = try await client.genericPOST("api/tasks?workspace=\(w)", body: data)
            if !(200..<300).contains(code) {
                throw APIError.http(code, "create task failed")
            }
            await refreshBoard()
            showToast("任务已创建: \(title)")
        } catch {
            boardError = error.localizedDescription
        }
    }

    func updateBoardTask(taskId: String, workspace: String, fields: [String: Any]) async {
        do {
            try await prepareClient()
            let w = workspace.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? workspace
            let t = taskId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? taskId
            let data = try JSONSerialization.data(withJSONObject: fields)
            let (_, code) = try await client.genericPATCH("api/tasks/\(t)?workspace=\(w)", body: data)
            if !(200..<300).contains(code) {
                throw APIError.http(code, "update task failed")
            }
            await refreshBoard()
        } catch {
            boardError = error.localizedDescription
        }
    }

    func deleteBoardTask(taskId: String, workspace: String) async {
        do {
            try await prepareClient()
            let w = workspace.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? workspace
            let t = taskId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? taskId
            let code = try await client.genericDELETE("api/tasks/\(t)?workspace=\(w)")
            if !(200..<300).contains(code) {
                throw APIError.http(code, "delete task failed")
            }
            await refreshBoard()
        } catch {
            boardError = error.localizedDescription
        }
    }

    // MARK: - Phase 2.4: Task artifacts

    @Published var taskArtifacts: [String: TaskArtifacts] = [:]

    func loadTaskArtifacts(taskId: String, workspace: String) async {
        do {
            try await prepareClient()
            let w = workspace.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? workspace
            let t = taskId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? taskId
            let data = try await client.genericGET("api/desktop/tasks/\(t)/artifacts?workspace=\(w)")
            let artifacts = try JSONDecoder().decode(TaskArtifacts.self, from: data)
            var copy = taskArtifacts
            copy[taskId] = artifacts
            taskArtifacts = copy
        } catch {
            // fail-soft
        }
    }

    // MARK: - Phase 3.2: Retry

    func retryFailedWork(workId: String, workspace: String) async {
        NotificationManager.requestAuthorization()
        do {
            try await prepareClient()
            let w = workspace.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? workspace
            let wid = workId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? workId
            let body = try JSONSerialization.data(withJSONObject: ["workspace": workspace])
            let (_, code) = try await client.genericPOST("api/desktop/flow/works/\(wid)/retry?workspace=\(w)", body: body)
            if !(200..<300).contains(code) {
                throw APIError.http(code, "retry failed")
            }
            showToast("已重试 work: \(workId)")
        } catch {
            showToast("重试失败: \(error.localizedDescription)")
        }
    }

    // MARK: - Phase 3.3: Failure analysis

    @Published var workFailures: [String: [FailureRecord]] = [:]

    func loadFailureAnalysis(workId: String, workspace: String) async {
        do {
            try await prepareClient()
            let w = workspace.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? workspace
            let wid = workId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? workId
            let data = try await client.genericGET("api/desktop/flow/works/\(wid)/failures?workspace=\(w)")
            let records = try JSONDecoder().decode([FailureRecord].self, from: data)
            var copy = workFailures
            copy[workId] = records
            workFailures = copy
        } catch {
            // fail-soft
        }
    }

    // MARK: - Phase 3.4: Project stats

    @Published var projectStats: [String: ProjectStats] = [:]

    func refreshProjectStats() async {
        do {
            try await prepareClient()
            let ws = projects.compactMap { $0.workspace }
            guard !ws.isEmpty else { return }
            let resp = try await client.fetchBoardSummaries(workspaces: ws)
            var stats: [String: ProjectStats] = [:]
            for (projectWS, snapshot) in resp.summaries {
                guard let counts = snapshot.counts else { continue }
                var s = ProjectStats()
                s.totalEpics = counts["backlog"] ?? 0
                s.activeWorks = (counts["in_progress"] ?? 0) + (counts["planned"] ?? 0)
                s.failedWorks = counts["abnormal"] ?? 0
                s.completedToday = counts["released"] ?? 0
                stats[projectWS] = s
            }
            projectStats = stats
        } catch {
            // fail-soft
        }
    }

    // MARK: - Phase 2.5: Custom prompts

    @Published var customPrompts: [QuickPromptItem] = []

    func loadCustomPrompts() {
        customPrompts = QuickPrompts.loadCustomPrompts()
    }

    func addCustomPrompt(title: String, prompt: String) {
        let item = QuickPromptItem(title: title, prompt: prompt)
        customPrompts.append(item)
        QuickPrompts.saveCustomPrompts(customPrompts)
    }

    func removeCustomPrompt(id: String) {
        customPrompts.removeAll { $0.title == id }
        QuickPrompts.saveCustomPrompts(customPrompts)
    }

    // MARK: - Phase 4.1: Update transfer with priority

    func submitTransferWithPriority(threadId: String? = nil, priority: String = "p2") async {
        // 扩展 TransferRequest 带 priority（Hub 侧需支持）
        // 当前直接调用 submitTransfer，priority 暂存于 note
        await submitTransfer(threadId: threadId)
    }

    // MARK: - Phase 4.4: Board filters

    @Published var boardStatusFilter: Set<String> = []
    @Published var boardExecutorFilter: String = ""
    @Published var boardPriorityFilter: Set<String> = []
    @Published var boardSearchQuery: String = ""

    var filteredBoardColumns: [String: [BoardTask]] {
        guard !boardStatusFilter.isEmpty || !boardExecutorFilter.isEmpty
                || !boardPriorityFilter.isEmpty || !boardSearchQuery.isEmpty
        else { return boardColumns }

        var result: [String: [BoardTask]] = [:]
        for (col, tasks) in boardColumns {
            let filtered = tasks.filter { task in
                if !boardStatusFilter.isEmpty, !boardStatusFilter.contains(task.status ?? "") {
                    return false
                }
                if !boardExecutorFilter.isEmpty,
                   (task.executor ?? "") != boardExecutorFilter {
                    return false
                }
                if !boardSearchQuery.isEmpty {
                    let q = boardSearchQuery.lowercased()
                    let title = (task.title ?? "").lowercased()
                    let note = (task.note ?? "").lowercased()
                    guard title.contains(q) || note.contains(q) else { return false }
                }
                return true
            }
            result[col] = filtered
        }
        return result
    }

    // MARK: - Phase 4.6: Export report

    func exportProjectReport(projectId: String) -> String {
        let tid = threadIdForProject( projectId)
        let messages = threadMessages[tid] ?? []
        let epic = currentEpicId ?? ""
        var report = "# 项目报告: \(projectId)\n\n"
        report += "## 概览\n"
        report += "- 对话轮数: \(messages.filter { $0.role == "user" }.count)\n"
        report += "- Epic: \(epic)\n"
        report += "- 活跃 Work: \(flowWorks.count)\n\n"
        report += "## Work 列表\n"
        for w in flowWorks {
            report += "- [\(w.displayStatus)] \(w.title) | \(w.displayExecutor)\n"
        }
        if !flowWorks.isEmpty {
            report += "\n## 执行状态\n"
            let active = flowWorks.filter(\.isActive).count
            let done = flowWorks.filter(\.isDone).count
            let failed = flowWorks.filter(\.isFailed).count
            report += "- 进行中: \(active)\n- 已完成: \(done)\n- 异常: \(failed)\n"
        }
        return report
    }

}
