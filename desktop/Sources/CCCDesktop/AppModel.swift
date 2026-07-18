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
    @Published var statusText: String = ""
    @Published var busy = false
    @Published var destination: SidebarDestination = .chat

    @Published var transferTitle = ""
    @Published var transferGoal = ""
    @Published var transferAcceptance = ""
    @Published var transferPipeline = "dev"
    @Published var transferExecutor = "opencode"
    @Published var showTransferSheet = false
    @Published var transferError: String?

    @Published var flowEmptyMessage = "定稿并转任务后，这里展开活动编排图"
    @Published var flowWorks: [FlowWork] = []
    @Published var flowEpic: FlowEpic?
    @Published var currentEpicId: String?
    @Published var lastError: String?
    @Published var expandedProjectIds: Set<String> = []

    private var pollTask: Task<Void, Never>?
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
        startFlowPoll()
    }

    func reconnect() async {
        await refreshProjects()
    }

    func refreshProjects() async {
        busy = true
        defer { busy = false }
        do {
            try await prepareClient()
            let resp = try await client.fetchProjects()
            projects = resp.projects
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
            }
            statusText = "已连接 \(serverURLString)"
            lastError = nil
        } catch {
            lastError = error.localizedDescription
            statusText = "连接失败"
        }
    }

    func selectProject(_ id: String) async {
        if id == selectedProjectId {
            expandedProjectIds.insert(id)
            return
        }
        selectedProjectId = id
        persistedProjectId = id
        expandedProjectIds.insert(id)
        selectedThreadId = nil
        messages = []
        currentEpicId = nil
        flowEpic = nil
        flowWorks = []
        await refreshThreads(projectId: id)
        await refreshFlow()
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
            lastError = error.localizedDescription
        }
    }

    func newThread() async {
        guard let pid = selectedProjectId else {
            lastError = "请先选择项目"
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
            lastError = error.localizedDescription
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
            lastError = error.localizedDescription
        }
    }

    func sendMessage() async {
        guard let pid = selectedProjectId else {
            lastError = "请先选择项目"
            return
        }
        if let p = selectedProject, p.isOrch {
            lastError = "编排仓不可聊业务；请选业务项目（如 ccc-demo）"
            return
        }
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        busy = true
        defer { busy = false }
        let userMsg = ChatMessage(role: "user", content: text)
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
            let outbound = messages
            let resp = try await client.chat(
                projectId: pid,
                sessionId: tid,
                messages: outbound
            )
            if let reply = resp.reply, !reply.isEmpty {
                messages.append(ChatMessage(role: "assistant", content: reply))
            } else if let msgs = resp.messages, !msgs.isEmpty {
                messages = msgs
            } else {
                throw APIError.decode("模型无有效回复")
            }
            lastError = nil
            await refreshThreads(projectId: pid)
        } catch {
            if messages.last?.id == userMsg.id {
                messages.removeLast()
                if draft.isEmpty { draft = text }
            }
            lastError = error.localizedDescription
        }
    }

    func openTransferSheet() {
        transferError = nil
        if transferTitle.isEmpty, let last = messages.last(where: { $0.role == "user" }) {
            transferTitle = String(last.content.prefix(40))
        }
        showTransferSheet = true
    }

    func submitTransfer() async {
        guard let pid = selectedProjectId else {
            transferError = "缺少项目"
            return
        }
        if let p = selectedProject, !p.isDispatchable {
            transferError = "当前项目不可下达（orch / engine=false）"
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
            """,
            complexity: "medium"
        )
        do {
            try await prepareClient()
            let resp = try await client.transfer(req)
            currentEpicId = resp.epic_id
            showTransferSheet = false
            transferError = nil
            statusText = "已转任务 \(resp.epic_id ?? "")"
            lastError = nil
            await refreshFlow()
        } catch {
            transferError = error.localizedDescription
        }
    }

    func refreshFlow() async {
        guard let pid = selectedProjectId else { return }
        do {
            try await prepareClient()
            let snap = try await client.flowSnapshot(projectId: pid, epicId: currentEpicId)
            if snap.empty == true {
                if currentEpicId == nil {
                    flowWorks = []
                    flowEpic = nil
                    flowEmptyMessage = snap.message ?? "定稿并转任务后，这里展开活动编排图"
                }
            } else {
                flowWorks = snap.works ?? []
                currentEpicId = snap.epic_id ?? currentEpicId
                if let epic = snap.epic {
                    flowEpic = epic
                } else if let eid = snap.epic_id {
                    flowEpic = FlowEpic(
                        id: eid,
                        title: eid,
                        split_status: nil,
                        column: "backlog"
                    )
                }
                flowEmptyMessage = ""
            }
        } catch {
            if flowWorks.isEmpty && currentEpicId == nil {
                // keep quiet during poll
            }
        }
    }

    func startFlowPoll() {
        pollTask?.cancel()
        pollTask = Task { [weak self] in
            while !Task.isCancelled {
                await self?.refreshFlow()
                try? await Task.sleep(nanoseconds: 2_500_000_000)
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
