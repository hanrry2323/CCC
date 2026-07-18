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
    @Published var showTransferSheet = false
    @Published var transferError: String?

    @Published var flowEmptyMessage = "聊透后转任务，编排将在此展开"
    @Published var flowWorks: [FlowWork] = []
    @Published var flowEpic: FlowEpic?
    @Published var flowHeadline: String = ""
    @Published var currentEpicId: String?
    @Published var lastError: String?
    @Published var expandedProjectIds: Set<String> = []

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
        }
        await refreshThreads(projectId: id)
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

        if transferTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            transferTitle = String(lastUser.replacingOccurrences(of: "\n", with: " ").prefix(40))
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
                transferAcceptance = a
            } else if !lastUser.isEmpty {
                transferAcceptance = "按对话约定完成，并可复查结果"
            }
        }
        if transferPipeline.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            transferPipeline = "dev"
        }
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
                    if !cleaned.isEmpty { return String(cleaned.prefix(400)) }
                }
            }
        }
        return nil
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
        // 附带对话摘要进 plan
        let chatDigest = messages
            .suffix(8)
            .map { "\($0.role): \(String($0.content.prefix(200)))" }
            .joined(separator: "\n")
        busy = true
        defer { busy = false }
        let req = TransferRequest(
            project_id: pid,
            thread_id: selectedThreadId,
            title: title,
            goal: goal,
            acceptance: accLines,
            pipeline: pipeline,
            feasibility: "ok",
            feasibility_reason: nil,
            executor_intent: transferExecutor,
            skills_hint: [],
            plan_md: """
            # Plan: \(title)

            ## 目标
            \(goal)

            ## 验收
            \(accLines.map { "- \($0)" }.joined(separator: "\n"))

            ## 对话摘要
            \(chatDigest)
            """,
            complexity: "medium"
        )
        do {
            try await prepareClient()
            let resp = try await client.transfer(req)
            currentEpicId = resp.epic_id
            showTransferSheet = false
            transferError = nil
            statusText = "已转任务"
            showToast("已创建待办 \(resp.epic_id ?? "")")
            await refreshFlow()
            restartFlowSSE()
        } catch {
            transferError = error.localizedDescription
        }
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
                    // 断线后短暂等待再连；期间用 snapshot 兜底
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
