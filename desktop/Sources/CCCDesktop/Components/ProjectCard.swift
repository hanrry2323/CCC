import SwiftUI

/// 侧栏项目卡片。
///
/// 尾部只保留**一个**主状态（优先级）：
/// 1. 对话生成中 → 动态指示
/// 2. 未读 → 蓝点
/// 3. 编排在跑 / 失败 → gear
/// 4. 空闲 → 无图标
struct ProjectCard: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState
    let project: DesktopProject
    let isSelected: Bool

    var body: some View {
        Button {
            window.projectId = project.id
            window.destination = .chat
            let threads = ConversationStore.listThreads(projectId: project.id)
            window.bindProject(project.id, availableThreads: threads)
            if let tid = window.threadId {
                model.ensureThreadHydrated(threadId: tid)
                model.clearThreadUnread(tid)
            } else {
                model.ensureThreadHydrated(projectId: project.id)
            }
            Task {
                await model.openProjectConversation(project.id)
                if let tid = model.selectedThreadId,
                   LocalSessionStore.projectId(fromThreadId: tid) == project.id {
                    window.threadId = tid
                    model.clearThreadUnread(tid)
                }
            }
        } label: {
            HStack(alignment: .center, spacing: 10) {
                Image(systemName: isSelected ? "folder.fill" : "folder")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(isSelected ? CCCTheme.accent : CCCTheme.faint)
                    .frame(width: 18)

                VStack(alignment: .leading, spacing: 3) {
                    Text(project.name)
                        .font(.system(size: 14, weight: isSelected ? .semibold : .medium))
                        .foregroundStyle(isSelected ? CCCTheme.ink : CCCTheme.secondary)
                        .lineLimit(1)
                    if !statusLine.isEmpty {
                        Text(statusLine)
                            .font(.system(size: 11.5))
                            .foregroundStyle(statusLineColor)
                            .lineLimit(1)
                    }
                }
                Spacer(minLength: 0)
                trailingStatus
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(isSelected ? CCCTheme.selected : Color.clear)
            )
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .contextMenu {
            Button("重置对话") {
                Task { await model.resetConversation(projectId: project.id) }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(project.name)，\(statusLine.isEmpty ? "空闲" : statusLine)")
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
            EmptyView()
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
