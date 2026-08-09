import SwiftUI

/// 侧栏项目卡片。
///
/// 尾部：新建会话「+」与定位复制按钮。
/// （旧版的状态图标/主状态优先级逻辑已由 ccc038 清理移除，保持卡片显示行为不变。）
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
        .accessibilityLabel("\(project.name)，空闲")
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

}
