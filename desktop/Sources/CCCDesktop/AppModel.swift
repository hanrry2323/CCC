import AppKit
import Foundation
import SwiftUI

@MainActor
final class AppModel: ObservableObject {
    @AppStorage("ccc.server") var serverURLString: String = "http://192.168.3.116:7777"
    @AppStorage("ccc.user") var authUser: String = "ccc"
    @AppStorage("ccc.pass") var authPass: String = "ccc"
    @AppStorage("ccc.selectedProject") var persistedProjectId: String = ""

    @Published var projects: [DesktopProject] = []
    @Published var threads: [DesktopThread] = []
    @Published var selectedProjectId: String?
    @Published var selectedThreadId: String?
    @Published var messages: [ChatMessage] = []
    @Published var draft: String = ""
    @Published var statusText: String = "未连接"
    @Published var busy = false
    @Published var connected = false
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
    /// 全 App 同时只允许 1 条对话流（Hub/Claude 双流会互相掐死）
    private var activeChatThreadId: String?
    /// 每会话独立对话流 task
    private var chatTasks: [String: Task<Void, Never>] = [:]
    private var streamingThreadIds: Set<String> = []
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

    /// 兼容旧 UI 命名：仅反映「当前会话」是否在生成
    var isStreaming: Bool { currentThreadStreaming }

    init() {
        let fallback = URL(string: "http://192.168.3.116:7777/")!
        client = APIClient(baseURL: fallback, user: "ccc", password: "ccc")
    }

