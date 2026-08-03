import AppKit
import Foundation
import SwiftUI

// MARK: - ChatState：隔离流式 delta 通知到消息列表区
@MainActor
final class ChatState: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var draft: String = ""
    @Published var streamStatus: String = ""

    func replaceMessage(id: UUID, _ update: (inout ChatMessage) -> Void) {
        guard let idx = messages.firstIndex(where: { $0.id == id }) else { return }
        var copy = messages
        update(&copy[idx])
        messages = copy
    }
}

@MainActor
final class AppModel: ObservableObject {
    // MARK: - AppStorage
    @AppStorage("ccc.server") var serverURLString: String = "http://192.168.3.116:7788"
    @AppStorage("ccc.user") var authUser: String = "ccc"
    @AppStorage("ccc.pass") var authPass: String = "ccc"
    @AppStorage("ccc.selectedProject") var persistedProjectId: String = ""
    
    @AppStorage("ccc.localWorkspace") var localWorkspacePath: String = ""
    @AppStorage("ccc.localWorkspaceMap") var localWorkspaceMapJSON: String = "{}"
    
    @AppStorage("ccc.dismissedFirstRunTip") var dismissedFirstRunTip: Bool = false
    @AppStorage("ccc.preferredModel") var preferredModel: String = "flash"
    @AppStorage("ccc.preferredToolMode") var preferredToolMode: String = "engineer"

    // MARK: - Published: Projects / Threads / Chat
    @Published var projects: [DesktopProject] = []
    @Published var threads: [DesktopThread] = []
    @Published var selectedProjectId: String?
    @Published var selectedThreadId: String?
    @Published var isContextPanelPresented = false
    @Published var composerAttachments: [ComposerAttachment] = []
    @Published var confirmEngineerMode = false
    @Published var chat = ChatState()
    @Published var statusText: String = "未连接"
    @Published var busy = false
    @Published var connected = false
    @Published var lastError: String?
    @Published var destination: SidebarDestination = .chat
    @Published var toast: String?
    @Published var activeQuickAction: String? = nil
    @Published var showSettingsHint = false
    @Published var expandedProjectIds: Set<String> = []
    @Published var renameThreadId: String?
    @Published var renameDraft: String = ""
    @Published var previewMarkdown: String?
    @Published var sessionTokens: Int = 0

    // MARK: - Published: Board
    @Published var boardColumns: [String: [BoardTask]] = [:]
    @Published var boardBusy = false
    @Published var boardError: String?
    @Published var boardWorkspaceLabel: String?
    @Published var boardShowHidden = false
    @Published private(set) var boardLastSuccess: Date?
    @Published private(set) var boardStale: Bool = false
    @Published private(set) var boardErrorKind: String?
    @Published var boardStatusFilter: Set<String> = []
    @Published var boardExecutorFilter: String = ""
    @Published var boardPriorityFilter: Set<String> = []
    @Published var boardSearchQuery: String = ""

    // MARK: - Published: Ops
    @Published var opsOverview: OpsOverview?
    @Published var opsRisks: [OpsRisk] = []
    @Published var opsRisksCount: Int?
    @Published var opsRisksHigh: Int?
    @Published var opsBusy = false
    @Published var opsError: String?
    @Published var opsSummary: OpsSummary?
    @Published var opsUpstreamDaily: [OpsUpstreamDailyRow] = []
    @Published var opsAdoptBusy = false
    @Published var opsAdoptError: String?
    
    @Published var opsCopiedHint: String?
    @Published var localPatrolAlerts: [OpsHealthAlert] = []
    @Published private(set) var opsDisplaySeverity: String = "amber"
    @Published private(set) var opsDisplayAlertCount: Int = 0
    @Published var inboxProposals: [InboxProposal] = []
    @Published var inboxAdoptBusy = false

    

    // MARK: - Published: Search / UI State
    @Published var searchQuery: String = ""
    @Published var searchResults: [LocalSessionStore.SearchResult] = []
    @Published var isSearching: Bool = false
    @Published var pendingScrollMessageId: String?
    @Published var isHelpPresented: Bool = false
    @Published var searchFocusTick: UInt64 = 0
    @Published var commandNewThreadTick: UInt64 = 0
    @Published var commandTransferTick: UInt64 = 0
    @Published var commandDestination: SidebarDestination?
    

    // MARK: - Published: Stack status
    @Published private(set) var stackStatus: String = "等待探测…"

    // MARK: - Published: Token tracking
    @Published var perMessageTokens: [UUID: Int] = [:]
    @Published var totalSessionCost: Double = 0

    // MARK: - Published: Manual epic
    @Published var isManualEpicPresented: Bool = false
    @Published var manualEpicForm: ManualEpicForm = ManualEpicForm()  // keep for UI

    // MARK: - Published: Templates
    @Published var templates: [TaskTemplate] = []
    @Published var isTemplatePickerPresented: Bool = false

    // MARK: - Published: Custom prompts
    @Published var customPrompts: [QuickPromptItem] = []

