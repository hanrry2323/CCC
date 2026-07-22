import SwiftUI

/// 侧栏项目卡片。
///
/// 尾部：新建会话「+」在状态图标左侧。
/// 主状态（优先级）：对话生成中 → 未读 → 编排异常/在跑 → 空闲。
struct ProjectCard: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState
    let project: DesktopProject
    let isSelected: Bool

    @State private var hovering = false

    var body: some View {
        HStack(alignment: .center, spacing: 8) {
            Button(action: openProject) {
                HStack(alignment: .center, spacing: 10) {
                    Image(systemName: isSelected ? "folder.fill" : "folder")
                        .font(.system(size: 14, weight: .regular))
                        .foregroundStyle(isSelected ? CCCTheme.accent : CCCTheme.faint.opacity(0.85))
                        .frame(width: 18)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(project.name)
                            .font(.system(size: 13.5, weight: .regular))
                            .foregroundStyle(isSelected ? CCCTheme.ink : CCCTheme.secondary)
                            .lineLimit(1)
                        if !statusLine.isEmpty {
                            Text(statusLine)
                                .font(.system(size: 11, weight: .light))
                                .foregroundStyle(statusLineColor)
                                .lineLimit(1)
                        }
                    }
                    Spacer(minLength: 4)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            Button {
                Task {
                    var txn = Transaction()
                    txn.disablesAnimations = true
                    withTransaction(txn) {
                        window.destination = .chat
                        window.projectId = project.id
                    }
                    let tid = await model.createNewThread(projectId: project.id)
                    withTransaction(txn) {
                        window.projectId = project.id
                        window.threadId = tid
                    }
                }
            } label: {
                Image(systemName: "plus")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(hovering || isSelected ? CCCTheme.secondary : CCCTheme.faint)
                    .frame(width: 20, height: 20)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .help("新建会话")
            .accessibilityLabel("新建会话")

            trailingStatus
                .frame(minWidth: 12, alignment: .trailing)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(isSelected ? CCCTheme.selected.opacity(0.55) : (hovering ? CCCTheme.hover : Color.clear))
        )
        .onHover { hovering = $0 }
        .contextMenu {
            Button("重置对话") {
                Task { await model.resetConversation(projectId: project.id) }
            }
            Button("新建会话") {
                Task {
                    let tid = await model.createNewThread(projectId: project.id)
                    window.destination = .chat
                    window.projectId = project.id
                    window.threadId = tid
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(project.name)，\(statusLine.isEmpty ? "空闲" : statusLine)")
    }

    private func openProject() {
        let threads = ConversationStore.listThreads(projectId: project.id)
        let keepTid: String? = {
            guard let cur = window.threadId,
                  LocalSessionStore.projectId(fromThreadId: cur) == project.id,
                  threads.contains(where: { $0.thread_id == cur })
            else { return nil }
            return cur
        }()
        var txn = Transaction()
        txn.disablesAnimations = true
        withTransaction(txn) {
            window.destination = .chat
            window.bindProject(project.id, availableThreads: threads)
            // 已在看本项目某会话时禁止被「最近线程」抢走（否则中栏会跳到空/别的 tid）
            if let keepTid {
                window.threadId = keepTid
            }
        }
        if let tid = window.threadId {
            model.ensureThreadHydrated(threadId: tid)
            model.clearThreadUnread(tid)
        } else {
            model.ensureThreadHydrated(projectId: project.id)
        }
        Task {
            await model.openProjectConversation(project.id)
            // #region agent log
            DebugAgentLog.log(
                hypothesisId: "H2",
                location: "ProjectCard.openProject",
                message: "after openProjectConversation",
                data: [
                    "projectId": project.id,
                    "keepTid": keepTid ?? "",
                    "windowThreadId": window.threadId ?? "",
                    "modelSelected": model.selectedThreadId ?? "",
                    "windowMsgCount": model.messagesForThread(window.threadId).count,
                ],
                runId: "post-fix"
            )
            // #endregion
            guard let keepTid else {
                // 本窗尚无会话：跟模型选中的最近线程
                guard let tid = model.selectedThreadId,
                      LocalSessionStore.projectId(fromThreadId: tid) == project.id
                else { return }
                var txn = Transaction()
                txn.disablesAnimations = true
                withTransaction(txn) {
                    window.threadId = tid
                }
                model.clearThreadUnread(tid)
                return
            }
            // 有 keep：模型若漂到别的 tid，拉回本窗会话，禁止空闪
            if model.selectedThreadId != keepTid {
                model.selectedThreadId = keepTid
                await model.openThread(keepTid)
            }
            model.clearThreadUnread(keepTid)
        }
    }

    @ViewBuilder
    private var trailingStatus: some View {
        switch primaryKind {
        case .chatting:
            ProgressView()
                .controlSize(.mini)
                .help("对话生成中")
                .accessibilityLabel("对话生成中")
        case .unread:
            Circle()
                .fill(CCCTheme.unread)
                .frame(width: 9, height: 9)
                .help("有未读回复")
                .accessibilityLabel("有未读")
        case .boardFail:
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 12))
                .foregroundStyle(CCCTheme.nodeFail)
                .help("编排异常")
        case .boardBusy:
            TimelineView(.periodic(from: .now, by: 0.8)) { timeline in
                let on = Int(timeline.date.timeIntervalSinceReferenceDate * 10) % 16 < 10
                Image(systemName: "gearshape.2.fill")
                    .font(.system(size: 12))
                    .foregroundStyle(CCCTheme.nodeRunning)
                    .opacity(on ? 1 : 0.35)
            }
            .help("编排执行中")
        case .idle:
            Color.clear.frame(width: 9, height: 9)
        }
    }

    private enum PrimaryKind {
        case chatting, unread, boardFail, boardBusy, idle
    }

    private var primaryKind: PrimaryKind {
        if isChatting { return .chatting }
        if model.projectHasUnread(project.id) { return .unread }
        switch boardState {
        case .failed: return .boardFail
        case .running, .testing, .pending: return .boardBusy
        default: return .idle
        }
    }

    private var isChatting: Bool {
        switch model.projectConvState[project.id] ?? "idle" {
        case "tool", "text": return true
        default: return false
        }
    }

    private enum BoardState {
        case idle, pending, running, testing, failed
    }

    private var boardState: BoardState {
        switch model.projectTaskState[project.id] ?? "idle" {
        case "pending": return .pending
        case "in_progress": return .running
        case "testing": return .testing
        case "failed": return .failed
        default: return .idle
        }
    }

    private var statusLine: String {
        var parts: [String] = []
        if isChatting {
            if (model.projectConvState[project.id] ?? "") == "tool" {
                parts.append("调工具")
            } else {
                parts.append("对话中")
            }
        } else if model.projectHasUnread(project.id) {
            parts.append("未读")
        }
        switch boardState {
        case .pending: parts.append("待拆解")
        case .running: parts.append("执行中")
        case .testing: parts.append("验收中")
        case .failed: parts.append("异常")
        case .idle: break
        }
        return parts.joined(separator: " · ")
    }

    private var statusLineColor: Color {
        if boardState == .failed { return CCCTheme.nodeFail }
        if isChatting { return CCCTheme.secondary }
        if model.projectHasUnread(project.id) { return CCCTheme.unread }
        return CCCTheme.faint
    }
}