    private func prepareClient() async throws {
        guard let url = APIClient.makeBaseURL(from: serverURLString) else {
            throw APIError.badURL
        }
        await client.update(baseURL: url, user: authUser, password: authPass)
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
        await refreshProjects()
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
        do {
            try await prepareClient()
            let resp = try await client.fetchProjects()
            projects = resp.projects
            connected = true
            showSettingsHint = false
            let preferred = persistedProjectId.isEmpty ? nil : persistedProjectId
            if let preferred, projects.contains(where: { $0.id == preferred }) {
                selectedProjectId = preferred
            } else if selectedProjectId == nil
                || !projects.contains(where: { $0.id == selectedProjectId }) {
                selectedProjectId = resp.default_project
                    ?? resp.projects.first(where: \.isDispatchable)?.id
                    ?? resp.projects.first?.id
            }
            if let pid = selectedProjectId {
                persistedProjectId = pid
                expandedProjectIds.insert(pid)
                await refreshThreads(projectId: pid)
                await bindFlowToCurrentThread()
            }
            statusText = "已连接"
            lastError = nil
        } catch {
            connected = false
            showSettingsHint = true
            lastError = error.localizedDescription
            statusText = "未连接 · \(serverURLString)"
            showToast("连不上 \(serverURLString)：\(error.localizedDescription)")
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
        do {
            try await prepareClient()
            threads = try await client.fetchThreads(projectId: projectId)
        } catch {
            showToast(error.localizedDescription)
        }
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
        do {
            try await prepareClient()
            let resp = try await client.createThread(projectId: pid, title: "方案讨论")
            threadSwitchGeneration &+= 1
            selectedThreadId = resp.thread_id
            messages = []
            threadMessages[resp.thread_id] = []
            applyFlowSnapshot(nil)
            flowEmptyMessage = "在本对话中转任务后，编排会出现在这里"
            threadFlow[resp.thread_id] = FlowThreadSnapshot(
                epicId: nil, epic: nil, works: [], headline: "",
                recentEpics: [], emptyMessage: flowEmptyMessage, fanoutHint: nil
            )
            refreshCurrentThreadStreaming()
            await refreshThreads(projectId: pid)
            destination = .chat
            restartFlowSSE()
        } catch {
            showToast(error.localizedDescription)
        }
    }

    func openThread(_ id: String) async {
        guard selectedProjectId != nil else { return }

        // 1) 落盘当前会话（消息 + 右栏）
        if let old = selectedThreadId, old != id {
            persistCurrentThreadSnapshot(threadId: old)
        }

        // 2) 秒切：先本地缓存，绝不沿用上一会话的 messages/flow
        threadSwitchGeneration &+= 1
        let gen = threadSwitchGeneration
        selectedThreadId = id
        destination = .chat
        messages = threadMessages[id] ?? []
        applyFlowSnapshot(threadFlow[id])  // nil → 清空右栏，防串会话
        refreshCurrentThreadStreaming()
        lastError = nil

        // 3) 后台同步 HTTP（不阻塞切换；generation 防回写错会话）
        let pid = selectedProjectId!
        Task { [weak self] in
            await self?.syncThreadFromServer(projectId: pid, threadId: id, generation: gen)
            await self?.syncFlowFromServer(projectId: pid, threadId: id, generation: gen)
        }
    }

    private func persistCurrentThreadSnapshot(threadId: String) {
        threadMessages[threadId] = messages
        threadFlow[threadId] = FlowThreadSnapshot(
            epicId: currentEpicId,
            epic: flowEpic,
            works: flowWorks,
            headline: flowHeadline,
            recentEpics: recentEpics,
            emptyMessage: flowEmptyMessage,
            fanoutHint: flowFanoutHint
        )
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

    /// 后台拉消息；流式中的会话以本地为准，不覆盖 toolSteps
    private func syncThreadFromServer(projectId: String, threadId: String, generation: UInt64) async {
        // 正在生成：禁止服务器快照冲掉工具轨
        if streamingThreadIds.contains(threadId) { return }
        do {
            try await prepareClient()
            let detail = try await client.fetchThread(projectId: projectId, threadId: threadId)
            guard threadSwitchGeneration == generation, selectedThreadId == threadId else { return }
            var loaded = detail.messages ?? []
            // 保留本地尚未落盘的流式尾巴
            if let cached = threadMessages[threadId],
               let live = cached.last(where: \.isStreaming) {
                if !loaded.contains(where: { $0.role == "assistant" && $0.content == live.content }) {
                    if let u = cached.last(where: { $0.role == "user" }) {
                        loaded.append(u)
                    }
                    loaded.append(live)
                }
            } else if let cached = threadMessages[threadId], !cached.isEmpty {
                // 本地有更完整的 tool 元数据时，合并最后一条助手
                if let localLast = cached.last(where: { $0.role == "assistant" && !$0.toolSteps.isEmpty }),
                   let idx = loaded.lastIndex(where: { $0.role == "assistant" }) {
                    loaded[idx].toolSteps = localLast.toolSteps
                    loaded[idx].filesChanged = localLast.filesChanged
                    loaded[idx].toolsFinished = localLast.toolsFinished
                }
            }
            threadMessages[threadId] = loaded
            if selectedThreadId == threadId {
                messages = loaded
            }
        } catch {
            // 缓存已显示；失败只 toast，不打成断线
            if selectedThreadId == threadId, threadMessages[threadId] == nil {
                showToast(error.localizedDescription)
            }
        }
    }

    private func syncFlowFromServer(projectId: String, threadId: String, generation: UInt64) async {
        do {
            try await prepareClient()
            let epics = try await client.fetchRecentEpics(projectId: projectId, threadId: threadId)
            guard threadSwitchGeneration == generation, selectedThreadId == threadId else { return }
            recentEpics = epics
            if currentEpicId == nil {
                currentEpicId = epics.first?.epic_id
            }
            if currentEpicId == nil {
                flowEmptyMessage = "本对话尚未转任务；聊透后点「转任务」"
                flowEpic = nil
                flowWorks = []
                flowHeadline = ""
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
        do {
            try await prepareClient()
            try await client.renameThread(projectId: pid, threadId: tid, title: title)
            renameThreadId = nil
            await refreshThreads(projectId: pid)
        } catch {
            showToast(error.localizedDescription)
        }
    }

    func deleteThread(_ threadId: String) async {
        guard let pid = selectedProjectId else { return }
        chatTasks[threadId]?.cancel()
        chatTasks[threadId] = nil
        streamingThreadIds.remove(threadId)
        threadMessages[threadId] = nil
        do {
            try await prepareClient()
            try await client.deleteThread(projectId: pid, threadId: threadId)
            if selectedThreadId == threadId {
                selectedThreadId = nil
                messages = []
                currentEpicId = nil
                flowEpic = nil
                flowWorks = []
                recentEpics = []
            }
            refreshCurrentThreadStreaming()
            await refreshThreads(projectId: pid)
            await bindFlowToCurrentThread()
        } catch {
            showToast(error.localizedDescription)
        }
    }

    private func refreshCurrentThreadStreaming() {
        if let tid = selectedThreadId {
            currentThreadStreaming = streamingThreadIds.contains(tid)
            if currentThreadStreaming, connected {
                statusText = "生成中…"
            } else if connected, statusText == "生成中…" || statusText.hasPrefix("本条失败") {
                statusText = "已连接"
            }
        } else {
            currentThreadStreaming = false
        }
    }

    private func persistMessages(for threadId: String, _ msgs: [ChatMessage]) {
        threadMessages[threadId] = msgs
        if selectedThreadId == threadId {
            messages = msgs
        }
    }

    private func mutateThreadMessages(threadId: String, _ body: (inout [ChatMessage]) -> Void) {
        var msgs = threadMessages[threadId] ?? (selectedThreadId == threadId ? messages : [])
        body(&msgs)
        persistMessages(for: threadId, msgs)
    }

    /// 同会话 stop-and-send；全 App 同时仅 1 条对话流（双流会打挂 Hub）
    func sendUserMessage(_ text: String, stopAndSend: Bool = true) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        Task { await self.sendUserMessageAndWait(trimmed, stopAndSend: stopAndSend) }
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
        if selectedProject?.isOrch == true {
            showToast("编排仓不可聊业务，请选 ccc-demo 等业务项目")
            composerBounce = trimmed
            return false
        }
        var tid = selectedThreadId
        if tid == nil {
            do {
                try await prepareClient()
                let t = try await client.createThread(projectId: pid, title: String(trimmed.prefix(40)))
                tid = t.thread_id
                selectedThreadId = tid
                threadMessages[t.thread_id] = messages
                await refreshThreads(projectId: pid)
            } catch {
                showToast(error.localizedDescription)
                composerBounce = trimmed
                return false
            }
        }
        guard let threadId = tid else { return false }

        if streamingThreadIds.contains(threadId) {
            if stopAndSend {
                let previous = chatTasks[threadId]
                cancelChat(threadId: threadId, silent: true)
                // 等旧 SSE 真正释放，避免 streamSession 双占槽位
                await previous?.value
            } else {
                showToast("正在生成，请先点停止")
                composerBounce = trimmed
                return false
            }
        }

        if let other = activeChatThreadId, other != threadId, streamingThreadIds.contains(other) {
            showToast("另一会话正在生成。请等它结束，或切过去点停止后再发。")
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
        streamingThreadIds.insert(threadId)
        activeChatThreadId = threadId
        flowSnapshotPaused = true
        defer {
            streamingThreadIds.remove(threadId)
            if activeChatThreadId == threadId { activeChatThreadId = nil }
            chatTasks[threadId] = nil
            flowSnapshotPaused = false
            refreshCurrentThreadStreaming()
            // 聊完追赶右栏 snapshot（SSE 仍在；暂停期间事件未刷）
            Task { await self.refreshFlow() }
        }
        refreshCurrentThreadStreaming()

        let userMsg = ChatMessage(role: "user", content: text)
        let assistantId = UUID()
        mutateThreadMessages(threadId: threadId) { msgs in
            msgs.append(userMsg)
            msgs.append(ChatMessage(id: assistantId, role: "assistant", content: "", isStreaming: true))
        }

        do {
            try await prepareClient()
            let outbound = (threadMessages[threadId] ?? []).filter { $0.id != assistantId }

            try await client.streamChat(
                projectId: projectId,
                sessionId: threadId,
                messages: outbound
            ) { [weak self] event in
                guard let self else { return }
                self.applyChatEvent(threadId: threadId, assistantId: assistantId, event: event)
            }

            var failedEmpty = false
            mutateThreadMessages(threadId: threadId) { msgs in
                guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
                msgs[idx].isStreaming = false
                msgs[idx].toolsFinished = true
                if msgs[idx].content.isEmpty && msgs[idx].toolSteps.isEmpty {
                    msgs.remove(at: idx)
                    failedEmpty = true
                }
            }
            if failedEmpty {
                throw APIError.decode("模型无有效回复")
            }
            if connected, selectedThreadId == threadId {
                statusText = "已连接"
            }
            try? await prepareClient()
            if let list = try? await client.fetchThreads(projectId: projectId) {
                threads = list
            }
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
                    statusText = "本条失败"
                }
                showToast("对话失败：\(error.localizedDescription)")
                if selectedThreadId == threadId {
                    composerBounce = text
                }
            }
        }
    }

    private func applyChatEvent(threadId: String, assistantId: UUID, event: ChatStreamEvent) {
        mutateThreadMessages(threadId: threadId) { msgs in
            guard let idx = msgs.firstIndex(where: { $0.id == assistantId }) else { return }
            switch event {
            case .delta(let chunk):
                msgs[idx].content += chunk
                if msgs[idx].content.trimmingCharacters(in: .whitespacesAndNewlines).count > 40,
                   !msgs[idx].toolSteps.isEmpty {
                    msgs[idx].toolsFinished = true
                }
            case .toolUse(let name, let input):
                let anyInput: [String: Any] = input
                let step = ToolStep(
                    name: name,
                    label: ToolProgressHelper.humanLabel(name: name, input: anyInput),
                    icon: ToolProgressHelper.icon(for: name),
                    status: .running
                )
                msgs[idx].toolSteps.append(step)
                if ToolProgressHelper.isWrite(name) {
                    msgs[idx].filesChanged += 1
                }
            case .toolResult(let ok):
                if let last = msgs[idx].toolSteps.indices.last {
                    msgs[idx].toolSteps[last].status = ok ? .done : .error
                }
            case .cost:
                break
            case .done:
                if !msgs[idx].toolSteps.isEmpty {
                    msgs[idx].toolsFinished = true
                }
            }
        }
    }

    func cancelChat(threadId: String? = nil, silent: Bool = false) {
        let tid = threadId ?? selectedThreadId
        guard let tid else { return }
        chatTasks[tid]?.cancel()
        chatTasks[tid] = nil
        streamingThreadIds.remove(tid)
        if activeChatThreadId == tid { activeChatThreadId = nil }
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
        refreshCurrentThreadStreaming()
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

    func openTransferSheet() {
        transferError = nil
        prefillTransferFromChat()
        showTransferSheet = true
    }

    /// 从对话启发式预填门禁字段
    func prefillTransferFromChat() {
        let users = messages.filter { $0.role == "user" }.map(\.content)
        let assistants = messages.filter { $0.role == "assistant" && !$0.isStreaming }.map(\.content)
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
    }

    func submitTransfer() async {
        guard let pid = selectedProjectId else {
            transferError = "缺少项目"
            return
        }
        if let p = selectedProject, !p.isDispatchable {
            transferError = "当前项目不可下达"
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
            return
        }
        if transferFeasibility == "blocked",
           transferFeasibilityReason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            transferError = "可行性为 blocked 时必须填写原因"
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
            resetTransferForm()
            statusText = "已转任务"
            var toastMsg = "已创建待办 \(resp.epic_id ?? "")"
            if resp.engine_wake?.ok == true {
                toastMsg += " · Engine 已唤醒"
            }
            showToast(toastMsg)
            await bindFlowToCurrentThread(preferEpicId: resp.epic_id)
            startFanoutWatchdog(epicId: resp.epic_id)
        } catch {
            transferError = error.localizedDescription
        }
    }

    /// 转任务后若 30s 仍无 works，右栏明示原因
    func startFanoutWatchdog(epicId: String?) {
        fanoutWatchTask?.cancel()
        flowFanoutHint = nil
        guard let epicId, !epicId.isEmpty else { return }
        fanoutWatchTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 30_000_000_000)
            guard !Task.isCancelled, let self else { return }
            await MainActor.run {
                guard self.currentEpicId == epicId else { return }
                if self.flowWorks.isEmpty {
                    let stage = self.flowHeadline.isEmpty
                        ? (self.flowEpic?.user_stage ?? self.flowEpic?.headline ?? "待拆解")
                        : self.flowHeadline
                    self.flowFanoutHint =
                        "扇出未跟上（\(stage)，works=0）。可能 product 失败或 Engine 忙碌。可开运维查看日志。"
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