    // MARK: - Private
    private var client: APIClient
    private var foregroundResumeTask: Task<Void, Never>?
    private var lastForegroundResumeAt: Date?
    private var opsSeverityPollTask: Task<Void, Never>?
    private var bootstrapStarted = false
    private var threadMessages: [String: [ChatMessage]] = [:]
    @Published private(set) var threadRevision: [String: UInt64] = [:]
    private var diskSaveTasks: [String: Task<Void, Never>] = [:]

    // MARK: - Computed
    var selectedProject: DesktopProject? {
        projects.first { $0.id == selectedProjectId }
    }

    var filteredBoardColumns: [String: [BoardTask]] {
        guard !boardStatusFilter.isEmpty || !boardExecutorFilter.isEmpty
                || !boardPriorityFilter.isEmpty || !boardSearchQuery.isEmpty
        else { return boardColumns }

        var result: [String: [BoardTask]] = [:]
        for (col, tasks) in boardColumns {
            let filtered = tasks.filter { task in
                if !boardStatusFilter.isEmpty, !boardStatusFilter.contains(task.status ?? "") { return false }
                if !boardExecutorFilter.isEmpty, (task.executor ?? "") != boardExecutorFilter { return false }
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

    // MARK: - Init
    init() {
        let raw = UserDefaults.standard.string(forKey: "ccc.server")
            ?? "http://192.168.3.116:7788"
        let url = APIClient.makeBaseURL(from: raw)
            ?? URL(string: "http://192.168.3.116:7788")!
        let user = UserDefaults.standard.string(forKey: "ccc.user") ?? "ccc"
        let pass = UserDefaults.standard.string(forKey: "ccc.pass") ?? "ccc"
        client = APIClient(baseURL: url, user: user, password: pass)
        hydrateFromDiskSync()
    }

    // MARK: - Local Persistence
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
        hydrateBoardCacheIfNeeded(projectId: pid)
        if !projects.isEmpty {
            connected = true
            statusText = "本机缓存 · Hub 同步中…"
        }
    }

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

    private func hydrateThreadFromDisk(projectId: String, threadId: String) {
        guard let disk = LocalSessionStore.load(projectId: projectId, threadId: threadId) else { return }
        let ram = threadMessages[threadId] ?? []
        let diskScore = LocalSessionStore.messageScore(disk.messages)
        let ramScore = LocalSessionStore.messageScore(ram)
        if ram.isEmpty || diskScore > ramScore {
            threadMessages[threadId] = disk.messages
        }
        bumpThreadRevision(threadId)
    }

    private func persistMessages(for threadId: String, _ msgs: [ChatMessage]) {
        threadMessages[threadId] = msgs
        bumpThreadRevision(threadId)
        scheduleDiskSave(threadId: threadId)
    }

    private func bumpThreadRevision(_ threadId: String) {
        var copy = threadRevision
        copy[threadId, default: 0] &+= 1
        threadRevision = copy
    }

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
        for tid in diskSaveTasks.keys {
            flushDiskSave(threadId: tid)
        }
    }

    private func writeDiskSave(threadId tid: String, projectId pid: String) {
        let msgs = (threadMessages[tid] ?? []).filter { msg in
            if !msg.isStreaming { return true }
            if !msg.content.isEmpty { return true }
            if !msg.toolSteps.isEmpty { return true }
            return false
        }
        let title = threads.first(where: { $0.thread_id == tid })?.title
        LocalSessionStore.saveMessages(
            projectId: pid,
            threadId: tid,
            messages: msgs,
            title: title,
            flow: nil,
            needsHubSync: false,
            claudeSessionId: nil
        )
    }

    private func mutateThreadMessages(threadId: String, _ body: (inout [ChatMessage]) -> Void) {
        var msgs = threadMessages[threadId] ?? []
        body(&msgs)
        persistMessages(for: threadId, msgs)
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

    func localPath(for projectId: String?) -> String? {
        guard let projectId, !projectId.isEmpty else {
            let g = localWorkspacePath.trimmingCharacters(in: .whitespacesAndNewlines)
            return g.isEmpty ? nil : g
        }
        if let mapped = workspaceMap[projectId]?.trimmingCharacters(in: .whitespacesAndNewlines),
           !mapped.isEmpty {
            if FileManager.default.fileExists(atPath: mapped) { return mapped }
            return nil
        }
        if projectId == "ccc" {
            let global = localWorkspacePath.trimmingCharacters(in: .whitespacesAndNewlines)
            if !global.isEmpty, FileManager.default.fileExists(atPath: global) { return global }
        }
        return nil
    }

    // MARK: - Client
    private func prepareClient(projectId: String? = nil) async throws {
        let pid = projectId ?? selectedProjectId
        _ = localPath(for: pid)
        // serverURLString is the SSOT for server address
    }

    // MARK: - Thread ID helpers
    private func threadIdForProject(_ projectId: String?) -> String {
        guard let pid = projectId, !pid.isEmpty else { return "" }
        return LocalSessionStore.migrateLegacyThread(projectId: pid)
    }

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

    static func projectId(fromThreadId threadId: String) -> String {
        if let range = threadId.range(of: "::") {
            return String(threadId[..<range.lowerBound])
        }
        return threadId
    }

    // MARK: - Bootstrap
    func bootstrap() async {
        guard !bootstrapStarted else { return }
        bootstrapStarted = true
        if let env = ProcessInfo.processInfo.environment["CCC_SERVER"]?.trimmingCharacters(in: .whitespacesAndNewlines),
           !env.isEmpty {
            serverURLString = env
        } else if serverURLString.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            serverURLString = "http://192.168.3.116:7788"
        }
        if projects.isEmpty {
            hydrateFromDiskSync()
        }
        Task { @MainActor in
            await self.refreshProjects(showBusy: false)
        }
        startOpsSeverityPoll()
    }

    // MARK: - Projects
    func refreshProjects() async {
        await refreshProjects(showBusy: true)
    }

    func refreshProjects(showBusy: Bool) async {
        if showBusy { busy = true }
        defer { if showBusy { busy = false } }
        do {
            try await prepareClient()
            let resp = try await client.fetchProjectsNewServer()
            projects = resp.projects
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
            connected = !projects.isEmpty
            lastError = nil
            statusText = "已连接"
            if selectedProjectId != nil {
                await refreshProjectStats()
            }
        } catch {
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
            connected = !projects.isEmpty
            showSettingsHint = !connected
            statusText = "连接失败"
            showToast("Hub 暂不可达：\(error.localizedDescription)")
        }
    }

    func selectProject(_ id: String, preferredThreadId: String? = nil) async {
        let switching = id != selectedProjectId
        if let prev = selectedProjectId, switching {
            let prevTid = resolveThreadId(projectId: prev, preferred: selectedThreadId)
            persistCurrentThreadSnapshot(threadId: prevTid)
        }
        let preferred = Self.resolvedPreferredThreadId(projectId: id, preferred: preferredThreadId)
        let localRecent = LocalSessionStore.threadsAsDesktop(projectId: id).first?.thread_id
        let eagerTid = preferred ?? localRecent ?? threadIdForProject(id)
        selectedProjectId = id
        persistedProjectId = id
        expandedProjectIds.insert(id)
        preferredToolMode = "engineer"
        ensureThreadHydrated(threadId: eagerTid)
        selectedThreadId = eagerTid
        if switching {
            hydrateBoardCacheIfNeeded(projectId: id)
        }
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
        }
    }

