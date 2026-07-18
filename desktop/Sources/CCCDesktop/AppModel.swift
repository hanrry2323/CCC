import Foundation
import SwiftUI

@MainActor
final class AppModel: ObservableObject {
    @AppStorage("ccc.server") var serverURLString: String = "http://192.168.3.116:7777"
    @AppStorage("ccc.user") var authUser: String = "ccc"
    @AppStorage("ccc.pass") var authPass: String = "ccc"

    @Published var projects: [DesktopProject] = []
    @Published var threads: [DesktopThread] = []
    @Published var selectedProjectId: String?
    @Published var selectedThreadId: String?
    @Published var messages: [ChatMessage] = []
    @Published var draft: String = ""
    @Published var statusText: String = ""
    @Published var busy = false

    // Transfer form (gate fields)
    @Published var transferTitle = ""
    @Published var transferGoal = ""
    @Published var transferAcceptance = ""
    @Published var transferPipeline = "dev"
    @Published var transferExecutor = "opencode"
    @Published var showTransferSheet = false

    // Flow rail
    @Published var flowEmptyMessage = "定稿并转任务后显示执行流程"
    @Published var flowWorks: [FlowWork] = []
    @Published var currentEpicId: String?
    @Published var lastError: String?

    private var pollTask: Task<Void, Never>?
    private var client: APIClient {
        let raw = serverURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        let base = URL(string: raw.hasSuffix("/") ? raw : raw + "/")!
        return APIClient(baseURL: base, user: authUser, password: authPass)
    }

    func bootstrap() async {
        await refreshProjects()
        startFlowPoll()
    }

    func refreshProjects() async {
        busy = true
        defer { busy = false }
        do {
            let resp = try await client.fetchProjects()
            projects = resp.projects
            if selectedProjectId == nil {
                selectedProjectId = resp.default_project ?? resp.projects.first(where: \.isDispatchable)?.id
            }
            if let pid = selectedProjectId {
                await refreshThreads(projectId: pid)
            }
            statusText = "已连接 \(serverURLString)"
            lastError = nil
        } catch {
            lastError = error.localizedDescription
            statusText = "连接失败"
        }
    }

    func selectProject(_ id: String) async {
        selectedProjectId = id
        selectedThreadId = nil
        messages = []
        await refreshThreads(projectId: id)
        await refreshFlow()
    }

    func refreshThreads(projectId: String) async {
        do {
            threads = try await client.fetchThreads(projectId: projectId)
        } catch {
            lastError = error.localizedDescription
        }
    }

    func newThread() async {
        guard let pid = selectedProjectId else { return }
        busy = true
        defer { busy = false }
        do {
            let resp = try await client.createThread(projectId: pid, title: "方案讨论")
            selectedThreadId = resp.thread_id
            messages = []
            await refreshThreads(projectId: pid)
        } catch {
            lastError = error.localizedDescription
        }
    }

    func openThread(_ id: String) async {
        guard let pid = selectedProjectId else { return }
        selectedThreadId = id
        do {
            let detail = try await client.fetchThread(projectId: pid, threadId: id)
            messages = detail.messages ?? []
        } catch {
            lastError = error.localizedDescription
        }
    }

    func sendMessage() async {
        guard let pid = selectedProjectId else { return }
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        busy = true
        defer { busy = false }
        do {
            if selectedThreadId == nil {
                let t = try await client.createThread(projectId: pid, title: String(text.prefix(40)))
                selectedThreadId = t.thread_id
            }
            guard let tid = selectedThreadId else { return }
            messages.append(ChatMessage(role: "user", content: text))
            draft = ""
            let resp = try await client.chat(projectId: pid, sessionId: tid, messages: messages)
            if let reply = resp.reply, !reply.isEmpty {
                messages.append(ChatMessage(role: "assistant", content: reply))
            } else if let msgs = resp.messages {
                messages = msgs
            }
            await refreshThreads(projectId: pid)
        } catch {
            lastError = error.localizedDescription
        }
    }

    func submitTransfer() async {
        guard let pid = selectedProjectId else { return }
        busy = true
        defer { busy = false }
        let accLines = transferAcceptance
            .split(separator: "\n")
            .map { String($0).trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        let req = TransferRequest(
            project_id: pid,
            thread_id: selectedThreadId,
            title: transferTitle,
            goal: transferGoal,
            acceptance: accLines.isEmpty ? [transferAcceptance] : accLines,
            pipeline: transferPipeline,
            feasibility: "ok",
            feasibility_reason: nil,
            executor_intent: transferExecutor,
            skills_hint: [],
            plan_md: """
            # Plan: \(transferTitle)

            ## 目标
            \(transferGoal)

            ## 验收
            \(accLines.map { "- \($0)" }.joined(separator: "\n"))
            """,
            complexity: "medium"
        )
        do {
            let resp = try await client.transfer(req)
            currentEpicId = resp.epic_id
            showTransferSheet = false
            statusText = "已转任务 \(resp.epic_id ?? "")"
            await refreshFlow()
        } catch {
            lastError = error.localizedDescription
        }
    }

    func refreshFlow() async {
        guard let pid = selectedProjectId else { return }
        do {
            let snap = try await client.flowSnapshot(projectId: pid, epicId: currentEpicId)
            if snap.empty == true {
                flowWorks = []
                flowEmptyMessage = snap.message ?? "定稿并转任务后显示执行流程"
                currentEpicId = nil
            } else {
                flowWorks = snap.works ?? []
                currentEpicId = snap.epic_id
                flowEmptyMessage = ""
            }
        } catch {
            // 静默：轮询失败不刷屏
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
}
