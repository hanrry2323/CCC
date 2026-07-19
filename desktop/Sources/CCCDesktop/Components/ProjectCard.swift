import SwiftUI

/// 侧栏项目卡片。
///
/// 两路状态**语义独立**（不是装饰）：
/// - **编排灯**（左）：Engine/看板队列 —— 这个项目后台有没有活
/// - **对话灯**（右）：本机 agent 会话 —— 这个项目对话框是否正在生成（切走仍亮）
///
/// 空闲不抢视线：字幕空、灯变淡灰点。
struct ProjectCard: View {
    @EnvironmentObject var model: AppModel
    let project: DesktopProject
    let isSelected: Bool

    var body: some View {
        Button {
            Task { await model.openProjectConversation(project.id) }
        } label: {
            HStack(alignment: .center, spacing: 10) {
                VStack(alignment: .leading, spacing: 3) {
                    Text(project.name)
                        .font(.system(size: 13, weight: isSelected ? .semibold : .medium))
                        .foregroundStyle(isSelected ? CCCTheme.ink : CCCTheme.secondary)
                        .lineLimit(1)
                    if !statusLine.isEmpty {
                        Text(statusLine)
                            .font(.system(size: 10.5))
                            .foregroundStyle(statusLineColor)
                            .lineLimit(1)
                    }
                }
                Spacer(minLength: 0)
                // 左编排 · 右对话 —— 水平排列，避免上下叠两个无意义圆点
                HStack(spacing: 6) {
                    StatusDot(
                        kind: .board,
                        state: boardState,
                        help: "编排：\(boardHelp)"
                    )
                    StatusDot(
                        kind: .chat,
                        state: chatState,
                        help: "对话：\(chatHelp)"
                    )
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 9)
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(isSelected ? CCCTheme.selected : Color.clear)
            )
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .contextMenu {
            Button("重置对话") { Task { await model.resetConversation() } }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(project.name)，编排\(boardHelp)，对话\(chatHelp)")
    }

    // MARK: - 状态源

    /// 编排：board 队列（Engine）
    private var boardState: DotState {
        switch model.projectTaskState[project.id] ?? "idle" {
        case "pending": return .pending
        case "in_progress": return .running
        case "testing": return .testing
        case "failed": return .failed
        default: return .idle
        }
    }

    /// 对话：本机 agent 流式（按项目，切走仍亮）
    private var chatState: DotState {
        switch model.projectConvState[project.id] ?? "idle" {
        case "tool": return .tooling
        case "text": return .talking
        default: return .idle
        }
    }

    /// 一行人话：优先对话（更即时），再拼编排
    private var statusLine: String {
        var parts: [String] = []
        switch chatState {
        case .talking: parts.append("对话中")
        case .tooling: parts.append("调工具")
        default: break
        }
        switch boardState {
        case .pending: parts.append("待拆解")
        case .running: parts.append("执行中")
        case .testing: parts.append("验收中")
        case .failed: parts.append("异常")
        default: break
        }
        return parts.joined(separator: " · ")
    }

    private var statusLineColor: Color {
        if boardState == .failed { return CCCTheme.nodeFail }
        if chatState == .talking || chatState == .tooling { return CCCTheme.secondary }
        return CCCTheme.faint
    }

    private var boardHelp: String {
        switch boardState {
        case .pending: return "待拆解"
        case .running: return "执行中"
        case .testing: return "验收中"
        case .failed: return "异常"
        default: return "空闲"
        }
    }

    private var chatHelp: String {
        switch chatState {
        case .talking: return "生成中"
        case .tooling: return "调工具"
        default: return "空闲"
        }
    }
}

// MARK: - Dot

private enum DotState {
    case idle, pending, running, testing, failed, talking, tooling
}

private enum DotKind { case board, chat }

private struct StatusDot: View {
    let kind: DotKind
    let state: DotState
    let help: String

    var body: some View {
        Group {
            switch state {
            case .idle:
                Circle()
                    .fill(CCCTheme.faint.opacity(0.28))
                    .frame(width: 7, height: 7)
            case .pending:
                Circle()
                    .fill(Color(red: 0.35, green: 0.55, blue: 0.85))
                    .frame(width: 8, height: 8)
            case .running:
                TimelineView(.periodic(from: .now, by: 0.7)) { timeline in
                    let on = Int(timeline.date.timeIntervalSinceReferenceDate * 10) % 14 < 9
                    Circle()
                        .fill(CCCTheme.nodeRunning)
                        .frame(width: 8, height: 8)
                        .opacity(on ? 1 : 0.25)
                }
            case .testing:
                Circle()
                    .fill(Color(red: 0.85, green: 0.65, blue: 0.15))
                    .frame(width: 8, height: 8)
            case .failed:
                Circle()
                    .fill(CCCTheme.nodeFail)
                    .frame(width: 8, height: 8)
            case .talking:
                TimelineView(.periodic(from: .now, by: 1.2)) { timeline in
                    let p = timeline.date.timeIntervalSinceReferenceDate
                        .truncatingRemainder(dividingBy: 1.2) / 1.2
                    Circle()
                        .fill(Color(red: 0.25, green: 0.55, blue: 0.95))
                        .frame(width: 8, height: 8)
                        .opacity(0.4 + 0.6 * (0.5 + 0.5 * sin(p * 2 * .pi)))
                }
            case .tooling:
                TimelineView(.periodic(from: .now, by: 0.9)) { timeline in
                    let p = timeline.date.timeIntervalSinceReferenceDate
                        .truncatingRemainder(dividingBy: 0.9) / 0.9
                    Circle()
                        .fill(Color(red: 0.55, green: 0.35, blue: 0.85))
                        .frame(width: 8, height: 8)
                        .opacity(0.4 + 0.6 * (0.5 + 0.5 * sin(p * 2 * .pi)))
                }
            }
        }
        .help(help)
        .accessibilityLabel(help)
    }
}
