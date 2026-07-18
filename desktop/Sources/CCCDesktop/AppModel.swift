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

    private var flowTask: Task<Void, Never>?
    private var client: APIClient

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
        if let env = ProcessInfo.processInfo.environment["CCC_SERVER"], !env.isEmpty {
            let current = serverURLString.trimmingCharacters(in: .whitespacesAndNewlines)
            if current.isEmpty || current == "http://192.168.3.116:7777" {
                serverURLString = env
            }
        }
        await refreshProjects()
    }

    func reconnect() async {
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
                await refreshEpicList()
                await refreshFlow()
                restartFlowSSE()
            }
            statusText = "已连接"
            lastError = nil
        } catch {
            connected = false
            showSettingsHint = true
            lastError = error.localizedDescription
            statusText = "连接失败"
            showToast(error.localizedDescription)
        }
    }

    func selectProject(_ id: String) async {
        let switching = id != selectedProjectId
        selectedProjectId = id
        persistedProjectId = id
        expandedProjectIds.insert(id)
        if switching {
            selectedThreadId = nil
            messages = []
            currentEpicId = nil
            flowEpic = nil
            flowWorks = []
            flowHeadline = ""
            recentEpics = []
            selectedNodeDetail = nil
        }
        await refreshThreads(projectId: id)
        await refreshEpicList()
        await refreshFlow()
        restartFlowSSE()
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
        busy = true
        defer { busy = false }
        do {
            try await prepareClient()
            let resp = try await client.createThread(projectId: pid, title: "方案讨论")
            selectedThreadId = resp.thread_id
            messages = []
            await refreshThreads(projectId: pid)
            destination = .chat
        } catch {
            showToast(error.localizedDescription)
        }
    }

    func openThread(_ id: String) async {
        guard let pid = selectedProjectId else { return }
        selectedThreadId = id
        destination = .chat
        do {
            try await prepareClient()
            let detail = try await client.fetchThread(projectId: pid, threadId: id)
            messages = detail.messages ?? []
            lastError = nil
        } catch {
            showToast(error.localizedDescription)
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
        do {
            try await prepareClient()
            try await client.deleteThread(projectId: pid, threadId: threadId)
            if selectedThreadId == threadId {
                selectedThreadId = nil
                messages = []
            }
            await refreshThreads(projectId: pid)
        } catch {
            showToast(error.localizedDescription)
        }
    }

    func sendMessage() async {
        guard let pid = selectedProjectId else {
            showToast("请先选择项目")
            return
        }
        if let p = selectedProject, p.isOrch {
            showToast("编排仓不可聊业务，请选 ccc-demo 等业务项目")
            return
        }
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        busy = true
        defer { busy = false }
        let userMsg = ChatMessage(role: "user", content: text)
        let assistantId = UUID()
        do {
            try await prepareClient()
            if selectedThreadId == nil {
                let t = try await client.createThread(
                    projectId: pid,
                    title: String(text.prefix(40))
                )
                selectedThreadId = t.thread_id
            }
            guard let tid = selectedThreadId else { return }
            messages.append(userMsg)
            draft = ""
            messages.append(ChatMessage(id: assistantId, role: "assistant", content: "", isStreaming: true))
            let outbound = messages.filter { $0.id != assistantId }

            try await client.streamChat(
                projectId: pid,
                sessionId: tid,
                messages: outbound
            ) { [weak self] delta in
                Task { @MainActor in
                    guard let self else { return }
                    if let idx = self.messages.firstIndex(where: { $0.id == assistantId }) {
                        self.messages[idx].content += delta
                    }
                }
            }
            if let idx = messages.firstIndex(where: { $0.id == assistantId }) {
                messages[idx].isStreaming = false
                if messages[idx].content.isEmpty {
                    messages.remove(at: idx)
                    throw APIError.decode("模型无有效回复")
                }
            }
            lastError = nil
            await refreshThreads(projectId: pid)
        } catch {
            messages.removeAll { $0.id == assistantId }
            if messages.last?.id == userMsg.id {
                messages.removeLast()
                if draft.isEmpty { draft = text }
            }
            showToast(error.localizedDescription)
        }
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
            await refreshEpicList()
            await refreshFlow()
            restartFlowSSE()
        } catch {
            transferError = error.localizedDescription
        }
    }

    func refreshEpicList() async {
        guard let pid = selectedProjectId else { return }
        do {
            try await prepareClient()
            recentEpics = try await client.fetchRecentEpics(projectId: pid)
        } catch {
            // 非致命
        }
    }

    func selectEpic(_ epicId: String) async {
        currentEpicId = epicId
        selectedNodeDetail = nil
        await refreshFlow()
        restartFlowSSE()
    }

    func refreshFlow() async {
        guard let pid = selectedProjectId else { return }
        do {
            try await prepareClient()
            let snap = try await client.flowSnapshot(projectId: pid, epicId: currentEpicId)
            applySnapshot(snap)
        } catch {
            // SSE 为主；snapshot 失败不刷屏
        }
    }

    private func applySnapshot(_ snap: FlowSnapshot) {
        if snap.empty == true {
            if currentEpicId == nil {
                flowWorks = []
                flowEpic = nil
                flowHeadline = ""
                flowEmptyMessage = snap.message ?? "聊透后转任务，编排将在此展开"
            }
            return
        }
        flowWorks = snap.works ?? []
        currentEpicId = snap.epic_id ?? currentEpicId
        flowEpic = snap.epic
        flowHeadline = snap.headline
            ?? snap.epic?.headline
            ?? (flowWorks.first(where: \.isActive).map { "正在：\($0.title)" } ?? "")
        flowEmptyMessage = ""
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
        flowTask?.cancel()
        guard let pid = selectedProjectId else { return }
        flowTask = Task { [weak self] in
            while !Task.isCancelled {
                do {
                    try await self?.prepareClient()
                    try await self?.client.streamFlowEvents(
                        projectId: pid,
                        epicId: self?.currentEpicId
                    ) { event, _ in
                        if ["fanout", "work_status", "epic_created", "executor"].contains(event) {
                            Task { @MainActor in
                                await self?.refreshFlow()
                            }
                        }
                    }
                } catch {
                    await self?.refreshFlow()
                    try? await Task.sleep(nanoseconds: 3_000_000_000)
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
        switch dest {
        case .chat:
            destination = .chat
        case .hub:
            openHubInBrowser(route: "#/board")
            destination = .chat
        case .ops:
            openHubInBrowser(route: "#/ops")
            destination = .chat
        }
    }
}
