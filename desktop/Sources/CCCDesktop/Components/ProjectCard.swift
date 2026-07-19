import SwiftUI

/// 侧栏项目卡片：项目名 + 双状态灯（后台任务 / 对话）
struct ProjectCard: View {
    @EnvironmentObject var model: AppModel
    let project: DesktopProject
    let isSelected: Bool

    var body: some View {
        Button {
            Task { await model.selectProject(project.id) }
        } label: {
            HStack(spacing: 10) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(project.name)
                        .font(.system(size: 13, weight: isSelected ? .semibold : .medium))
                        .foregroundStyle(isSelected ? CCCTheme.ink : CCCTheme.secondary)
                        .lineLimit(1)
                    Text(taskStatusLabel)
                        .font(.system(size: 10.5))
                        .foregroundStyle(CCCTheme.faint)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
                VStack(spacing: 4) {
                    taskLight
                    convLight
                }
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
            Button("重置对话") { Task { await model.resetConversation() } }
        }
    }

    // MARK: - 后台任务灯

    private var taskState: String {
        model.projectTaskState[project.id] ?? "idle"
    }

    private var taskStatusLabel: String {
        switch taskState {
        case "pending": return "待拆解"
        case "in_progress": return "执行中"
        case "testing": return "验收中"
        case "done": return "已完成"
        case "failed": return "异常"
        default: return project.role == "orch" ? "编排仓" : "空闲"
        }
    }

    @ViewBuilder
    private var taskLight: some View {
        switch taskState {
        case "pending":
            Circle().fill(CCCTheme.nodePending).frame(width: 8, height: 8)
        case "in_progress":
            TimelineView(.periodic(from: .now, by: 0.8)) { _ in
                Circle()
                    .fill(CCCTheme.nodeRunning)
                    .frame(width: 8, height: 8)
                    .opacity(0.4)
                    .overlay(
                        Circle().fill(CCCTheme.nodeRunning).frame(width: 8, height: 8)
                    )
            }
        case "testing":
            Circle().fill(Color.yellow.opacity(0.85)).frame(width: 8, height: 8)
        case "done":
            Circle().fill(CCCTheme.nodeDone.opacity(0.7)).frame(width: 8, height: 8)
        case "failed":
            Circle().fill(CCCTheme.nodeFail).frame(width: 8, height: 8)
        default:
            Circle().fill(CCCTheme.faint.opacity(0.4)).frame(width: 8, height: 8)
        }
    }

    // MARK: - 对话灯

    private var convState: String {
        model.projectConvState[project.id] ?? "idle"
    }

    @ViewBuilder
    private var convLight: some View {
        switch convState {
        case "text":
            TimelineView(.periodic(from: .now, by: 1.4)) { timeline in
                let phase = (timeline.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: 1.4)) / 1.4
                Circle()
                    .fill(Color.blue)
                    .frame(width: 7, height: 7)
                    .opacity(0.35 + 0.5 * (0.5 + 0.5 * sin(phase * 2 * .pi)))
            }
        case "tool":
            TimelineView(.periodic(from: .now, by: 1.0)) { timeline in
                let phase = (timeline.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: 1.0)) / 1.0
                Circle()
                    .fill(Color.purple)
                    .frame(width: 7, height: 7)
                    .opacity(0.35 + 0.5 * (0.5 + 0.5 * sin(phase * 2 * .pi)))
            }
        default:
            Color.clear.frame(width: 7, height: 7)
        }
    }
}