    func openProjectConversation(_ id: String, preferredThreadId: String? = nil) async {
        destination = .chat
        if let pref = Self.resolvedPreferredThreadId(projectId: id, preferred: preferredThreadId) {
            ensureThreadHydrated(threadId: pref)
        } else {
            ensureThreadHydrated(projectId: id)
        }
        await selectProject(id, preferredThreadId: preferredThreadId)
    }

    func refreshThreads(projectId: String) async {
        let tid = threadIdForProject(projectId)
        let local = LocalSessionStore.threadsAsDesktop(projectId: projectId)
        if local.isEmpty,
           !LocalSessionStore.isArchived(projectId: projectId, threadId: tid) {
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

    func reconnect() async {
        statusText = "连接中…"
        await refreshProjects()
    }

    // MARK: - Threads
    func loadConversation(threadId: String) async {
        guard !threadId.isEmpty else { return }
        selectedThreadId = threadId
        ensureThreadHydrated(threadId: threadId)
        let state = ConversationStore.load(threadId: threadId)
        let disk = state.messages
        let ram = threadMessages[threadId] ?? []
        if !ram.isEmpty
            && LocalSessionStore.messageScore(ram) >= LocalSessionStore.messageScore(disk) {
            if threadMessages[threadId] == nil {
                threadMessages[threadId] = ram
            }
        } else if !disk.isEmpty {
            threadMessages[threadId] = disk
        } else if !ram.isEmpty {
            threadMessages[threadId] = ram
        } else {
            threadMessages[threadId] = disk
        }
        bumpThreadRevision(threadId)
        chat.messages = threadMessages[threadId] ?? []
        sessionTokens = 0
        lastError = nil
    }

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

    func hasHydratedThread(_ threadId: String?) -> Bool {
        guard let threadId, !threadId.isEmpty else { return false }
        return threadMessages[threadId] != nil
    }

    func ensureThreadHydrated(projectId: String) {
        let recent = LocalSessionStore.threadsAsDesktop(projectId: projectId).first?.thread_id
        let tid = (recent?.isEmpty == false) ? recent! : threadIdForProject(projectId)
        ensureThreadHydrated(threadId: tid)
    }

    func messagesForThread(_ threadId: String?) -> [ChatMessage] {
        guard let threadId, !threadId.isEmpty else { return [] }
        return threadMessages[threadId] ?? []
    }

    func openThread(_ id: String) async {
        guard !id.isEmpty else { return }
        let pid = LocalSessionStore.projectId(fromThreadId: id)
        selectedProjectId = pid
        destination = .chat
        selectedThreadId = id
        clearThreadUnread(id)
        ensureThreadHydrated(threadId: id)
        await loadConversation(threadId: id)
    }

    func clearThreadUnread(_ threadId: String) {}

    func projectHasUnread(_ projectId: String) -> Bool { false }

    @discardableResult
    func createNewThread(projectId: String) async -> String {
        let tid = ConversationStore.createThread(projectId: projectId, title: "新对话")
        threads = ConversationStore.listThreads(projectId: projectId)
        await openThread(tid)
        return tid
    }

    @discardableResult
    func forkThread(threadId: String) async -> String? {
        flushDiskSave(threadId: threadId)
        guard let newId = ConversationStore.forkThread(threadId: threadId) else {
            showToast("分叉失败")
            return nil
        }
        let pid = LocalSessionStore.projectId(fromThreadId: newId)
        threads = ConversationStore.listThreads(projectId: pid)
        await openThread(newId)
        showToast("已分叉会话")
        return newId
    }

    func newThread() async {
        await resetConversation()
    }

    func resetConversation(projectId: String? = nil) async {
        guard let pid = projectId ?? selectedProjectId else {
            showToast("请先选择项目")
            return
        }
        let priorThreads = LocalSessionStore.threadsAsDesktop(projectId: pid)
        for t in priorThreads {
            threadMessages.removeValue(forKey: t.thread_id)
        }
        let mainId = threadIdForProject(pid)
        threadMessages.removeValue(forKey: mainId)
        LocalSessionStore.reset(projectId: pid)
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
            chat.messages = []
        }
        showToast("对话已重置")
        destination = .chat
    }

    func archiveThread(threadId: String) async {
        let pid = LocalSessionStore.projectId(fromThreadId: threadId)
        ConversationStore.archiveThread(threadId: threadId)
        threadMessages.removeValue(forKey: threadId)
        threads = ConversationStore.listThreads(projectId: pid)
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

    func renameThread(threadId: String, title: String) {
        let pid = LocalSessionStore.projectId(fromThreadId: threadId)
        LocalSessionStore.rename(projectId: pid, threadId: threadId, title: title)
        threads = ConversationStore.listThreads(projectId: pid)
    }

    func deleteThread(_ threadId: String) async {
        _ = threadId
        await resetConversation()
    }

    func beginRenameThread(_ thread: DesktopThread) {
        _ = thread
    }

    func commitRenameThread() async {
        renameThreadId = nil
    }

    private func persistCurrentThreadSnapshot(threadId: String) {
        if threadMessages[threadId] == nil,
           selectedThreadId == threadId,
           !chat.messages.isEmpty {
            threadMessages[threadId] = chat.messages
        }
        flushDiskSave(threadId: threadId)
    }

    // MARK: - Server Auth
    func loginToServer() async {
        guard let url = APIClient.makeBaseURL(from: serverURLString) else {
            serverLoginError = "服务端地址无效"
            return
        }
        await client.configureNewServer(url: url)
        let user = authUser.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !user.isEmpty, !authPass.isEmpty else {
            serverLoginError = "请填写账号和密码"
            return
        }
        do {
            _ = try await client.loginToNewServer(username: user, password: authPass)
            serverLoggedIn = true
            serverLoginError = nil
            showToast("服务端登录成功")
        } catch let apiErr as APIError {
            serverLoggedIn = false
            serverLoginError = apiErr.localizedDescription
        } catch {
            serverLoggedIn = false
            serverLoginError = "登录失败：\(error.localizedDescription)"
        }
    }

    func logoutFromServer() {
        Task { await client.configureNewServer(url: nil) }
        serverLoggedIn = false
        showToast("已登出服务端")
    }

    @Published var serverLoggedIn: Bool = false
    @Published var serverLoginError: String?

    // MARK: - Chat
    func sendUserMessage(_ text: String, projectId: String? = nil, threadId: String? = nil,
                         stopAndSend: Bool = true, attachments: [ComposerAttachment]? = nil,
                         displayText: String? = nil) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        if attachments == nil { composerAttachments = [] }
        let pid = projectId ?? selectedProjectId
        let shown = displayText?.trimmingCharacters(in: .whitespacesAndNewlines)
        Task {
            await self.sendUserMessageAndWait(
                trimmed, projectId: pid, threadId: threadId,
                stopAndSend: stopAndSend,
                displayText: (shown?.isEmpty == false) ? shown : nil
            )
        }
    }

    @discardableResult
    func sendUserMessageAndWait(_ text: String, projectId: String? = nil,
                                 threadId preferredThreadId: String? = nil,
                                 stopAndSend: Bool = true,
                                 displayText: String? = nil) async -> Bool {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return false }
        guard let pid = projectId ?? selectedProjectId else {
            showToast("请先选择项目")
            activeQuickAction = nil
            return false
        }
        let threadId = resolveThreadId(projectId: pid, preferred: preferredThreadId)
        ensureThreadHydrated(threadId: threadId)
        if selectedProjectId == pid {
            if selectedThreadId != threadId { selectedThreadId = threadId }
            chat.messages = threadMessages[threadId] ?? []
        }
        let shown = displayText?.trimmingCharacters(in: .whitespacesAndNewlines)
        let task = Task { [weak self] in
            guard let self else { return }
            await self.runNewServerChat(
                projectId: pid, threadId: threadId, text: trimmed,
                displayText: (shown?.isEmpty == false) ? shown : nil
            )
        }
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

    func cancelChat(threadId: String? = nil, silent: Bool = false, dropSlot: Bool = false) {
        let tid = threadId ?? selectedThreadId
        guard let tid else { return }
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
        if !silent { showToast("已取消生成") }
    }

    private func runNewServerChat(projectId: String, threadId: String, text: String,
                                   displayText: String? = nil) async {
        let userMsg = ChatMessage(role: "user", content: text, displayContent: displayText)
        let assistantId = UUID()
        mutateThreadMessages(threadId: threadId) { msgs in
            msgs.append(userMsg)
            msgs.append(ChatMessage(id: assistantId, role: "assistant", content: "", isStreaming: true))
        }
        chat.streamStatus = "新服务端生成中…"
        statusText = "新服务端生成中…"

        if !serverLoggedIn {
            mutateThreadMessages(threadId: threadId) { msgs in
                guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                msgs[idx].content = "请先在「设置 → 新服务端（T19）」登录后再对话。"
                msgs[idx].isStreaming = false
            }
            chat.streamStatus = ""
            statusText = "已连接"
            return
        }

        do {
            try Task.checkCancellation()
            if let url = APIClient.makeBaseURL(from: serverURLString) {
                await client.configureNewServer(url: url)
            }
            let reply = try await client.sendConversation(message: text)
            mutateThreadMessages(threadId: threadId) { msgs in
                guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                msgs[idx].content = reply
                msgs[idx].isStreaming = false
            }
        } catch is CancellationError {
            mutateThreadMessages(threadId: threadId) { msgs in
                guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                msgs[idx].content = "（已停止）"
                msgs[idx].isStreaming = false
            }
        } catch let apiErr as APIError {
            var is401 = false
            if case .http(let code, _) = apiErr, code == 401 { is401 = true }
            if is401 {
                serverLoggedIn = false
                serverLoginError = "会话已过期，请重新登录"
            }
            let errText = is401
                ? "会话已过期（401），请在「设置 → 新服务端（T19）」重新登录。"
                : "对话失败：\(apiErr.localizedDescription)"
            mutateThreadMessages(threadId: threadId) { msgs in
                guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                msgs[idx].content = errText
                msgs[idx].isStreaming = false
            }
        } catch {
            mutateThreadMessages(threadId: threadId) { msgs in
                guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                msgs[idx].content = "对话失败：\(error.localizedDescription)"
                msgs[idx].isStreaming = false
            }
        }
        chat.streamStatus = ""
        statusText = "已连接"
        flushDiskSave(threadId: threadId)
        chat.messages = threadMessages[threadId] ?? []
    }

    // MARK: - Message Editing
    func updateMessage(threadId: String, messageId: UUID, newContent: String) {
        mutateThreadMessages(threadId: threadId) { msgs in
            guard let idx = msgs.firstIndex(where: { $0.id == messageId }) else { return }
            msgs[idx].content = newContent
            msgs[idx].edited = true
        }
        flushDiskSave(threadId: threadId)
    }

    func editUserMessage(_ message: ChatMessage, projectId: String? = nil, threadId: String? = nil) {
        guard message.role == "user" else { return }
        let pid = projectId ?? selectedProjectId
        _ = pid.map { resolveThreadId(projectId: $0, preferred: threadId) } ?? selectedThreadId
        chat.draft = message.content
        destination = .chat
        showToast("已填入输入框，改完再发送")
    }

    func regenerateAssistant(after message: ChatMessage, projectId: String? = nil, threadId: String? = nil) {
        guard message.role == "assistant" else { return }
        let pid = projectId ?? selectedProjectId
        guard let pid else { return }
        let tid = resolveThreadId(projectId: pid, preferred: threadId)
        let msgs = threadMessages[tid] ?? []
        guard let idx = msgs.firstIndex(where: { $0.id == message.id }) else { return }
        var userText: String?
        var i = idx - 1
        while i >= 0 {
            if msgs[i].role == "user" { userText = msgs[i].content; break }
            i -= 1
        }
        guard let text = userText, !text.isEmpty else {
            showToast("找不到上一条用户消息")
            return
        }
        sendUserMessage(text, projectId: pid, threadId: tid, stopAndSend: true)
    }

    func previewMessage(_ text: String) {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty else { showToast("无可预览内容"); return }
        previewMarkdown = t
    }

    // MARK: - Window Focus
    func setWindowFocus(from previous: String?, to next: String?) {
        if let n = next, !n.isEmpty {
            ensureThreadHydrated(projectId: n)
        }
    }

    func setWindowThreadFocus(from previous: String?, to next: String?) {
        if let n = next, !n.isEmpty {
            clearThreadUnread(n)
            ensureThreadHydrated(threadId: n)
        }
    }

    func ensureWindowFocus(projectId: String?) {
        guard let projectId, !projectId.isEmpty else { return }
        setWindowFocus(from: nil, to: projectId)
    }

    // MARK: - UI State
    func dismissToast() { toast = nil }

    func showToast(_ msg: String, holdSeconds: Double = 5) {
        toast = msg
        let hold = max(1.5, holdSeconds)
        Task {
            try? await Task.sleep(nanoseconds: UInt64(hold * 1_000_000_000))
            if toast == msg { toast = nil }
        }
    }

    func selectDestination(_ dest: SidebarDestination, projectId: String? = nil) {
        let prev = destination
        destination = dest
        let pid = projectId ?? selectedProjectId
        switch dest {
        case .chat:
            if prev != .chat, let pid {
                let tid = threadIdForProject(pid)
                if selectedProjectId == pid { selectedThreadId = tid }
                ensureThreadHydrated(projectId: pid)
                if selectedProjectId == pid {
                    chat.messages = threadMessages[tid] ?? []
                }
            }
        case .board:
            if let pid {
                let tid = threadIdForProject(pid)
                persistCurrentThreadSnapshot(threadId: tid)
                hydrateBoardCacheIfNeeded(projectId: pid)
            } else if let tid = selectedThreadId {
                persistCurrentThreadSnapshot(threadId: tid)
            }
            Task {
                await self.refreshBoard(projectId: pid)
            }
        case .ops:
            if let pid {
                let tid = threadIdForProject(pid)
                persistCurrentThreadSnapshot(threadId: tid)
            } else if let tid = selectedThreadId {
                persistCurrentThreadSnapshot(threadId: tid)
            }
            Task { await self.refreshOps() }
        }
    }

    func updateStackStatus() {
        let boardOK = !boardStale && boardErrorKind == nil
        let s: String
        if !boardOK {
            s = "看板不可用（保留上次快照）"
        } else {
            s = "已连接"
        }
        if stackStatus != s { stackStatus = s }
    }

    func dismissFirstRunTip() { dismissedFirstRunTip = true }

    // MARK: - Quick Prompts
    func applyQuickPrompt(_ prompt: String, uiLabel: String, projectId: String? = nil, threadId: String? = nil) {
        destination = .chat
        activeQuickAction = uiLabel
        showToast("已开始：\(uiLabel)")
        NSHapticFeedbackManager.defaultPerformer.perform(.generic, performanceTime: .now)
        sendUserMessage(prompt, projectId: projectId, threadId: threadId, stopAndSend: true, displayText: "【快捷】\(uiLabel)")
    }

    // MARK: - Tool Mode
    func requestEngineerMode() {
        if preferredToolMode == "engineer" {
            preferredToolMode = "discuss"
            showToast("已切到规划模式（可选只读）")
            return
        }
        preferredToolMode = "engineer"
        showToast("全功能模式：开发 / 定任务 / 优化（工具全开）")
    }

    func confirmEnableEngineerMode() {
        preferredToolMode = "engineer"
        confirmEngineerMode = false
        showToast("全功能模式：开发 / 定任务 / 优化（工具全开）")
    }

    // MARK: - Search
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

    // MARK: - Export / Import
    func exportThreadJSONToPasteboard(threadId: String? = nil) {
        let tid = threadId ?? selectedThreadId
        guard let tid else { return }
        let pid = LocalSessionStore.projectId(fromThreadId: tid)
        flushDiskSave(threadId: tid)
        guard let data = LocalSessionStore.exportV1JSON(projectId: pid, threadId: tid),
              let str = String(data: data, encoding: .utf8) else {
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
              let newId = LocalSessionStore.importV1(data, projectId: pid) else {
            showToast("剪贴板不是有效会话 JSON")
            return
        }
        threads = ConversationStore.listThreads(projectId: pid)
        await openThread(newId)
        showToast("已导入会话")
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

    func exportThreadToPasteboard(threadId: String? = nil) {
        let md = exportThreadMarkdown(threadId: threadId)
        guard !md.isEmpty else { showToast("无可导出内容"); return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(md, forType: .string)
        showToast("会话已复制为 Markdown")
    }

    func copyMessage(_ text: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        showToast("已复制")
    }

    // MARK: - Reveal Changed Files
    func revealChangedFiles(message: ChatMessage, projectId: String?) {
        let paths = message.changedFilePaths
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

    // MARK: - Composer Attachments
    func addComposerAttachment(path: String) {
        let p = path.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !p.isEmpty else { return }
        if composerAttachments.contains(where: { $0.path == p }) { return }
        composerAttachments.append(ComposerAttachment(path: p))
    }

    func removeComposerAttachment(id: UUID) {
        composerAttachments.removeAll { $0.id == id }
    }

    // MARK: - Board
    func refreshBoard(projectId: String? = nil) async {
        boardBusy = true
        boardError = nil
        defer { boardBusy = false }
        let pid = projectId ?? selectedProjectId
        let proj = projects.first { $0.id == pid }
        let ws = proj?.workspace ?? pid ?? "CCC"
        boardWorkspaceLabel = ws
        if let pid, boardColumns.isEmpty {
            hydrateBoardCacheIfNeeded(projectId: pid)
        }
        do {
            try await prepareClient()
            let snap = try await client.fetchBoardNewServer(workspace: ws, includeHidden: boardShowHidden)
            let cols = snap.columns ?? [:]
            applyBoardSnapshot(columns: cols, error: nil)
            if let pid {
                LocalSessionStore.saveBoardCache(projectId: pid, workspace: ws, columns: cols)
            }
        } catch {
            if let apiErr = error as? APIError, case .http(let code, _) = apiErr, code == 401 {
                serverLoggedIn = false
                serverLoginError = "看板会话已过期，请重新登录"
                boardError = "看板会话已过期，请在「设置 → 新服务端（T19）」重新登录"
                applyBoardSnapshot(columns: boardColumns, error: error)
                return
            }
            boardError = error.localizedDescription
            applyBoardSnapshot(columns: boardColumns, error: error)
        }
    }

    func setBoardShowHidden(_ show: Bool) async {
        boardShowHidden = show
        await refreshBoard()
    }

    func fetchTaskDetail(_ task: BoardTask) async throws -> BoardTaskDetail {
        try await prepareClient()
        let ws = boardWorkspaceLabel ?? selectedProject?.workspace ?? "CCC"
        return try await client.fetchTaskDetailNewServer(taskId: task.id, workspace: ws)
    }

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
            if boardColumns.isEmpty { boardColumns = [:] }
        } else {
            boardColumns = columns
            boardError = nil
            boardErrorKind = nil
            boardStale = false
            boardLastSuccess = Date()
        }
        updateStackStatus()
    }

    // MARK: - Ops
    func refreshOps() async {
        opsBusy = true
        opsError = nil
        defer { opsBusy = false }
        do {
            try await prepareClient()
            let summary = try await client.fetchOpsSummaryNewServer()
            opsSummary = summary
            opsOverview = summary.overview
            opsRisks = []
            opsRisksCount = 0
            opsRisksHigh = 0
            opsUpstreamDaily = []
            inboxProposals = []
            loadLocalPatrolAlerts()
            recomputeOpsDisplay()
        } catch {
            if let apiErr = error as? APIError, case .http(let code, _) = apiErr, code == 401 {
                serverLoggedIn = false
                serverLoginError = "运维会话已过期，请重新登录"
                opsError = "运维会话已过期，请在「设置 → 新服务端（T19）」重新登录"
                loadLocalPatrolAlerts()
                recomputeOpsDisplay()
                return
            }
            opsError = error.localizedDescription
            loadLocalPatrolAlerts()
            recomputeOpsDisplay()
        }
    }

    func recomputeOpsDisplay() {
        let sev = OpsHealthDisplay.severity(
            summary: opsSummary, localPatrol: localPatrolAlerts
        )
        let n = OpsHealthDisplay.alerts(
            summary: opsSummary, localPatrol: localPatrolAlerts
        ).count
        if opsDisplaySeverity != sev { opsDisplaySeverity = sev }
        if opsDisplayAlertCount != n { opsDisplayAlertCount = n }
    }

    private func loadLocalPatrolAlerts() {
        let alertsDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".ccc/alerts")
        var items: [OpsHealthAlert] = []
        defer { localPatrolAlerts = items }
        guard let contents = try? FileManager.default.contentsOfDirectory(
            at: alertsDir,
            includingPropertiesForKeys: [.contentModificationDateKey],
            options: [.skipsHiddenFiles]
        ) else { return }
        let patrol = contents
            .filter { $0.pathExtension == "md" && $0.lastPathComponent.contains("authority-patrol") }
            .sorted { a, b in
                let da = (try? a.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
                let db = (try? b.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
                return da > db
            }
            .prefix(5)
        for url in patrol {
            guard let data = try? Data(contentsOf: url, options: .mappedIfSafe),
                  let text = String(data: data, encoding: .utf8) else { continue }
            let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty else { continue }
            let title: String = {
                for line in trimmed.components(separatedBy: "\n") {
                    let s = line.trimmingCharacters(in: .whitespaces)
                    if s.hasPrefix("# ") { return String(s.dropFirst(2)).trimmingCharacters(in: .whitespaces) }
                }
                return url.deletingPathExtension().lastPathComponent
            }()
            let detailSource: String = {
                var lines = trimmed.components(separatedBy: "\n")
                if let idx = lines.firstIndex(where: { $0.trimmingCharacters(in: .whitespaces).hasPrefix("# ") }) {
                    lines.remove(at: idx)
                }
                return lines.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
            }()
            let detail = String(detailSource.prefix(200)).trimmingCharacters(in: .whitespacesAndNewlines)
            let payload = String(trimmed.prefix(4000))
            items.append(OpsHealthAlert(
                id: "patrol-\(url.lastPathComponent)",
                title: title,
                detail: detail.isEmpty ? nil : detail,
                source: "authority-patrol",
                severity: "red",
                copy_payload: payload
            ))
        }
    }

    func startOpsSeverityPoll() {
        opsSeverityPollTask?.cancel()
        opsSeverityPollTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            while !Task.isCancelled {
                guard let self else { break }
                await self.pollOpsSeverityLight()
                try? await Task.sleep(nanoseconds: 60_000_000_000)
            }
        }
    }

    private func pollOpsSeverityLight() async {
        do {
            try await prepareClient()
            if let summary = try? await client.fetchOpsSummaryNewServer() {
                opsSummary = summary
                if let ov = summary.overview { opsOverview = ov }
                opsRisks = []
                opsRisksCount = 0
                opsRisksHigh = 0
            }
            loadLocalPatrolAlerts()
            recomputeOpsDisplay()
        } catch {
            loadLocalPatrolAlerts()
            recomputeOpsDisplay()
        }
    }

    // MARK: - Templates
    func loadTemplates() {
        guard let data = UserDefaults.standard.data(forKey: "ccc.taskTemplates"),
              let items = try? JSONDecoder().decode([TaskTemplate].self, from: data)
        else { templates = []; return }
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

    // MARK: - Custom Prompts
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

    // MARK: - Token Tracking
    private func trackTokenUsage(threadId: String, msgId: UUID, content: String) {
        let tokens = content.count / 4
        threadSessionTokens[threadId, default: 0] += tokens
        if selectedThreadId == threadId {
            sessionTokens = threadSessionTokens[threadId] ?? 0
        }
        totalSessionCost += Double(tokens) * 0.000003
        var copy = perMessageTokens
        copy[msgId] = tokens
        perMessageTokens = copy
    }

    private var threadSessionTokens: [String: Int] = [:]

    func sessionTokenCount(for threadId: String) -> Int {
        threadSessionTokens[threadId] ?? (selectedThreadId == threadId ? sessionTokens : 0)
    }

    // MARK: - Project Stats
    @Published var projectStats: [String: ProjectStats] = [:]

    private func refreshProjectStats() async {
        do {
            try await prepareClient()
            let ws = projects.compactMap { $0.workspace }
            guard !ws.isEmpty else { return }
            let resp = try await client.fetchBoardSummariesNewServer(workspaces: ws)
            var stats: [String: ProjectStats] = [:]
            for (projectWS, snapshot) in resp.summaries {
                guard let rawCounts = snapshot.counts else { continue }
                let counts = Self.mapNewServerCounts(rawCounts)
                var s = ProjectStats()
                s.totalEpics = counts["backlog"] ?? 0
                s.activeWorks = (counts["in_progress"] ?? 0) + (counts["planned"] ?? 0)
                s.failedWorks = counts["abnormal"] ?? 0
                s.completedToday = counts["released"] ?? 0
                stats[projectWS] = s
            }
            projectStats = stats
        } catch {}
    }

    static func mapNewServerCounts(_ counts: [String: Int]) -> [String: Int] {
        return [
            "backlog": counts["待分派"] ?? 0,
            "in_progress": counts["执行中"] ?? 0,
            "verified": counts["已回写"] ?? 0,
            "released": counts["已关闭"] ?? 0,
            "abnormal": counts["打回"] ?? 0,
        ]
    }

    // MARK: - Stubs (合约兼容壳)

    /// 兼容旧调用
    var canChat: Bool { serverLoggedIn }

    var projectConvState: [String: String] = [:]
    var projectTaskState: [String: String] = [:]
    var threadUnread: Set<String> = []
    var composerBounce: String?
    var composerBounceThreadId: String?

    func isThreadStreaming(_ threadId: String) -> Bool { false }
    func isThreadUnread(_ threadId: String) -> Bool { threadUnread.contains(threadId) }
    func streamStatus(for threadId: String?) -> String { "" }

    func moveBoardTask(_ task: BoardTask, to: String) async {
        showToast("任务状态由执行体回写流转，壳不直接改（契约 §4/§8）")
    }

    func hideCompletedEpics() async {
        showToast("任务状态由执行体回写流转，壳不直接改（契约 §4/§8）")
    }

    func reopenBoardTask(_ task: BoardTask, to: String = "planned") async {
        showToast("任务状态由执行体回写/文档流转，壳不直接改（契约 §4/§8）")
    }

    func reopenOpsTask(taskId: String, workspace: String, to: String = "planned") async {
        showToast("任务状态由执行体回写/文档流转，壳不直接改（契约 §4/§8）")
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

    func adoptInboxProposal(_ id: String) async {
        showToast("采纳由执行体回写/文档流转，壳不直接改（契约 §4/§8）")
    }

    func runDailyReview(workspace: String) async {
        showToast("日审由执行体回写/文档流转，壳不直接改（契约 §4/§8）")
    }

    func adoptSuggestion(workspace: String, title: String, description: String, tags: [String] = ["ops-auto"]) async {
        showToast("采纳由执行体回写/文档流转，壳不直接改（契约 §4/§8）")
    }

    func createManualEpic(projectId: String, form: ManualEpicForm) async {
        showToast("由执行体回写/文档流转，壳不直接改（契约 §4/§8）")
    }

    func onForegroundResume() {}
    func manualCompact(threadId: String) async {
        showToast("已压缩上下文")
    }
    func toggleProjectExpanded(_ id: String) {
        if expandedProjectIds.contains(id) { expandedProjectIds.remove(id) }
        else { expandedProjectIds.insert(id) }
    }
}