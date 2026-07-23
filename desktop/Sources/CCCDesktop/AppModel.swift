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
    @AppStorage("ccc.server") var serverURLString: String = "http://127.0.0.1:17777"
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
    /// 对话模型偏好（请求级传 sidecar；默认 flash = MiniMax-M3）
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
    @Published var sidecarRuntimeLabel: String = ""
    @Published var sidecarConfigDir: String = ""
    @Published var sidecarLoopCodeVersion: String = ""
    /// 对话状态（messages + draft），独立 ObservableObject 隔离 delta 通知
    @Published var chat = ChatState()
    @Published var statusText: String = "未连接"
    /// "local" = 本机 sidecar 可聊；"none" = 本机 Agent 未就绪（禁止 Hub 聊天回退）
    @Published var agentMode: String = "none"
    /// 状态栏：本机 Agent / 本机 Agent 未就绪
    @Published var agentBadge: String = "本机 Agent 未就绪"
    /// 可聊 = sidecar 健康（与 hubReachable 独立）
    var canChat: Bool { agentMode == "local" }
    /// 可确认转任务 = 业务仓可下达（不依赖 Hub；确认后进本机 outbox，sidecar 后台投递）
    var canTransfer: Bool {
        canTransfer(projectId: selectedProjectId)
    }

    func canTransfer(projectId: String?) -> Bool {
        guard let projectId else { return false }
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
    @Published private(set) var hubReachable = false
    /// Hub 最近一次判失败时刻（可见重试文案）
    @Published private(set) var hubLastFailureAt: Date?
    /// 本轮不可达以来的探活失败次数
    @Published private(set) var hubRecoverAttempts: Int = 0
    /// 不可达时每轮探活递增，驱动「Ns 前失败」刷新
    @Published private(set) var hubRecoverTick: UInt64 = 0
    /// Phase16：Hub 后台刷新中（首屏已用本机缓存）
    @Published private(set) var hubSyncing = false
    /// Hub flow SSE 的连接与恢复代次（稳定性诊断）
    @Published private(set) var flowConnectionGeneration: [String: UInt64] = [:]
    @Published private(set) var flowReconnectCount: [String: Int] = [:]
    @Published private(set) var flowLastError: [String: String] = [:]
    /// 兼容旧路径 / smoke；多窗 UI 用 WindowChatState.destination
    @Published var destination: SidebarDestination = .chat
    @Published var toast: String?
    /// 快捷条进行中标签（对齐基线/下一步/…）；点按时立即置位，流结束清空
    @Published var activeQuickAction: String? = nil
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
    /// 运维页合并：本机 sidecar 是否 ok（Hub 无法探 M1）
    @Published var opsAgentOk: Bool?
    @Published var opsAgentRuntime: String?
    @Published var opsAgentModel: String?
    @Published var opsCopiedHint: String?
    @Published var inboxProposals: [InboxProposal] = []
    @Published var inboxAdoptBusy = false
    /// 顶栏：本机 Agent 大模型调用（日总量 + 近 5 秒）
    @Published private(set) var agentLLMDailyCount: Int = 0
    @Published private(set) var agentLLMRecent5s: Int = 0
    /// 非 Published：TitlebarUsageAccessory 自读；禁止 1Hz 拖 SwiftUI 树
    private(set) var agentUsageTick: UInt64 = 0
    private var agentLLMCallTimestamps: [Date] = []
    private var agentUsageTask: Task<Void, Never>?
    private static let agentLLMDayKey = "ccc.agentLLM.day"
    private static let agentLLMDailyKey = "ccc.agentLLM.dailyCount"

    /// 项目级看板列计数（右栏顶条）；key=projectId
    @Published private(set) var projectBoardCounts: [String: [String: Int]] = [:]
    /// 上一拍 counts，用于 Δ
    private var projectBoardCountsPrev: [String: [String: Int]] = [:]
    /// 项目级编排快照（右栏 SSOT；同项目任意会话共享）
    @Published private(set) var projectFlow: [String: FlowThreadSnapshot] = [:]
    @Published private(set) var projectFlowRevision: [String: UInt64] = [:]

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
    /// 同 turn 已生成的最新 partial：用于在 retry 2 之前保留半截内容到 transientNote
    private var partialByTurn: [String: String] = [:]
    /// 侧路回调：让 `runChatStream` 在 `applyChatEvent` 之后更新 partial 镜像
    private var onChatEventInPlace: ((String, UUID, ChatStreamEvent) -> Void)?
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
    /// Hub 不可达时自动探活（对称 agentRecover；≤5s 周期）
    private var hubRecoverTask: Task<Void, Never>?
    /// 回前台 resume 防抖：避免 scenePhase 连触发叠请求
    private var foregroundResumeTask: Task<Void, Never>?
    private var lastForegroundResumeAt: Date?
    /// 每项目上次真暖时间（多窗分别记）
    private var lastWarmAtByProject: [String: Date] = [:]
    /// 本机落盘节流：按 threadId 独立，避免多会话互相取消丢落盘
    private var diskSaveTasks: [String: Task<Void, Never>] = [:]

    /// 兼容旧 UI 命名：仅反映「当前会话」是否在生成
    var isStreaming: Bool { currentThreadStreaming }

    init() {
        // 与 @AppStorage 默认一致：Hub 走本机 SSH 隧道（LAN :7777 偶发 TCP 卡死）
        let raw = UserDefaults.standard.string(forKey: "ccc.server")
            ?? "http://127.0.0.1:17777"
        let url = APIClient.makeBaseURL(from: raw)
            ?? URL(string: "http://127.0.0.1:17777")!
        let user = UserDefaults.standard.string(forKey: "ccc.user") ?? "ccc"
        let pass = UserDefaults.standard.string(forKey: "ccc.pass") ?? "ccc"
        client = APIClient(baseURL: url, user: user, password: pass)
        // Phase16：首帧前同步灌本机缓存，侧栏/对话/右栏秒开（Hub 后台同步）
        hydrateFromDiskSync()
    }

    /// Hub 稳定性：LAN :7777 偶发 TCP 卡死；本机 SSH 隧道 :17777 为默认主路径
    private static let hubTunnelURL = "http://127.0.0.1:17777"

    /// 若仍指向 LAN，且隧道已通 → 自动切到隧道（一次迁移，写回 AppStorage）
    private func preferHubTunnelIfReady() async {
        let cur = serverURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        let looksLan = cur.contains("192.168.3.116")
        guard looksLan || cur.isEmpty else { return }
        guard let url = URL(string: "\(Self.hubTunnelURL)/api/desktop/config") else { return }
        var req = URLRequest(url: url)
        req.timeoutInterval = 2
        let token = Data("\(authUser):\(authPass)".utf8).base64EncodedString()
        req.setValue("Basic \(token)", forHTTPHeaderField: "Authorization")
        do {
            let (_, resp) = try await URLSession.shared.data(for: req)
            guard (resp as? HTTPURLResponse)?.statusCode == 200 else { return }
            serverURLString = Self.hubTunnelURL
            // #region agent log
            DebugAgentLog.log(
                hypothesisId: "H-HUB",
                location: "AppModel.preferHubTunnelIfReady",
                message: "migrated ccc.server LAN→tunnel",
                data: ["from": cur, "to": Self.hubTunnelURL],
                runId: "post-fix"
            )
            // #endregion
        } catch {
            // 隧道未起：保持 LAN，recover loop 继续探
        }
    }

    /// Phase16：从 `projects-cache` + session 盘灌 RAM；有缓存则立刻 `connected`
    private func hydrateFromDiskSync() {
        if let cache = LocalSessionStore.loadProjects(), !cache.projects.isEmpty {
            projects = cache.projects
            let preferred = persistedProjectId.trimmingCharacters(in: .whitespacesAndNewlines)
            if !preferred.isEmpty, projects.contains(where: { $0.id == preferred }) {
                selectedProjectId = preferred
            } else if selectedProjectId == nil
                || !projects.contains(where: { $0.id == selectedProjectId })
            {
                selectedProjectId = cache.default_project
                    ?? cache.projects.first(where: \.isDispatchable)?.id
                    ?? cache.projects.first?.id
            }
        }
        guard let pid = selectedProjectId, !pid.isEmpty else {
            if !projects.isEmpty {
                connected = true
                statusText = "本机缓存 · 待选项目"
                hubSyncing = true
            }
            return
        }
        expandedProjectIds.insert(pid)
        let recent = LocalSessionStore.threadsAsDesktop(projectId: pid).first?.thread_id
        let tid = recent ?? threadIdForProject(pid)
        var local = LocalSessionStore.threadsAsDesktop(projectId: pid)
        if local.isEmpty, !LocalSessionStore.isArchived(projectId: pid, threadId: tid) {
            LocalSessionStore.saveMessages(
                projectId: pid,
                threadId: tid,
                messages: [],
                title: "对话",
                allowDowngrade: true
            )
            local = LocalSessionStore.threadsAsDesktop(projectId: pid)
        }
        threads = local
        selectedThreadId = tid
        if !LocalSessionStore.isArchived(projectId: pid, threadId: tid) {
            hydrateThreadFromDisk(projectId: pid, threadId: tid)
        }
        applyFlowSnapshot(threadFlow[tid])
        syncLegacyChatMirror(from: tid)
        hydrateTransferDeliveryFromDisk()
        hydrateBoardCacheIfNeeded(projectId: pid)
        rearmFanoutWatchdogIfNeeded(projectId: pid)
        if !projects.isEmpty {
            connected = true
            statusText = "本机缓存 · Hub 同步中…"
            hubSyncing = true
        }
    }

    /// R1：从 receipts / outbox / failed / 磁盘 flow 重建投递徽章（再开第一帧诚实）
    private func hydrateTransferDeliveryFromDisk() {
        applyReceiptsFromDisk()
        var map = transferDeliveryByThread
        for item in LocalSessionStore.loadTransferOutbox() {
            if item.attempts >= LocalSessionStore.maxTransferOutboxAttempts {
                map[item.thread_id] = .failed
            } else {
                map[item.thread_id] = .queued
            }
        }
        for item in LocalSessionStore.loadFailedTransfers() {
            map[item.thread_id] = .failed
        }
        // 无 outbox 但有未完成 epic → 已投递/已受理（sidecar 可能已在关 App 期间投完）
        for (tid, snap) in threadFlow {
            if map[tid] != nil { continue }
            let eid = (snap.epicId ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            guard !eid.isEmpty, !eid.hasPrefix("pending:") else { continue }
            let stage = (snap.epic?.user_stage ?? "").lowercased()
            if stage == "done" { continue }
            if snap.works.isEmpty {
                map[tid] = .delivered
            } else {
                map[tid] = .accepted
            }
        }
        transferDeliveryByThread = map
    }

    /// R2：看板磁盘缓存上屏
    private func hydrateBoardCacheIfNeeded(projectId: String) {
        guard let cache = LocalSessionStore.loadBoardCache(projectId: projectId) else { return }
        if boardColumns.isEmpty {
            boardColumns = cache.columns
            boardWorkspaceLabel = cache.workspace ?? projectId
            boardStale = true
            boardError = nil
            updateStackStatus()
        }
    }

    /// R4/R5：hydrate 后若 epic 未拆分，重挂 fanout watchdog；禁闪「编排空闲」
    private func rearmFanoutWatchdogIfNeeded(projectId: String?) {
        let pid = projectId ?? selectedProjectId
        guard let pid else { return }
        let tid = threadIdForProject(pid)
        guard var snap = threadFlow[tid] else { return }
        let eid = (snap.epicId ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !eid.isEmpty else { return }
        let stage = (snap.epic?.user_stage ?? snap.headline).lowercased()
        if stage == "done" { return }
        if snap.works.isEmpty {
            if snap.emptyMessage.contains("编排空闲") || snap.emptyMessage.isEmpty {
                snap.emptyMessage = "编排同步中…"
                threadFlow[tid] = snap
                bumpFlowRevision(tid)
                if selectedProjectId == pid {
                    applyFlowSnapshot(snap)
                }
            }
            startFanoutWatchdog(epicId: eid, projectId: pid, threadId: tid)
        }
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

    /// 显式 map 优先；业务仓无本机第二树时返回 nil（sidecar 回落平台 DEFAULT_CWD，事实靠 Hub 基线）。
    /// 仅 `ccc` 可回落到 ccc.home / 全局本机路径。禁止用 Hub 的 2017 路径或「全局路径冒充业务 cwd」。
    func localPath(for projectId: String?) -> String? {
        guard let projectId, !projectId.isEmpty else {
            let g = localWorkspacePath.trimmingCharacters(in: .whitespacesAndNewlines)
            return g.isEmpty ? nil : g
        }
        if let mapped = workspaceMap[projectId]?.trimmingCharacters(in: .whitespacesAndNewlines),
           !mapped.isEmpty {
            if FileManager.default.fileExists(atPath: mapped) {
                return mapped
            }
            return nil
        }
        if projectId == "ccc" {
            let home = cccHomePath.trimmingCharacters(in: .whitespacesAndNewlines)
            if !home.isEmpty, FileManager.default.fileExists(atPath: home) {
                return home
            }
            let global = localWorkspacePath.trimmingCharacters(in: .whitespacesAndNewlines)
            if !global.isEmpty, FileManager.default.fileExists(atPath: global) {
                return global
            }
        }
        return nil
    }

    private func prepareClient(projectId: String? = nil, ensureAgent: Bool = true) async throws {
        guard let url = APIClient.makeBaseURL(from: serverURLString) else {
            throw APIError.badURL
        }
        // Hub 编排同步不必等 sidecar；对话路径才 ensureAgent
        let chatURL: URL?
        if ensureAgent {
            chatURL = await ensureLocalAgent()
        } else if let cached = cachedAgentBaseURL {
            chatURL = cached
        } else {
            chatURL = APIClient.makeBaseURL(from: agentURLString)
        }
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

        // 一次 /health：勿 probe 后再打一遍
        if let info = await client.fetchAgentHealth(base: candidate), info.ok {
            agentProbeOKUntil = Date().addingTimeInterval(10)
            cachedAgentBaseURL = candidate
            agentMode = "local"
            agentBadge = "本机 Agent"
            didToastHubFallback = false
            sidecarReportedModel = info.model ?? ""
            sidecarRuntimeLabel = info.agentRuntime ?? ""
            sidecarConfigDir = info.configDir ?? ""
            sidecarLoopCodeVersion = info.loopCodeVersion ?? ""
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

    /// Hub 不可达时每 4s 轻量探活；恢复后 flush outbox + snapshot（F1；对称 sidecar recover）
    private func startHubRecoverLoopIfNeeded() {
        guard !hubReachable else { return }
        if hubRecoverTask != nil { return }
        hubRecoverTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 4_000_000_000) // ≤5s SLA
                guard let self, !Task.isCancelled else { break }
                if self.hubReachable {
                    self.hubRecoverTask = nil
                    break
                }
                // 驱动 UI「Ns 前失败」刷新
                await MainActor.run { self.hubRecoverTick &+= 1 }
                if await self.probeAndRecoverHub() {
                    self.hubRecoverTask = nil
                    break
                }
            }
        }
    }

    /// 轻量探活：health 3s；成功再补 projects / flush。失败静默（勿 toast 刷屏），但刷新 attempts。
    @discardableResult
    private func probeAndRecoverHub() async -> Bool {
        do {
            try await prepareClient(ensureAgent: false)
            _ = try await client.probeHubHealth()
            // 探活成功：补全项目列表（失败不挡可达态）
            if let resp = try? await client.fetchProjects() {
                projects = resp.projects
                LocalSessionStore.saveProjects(resp.projects, defaultProject: resp.default_project)
            }
            setHubReachable(true, source: "hub_recover_probe")
            hubRecoverAttempts = 0
            hubLastFailureAt = nil
            let localOK = agentMode == "local"
            connected = localOK || !projects.isEmpty
            lastError = nil
            updateConnectionStatusText(localOK: localOK, hubOK: true)
            await flushPendingHubSync()
            // 耗尽 failed 在 Hub 恢复时自动救回 outbox（不必只靠「后台再试」）
            let requeued = LocalSessionStore.requeueAllFailedTransfers()
            if requeued > 0 {
                for item in LocalSessionStore.loadTransferOutbox() {
                    setTransferDelivery(item.thread_id, .queued)
                }
            }
            let delivered = await flushTransferOutbox()
            applyReceiptsFromDisk()
            reconcileTransferDeliveryWithOutbox()
            await bindFlowToCurrentThread()
            await refreshProjectTaskState()
            if delivered > 0 {
                showToast("Hub 已恢复 · 排队任务已投递")
            } else if requeued > 0 {
                showToast("Hub 已恢复 · 失败投递已重新排队")
            }
            return true
        } catch {
            hubRecoverAttempts += 1
            hubLastFailureAt = Date()
            setHubReachable(false, source: "hub_recover_probe", error: error)
            return false
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
        // #region agent log
        DebugAgentLog.log(
            hypothesisId: "H1",
            location: "AppModel.setAgentModeNone",
            message: "agentMode→none (canChat false hides messageArea)",
            data: ["reason": reason, "prevMode": agentMode, "selectedThreadId": selectedThreadId ?? ""]
        )
        // #endregion
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
            serverURLString = Self.hubTunnelURL
        }
        await preferHubTunnelIfReady()
        // Phase16：init 已 hydrate；此处再幂等一次（防 UISmoke 等路径跳过 init 副作用）
        if projects.isEmpty {
            hydrateFromDiskSync()
        }
        // Hub / sidecar 后台刷新 —— 不挡首屏；flush 在 refreshProjects 内异步，勿重复串行
        hubSyncing = true
        Task { @MainActor in
            await self.refreshProjects(showBusy: false)
            if self.agentMode != "local" {
                self.startAgentRecoverLoopIfNeeded()
            }
            self.rearmFanoutWatchdogIfNeeded(projectId: self.selectedProjectId)
        }
        startProjectTaskPolling()
        startAgentUsageTicker()
        if ProcessInfo.processInfo.environment["CCC_DESKTOP_UI_SMOKE"] == "1" {
            // smoke 需等首轮 refresh 完成再发消息
            while hubSyncing {
                try? await Task.sleep(nanoseconds: 50_000_000)
            }
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

    /// - Parameter holdSeconds: 展示时长；长耗时操作用更长 hold，避免「点了没反馈」
    func showToast(_ msg: String, holdSeconds: Double = 5) {
        toast = msg
        let hold = max(1.5, holdSeconds)
        Task {
            try? await Task.sleep(nanoseconds: UInt64(hold * 1_000_000_000))
            if toast == msg { toast = nil }
        }
    }

    /// Hub / 网络错误 → 白话（对齐基线等快捷条用）
    private func friendlyHubError(_ error: Error, action: String) -> String {
        if let api = error as? APIError {
            switch api {
            case .badURL:
                return "\(action)失败：Hub 地址无效（设置里检查 Server）"
            case .http(let code, let body):
                if code == 0 || code == 502 || code == 503 || code == 504 {
                    return "\(action)失败：Hub 暂不可达（HTTP \(code)）。可聊；恢复后重试"
                }
                let brief = body.trimmingCharacters(in: .whitespacesAndNewlines)
                if brief.isEmpty { return "\(action)失败：HTTP \(code)" }
                return "\(action)失败：HTTP \(code) \(brief.prefix(120))"
            default:
                return "\(action)失败：\(api.localizedDescription)"
            }
        }
        let ns = error as NSError
        if ns.domain == NSURLErrorDomain {
            switch ns.code {
            case NSURLErrorTimedOut, NSURLErrorCannotConnectToHost, NSURLErrorNetworkConnectionLost,
                 NSURLErrorNotConnectedToInternet, NSURLErrorDNSLookupFailed:
                return "\(action)失败：连不上 Hub（\(serverURLString)）。可聊；恢复后重试「\(action)」"
            default:
                break
            }
        }
        return "\(action)失败：\(error.localizedDescription)"
    }

    func refreshProjects() async {
        await refreshProjects(showBusy: true)
    }

    /// Phase16：`showBusy=false` 用于冷启动后台同步，避免首屏全局转圈
    func refreshProjects(showBusy: Bool) async {
        if showBusy {
            busy = true
        }
        defer {
            if showBusy { busy = false }
            if hubSyncing { hubSyncing = false }
        }
        // Agent 与 Hub 并行：同步 Hub 不再等 sidecar 探活/自启
        async let agentURL: URL? = ensureLocalAgent()

        do {
            try await prepareClient(ensureAgent: false)
            let resp = try await client.fetchProjects()
            projects = resp.projects
            setHubReachable(true, source: "refresh_projects")
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
            }
            let localOK = (await agentURL) != nil || agentMode == "local"
            connected = localOK || !projects.isEmpty
            lastError = nil
            updateConnectionStatusText(localOK: localOK, hubOK: true)
            // 项目列表已上屏 → 结束「同步中」；流程轨/灯/outbox 继续后台
            hubSyncing = false
            startWarmLoopIfNeeded()

            if selectedProjectId != nil {
                async let bind: Void = bindFlowToCurrentThread()
                async let lights: Void = refreshProjectTaskState()
                await bind
                await lights
            } else {
                await refreshProjectTaskState()
            }

            Task { @MainActor in
                await self.flushPendingHubSync()
                let requeued = LocalSessionStore.requeueAllFailedTransfers()
                if requeued > 0 {
                    for item in LocalSessionStore.loadTransferOutbox() {
                        self.setTransferDelivery(item.thread_id, .queued)
                    }
                }
                await self.flushTransferOutbox()
                self.applyReceiptsFromDisk()
                self.reconcileTransferDeliveryWithOutbox()
            }
        } catch {
            _ = await agentURL
            hubSyncing = false
            setHubReachable(false, source: "refresh_projects", error: error)
            lastError = error.localizedDescription
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
            let localOK = agentMode == "local"
            connected = localOK || !projects.isEmpty
            showSettingsHint = !localOK && !hubReachable
            updateConnectionStatusText(localOK: localOK, hubOK: false)
            if !localOK {
                showToast("本机 Agent 未就绪（对话不可用）。Hub：\(error.localizedDescription)")
            } else {
                showToast("Hub 暂不可达（可聊；转任务确认后排队，恢复后自动投递）")
            }
            if localOK { startWarmLoopIfNeeded() }
        }
    }

    private func setHubReachable(_ reachable: Bool, source: String, error: Error? = nil) {
        if reachable {
            hubLastFailureAt = nil
            hubRecoverAttempts = 0
        } else {
            hubLastFailureAt = Date()
        }
        guard hubReachable != reachable else {
            // 已不可达但探活任务未跑时补启（幂等）
            if !reachable { startHubRecoverLoopIfNeeded() }
            return
        }
        hubReachable = reachable
        DesktopChatTurnLedger.append([
            "event": "hub_reachability",
            "reachable": reachable,
            "source": source,
            "error_type": error.map { String(describing: type(of: $0)) } ?? "",
        ])
        if !reachable {
            startHubRecoverLoopIfNeeded()
        }
        // 可达时不 cancel hubRecoverTask：由循环自检 hubReachable 后停，避免探活任务内 set true 时把自己 cancel 掉
    }

    private func updateConnectionStatusText(localOK: Bool, hubOK: Bool) {
        if localOK && hubOK {
            statusText = "已连接 · 本机 Agent"
            agentBadge = "本机 Agent"
        } else if localOK && !hubOK {
            statusText = "本机 Agent · \(hubRetryStatusPhrase)"
            agentBadge = "本机 Agent"
        } else if !localOK && hubOK {
            statusText = "Hub 可达 · 可转任务 · 本机 Agent 未就绪"
            agentBadge = "本机 Agent 未就绪"
        } else {
            statusText = "本机 Agent 未就绪 · \(hubRetryStatusPhrase)"
            agentBadge = "本机 Agent 未就绪"
        }
    }

    /// 不可达时的可见重试文案（右栏 / 状态栏共用）
    var hubRetryStatusPhrase: String {
        _ = hubRecoverTick // 订阅 tick，保证秒数刷新
        let attempts = max(hubRecoverAttempts, 1)
        guard let at = hubLastFailureAt else {
            return "Hub · 重试中"
        }
        let secs = max(0, Int(Date().timeIntervalSince(at)))
        return "Hub · 重试中 · 第\(attempts)次 · \(secs)s 前失败"
    }

    func selectProject(_ id: String, preferredThreadId: String? = nil) async {
        let switching = id != selectedProjectId
        // 先把「即将离开」的线程钉进 RAM+盘；SSOT 是 threadMessages，不靠 chat.messages
        if let prev = selectedProjectId, switching {
            let prevTid = resolveThreadId(projectId: prev, preferred: selectedThreadId)
            persistCurrentThreadSnapshot(threadId: prevTid)
        }
        // 显式 preferred（同项目且索引/磁盘存在）优先，禁止被「最近线程」冲掉中栏
        let preferred = Self.resolvedPreferredThreadId(projectId: id, preferred: preferredThreadId)
        let localRecent = LocalSessionStore.threadsAsDesktop(projectId: id).first?.thread_id
        let eagerTid = preferred ?? localRecent ?? threadIdForProject(id)
        selectedProjectId = id
        persistedProjectId = id
        expandedProjectIds.insert(id)
        // 编排运维 Agent：进入 ccc 时默认工程师模式（可写本机 CCC）
        if id == "ccc", preferredToolMode != "discuss" {
            preferredToolMode = "engineer"
        }
        ensureThreadHydrated(threadId: eagerTid)
        selectedThreadId = eagerTid
        if switching {
            selectedNodeDetail = nil
            ensureFlowSSE()
            // 右栏先贴本线程缓存，等 load 完成再精修（禁止先清空）
            if let snap = threadFlow[eagerTid] {
                applyFlowSnapshot(snap)
            }
            hydrateBoardCacheIfNeeded(projectId: id)
            rearmFanoutWatchdogIfNeeded(projectId: id)
            reconcileTransferDeliveryWithOutbox()
        }
        // 多会话：刷新索引后再对齐；有 preferred 则钉死，不被 recent 覆盖
        await refreshThreads(projectId: id)
        let recent = threads.first(where: {
            LocalSessionStore.projectId(fromThreadId: $0.thread_id) == id
        })?.thread_id
        let tid = preferred ?? recent ?? threadIdForProject(id)
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
    func openProjectConversation(_ id: String, preferredThreadId: String? = nil) async {
        destination = .chat
        // 点卡瞬间先灌 RAM，保证本窗立刻只显示目标 tid（不等 await）
        if let pref = Self.resolvedPreferredThreadId(projectId: id, preferred: preferredThreadId) {
            ensureThreadHydrated(threadId: pref)
        } else {
            ensureThreadHydrated(projectId: id)
        }
        await selectProject(id, preferredThreadId: preferredThreadId)
    }

    /// preferred 须属 pid，且在索引或磁盘会话中存在
    private static func resolvedPreferredThreadId(projectId: String, preferred: String?) -> String? {
        guard let raw = preferred?.trimmingCharacters(in: .whitespacesAndNewlines), !raw.isEmpty,
              Self.projectId(fromThreadId: raw) == projectId
        else { return nil }
        let listed = LocalSessionStore.threadsAsDesktop(projectId: projectId)
            .contains(where: { $0.thread_id == raw })
        if listed { return raw }
        if LocalSessionStore.load(projectId: projectId, threadId: raw) != nil { return raw }
        return nil
    }

    /// 多窗：保证指定 thread 在 RAM 中已水合。
    func ensureThreadHydrated(threadId: String) {
        guard !threadId.isEmpty else { return }
        if threadMessages[threadId] == nil {
            let pid = LocalSessionStore.projectId(fromThreadId: threadId)
            hydrateThreadFromDisk(projectId: pid, threadId: threadId)
            if threadMessages[threadId] == nil {
                // 流式中 hydrate 可能跳过：勿种空覆盖
                if streamingThreadIds.contains(threadId) || chatTasks[threadId] != nil {
                    return
                }
                // 新会话 / 磁盘 miss：种空数组以结束「加载中」。空列表不再卸 messageArea（见 CodexChatPane）。
                DebugAgentLog.log(
                    hypothesisId: "H3",
                    location: "AppModel.ensureThreadHydrated",
                    message: "seed empty RAM (disk miss or new thread)",
                    data: ["threadId": threadId, "projectId": pid]
                )
                threadMessages[threadId] = []
            }
            bumpThreadRevision(threadId)
        }
    }

    /// 中栏：RAM 尚未登记该 tid（水合前）→ 转圈，勿 offlineCenter
    func hasHydratedThread(_ threadId: String?) -> Bool {
        guard let threadId, !threadId.isEmpty else { return false }
        return threadMessages[threadId] != nil
    }

    /// 兼容旧 API：水合该项目「最近活动线程」，禁止盲种已归档的 ::main（H3）
    func ensureThreadHydrated(projectId: String) {
        let recent = LocalSessionStore.threadsAsDesktop(projectId: projectId).first?.thread_id
        let tid = (recent?.isEmpty == false) ? recent! : threadIdForProject(projectId)
        // #region agent log
        if tid.hasSuffix("::main") {
            DebugAgentLog.log(
                hypothesisId: "H3",
                location: "AppModel.ensureThreadHydrated(projectId:)",
                message: "hydrating legacy ::main (no recent thread)",
                data: ["projectId": projectId, "threadId": tid],
                runId: "post-fix"
            )
        }
        // #endregion
        ensureThreadHydrated(threadId: tid)
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
        } else if !disk.isEmpty {
            threadMessages[tid] = disk
        } else if !ram.isEmpty {
            // 定稿/开 TransferSheet 时偶发空盘快照 — 禁止用空数组抹掉中栏
            threadMessages[tid] = ram
        } else {
            threadMessages[tid] = disk
        }
        // #region agent log
        let after = threadMessages[tid]?.count ?? -1
        if after == 0 || (ram.count > 0 && after < ram.count) {
            DebugAgentLog.log(
                hypothesisId: "H3",
                location: "AppModel.loadConversation",
                message: "thread message count drop/empty after load",
                data: [
                    "threadId": tid,
                    "ram": ram.count,
                    "disk": disk.count,
                    "after": after,
                    "keepRam": keepRam,
                    "streaming": streamingThreadIds.contains(tid),
                ]
            )
        }
        // #endregion
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
        // 磁盘里的 pending: 若投递已结束 → 立刻清幽灵，勿等下一次空 snapshot
        if Self.isPendingEpicId(threadFlow[tid]?.epicId) {
            clearStalePendingIfNeeded(threadId: tid, remoteEpicsEmpty: true)
        }
        bumpThreadRevision(tid)
        bumpFlowRevision(tid)
        // chat.messages 仅作「全局选中线程」镜像（smoke/旧路径）；UI 列表读 threadMessages
        syncLegacyChatMirror(from: tid)
        // 只清/刷本线程定稿条；已交接则禁止复活确认卡
        if shouldSuppressTransferDraft(for: tid) {
            setThreadTransferDraft(tid, nil)
        } else if let lastAsst = (threadMessages[tid] ?? []).last(where: { $0.role == "assistant" && !$0.isStreaming }) {
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
        let pid = (selectedProjectId ?? "").trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if !pid.isEmpty, pid != "ccc" {
            showToast("业务仓不可工程师模式：请定稿转任务")
            preferredToolMode = "discuss"
            return
        }
        confirmEngineerMode = true
    }

    func confirmEnableEngineerMode() {
        let pid = (selectedProjectId ?? "").trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if !pid.isEmpty, pid != "ccc" {
            preferredToolMode = "discuss"
            confirmEngineerMode = false
            showToast("业务仓不可工程师模式：请定稿转任务")
            return
        }
        preferredToolMode = "engineer"
        confirmEngineerMode = false
        showToast("工程师模式：允许本机改文件（仅 ccc）")
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
            // #region agent log
            if ram.count > 0, disk.messages.count < ram.count {
                DebugAgentLog.log(
                    hypothesisId: "H3",
                    location: "AppModel.hydrateThreadFromDisk",
                    message: "disk overwrite shrinks RAM",
                    data: [
                        "threadId": threadId,
                        "ram": ram.count,
                        "disk": disk.messages.count,
                        "ramScore": ramScore,
                        "diskScore": diskScore,
                    ]
                )
            } else if ram.isEmpty, disk.messages.isEmpty {
                DebugAgentLog.log(
                    hypothesisId: "H3",
                    location: "AppModel.hydrateThreadFromDisk",
                    message: "hydrate keeps empty (ram+disk empty)",
                    data: ["threadId": threadId]
                )
            }
            // #endregion
            threadMessages[threadId] = disk.messages
        }
        if let flow = disk.flow, threadFlow[threadId] == nil || (threadFlow[threadId]?.works.isEmpty == true && !flow.works.isEmpty) {
            threadFlow[threadId] = flow
        } else if threadFlow[threadId] == nil, disk.flow != nil {
            threadFlow[threadId] = disk.flow
        }
        if Self.isPendingEpicId(threadFlow[threadId]?.epicId) {
            clearStalePendingIfNeeded(threadId: threadId, remoteEpicsEmpty: true)
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
            // R5：有 bind 禁止闪「编排空闲」
            var empty = snap.emptyMessage
            let eid = (snap.epicId ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            if !eid.isEmpty, snap.works.isEmpty,
               empty.contains("编排空闲") || empty.isEmpty {
                empty = "编排同步中…"
            }
            flowEmptyMessage = empty
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
            try await prepareClient(ensureAgent: false)
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
            setHubReachable(true, source: "thread_backup_fetch")
        } catch {
            hydrateThreadFromDisk(projectId: projectId, threadId: threadId)
            bumpThreadRevision(threadId)
            syncLegacyChatMirror(from: threadId)
        }
    }

    /// 右栏：本地 boundEpicId 为 SSOT；Hub 列表只作 enrichment，空列表不冲本地
    private func syncFlowFromServer(projectId: String, threadId: String, generation: UInt64) async {
        do {
            try await prepareClient(ensureAgent: false)
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
                await refreshFlowNow(projectId: projectId, threadId: threadId)
            } else if let hint = epicsResp.boundHint, !hint.isEmpty {
                if selectedThreadId == threadId {
                    currentEpicId = hint
                }
                await refreshFlowNow(projectId: projectId, threadId: threadId)
            } else if let match = epics.first(where: { ($0.thread_id ?? "") == threadId })?.epic_id {
                // 只接受「精确 thread 匹配」的 Hub 建议；不挑项目里任意最近 epic（Phase14）
                if selectedThreadId == threadId {
                    currentEpicId = match
                }
                await refreshFlowNow(projectId: projectId, threadId: threadId)
            } else if hasLocalFlow {
                // Hub 列表为空 / 不匹配时，保留本地绑定；不要用 epics.first 抢绑
                return
            } else {
                // Phase14：未绑定且无合法 hint/match → 空态，禁止默默挂项目里任意一笔最近 epic
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
        // #region agent log
        let prev = threadMessages[threadId]?.count ?? 0
        if prev > 0, msgs.isEmpty {
            DebugAgentLog.log(
                hypothesisId: "H3",
                location: "AppModel.persistMessages",
                message: "persist empty over non-empty RAM",
                data: ["threadId": threadId, "prev": prev]
            )
        }
        // #endregion
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

    private func bumpProjectFlowRevision(_ projectId: String) {
        guard !projectId.isEmpty else { return }
        var copy = projectFlowRevision
        copy[projectId, default: 0] &+= 1
        projectFlowRevision = copy
    }

    /// 写项目级右栏快照（与 threadFlow 镜像；UI 只读这个）
    private func setProjectFlow(_ projectId: String, _ snap: FlowThreadSnapshot) {
        guard !projectId.isEmpty else { return }
        var copy = projectFlow
        copy[projectId] = snap
        projectFlow = copy
        bumpProjectFlowRevision(projectId)
    }

    /// 多窗显示 SSOT：只读 threadMessages，绝不回落全局 chat.messages（否则切项目会串台）。
    func messagesForThread(_ threadId: String?) -> [ChatMessage] {
        guard let threadId, !threadId.isEmpty else { return [] }
        return threadMessages[threadId] ?? []
    }

    /// 右栏按项目取编排（同项目任意会话同一份）
    func flowSnapshot(forProject projectId: String?) -> FlowThreadSnapshot? {
        guard let projectId, !projectId.isEmpty else { return nil }
        return projectFlow[projectId]
    }

    /// 兼容旧调用：thread → 映射到所属项目的 projectFlow
    func flowSnapshot(for threadId: String?) -> FlowThreadSnapshot? {
        guard let threadId, !threadId.isEmpty else { return nil }
        let pid = LocalSessionStore.projectId(fromThreadId: threadId)
        if let pf = projectFlow[pid] { return pf }
        return threadFlow[threadId]
    }

    /// 看板列计数（右栏顶条）
    func boardCounts(forProject projectId: String?) -> [String: Int] {
        guard let projectId, !projectId.isEmpty else { return [:] }
        return projectBoardCounts[projectId] ?? [:]
    }

    func boardCountsDelta(forProject projectId: String?) -> [String: Int] {
        guard let projectId, !projectId.isEmpty else { return [:] }
        let cur = projectBoardCounts[projectId] ?? [:]
        let prev = projectBoardCountsPrev[projectId] ?? [:]
        var delta: [String: Int] = [:]
        let keys = Set(cur.keys).union(prev.keys)
        for k in keys {
            let d = (cur[k] ?? 0) - (prev[k] ?? 0)
            if d != 0 { delta[k] = d }
        }
        return delta
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

    /// 运维红灯 / 板务交接：打开编排运维（ccc）会话并填入摘要
    func handoffToOpsAgent(payload: String, sourceProjectId: String? = nil) async {
        var text = payload.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        if let src = sourceProjectId?.trimmingCharacters(in: .whitespacesAndNewlines), !src.isEmpty,
           !text.contains("project_id=")
        {
            text = "【交编排运维】来源项目=\(src)\n\(text)"
        }
        if !text.contains("编排运维") && !text.contains("hub_repair") {
            text = "【CCC 编排运维】请清板或处理下列运维问题（可用 hub_repair 跨项目）：\n\(text)"
        }
        destination = .chat
        await openProjectConversation("ccc")
        fillComposer(text: text, threadId: selectedThreadId)
        opsCopiedHint = "已交编排运维"
    }

    /// 把文本填入输入框（经 composerBounce → ContentView）
    func fillComposer(text: String, threadId: String?) {
        setComposerBounce(text, threadId: threadId)
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
        // 长工具回合：assistant 常 isStreaming=true 且 content 空，但 toolSteps 已堆满。
        // 旧过滤 `!$0.isStreaming || !$0.content.isEmpty` 会把整条助手（含工具轨）丢掉，
        // done 瞬间若尚未清 isStreaming，落盘变瘦 → 随后 hydrate 像「对话消失」。
        let msgs = (threadMessages[tid] ?? []).filter { msg in
            if !msg.isStreaming { return true }
            if !msg.content.isEmpty { return true }
            if !msg.toolSteps.isEmpty { return true }
            return false
        }
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

    /// Phase 1.4 + Stability: delta 热路径——就地改 content；切回后 UUID 仍在 RAM 时可续写。
    /// 小 delta 合批：≥30ms 才把累积 chunk 写入 RAM；tool/status/done 立即处理；
    /// 流末/cancel/error 强制 flush。
    private var pendingDeltaThreadId: String?
    private var pendingDeltaAssistantId: UUID?
    private var pendingDeltaBuffer: String = ""
    private var pendingDeltaTask: Task<Void, Never>?

    private func applyDeltaInPlace(threadId: String, assistantId: UUID, chunk: String) {
        // 流已结束 / 已取消：拒绝迟到分片（含未取消完的旧 Task）回写，防字乱序与假 streaming
        let live = streamingThreadIds.contains(threadId) || chatTasks[threadId] != nil
        guard live else { return }
        if pendingDeltaThreadId == threadId, pendingDeltaAssistantId == assistantId {
            pendingDeltaBuffer += chunk
        } else {
            flushPendingDelta()
            pendingDeltaThreadId = threadId
            pendingDeltaAssistantId = assistantId
            pendingDeltaBuffer = chunk
        }
        // 对齐基线等「单包大 delta」：立刻落盘，避免 done 抢在 35ms 合批之前触发 empty_reply
        if pendingDeltaBuffer.count >= 400 {
            flushPendingDelta()
            return
        }
        if pendingDeltaTask == nil {
            pendingDeltaTask = Task { @MainActor [weak self] in
                try? await Task.sleep(nanoseconds: 35_000_000)
                self?.flushPendingDelta()
            }
        }
    }

    private func flushPendingDelta() {
        pendingDeltaTask?.cancel()
        pendingDeltaTask = nil
        defer {
            pendingDeltaBuffer = ""
            pendingDeltaThreadId = nil
            pendingDeltaAssistantId = nil
        }
        guard let tid = pendingDeltaThreadId,
              let aid = pendingDeltaAssistantId,
              !pendingDeltaBuffer.isEmpty
        else { return }
        let chunk = pendingDeltaBuffer
        var msgs = threadMessages[tid] ?? []
        if let idx = msgs.firstIndex(where: { $0.id == aid }) {
            msgs[idx].content += chunk
            if msgs[idx].transientNote != nil {
                msgs[idx].transientNote = nil
            }
            msgs[idx].isStreaming = true
        } else {
            msgs.append(
                ChatMessage(
                    id: aid,
                    role: "assistant",
                    content: chunk,
                    isStreaming: true
                )
            )
        }
        threadMessages[tid] = msgs
        bumpThreadRevision(tid)
        if selectedThreadId == tid {
            if chat.messages.contains(where: { $0.id == aid }) {
                chat.replaceMessage(id: aid) { m in
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
    }

    private func flushAssistantCheckpoint(threadId: String, assistantId: UUID) {
        flushPendingDelta()
        flushDiskSave(threadId: threadId)
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
            try await prepareClient(ensureAgent: false)
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
                try await prepareClient(ensureAgent: false)
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

    /// 不再由 Desktop POST Hub；只 nudge sidecar + 用收据/磁盘校正徽章。
    /// - Returns: 本轮从收据新对齐的 delivered 笔数（供 toast）
    @discardableResult
    private func flushTransferOutbox() async -> Int {
        let before = Set(LocalSessionStore.loadTransferReceipts().map(\.client_request_id))
        _ = await nudgeSidecarOutboxFlush()
        applyReceiptsFromDisk()
        reconcileTransferDeliveryWithOutbox()
        let after = LocalSessionStore.loadTransferReceipts()
        return after.filter { !before.contains($0.client_request_id) }.count
    }

    /// 把 sidecar 写下的 receipts 合入右栏 / 徽章（App 再开也诚实）
    func applyReceiptsFromDisk() {
        let receipts = LocalSessionStore.loadTransferReceipts()
        guard !receipts.isEmpty else { return }
        for r in receipts {
            let crid = r.client_request_id.trimmingCharacters(in: .whitespacesAndNewlines)
            let eid = r.epic_id.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !crid.isEmpty, !eid.isEmpty else { continue }
            let tid = r.thread_id.trimmingCharacters(in: .whitespacesAndNewlines)
            let threadId: String = {
                if !tid.isEmpty { return tid }
                if let fromOutbox = LocalSessionStore.loadTransferOutbox()
                    .first(where: { $0.client_request_id == crid })?.thread_id,
                   !fromOutbox.isEmpty {
                    return fromOutbox
                }
                if let fromFailed = LocalSessionStore.loadFailedTransfers()
                    .first(where: { $0.client_request_id == crid })?.thread_id,
                   !fromFailed.isEmpty {
                    return fromFailed
                }
                return selectedThreadId ?? ""
            }()
            LocalSessionStore.dequeueTransfer(clientRequestId: crid)
            LocalSessionStore.dequeueFailedTransfer(clientRequestId: crid)
            guard !threadId.isEmpty else { continue }
            if var snap = threadFlow[threadId] {
                let cur = snap.epicId ?? ""
                if cur.isEmpty || cur.hasPrefix("pending:") {
                    snap.epicId = eid
                    snap.headline = "已投递 · \(eid)"
                    threadFlow[threadId] = snap
                    bumpFlowRevision(threadId)
                    persistCurrentThreadSnapshot(threadId: threadId)
                }
            }
            let accepted = flowConfirmsOrchestrationAccepted(threadId: threadId, epicId: eid)
            setTransferDelivery(threadId, accepted ? .accepted : .delivered)
        }
    }

    /// R8：按 outbox/failed 剩余校正徽章（sidecar 关 App 投完后 UI 对齐）
    func reconcileTransferDeliveryWithOutbox() {
        let pendingTids = Set(LocalSessionStore.loadTransferOutbox().map(\.thread_id))
        let failedTids = Set(LocalSessionStore.loadFailedTransfers().map(\.thread_id))
        var copy = transferDeliveryByThread
        for (tid, phase) in copy {
            if pendingTids.contains(tid) {
                if phase != .delivering {
                    copy[tid] = .queued
                }
            } else if failedTids.contains(tid) {
                copy[tid] = .failed
            } else if phase == .queued || phase == .delivering {
                if let snap = threadFlow[tid],
                   let eid = snap.epicId?.trimmingCharacters(in: .whitespacesAndNewlines),
                   !eid.isEmpty {
                    copy[tid] = flowConfirmsOrchestrationAccepted(threadId: tid, epicId: eid)
                        ? .accepted : .delivered
                } else {
                    copy[tid] = .delivered
                }
            }
        }
        // 补上 hydrate 时未覆盖的 pending/failed
        for item in LocalSessionStore.loadTransferOutbox() where copy[item.thread_id] == nil {
            copy[item.thread_id] = .queued
        }
        for item in LocalSessionStore.loadFailedTransfers() where copy[item.thread_id] == nil {
            copy[item.thread_id] = .failed
        }
        transferDeliveryByThread = copy
    }

    /// R9：投递失败条「后台再试」（用户不点 Hub，只触发本机重排队）
    func retryFailedTransfersInBackground() {
        let n = LocalSessionStore.requeueAllFailedTransfers()
        guard n > 0 else {
            showToast("没有待重试的投递")
            return
        }
        for item in LocalSessionStore.loadTransferOutbox() {
            setTransferDelivery(item.thread_id, .queued)
        }
        showToast("已重新排队 \(n) 笔 · 后台投递")
        Task { @MainActor in
            await flushTransferOutbox()
            reconcileTransferDeliveryWithOutbox()
        }
    }

    /// L2：回前台 — 轻量接续；防抖 + 空队列跳过 flush，不与冷启动叠打
    func onForegroundResume() {
        if hubSyncing { return }
        if let last = lastForegroundResumeAt, Date().timeIntervalSince(last) < 2.0 {
            return
        }
        foregroundResumeTask?.cancel()
        foregroundResumeTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: 250_000_000)
            guard !Task.isCancelled else { return }
            self.lastForegroundResumeAt = Date()
            self.applyReceiptsFromDisk()
            self.reconcileTransferDeliveryWithOutbox()
            let hasOutbox = !LocalSessionStore.loadTransferOutbox().isEmpty
            if hasOutbox {
                await self.flushTransferOutbox()
            }
            if self.hubReachable {
                let hasPending = !LocalSessionStore.loadPendingSync().isEmpty
                if hasPending {
                    await self.flushPendingHubSync()
                }
                async let bind: Void = self.bindFlowToCurrentThread()
                async let lights: Void = self.refreshProjectTaskState()
                await bind
                await lights
                if self.destination == .board {
                    await self.refreshBoard()
                }
            } else {
                self.startHubRecoverLoopIfNeeded()
            }
        }
    }

    /// 只读同步文案（流程轨/状态栏；跟当前项目 snap）
    var orchestrationSyncLabel: String {
        if hubSyncing { return "本机缓存 · 同步中" }
        if !hubReachable { return hubRetryStatusPhrase }
        let eid = (selectedProjectId.flatMap { projectFlow[$0]?.epicId }) ?? currentEpicId
        if let eid, !eid.isEmpty { return "已接上 · 编排中" }
        return "已接上"
    }

    func orchestrationSyncLabel(forProject projectId: String?) -> String {
        if hubSyncing { return "本机缓存 · 同步中" }
        if !hubReachable { return hubRetryStatusPhrase }
        if let pid = projectId, let eid = projectFlow[pid]?.epicId, !eid.isEmpty {
            return "已接上 · 编排中"
        }
        return "已接上"
    }

    func transferDelivery(for threadId: String?) -> TransferDeliveryPhase? {
        guard let threadId else { return nil }
        return transferDeliveryByThread[threadId]
    }

    private func setTransferDelivery(_ threadId: String, _ phase: TransferDeliveryPhase) {
        guard !threadId.isEmpty else { return }
        var copy = transferDeliveryByThread
        copy[threadId] = phase
        transferDeliveryByThread = copy
    }

    /// flow/snapshot 或 recentEpics 是否已确认编排看见该 epic（≠ 仅本机 prefer 绑定）
    private func flowConfirmsOrchestrationAccepted(threadId: String, epicId: String) -> Bool {
        guard let snap = threadFlow[threadId] else { return false }
        if snap.recentEpics.contains(where: { $0.epic_id == epicId }) { return true }
        if let epic = snap.epic {
            let id = (epic.id ?? snap.epicId ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            if id == epicId { return true }
        }
        if !snap.works.isEmpty, snap.epicId == epicId { return true }
        return false
    }

    /// delivered → accepted（仅本 thread；他 thread 不覆盖）
    private func promoteTransferAcceptedIfNeeded(threadId: String, epicId: String) {
        guard transferDeliveryByThread[threadId] == .delivered else { return }
        guard !epicId.isEmpty else { return }
        setTransferDelivery(threadId, .accepted)
    }

    /// - Returns: true 仅当 epic_id 非空并已进入 delivered（或进一步 accepted）
    @discardableResult
    private func applyTransferSuccess(
        resp: TransferResponse,
        tid: String,
        pid: String,
        requestId: String? = nil
    ) async -> Bool {
        let eid = (resp.epic_id ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !eid.isEmpty else {
            // 禁止空 epic_id 驱动 ui / fanout（Phase6：空前缀会误匹配全板）
            setTransferDelivery(tid, .failed)
            showToast("转任务失败：Hub 未返回 epic_id")
            return false
        }
        if selectedProjectId == pid {
            selectedThreadId = tid
            currentEpicId = eid
        }
        let pendingId = requestId.map { "pending:\($0)" }
        var snap = threadFlow[tid] ?? FlowThreadSnapshot(
            epicId: eid, epic: nil, works: [], headline: "",
            recentEpics: threadFlow[tid]?.recentEpics ?? recentEpics,
            emptyMessage: "", fanoutHint: nil
        )
        var recent = snap.recentEpics
        if let pendingId, let idx = recent.firstIndex(where: { $0.epic_id == pendingId }) {
            let prev = recent[idx]
            recent[idx] = FlowEpicRef(
                epic_id: eid,
                title: prev.title,
                updated_at: ISO8601DateFormatter().string(from: Date()),
                thread_id: tid,
                user_stage: prev.user_stage ?? "pending"
            )
        } else if !recent.contains(where: { $0.epic_id == eid }) {
            recent.insert(
                FlowEpicRef(
                    epic_id: eid,
                    title: snap.epic?.title,
                    updated_at: ISO8601DateFormatter().string(from: Date()),
                    thread_id: tid,
                    user_stage: "pending"
                ),
                at: 0
            )
        }
        recent.removeAll {
            $0.epic_id.hasPrefix("pending:") && $0.epic_id != pendingId
        }
        let keptTitle = snap.epic?.title
            ?? recent.first(where: { $0.epic_id == eid })?.title
        snap.epicId = eid
        snap.epic = FlowEpic(
            id: eid,
            title: keptTitle,
            split_status: "pending",
            column: "backlog",
            goal_summary: snap.epic?.goal_summary,
            pipeline: snap.epic?.pipeline,
            user_stage: "pending",
            headline: "扇出中…",
            description: snap.epic?.description
        )
        snap.recentEpics = recent
        snap.emptyMessage = "扇出中…"
        snap.headline = "扇出中…"
        threadFlow[tid] = snap
        bumpFlowRevision(tid)
        persistCurrentThreadSnapshot(threadId: tid)
        dismissTransferSheet(threadId: tid)
        // 确认卡已在 submit 时收掉；再清一次防表单残留
        resetTransferForm(threadId: tid)
        // HTTP 成功 + epic_id → delivered；禁止直接跳 accepted
        setTransferDelivery(tid, .delivered)
        statusText = "已转任务"
        var toastMsg = "已投递 \(eid)"
        if resp.idempotent_replay == true {
            toastMsg = "已投递（幂等）\(eid)"
        }
        // 既有受理信号：engine_wake.ok；区分 Engine 真在跑 vs 仅写了队列 / 仓不可消费
        if let wake = resp.engine_wake {
            if wake.ok == true {
                if wake.workspace_eligible == false {
                    toastMsg += " · 仓不可被 Engine 消费（orch/engine=false）"
                } else if wake.engine_running == false {
                    let note = wake.launch_note ?? wake.message ?? wake.block_reason ?? "kickstart"
                    toastMsg += " · 已写队列，Engine 未起（\(note)）"
                } else if let br = wake.block_reason, !br.isEmpty {
                    toastMsg += " · 阻塞：\(br)"
                } else {
                    toastMsg += " · Engine 已唤醒"
                    setTransferDelivery(tid, .accepted)
                }
            } else {
                let why = wake.message ?? wake.block_reason ?? "wake 失败"
                toastMsg += " · Engine 未唤醒：\(why)"
            }
        }
        showToast(toastMsg)
        lastAnimatedEpicId = nil
        flowSplitGeneration &+= 1
        await bindFlowToThread(projectId: pid, threadId: tid, preferEpicId: eid)
        // 仅当 flow/snapshot 真确认编排看见，才从 delivered 升 accepted
        if transferDeliveryByThread[tid] == .delivered,
           flowConfirmsOrchestrationAccepted(threadId: tid, epicId: eid) {
            setTransferDelivery(tid, .accepted)
        }
        startFanoutWatchdog(epicId: eid, projectId: pid, threadId: tid)
        return true
    }

    /// 窗体 pane thread 优先；禁止只写 `::main` 导致「投了 A、画了 B」
    func resolveFlowThreadId(projectId: String, preferred: String? = nil) -> String {
        if let preferred {
            let t = preferred.trimmingCharacters(in: .whitespacesAndNewlines)
            if !t.isEmpty, Self.projectId(fromThreadId: t) == projectId {
                return t
            }
        }
        return threadIdForProject(projectId)
    }

    /// 一点击：右栏立刻出现大卡骨架（pending:client_request_id）
    private func insertOptimisticTransferRail(
        tid: String,
        pid: String,
        requestId: String,
        title: String,
        goal: String,
        pipeline: String,
        persistDisk: Bool = true
    ) {
        let pendingId = "pending:\(requestId)"
        let epic = FlowEpic(
            id: pendingId,
            title: title,
            split_status: "pending",
            column: "backlog",
            goal_summary: String(goal.prefix(200)),
            pipeline: pipeline,
            user_stage: "pending",
            headline: "已交接 · 编排同步中…",
            description: goal
        )
        let ref = FlowEpicRef(
            epic_id: pendingId,
            title: title,
            updated_at: ISO8601DateFormatter().string(from: Date()),
            thread_id: tid,
            user_stage: "pending"
        )
        var snap = threadFlow[tid] ?? FlowThreadSnapshot(
            epicId: pendingId, epic: epic, works: [], headline: "已交接 · 编排同步中…",
            recentEpics: [], emptyMessage: "已交接 · 编排同步中…", fanoutHint: nil
        )
        var recent = snap.recentEpics
        recent.removeAll { $0.epic_id.hasPrefix("pending:") }
        recent.insert(ref, at: 0)
        snap.epicId = pendingId
        snap.epic = epic
        snap.works = []
        snap.headline = "已交接 · 编排同步中…"
        snap.emptyMessage = "已交接 · 编排同步中…"
        snap.fanoutHint = nil
        snap.stopLossHint = nil
        snap.recentEpics = recent
        threadFlow[tid] = snap
        bumpFlowRevision(tid)
        if persistDisk {
            persistCurrentThreadSnapshot(threadId: tid)
        }
        if selectedThreadId == tid || selectedProjectId == pid {
            applyFlowSnapshot(snap)
            currentEpicId = pendingId
        }
        flowSplitGeneration &+= 1
        reconcileFlowSSE()
    }

    static func promptMode(forUserText text: String) -> String {
        StreamSessionController.resolvePromptMode(forUserText: text)
    }

    /// discuss = 只读探查（默认）；engineer = 允许本机写文件（偏好或口令；仅 ccc）
    static func toolMode(forUserText text: String) -> String {
        // 兼容旧调用：无偏好时只看口令
        StreamSessionController.resolveToolMode(preferred: "discuss", userText: text, projectId: nil)
    }

    func resolvedToolMode(forUserText text: String, projectId: String? = nil) -> String {
        let pid = projectId ?? selectedProjectId
        return StreamSessionController.resolveToolMode(
            preferred: preferredToolMode,
            userText: text,
            projectId: pid
        )
    }

    func resolvedModel() -> String {
        StreamSessionController.resolveModel(preferredModel)
    }

    /// 同会话 stop-and-send；仅本机 sidecar，可多路并行（可指定 projectId / threadId 供多窗多会话）
    /// - Parameter displayText: 气泡展示短文案（快捷条）；Agent 仍收 `text` 全文
    func sendUserMessage(
        _ text: String,
        projectId: String? = nil,
        threadId: String? = nil,
        stopAndSend: Bool = true,
        attachments: [ComposerAttachment]? = nil,
        displayText: String? = nil
    ) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let atts = attachments ?? composerAttachments
        let composed = StreamSessionController.composeUserText(text: trimmed, attachments: atts)
        guard !composed.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        if attachments == nil { composerAttachments = [] }
        let pid = projectId ?? selectedProjectId
        let shown = displayText?.trimmingCharacters(in: .whitespacesAndNewlines)
        Task {
            await self.sendUserMessageAndWait(
                composed,
                projectId: pid,
                threadId: threadId,
                stopAndSend: stopAndSend,
                displayText: (shown?.isEmpty == false) ? shown : nil
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
            // 快捷条忙碌态随本线程流结束清除
            if activeQuickAction != nil {
                activeQuickAction = nil
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

    /// 启动项目卡片后台任务态轮询（Chat 页低频灯；首轮由 bootstrap 立即拉）
    func startProjectTaskPolling() {
        guard projectPollTask == nil else { return }
        projectPollTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { break }
                await self.refreshProjectTaskState()
                // R7：Chat 页只刷 summaries 灯，约 20s；Board 页另有 15s 整板轮询
                try? await Task.sleep(nanoseconds: 20_000_000_000)
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
            try await prepareClient(ensureAgent: false)
            let resp = try await client.fetchBoardSummaries(workspaces: workspaces)
            var newState: [String: String] = [:]
            var newCounts: [String: [String: Int]] = [:]
            var newStats: [String: ProjectStats] = [:]
            for proj in projects {
                let ws = proj.workspace ?? proj.id
                if let snap = resp.summaries[ws] {
                    let counts = snap.counts ?? [:]
                    newState[proj.id] = Self.deriveTaskState(from: counts)
                    newCounts[proj.id] = counts
                    var s = ProjectStats()
                    s.totalEpics = counts["backlog"] ?? 0
                    s.activeWorks = (counts["in_progress"] ?? 0) + (counts["planned"] ?? 0) + (counts["testing"] ?? 0)
                    s.failedWorks = counts["abnormal"] ?? 0
                    s.completedToday = counts["released"] ?? 0
                    newStats[proj.id] = s
                }
            }
            // Δ：上一拍 → 当前
            projectBoardCountsPrev = projectBoardCounts
            projectBoardCounts = newCounts
            projectTaskState = newState
            projectStats = newStats
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
        stopAndSend: Bool = true,
        displayText: String? = nil
    ) async -> Bool {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return false }
        guard let pid = projectId ?? selectedProjectId else {
            showToast("请先选择项目")
            setComposerBounce(trimmed, threadId: nil)
            activeQuickAction = nil
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
            activeQuickAction = nil
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
                activeQuickAction = nil
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
            activeQuickAction = nil
            return false
        }

        let shown = displayText?.trimmingCharacters(in: .whitespacesAndNewlines)
        let task = Task { [weak self] in
            guard let self else { return }
            await self.runChatStream(
                projectId: pid,
                threadId: threadId,
                text: trimmed,
                displayText: (shown?.isEmpty == false) ? shown : nil
            )
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

    private func runChatStream(
        projectId: String,
        threadId: String,
        text: String,
        displayText: String? = nil
    ) async {
        let turnId = UUID().uuidString
        activeTurnIds[threadId] = turnId
        setThreadStreaming(threadId, true)
        activeChatThreadId = threadId
        defer {
            setThreadStreaming(threadId, false)
            if activeChatThreadId == threadId {
                activeChatThreadId = streamingThreadIds.first
            }
            chatTasks[threadId] = nil
            if activeTurnIds[threadId] == turnId {
                activeTurnIds.removeValue(forKey: threadId)
            }
            // 聊完追赶该项目右栏（后台窗也要 live 刷新 threadFlow）
            let flowGen = threadSwitchGeneration
            Task { [flowGen, projectId] in
                guard self.threadSwitchGeneration == flowGen else { return }
                await self.refreshFlow(projectId: projectId)
            }
        }

        // content=发给 Agent 的全文；displayContent=气泡短标签（快捷条）
        let userMsg = ChatMessage(
            role: "user",
            content: text,
            displayContent: displayText
        )
        let assistantId = UUID()
        partialByTurn[turnId] = ""
        onChatEventInPlace = { [weak self] tid, aid, event in
            guard let self else { return }
            guard self.activeTurnIds[tid] == turnId else { return }
            if case .delta(let chunk, _) = event, !chunk.isEmpty {
                // 合批未 flush 时 cell.content 可能仍空；用累计 chunk 保 partial
                let prior = self.partialByTurn[turnId] ?? ""
                if let cell = self.threadMessages[tid]?.first(where: { $0.id == aid }),
                   !cell.content.isEmpty {
                    self.partialByTurn[turnId] = cell.content
                } else {
                    self.partialByTurn[turnId] = prior + chunk
                }
            }
        }
        defer { onChatEventInPlace = nil }
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
            // 映射指向已删路径时提示一次（无映射=正常：业务仓不留本机第二树）
            if let mapped = workspaceMap[projectId]?.trimmingCharacters(in: .whitespacesAndNewlines),
               !mapped.isEmpty,
               !FileManager.default.fileExists(atPath: mapped) {
                showToast("本机映射路径已失效，已忽略；事实以 Hub/2017 基线为准")
            }
            let mode = Self.promptMode(forUserText: text)
            let tools = resolvedToolMode(forUserText: text, projectId: projectId)
            let modelName = resolvedModel()
            // 发送前：不抢锁的轻量 health 检查，确保 sidecar 真活着
            setThreadStreamStatus(threadId, "本机生成中…")
            if let chatBase = await ensureLocalAgent() {
                if await !client.probeLocalAgent(base: chatBase) {
                    invalidateAgentProbeCache()
                    throw APIError.stream(code: "connect_failed", message: "本机 Agent 未就绪，请执行 bash scripts/install-agent-sidecar-plist.sh --start")
                }
            }
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
                        // 重连前保留用户原文 + 上一轮 partial，避免「闪空」丢字
                        let partialSnapshot = partialByTurn[turnId] ?? ""
                        mutateThreadMessages(threadId: threadId) { msgs in
                            guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                            if !partialSnapshot.isEmpty {
                                msgs[idx].transientNote = "上次中断于此：\(partialSnapshot.suffix(120))"
                            }
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
                    let streamResult = try await client.streamChat(
                        projectId: projectId,
                        sessionId: threadId,
                        turnId: turnId,
                        messages: attempt == 1 ? outbound : outboundAttempt,
                        promptMode: mode,
                        toolMode: tools,
                        projectPath: streamProjectPath,
                        claudeSessionId: threadClaudeSessionIds[threadId],
                        model: modelName
                    ) { [weak self] event in
                        guard let model = self else { return }
                        await MainActor.run {
                            model.applyChatEvent(
                                threadId: threadId,
                                assistantId: assistantId,
                                expectedTurnId: turnId,
                                event: event
                            )
                        }
                    }
                    streamError = nil
                    DesktopChatTurnLedger.append([
                        "event": "ok",
                        "turn_id": turnId,
                        "threadId": threadId,
                        "projectId": projectId,
                        "attempt": attempt,
                        "sidecar_duration_ms": streamResult.durationMs ?? 0,
                        "delta_events": streamResult.eventCounts["delta"] ?? 0,
                        "tool_events": (streamResult.eventCounts["tool_use"] ?? 0)
                            + (streamResult.eventCounts["tool_result"] ?? 0),
                        "duration_ms": Int(Date().timeIntervalSince(turnStarted) * 1000),
                    ])
                    if lastTurnFailure?.threadId == threadId {
                        lastTurnFailure = nil
                    }
                    // 重试首次成功后清掉「上次中断于此」提示，避免下一轮残留
                    mutateThreadMessages(threadId: threadId) { msgs in
                        guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                        msgs[idx].transientNote = nil
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
                        "turn_id": turnId,
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

            // 必须先把合批中的 delta 写入消息，再做空回复判定。
            // 否则：SSE 已 ok（delta_events≥1）→ 判空删气泡 → catch 再 flush → 正文+「回复中断」并存。
            flushPendingDelta()

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
            flushAssistantCheckpoint(threadId: threadId, assistantId: assistantId)
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
            flushAssistantCheckpoint(threadId: threadId, assistantId: assistantId)
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
            flushAssistantCheckpoint(threadId: threadId, assistantId: assistantId)
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
                    "turn_id": turnId,
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

    private func applyChatEvent(
        threadId: String,
        assistantId: UUID,
        expectedTurnId: String,
        event: ChatStreamEvent
    ) {
        guard activeTurnIds[threadId] == expectedTurnId else { return }
        onChatEventInPlace?(threadId, assistantId, event)
        let eventTurnId: String? = {
            switch event {
            case .ping(let id), .delta(_, let id), .status(_, let id): return id
            case .toolUse(_, _, let id), .toolResult(_, let id): return id
            case .cost(_, _, let id): return id
            case .done(_, _, let id, _): return id
            }
        }()
        if let eventTurnId, !eventTurnId.isEmpty, eventTurnId != expectedTurnId {
            return
        }
        // done：先冲 pending delta，再 mutate 里关 isStreaming；顺序反了会丢末包或落盘滤掉工具轨
        if case .done = event {
            flushPendingDelta()
        }
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
        case .delta(let chunk, _):
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
        case .status(let note, _):
            mutateThreadMessages(threadId: threadId) { msgs in
                guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                msgs[idx].transientNote = note
            }
            // mutateThreadMessages → messages= 已触发 @Published；勿再 objectWillChange
            return
        case .toolUse, .toolResult, .cost, .done:
            break
        }
        if case .toolUse(let name, _, _) = event {
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
            case .toolUse(let name, let input, _):
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
            case .toolResult(let ok, _):
                // 只更新该 step 状态 + resultHint；勿在工具间空隙置 toolsFinished（否则绿勾闪）
                if let ri = msgs[idx].toolSteps.lastIndex(where: { $0.status == .running }) {
                    msgs[idx].toolSteps[ri].status = ok ? .done : .error
                    let step = msgs[idx].toolSteps[ri]
                    msgs[idx].toolSteps[ri].resultHint = ToolProgressHelper.resultHint(
                        name: step.name, ok: ok, label: step.label
                    )
                } else if let last = msgs[idx].toolSteps.indices.last {
                    msgs[idx].toolSteps[last].status = ok ? .done : .error
                    let step = msgs[idx].toolSteps[last]
                    msgs[idx].toolSteps[last].resultHint = ToolProgressHelper.resultHint(
                        name: step.name, ok: ok, label: step.label
                    )
                }
            case .cost(let tokens, _, _):
                if let t = tokens, t > 0 {
                    threadSessionTokens[threadId, default: 0] += t
                    if selectedThreadId == threadId {
                        sessionTokens = threadSessionTokens[threadId] ?? 0
                    }
                }
            case .done(_, let claudeSessionId, _, _):
                for i in msgs[idx].toolSteps.indices where msgs[idx].toolSteps[i].status == .running {
                    msgs[idx].toolSteps[i].status = .done
                }
                if !msgs[idx].toolSteps.isEmpty {
                    msgs[idx].toolsFinished = true
                }
                // 必须在 flushDiskSave 前关掉 isStreaming，否则 writeDiskSave 会把「空正文+工具轨」整条滤掉
                msgs[idx].isStreaming = false
                msgs[idx].transientNote = nil
                if let sid = claudeSessionId?.trimmingCharacters(in: .whitespacesAndNewlines), !sid.isEmpty {
                    threadClaudeSessionIds[threadId] = sid
                }
            }
        }
        if case .done = event {
            // delta 已在 mutate 前 flush；此处只清 fence + 落盘（消息已 isStreaming=false）
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
        activeTurnIds[tid] = nil
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
        // 点按瞬间：芯片高亮 + toast，勿等网络
        activeQuickAction = uiLabel
        showToast("已开始：\(uiLabel)")
        NSHapticFeedbackManager.defaultPerformer.perform(.generic, performanceTime: .now)
        sendUserMessage(
            prompt,
            projectId: projectId,
            threadId: threadId,
            stopAndSend: true,
            displayText: "【快捷】\(uiLabel)"
        )
    }

    func alignBaseline(projectId: String? = nil, threadId: String? = nil) async {
        guard let pid = projectId ?? selectedProjectId else {
            showToast("请先选择项目")
            return
        }
        guard canChat else {
            showToast("本机 Agent 未就绪，无法对齐基线")
            return
        }
        destination = .chat
        // 点按瞬间反馈（Hub 拉取前）；hold 加长，避免默认 5s 消失后像「没反应」
        activeQuickAction = "对齐基线"
        showToast("对齐基线：正在从 Hub 拉取快照…", holdSeconds: 20)
        NSHapticFeedbackManager.defaultPerformer.perform(.generic, performanceTime: .now)
        let tid = threadId ?? selectedThreadId
        if let tid {
            setThreadStreamStatus(tid, "对齐基线：拉取快照…")
        }
        do {
            try await prepareClient(projectId: pid)
            if !hubReachable {
                // 仍尝试一次拉取；先给可见提示，避免静默长等
                showToast("Hub 标记不可达，仍尝试拉取…", holdSeconds: 15)
            }
            let resp = try await client.fetchProjectBaseline(projectId: pid)
            setHubReachable(true, source: "align_baseline")
            let prompt = (resp.prompt ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            guard !prompt.isEmpty else {
                showToast("基线为空（Hub 返回无 prompt）")
                activeQuickAction = nil
                if let tid { setThreadStreamStatus(tid, "") }
                return
            }
            showToast("对齐基线：已注入，生成中…", holdSeconds: 8)
            sendUserMessage(
                prompt,
                projectId: pid,
                threadId: tid,
                stopAndSend: true,
                displayText: "【快捷】对齐基线"
            )
        } catch {
            setHubReachable(false, source: "align_baseline_fail")
            showToast(friendlyHubError(error, action: "对齐基线"), holdSeconds: 10)
            activeQuickAction = nil
            if let tid { setThreadStreamStatus(tid, "") }
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
        guard let tid else {
            if let d = TransferDraftParser.parse(from: content), d.isGateReady || !d.title.isEmpty {
                pendingTransferDraft = d
            }
            return
        }
        // 已交接/投递中：禁止从助手消息把确认卡复活
        if shouldSuppressTransferDraft(for: tid) { return }
        if let d = TransferDraftParser.parse(from: content), d.isGateReady || !d.title.isEmpty {
            setThreadTransferDraft(tid, d)
            applyTransferDraft(d, fallbackContent: nil, threadId: tid)
            if d.isGateReady { setTransferDelivery(tid, .draft) }
        }
    }

    /// 该 thread 已有进行中编排或投递态时，禁止再弹出确认卡
    private func shouldSuppressTransferDraft(for threadId: String) -> Bool {
        if let phase = transferDeliveryByThread[threadId] {
            switch phase {
            case .queued, .delivering, .delivered, .accepted:
                return true
            case .draft, .failed:
                break
            }
        }
        guard let eid = threadFlow[threadId]?.epicId?
            .trimmingCharacters(in: .whitespacesAndNewlines),
              !eid.isEmpty
        else { return false }
        if eid.hasPrefix("pending:") { return true }
        let stage = (threadFlow[threadId]?.epic?.user_stage ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
        return stage != "done"
    }

    static func isPendingEpicId(_ epicId: String?) -> Bool {
        let eid = (epicId ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return eid.hasPrefix("pending:")
    }

    /// 乐观 pending 大卡是否仍应保留：仅投递未完成时。
    private func shouldKeepPendingOptimistic(threadId: String) -> Bool {
        if LocalSessionStore.loadTransferOutbox().contains(where: { $0.thread_id == threadId }) {
            return true
        }
        guard let phase = transferDeliveryByThread[threadId] else { return false }
        switch phase {
        case .queued, .delivering:
            return true
        case .delivered, .accepted, .failed, .draft:
            return false
        }
    }

    /// Hub 列表空且无在途投递时，清掉 pending 幽灵卡。
    private func clearStalePendingIfNeeded(threadId: String, remoteEpicsEmpty: Bool) {
        guard remoteEpicsEmpty else { return }
        guard var snap = threadFlow[threadId], Self.isPendingEpicId(snap.epicId) else { return }
        guard !shouldKeepPendingOptimistic(threadId: threadId) else { return }
        snap.works = []
        snap.epic = nil
        snap.epicId = nil
        snap.headline = ""
        snap.fanoutHint = nil
        snap.stopLossHint = nil
        snap.recentEpics = []
        snap.emptyMessage = "编排空闲 · 下一笔定稿后出现在这里"
        threadFlow[threadId] = snap
        bumpFlowRevision(threadId)
        if selectedThreadId == threadId {
            applyFlowSnapshot(snap)
            currentEpicId = nil
            recentEpics = []
            lastAnimatedEpicId = nil
        }
        flushDiskSave(threadId: threadId)
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

    func mutateTransferFormPublic(_ threadId: String, _ update: (inout TransferFormState) -> Void) {
        mutateTransferForm(threadId, update)
    }

    /// TransferSheet 本地草稿写回（确认/退回/预填后）
    func commitTransferForm(_ threadId: String, _ form: TransferFormState) {
        setTransferForm(threadId, form)
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
            if !d.complexity.isEmpty { form.complexity = d.complexity }
            form.bumpVersion = d.bumpVersion
            form.source = d.source
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
                    // 启发式预填截断，避免 TransferSheet 挂巨文卡顿
                    form.planMd = String(lastAssistant.prefix(8_000))
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

        // 一点击：立刻收确认卡 + 右栏乐观大卡，再后台 outbox
        let requestId = UUID().uuidString
        insertOptimisticTransferRail(
            tid: tid,
            pid: pid,
            requestId: requestId,
            title: title,
            goal: goal,
            pipeline: pipeline,
            persistDisk: false
        )
        resetTransferForm(threadId: tid)
        dismissTransferSheet(threadId: tid)
        mutateTransferForm(tid) { $0.error = nil }

        let cx = form.complexity.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let complexity = ["small", "medium", "large"].contains(cx) ? cx : "medium"
        let note = form.humanNote.trimmingCharacters(in: .whitespacesAndNewlines)
        let outboxItem = LocalSessionStore.TransferOutboxItem(
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
            complexity: complexity,
            bump_version: form.bumpVersion,
            human_note: note,
            attempts: 0,
            saved_at: ISO8601DateFormatter().string(from: Date())
        )
        setTransferDelivery(tid, .queued)

        // 前台只确认「已排队」；磁盘 + enqueue 放到下一拍，减确认 hitch
        if hubReachable {
            showToast("已排队 · 后台投递中")
        } else {
            showToast("已排队 · Hub 恢复后自动投递")
            startHubRecoverLoopIfNeeded()
        }
        Task { @MainActor in
            await Task.yield()
            LocalSessionStore.enqueueTransfer(outboxItem)
            self.persistCurrentThreadSnapshot(threadId: tid)
            await self.nudgeSidecarOutboxFlush()
        }
    }

    /// 带人工备注继续投递（不改 acceptance 正文）
    func submitTransferWithNote(threadId: String? = nil, note: String) async {
        let tid = threadId ?? transferSheetThreadId ?? selectedThreadId
        guard let tid else { return }
        mutateTransferForm(tid) { $0.humanNote = note }
        await submitTransfer(threadId: tid)
    }

    /// 退回对话：不写 backlog，注入提示后关卡
    func rejectTransferBackToChat(threadId: String? = nil, note: String = "") {
        let tid = threadId ?? transferSheetThreadId ?? selectedThreadId
        guard let tid else { return }
        let remark = note.trimmingCharacters(in: .whitespacesAndNewlines)
        let body: String
        if remark.isEmpty {
            body = "【任务卡已退回】未投递。请改方案后重新定稿，再点转任务。"
        } else {
            body = "【任务卡已退回】未投递。备注：\(remark)\n请按备注改方案后重新定稿，再点转任务。"
        }
        var msgs = threadMessages[tid] ?? []
        msgs.append(ChatMessage(role: "system", content: body))
        threadMessages[tid] = msgs
        bumpThreadRevision(tid)
        persistCurrentThreadSnapshot(threadId: tid)
        dismissTransferSheet(threadId: tid)
        showToast("已退回对话 · 未投递")
    }

    /// 轻推本机 sidecar 立刻冲刷 outbox（失败忽略；周期 loop 仍会投）
    @discardableResult
    func nudgeSidecarOutboxFlush() async -> Bool {
        do {
            try await prepareClient(ensureAgent: false)
            let summary = try await client.nudgeOutboxFlush()
            let delivered = (summary["delivered"] as? Int)
                ?? (summary["delivered"] as? NSNumber)?.intValue
                ?? 0
            if delivered > 0 {
                await MainActor.run {
                    self.applyReceiptsFromDisk()
                    self.reconcileTransferDeliveryWithOutbox()
                }
            }
            return delivered > 0
        } catch {
            return false
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

    /// 转任务后若 45s 仍无 works，右栏明示阻塞因（按 pane thread 写 threadFlow）
    func startFanoutWatchdog(epicId: String?, projectId: String? = nil, threadId: String? = nil) {
        fanoutWatchTask?.cancel()
        let pid = projectId ?? selectedProjectId
        guard let epicId, !epicId.isEmpty, let pid else { return }
        // 乐观 pending: 未上 Hub，勿误报扇出超时
        if Self.isPendingEpicId(epicId) { return }
        let tid = resolveFlowThreadId(projectId: pid, preferred: threadId)
        if selectedProjectId == pid {
            flowFanoutHint = nil
        }
        fanoutWatchTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 45_000_000_000)
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
                    let ss = snap.epic?.split_status ?? ""
                    var hint = "45 秒内未见扇出（\(stage)）。"
                    if ss == "failed" {
                        hint += "大卡已 failed——先板务清残卡或查 product 失败原因，勿静默重投。"
                    } else if ss == "pending" || ss.isEmpty {
                        hint += "仍 pending：查 Engine 是否在跑、仓是否 engine-eligible、上游是否健康。"
                    } else {
                        hint += "可复制给对话，让 Agent 查 Engine/扇出阻塞因。"
                    }
                    snap.fanoutHint = hint
                    self.threadFlow[tid] = snap
                    self.bumpFlowRevision(tid)
                    self.setProjectFlow(pid, snap)
                    if self.selectedProjectId == pid {
                        self.flowFanoutHint = hint
                    }
                    self.showToast(hint, holdSeconds: 12)
                }
            }
        }
    }

    func clearFanoutHint(projectId: String? = nil, threadId: String? = nil) {
        let pid = projectId ?? selectedProjectId
        if let pid {
            let tid = resolveFlowThreadId(projectId: pid, preferred: threadId)
            if var snap = projectFlow[pid] ?? threadFlow[tid] {
                snap.fanoutHint = nil
                writeFlowSnap(projectId: pid, threadId: tid, snap)
            }
        }
        if projectId == nil || projectId == selectedProjectId {
            flowFanoutHint = nil
        }
        fanoutWatchTask?.cancel()
        fanoutWatchTask = nil
    }

    func clearStopLossHint(projectId: String? = nil, threadId: String? = nil) {
        let pid = projectId ?? selectedProjectId
        if let pid {
            let tid = resolveFlowThreadId(projectId: pid, preferred: threadId)
            if var snap = projectFlow[pid] ?? threadFlow[tid] {
                snap.stopLossHint = nil
                writeFlowSnap(projectId: pid, threadId: tid, snap)
            }
        }
        if projectId == nil || projectId == selectedProjectId {
            flowStopLossHint = nil
        }
    }

    /// 写 thread + project 双份；右栏 UI 只读 projectFlow
    private func writeFlowSnap(projectId: String, threadId: String, _ snap: FlowThreadSnapshot) {
        threadFlow[threadId] = snap
        bumpFlowRevision(threadId)
        setProjectFlow(projectId, snap)
    }

    /// 右栏与项目绑定：同项目任意会话共享编排
    func bindFlowToCurrentThread(preferEpicId: String? = nil) async {
        guard let pid = selectedProjectId else { return }
        await bindFlowToProject(projectId: pid, preferEpicId: preferEpicId)
    }

    /// 项目级编排绑定（右栏 SSOT）
    func bindFlowToProject(projectId: String, preferEpicId: String? = nil) async {
        let pid = projectId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !pid.isEmpty else { return }
        let isSelected = selectedProjectId == pid
        if isSelected { selectedNodeDetail = nil }

        let preexisting = projectFlow[pid]?.epicId ?? (isSelected ? currentEpicId : nil)
        let fastEpic = (preferEpicId?.trimmingCharacters(in: .whitespacesAndNewlines)).flatMap {
            $0.isEmpty ? nil : $0
        } ?? preexisting?.trimmingCharacters(in: .whitespacesAndNewlines)

        if let fast = fastEpic, !fast.isEmpty {
            var snap = projectFlow[pid] ?? FlowThreadSnapshot(
                epicId: fast, epic: nil, works: [], headline: "",
                recentEpics: projectFlow[pid]?.recentEpics ?? [],
                emptyMessage: "编排同步中…", fanoutHint: nil
            )
            snap.epicId = fast
            if snap.emptyMessage.contains("编排空闲") {
                snap.emptyMessage = Self.isPendingEpicId(fast)
                    ? "已交接 · 编排同步中…"
                    : "编排同步中…"
            }
            let tid = resolveFlowThreadId(projectId: pid, preferred: nil)
            writeFlowSnap(projectId: pid, threadId: tid, snap)
            if isSelected { applyFlowSnapshot(snap) }
            if !Self.isPendingEpicId(fast) {
                await refreshFlowNow(projectId: pid, threadId: tid)
            }
            reconcileFlowSSE()
            Task { @MainActor in
                await self.refreshEpicListOnly(projectId: pid, threadId: nil)
            }
            return
        }

        do {
            try await prepareClient(ensureAgent: false)
            // threadId=nil → Hub project_single：项目全部活跃大卡
            let epicsResp = try await client.fetchRecentEpicsDetailed(
                projectId: pid,
                threadId: nil
            )
            var snap = projectFlow[pid] ?? FlowThreadSnapshot(
                epicId: nil, epic: nil, works: [], headline: "",
                recentEpics: [], emptyMessage: "编排空闲 · 下一笔定稿后出现在这里", fanoutHint: nil
            )
            snap.recentEpics = mergeRecentEpics(local: snap.recentEpics, remote: epicsResp.epics)
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
            } else if let first = epicsResp.epics.first?.epic_id, !first.isEmpty {
                resolvedEpic = first
            } else if hasLocalFlow {
                resolvedEpic = localBound
            } else {
                resolvedEpic = nil
                snap.epic = nil
                snap.works = []
                snap.epicId = nil
                snap.headline = ""
                snap.emptyMessage = "编排空闲 · 下一笔定稿后出现在这里"
            }

            if let eid = resolvedEpic, !eid.isEmpty {
                snap.epicId = eid
            }
            let tid = resolveFlowThreadId(projectId: pid, preferred: nil)
            writeFlowSnap(projectId: pid, threadId: tid, snap)
            if isSelected {
                recentEpics = snap.recentEpics
                currentEpicId = resolvedEpic
                applyFlowSnapshot(snap)
            }
            if let eid = resolvedEpic, !eid.isEmpty, !Self.isPendingEpicId(eid) {
                await refreshFlowNow(projectId: pid, threadId: tid)
            }
            reconcileFlowSSE()
        } catch {
            if isSelected {
                flowEmptyMessage = "流程加载失败"
            }
            if var snap = projectFlow[pid] {
                snap.emptyMessage = "流程加载失败"
                setProjectFlow(pid, snap)
            }
        }
    }

    /// 兼容旧调用：右栏以 project 为准
    func bindFlowToThread(
        projectId: String,
        threadId: String? = nil,
        preferEpicId: String? = nil
    ) async {
        await bindFlowToProject(projectId: projectId, preferEpicId: preferEpicId)
        if let raw = threadId?.trimmingCharacters(in: .whitespacesAndNewlines), !raw.isEmpty,
           let snap = projectFlow[projectId] {
            threadFlow[raw] = snap
            bumpFlowRevision(raw)
        }
    }

    /// 合并 recentEpics：保留本地 pending:，远程真 epic 优先；去重
    private func mergeRecentEpics(
        local: [FlowEpicRef],
        remote: [FlowEpicRef]
    ) -> [FlowEpicRef] {
        var byId: [String: FlowEpicRef] = [:]
        for r in remote { byId[r.epic_id] = r }
        for l in local {
            if l.epic_id.hasPrefix("pending:") {
                byId[l.epic_id] = l
            } else if byId[l.epic_id] == nil {
                byId[l.epic_id] = l
            } else if let remote = byId[l.epic_id], remote.user_stage == nil, l.user_stage != nil {
                var merged = remote
                merged.user_stage = l.user_stage
                byId[l.epic_id] = merged
            }
        }
        let pending = byId.values.filter { $0.epic_id.hasPrefix("pending:") }
        let rest = byId.values.filter { !$0.epic_id.hasPrefix("pending:") }
            .sorted { ($0.updated_at ?? "") > ($1.updated_at ?? "") }
        return pending + rest
    }

    /// 只刷 recentEpics 列表（快路径后补；失败静默）；threadId=nil → 项目级
    private func refreshEpicListOnly(projectId: String, threadId: String?) async {
        do {
            try await prepareClient(ensureAgent: false)
            let epicsResp = try await client.fetchRecentEpicsDetailed(
                projectId: projectId,
                threadId: threadId
            )
            var snap = projectFlow[projectId]
                ?? threadFlow[threadId ?? ""]
                ?? FlowThreadSnapshot(
                    epicId: nil, epic: nil, works: [], headline: "",
                    recentEpics: [], emptyMessage: "", fanoutHint: nil
                )
            snap.recentEpics = mergeRecentEpics(local: snap.recentEpics, remote: epicsResp.epics)
            setProjectFlow(projectId, snap)
            let tid = threadId ?? resolveFlowThreadId(projectId: projectId, preferred: nil)
            threadFlow[tid] = snap
            bumpFlowRevision(tid)
            if selectedProjectId == projectId {
                recentEpics = snap.recentEpics
                applyFlowSnapshot(snap)
            }
        } catch {
            // 列表可缺；snapshot/SSE 已接上
        }
    }

    func refreshEpicList(projectId: String? = nil, threadId: String? = nil) async {
        if let pid = projectId ?? selectedProjectId {
            await bindFlowToProject(projectId: pid)
        }
    }

    func selectEpic(_ epicId: String, projectId: String? = nil, threadId: String? = nil) async {
        let pid = projectId ?? selectedProjectId
        guard let pid else { return }
        let tid = resolveFlowThreadId(projectId: pid, preferred: threadId)
        var snap = projectFlow[pid] ?? threadFlow[tid] ?? FlowThreadSnapshot(
            epicId: epicId, epic: nil, works: [], headline: "",
            recentEpics: [], emptyMessage: "", fanoutHint: nil
        )
        snap.epicId = epicId
        writeFlowSnap(projectId: pid, threadId: tid, snap)
        if selectedProjectId == pid {
            currentEpicId = epicId
            selectedNodeDetail = nil
        }
        if Self.isPendingEpicId(epicId) {
            reconcileFlowSSE()
            return
        }
        await refreshFlowNow(projectId: pid, threadId: tid)
        reconcileFlowSSE()
    }

    func refreshFlow(projectId: String? = nil, threadId: String? = nil) async {
        let pid = projectId ?? selectedProjectId
        guard let pid else { return }
        let tid = resolveFlowThreadId(projectId: pid, preferred: threadId)
        // 合并短时间内的多次刷新，避免 snapshot 风暴打挂 Hub
        flowRefreshTasks[tid]?.cancel()
        flowRefreshTasks[tid] = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 500_000_000)
            guard !Task.isCancelled, let self else { return }
            await self.refreshFlowNow(projectId: pid, threadId: tid)
        }
    }

    private func refreshFlowNow(projectId: String? = nil, threadId: String? = nil) async {
        let pid = projectId ?? selectedProjectId
        guard let pid else { return }
        guard !flowSnapshotPaused else { return }
        let tid = resolveFlowThreadId(projectId: pid, preferred: threadId)
        let epicId = projectFlow[pid]?.epicId
            ?? threadFlow[tid]?.epicId
            ?? (selectedProjectId == pid ? currentEpicId : nil)
        if Self.isPendingEpicId(epicId) { return }
        do {
            try await prepareClient(ensureAgent: false)
            let snap = try await client.flowSnapshot(projectId: pid, epicId: epicId)
            applySnapshot(snap, projectId: pid, threadId: tid)
        } catch {
            // SSE 为主；snapshot 失败不刷屏、不改 connected
        }
    }

    private func applySnapshot(_ snap: FlowSnapshot, projectId: String, threadId: String? = nil) {
        let tid = resolveFlowThreadId(projectId: projectId, preferred: threadId)
        let isSelected = selectedProjectId == projectId
        var cached = threadFlow[tid] ?? FlowThreadSnapshot(
            epicId: nil, epic: nil, works: [], headline: "",
            recentEpics: isSelected ? recentEpics : [],
            emptyMessage: "编排空闲 · 下一笔定稿后出现在这里",
            fanoutHint: nil
        )

        if snap.empty == true {
            // pending: 仅投递仍在途时保留乐观大卡；已送达/失败/队列空且 Hub 空 → 清幽灵
            if Self.isPendingEpicId(cached.epicId),
               shouldKeepPendingOptimistic(threadId: tid) {
                return
            }
            let sunk = (snap.sunk == true) || (snap.missing_on_board == true)
                || Self.isPendingEpicId(cached.epicId)
            cached.works = []
            cached.epic = nil
            cached.epicId = nil
            cached.headline = ""
            cached.fanoutHint = nil
            cached.stopLossHint = nil
            cached.emptyMessage = snap.message
                ?? "编排空闲 · 下一笔定稿后出现在这里"
            if sunk {
                // 沉底/板上已无/过期 pending → 历史栈一并清空，避免右栏残留任务条
                cached.recentEpics = []
            }
            threadFlow[tid] = cached
            bumpFlowRevision(tid)
            setProjectFlow(projectId, cached)
            if isSelected {
                applyFlowSnapshot(cached)
                currentEpicId = nil
                if sunk {
                    recentEpics = []
                }
                lastAnimatedEpicId = nil
            }
            flushDiskSave(threadId: tid)
            return
        }
        // 兼容旧 Hub：empty=false 但 epic 卡缺失 + 无 works → 视作幽灵绑定，清轨
        if snap.epic == nil && (snap.works ?? []).isEmpty {
            let ghostStage = (snap.user_stage ?? "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
                .lowercased()
            if !Self.isPendingEpicId(cached.epicId),
               ghostStage.isEmpty || ghostStage == "pending" || ghostStage == "idle" {
                cached.works = []
                cached.epic = nil
                cached.epicId = nil
                cached.headline = ""
                cached.fanoutHint = nil
                cached.stopLossHint = nil
                cached.recentEpics = []
                cached.emptyMessage = "编排空闲 · 下一笔定稿后出现在这里"
                threadFlow[tid] = cached
                bumpFlowRevision(tid)
                setProjectFlow(projectId, cached)
                if isSelected {
                    applyFlowSnapshot(cached)
                    currentEpicId = nil
                    recentEpics = []
                    lastAnimatedEpicId = nil
                }
                flushDiskSave(threadId: tid)
                return
            }
        }
        let stage = (snap.user_stage ?? snap.epic?.user_stage ?? snap.epic?.split_status ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
        // 编排完成：右栏时间线退场；栈里保留「已完成」灰条
        if stage == "done" {
            let eid = snap.epic_id ?? cached.epicId
            var keptRecent = cached.recentEpics
            if let eid, !eid.isEmpty {
                if let idx = keptRecent.firstIndex(where: { $0.epic_id == eid }) {
                    keptRecent[idx].user_stage = "done"
                } else {
                    keptRecent.insert(
                        FlowEpicRef(
                            epic_id: eid,
                            title: snap.epic?.title ?? cached.epic?.title,
                            updated_at: ISO8601DateFormatter().string(from: Date()),
                            thread_id: tid,
                            user_stage: "done"
                        ),
                        at: 0
                    )
                }
            }
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
            setProjectFlow(projectId, cached)
            if isSelected {
                applyFlowSnapshot(cached)
                lastAnimatedEpicId = nil
                recentEpics = keptRecent
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
        cached.emptyMessage = works.isEmpty ? "扇出中…" : ""
        // 同步栈内 stage
        if let eid, let idx = cached.recentEpics.firstIndex(where: { $0.epic_id == eid }) {
            cached.recentEpics[idx].user_stage = snap.user_stage ?? snap.epic?.user_stage
            if cached.recentEpics[idx].title == nil {
                cached.recentEpics[idx] = FlowEpicRef(
                    epic_id: eid,
                    title: snap.epic?.title ?? cached.recentEpics[idx].title,
                    updated_at: cached.recentEpics[idx].updated_at,
                    thread_id: tid,
                    user_stage: cached.recentEpics[idx].user_stage
                )
            }
        } else if let eid, !eid.isEmpty, !cached.recentEpics.contains(where: { $0.epic_id == eid }) {
            cached.recentEpics.insert(
                FlowEpicRef(
                    epic_id: eid,
                    title: snap.epic?.title,
                    updated_at: ISO8601DateFormatter().string(from: Date()),
                    thread_id: tid,
                    user_stage: snap.user_stage ?? snap.epic?.user_stage
                ),
                at: 0
            )
        }
        // Phase9：abnormal / failed 止损可见（右栏 + 一次性 toast）
        let hasAbnormal = works.contains(where: \.isFailed)
        let stopLoss = (stage == "failed" || hasAbnormal)
        if stopLoss {
            let title = works.first(where: \.isFailed)?.title
                ?? snap.epic?.title
                ?? eid
                ?? "任务"
            let hint = "编排异常：\(title) · 复制给对话，让 Agent 处理"
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
        setProjectFlow(projectId, cached)
        if isSelected {
            applyFlowSnapshot(cached)
            recentEpics = cached.recentEpics
        }
        // Hub snapshot 非空且带 epic → 编排面已看见；delivered 升 accepted（按 thread）
        if let eid, !eid.isEmpty {
            promoteTransferAcceptedIfNeeded(threadId: tid, epicId: eid)
        }
    }

    func openNodeDetail(id: String, projectId: String? = nil) {
        let pid = projectId ?? selectedProjectId
        let snap = pid.flatMap { projectFlow[$0] }
            ?? pid.flatMap { threadFlow[threadIdForProject($0)] }
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
                    try await self?.prepareClient(ensureAgent: false)
                    await MainActor.run {
                        let next = (self?.flowConnectionGeneration[projectId] ?? 0) &+ 1
                        self?.flowConnectionGeneration[projectId] = next
                        self?.flowBackoffNs[projectId] = 3_000_000_000
                        self?.flowLastError.removeValue(forKey: projectId)
                        DesktopChatTurnLedger.append([
                            "event": "flow_connected",
                            "projectId": projectId,
                            "generation": next,
                            "reconnect_count": self?.flowReconnectCount[projectId] ?? 0,
                        ])
                    }
                    // Phase14：把本项目当前选中的 epic 透传给 Hub，让 Hub 在 JSONL 推送时按
                    // epic_id 过滤（避免他 epic 噪声打扰本轨）；不传则 Hub 推该项目全部事件。
                    let subscribedEpic = await MainActor.run { () -> String? in
                        guard let self else { return nil }
                        return self.projectFlow[projectId]?.epicId
                            ?? self.threadFlow[self.threadIdForProject(projectId)]?.epicId
                            ?? (self.selectedProjectId == projectId ? self.currentEpicId : nil)
                    }
                    try await self?.client.streamFlowEvents(
                        projectId: projectId,
                        epicId: subscribedEpic
                    ) { event, payload in
                        // Phase14：白名单扩到 epic_done；本 epic 命中立刻清轨（不等 8s 看板轮询）
                        let refreshEvents: Set<String> = [
                            "fanout", "work_status", "epic_created", "executor",
                        ]
                        let terminalEvents: Set<String> = ["epic_done"]
                        if refreshEvents.contains(event) {
                            Task { @MainActor in
                                guard let self else { return }
                                guard !self.flowSnapshotPaused else { return }
                                let stillWanted = self.focusedProjectIds.contains(projectId)
                                    || self.selectedProjectId == projectId
                                guard stillWanted else { return }
                                // 客户端二次校验：epic_id 缺失/不匹配 → 拒绝（防他 epic 噪声）
                                if let eid = payload["epic_id"] as? String, !eid.isEmpty {
                                    let bound = self.projectFlow[projectId]?.epicId
                                        ?? self.threadFlow[self.threadIdForProject(projectId)]?.epicId
                                        ?? (self.selectedProjectId == projectId ? self.currentEpicId : nil)
                                    if let bound, !bound.isEmpty, eid != bound {
                                        return
                                    }
                                }
                                await self.refreshFlow(projectId: projectId)
                            }
                            return
                        }
                        if terminalEvents.contains(event) {
                            Task { @MainActor in
                                guard let self else { return }
                                guard !self.flowSnapshotPaused else { return }
                                // epic_done 本 epic 触发 → 立即清轨；非本 epic 拒绝
                                if let eid = payload["epic_id"] as? String, !eid.isEmpty {
                                    let bound = self.projectFlow[projectId]?.epicId
                                        ?? self.threadFlow[self.threadIdForProject(projectId)]?.epicId
                                        ?? (self.selectedProjectId == projectId ? self.currentEpicId : nil)
                                    if let bound, !bound.isEmpty, eid != bound { return }
                                }
                                await self.handleEpicDoneTerminal(projectId: projectId)
                            }
                            return
                        }
                    }
                    try? await Task.sleep(nanoseconds: 2_000_000_000)
                } catch {
                    if Task.isCancelled { break }
                    let delay = await MainActor.run { () -> UInt64 in
                        let d = self?.flowBackoffNs[projectId] ?? 3_000_000_000
                        self?.flowBackoffNs[projectId] = min(d + 2_000_000_000, 12_000_000_000)
                        let count = (self?.flowReconnectCount[projectId] ?? 0) + 1
                        self?.flowReconnectCount[projectId] = count
                        self?.flowLastError[projectId] = error.localizedDescription
                        DesktopChatTurnLedger.append([
                            "event": "flow_disconnected",
                            "projectId": projectId,
                            "generation": self?.flowConnectionGeneration[projectId] ?? 0,
                            "reconnect_count": count,
                            "backoff_ms": Int(d / 1_000_000),
                            "error_type": String(describing: type(of: error)),
                        ])
                        return d
                    }
                    try? await Task.sleep(nanoseconds: delay)
                }
            }
        }
    }

    /// Phase14：epic_done 直接清右栏（不依赖 8s 看板轮询）。failed 由 Phase9 止损接管，
    /// 这里只处理 done 路径；异常继续保留 stopLossHint（已存在）。
    private func handleEpicDoneTerminal(projectId: String) async {
        let tid = threadIdForProject(projectId)
        let isSelected = selectedProjectId == projectId
        var snap = threadFlow[tid] ?? FlowThreadSnapshot(
            epicId: nil, epic: nil, works: [], headline: "",
            recentEpics: isSelected ? recentEpics : [],
            emptyMessage: "编排空闲 · 下一笔定稿后出现在这里",
            fanoutHint: nil
        )
        let keptRecent = snap.recentEpics
        snap.works = []
        snap.epic = nil
        snap.epicId = nil
        snap.headline = ""
        snap.fanoutHint = nil
        snap.stopLossHint = nil
        snap.recentEpics = keptRecent
        snap.emptyMessage = "编排空闲 · 下一笔定稿后出现在这里"
        threadFlow[tid] = snap
        bumpFlowRevision(tid)
        if isSelected {
            recentEpics = keptRecent
            applyFlowSnapshot(snap)
            lastAnimatedEpicId = nil
        }
        flushDiskSave(threadId: tid)
        DesktopChatTurnLedger.append([
            "event": "flow_epic_done_cleared",
            "projectId": projectId,
            "threadId": tid,
        ])
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
                // R2：先进磁盘缓存，再静默拉 live
                hydrateBoardCacheIfNeeded(projectId: pid)
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
        // 无列时先上缓存，避免白闪
        if let pid, boardColumns.isEmpty {
            hydrateBoardCacheIfNeeded(projectId: pid)
        }
        do {
            try await prepareClient(ensureAgent: false)
            let snap = try await client.fetchBoard(workspace: ws, includeHidden: boardShowHidden)
            let cols = snap.columns ?? [:]
            applyBoardSnapshot(columns: cols, error: nil)
            if let pid {
                LocalSessionStore.saveBoardCache(projectId: pid, workspace: ws, columns: cols)
            }
        } catch {
            boardError = error.localizedDescription
            applyBoardSnapshot(columns: boardColumns, error: error)
        }
    }

    func setBoardShowHidden(_ show: Bool) async {
        boardShowHidden = show
        await refreshBoard()
    }

    func moveBoardTask(_ task: BoardTask, to: String) async {
        let ws = boardWorkspaceLabel ?? selectedProject?.workspace ?? "CCC"
        do {
            try await prepareClient(ensureAgent: false)
            try await client.moveTask(taskId: task.id, to: to, workspace: ws)
            await refreshBoard()
        } catch {
            boardError = "移动失败: \(error.localizedDescription)"
        }
    }

    func hideCompletedEpics() async {
        let ws = boardWorkspaceLabel ?? selectedProject?.workspace ?? "CCC"
        do {
            try await prepareClient(ensureAgent: false)
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
            try await prepareClient(ensureAgent: false)
            try await client.reopenTask(taskId: task.id, to: to, workspace: ws)
            await refreshBoard()
        } catch {
            boardError = "重开失败: \(error.localizedDescription)"
        }
    }

    func reopenOpsTask(taskId: String, workspace: String, to: String = "planned") async {
        opsBusy = true
        opsAdoptError = nil
        defer { opsBusy = false }
        do {
            try await prepareClient(ensureAgent: false)
            try await client.reopenTask(taskId: taskId, to: to, workspace: workspace)
            await refreshOps()
        } catch {
            opsAdoptError = "运维重开失败: \(error.localizedDescription)"
        }
    }

    func openBoardFromOps(workspace: String) {
        let ws = workspace.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !ws.isEmpty else { return }
        boardWorkspaceLabel = ws
        if let p = projects.first(where: { ($0.workspace ?? $0.id) == ws || $0.id == ws }) {
            selectDestination(.board, projectId: p.id)
        } else {
            selectDestination(.board, projectId: selectedProjectId)
        }
    }

    func fetchTaskDetail(_ task: BoardTask) async throws -> BoardTaskDetail {
        try await prepareClient(ensureAgent: false)
        let ws = boardWorkspaceLabel ?? selectedProject?.workspace ?? "CCC"
        return try await client.fetchTaskDetail(taskId: task.id, workspace: ws)
    }

    func refreshOps() async {
        opsBusy = true
        opsError = nil
        defer { opsBusy = false }
        do {
            try await prepareClient(ensureAgent: false)
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
            // M1 sidecar → 运维总灯合并（Hub domains.agent_mcp 占位）
            let agentStr = agentURLString.trimmingCharacters(in: .whitespacesAndNewlines)
            if let agentBase = APIClient.makeBaseURL(from: agentStr),
               let info = await client.fetchAgentHealth(base: agentBase) {
                opsAgentOk = info.ok
                opsAgentRuntime = info.agentRuntime
                opsAgentModel = info.model
            } else {
                opsAgentOk = false
                opsAgentRuntime = nil
                opsAgentModel = nil
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
            try await prepareClient(ensureAgent: false)
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
            try await prepareClient(ensureAgent: false)
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
            try await prepareClient(ensureAgent: false)
            try await client.adoptSuggestion(workspace: workspace, title: title, description: description, tags: tags)
        } catch {
            opsAdoptError = "采纳失败: \(error.localizedDescription)"
        }
    }

    // MARK: - Stale snapshot scratch (P3: Board degraded UI differentiation)

    @Published private(set) var boardLastSuccess: Date?
    @Published private(set) var boardStale: Bool = false
    @Published private(set) var boardErrorKind: String?
    /// Hub/Board 分层状态文案：本机可聊 / Hub 编排 / Board 快照。
    @Published private(set) var stackStatus: String = "等待探测…"

    /// `applyDeltaInPlace` 合批用：与现有 flow 兼容，原文件保留。
    enum StackStatus: String, Codable, Equatable {
        case localOnly
        case hubOnline
        case boardStale
        case boardOffline
        case hubOffline
        case bothDown
    }

    func updateStackStatus() {
        let localOK = canChat
        let boardOK = !boardStale && boardErrorKind == nil
        let hubOK = hubReachable
        let s: String
        if !localOK && !hubOK {
            s = "本机 Agent + Hub 均不可用"
        } else if !localOK && !boardOK {
            s = "本机 Agent 不可用 · 看板不可用"
        } else if !localOK {
            s = "本机 Agent 不可用 · Hub 可达"
        } else if !hubOK {
            s = "本机 Agent 可用 · Hub 暂不可达"
        } else if !boardOK {
            s = "Hub 可达 · 看板不可用（保留上次快照）"
        } else {
            s = "已连接 · 本机 Agent + Hub + 看板"
        }
        if stackStatus != s { stackStatus = s }
    }

    /// 由 refreshBoard 写入：成功 → 标记新鲜；失败 → 标记陈旧但保留旧数据。
    private func applyBoardSnapshot(columns: [String: [BoardTask]], error: Error?) {
        if let error {
            boardStale = true
            let kind: String
            if (error as? URLError)?.code == .notConnectedToInternet
                || (error as? URLError)?.code == .networkConnectionLost
                || (error as? URLError)?.code == .cannotConnectToHost
                || (error as? URLError)?.code == .timedOut {
                kind = "offline"
            } else {
                kind = "server_error"
            }
            if boardErrorKind != kind { boardErrorKind = kind }
            if boardColumns.isEmpty {
                boardColumns = [:]
            }
        } else {
            boardColumns = columns
            boardError = nil
            boardErrorKind = nil
            boardStale = false
            boardLastSuccess = Date()
        }
        updateStackStatus()
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
        // 不 bump tick：TitlebarUsageAccessory 自带 timer；避免 1Hz objectWillChange 拖聊天重绘
        agentUsageTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                guard !Task.isCancelled, let self else { break }
                await MainActor.run {
                    self.refreshAgentLLMRecent5s(now: Date())
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
        let n = agentLLMCallTimestamps.count
        // 仅数值变化才 @Published，避免 1Hz 拖整树
        if agentLLMRecent5s != n {
            agentLLMRecent5s = n
        }
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

    /// 转任务按钮旁人话门禁（nil = 可点）。Hub 离线不挡确认。
    func transferGateHint(projectId: String?, threadId: String?) -> String? {
        guard let projectId else {
            return "先在左侧选择一个业务项目"
        }
        if let p = projects.first(where: { $0.id == projectId }), p.isOrch == true {
            return "当前是编排仓：请切到业务项目再转任务"
        }
        if !canTransfer(projectId: projectId) {
            return "该项目不可下达，请换业务仓（可先聊；确认后排队）"
        }
        if let d = transferDraft(for: threadId), !d.isGateReady {
            return "定稿未过门禁：补全标题、目标与至少一条验收"
        }
        if !hubReachable {
            return "Hub 离线：确认后排队，恢复后自动投递"
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
        // R12：Hub 往返不锁全局 busy
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
            try await prepareClient(ensureAgent: false)
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
            try await prepareClient(ensureAgent: false)
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
            try await prepareClient(ensureAgent: false)
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
            try await prepareClient(ensureAgent: false)
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
            try await prepareClient(ensureAgent: false)
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
            try await prepareClient(ensureAgent: false)
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
            try await prepareClient(ensureAgent: false)
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
            try await prepareClient(ensureAgent: false)
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
