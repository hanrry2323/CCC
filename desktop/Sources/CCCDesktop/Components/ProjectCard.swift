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

    private var projectDisplayName: String {
        if project.id == "ccc" { return "CCC 平台" }
        let n = project.name.trimmingCharacters(in: .whitespacesAndNewlines)
        return n.isEmpty ? project.id : n
    }

    var body: some View {
        HStack(alignment: .center, spacing: 8) {
            Button(action: openProject) {
                HStack(alignment: .center, spacing: 10) {
                    Image(systemName: isSelected ? "folder.fill" : "folder")
                        .font(.system(size: 14, weight: .regular))
                        .foregroundStyle(isSelected ? CCCTheme.accent : CCCTheme.faint.opacity(0.85))
                        .frame(width: 18)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(projectDisplayName)
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

            LocatorCopyButton(
                text: CardLocator.line(project: project.id, kind: "project", id: project.id, title: project.name)
            )
            trailingStatus
                .frame(minWidth: 12, alignment: .trailing)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(isSelected ? CCCTheme.selected.opacity(0.55) : (hovering ? CCCTheme.hover : Color.clear))
        )
        .powHoverSpring()
        .powSpringClick()
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
            await model.openProjectConversation(project.id, preferredThreadId: keepTid)
            // preferred 已由 selectProject 钉死；仅当本窗尚无会话时跟模型
            guard keepTid == nil else {
                if window.threadId != keepTid {
                    var txn = Transaction()
                    txn.disablesAnimations = true
                    withTransaction(txn) { window.threadId = keepTid }
                }
                model.clearThreadUnread(keepTid!)
                return
            }
            guard let tid = model.selectedThreadId,
                  LocalSessionStore.projectId(fromThreadId: tid) == project.id
            else { return }
            var txn = Transaction()
            txn.disablesAnimations = true
            withTransaction(txn) {
                window.threadId = tid
            }
            model.clearThreadUnread(tid)
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
        .idle
    }

    private var statusLine: String {
        ""
    }

    private var statusLineColor: Color {
        CCCTheme.faint
    }
}
