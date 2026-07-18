import SwiftUI

/// 原生看板：列只读 + 当前 epic 高亮 + 刷新
struct BoardView: View {
    @EnvironmentObject var model: AppModel

    private let columnOrder = [
        "backlog", "planned", "in_progress", "testing", "verified", "released", "abnormal",
    ]

    private let columnTitles: [String: String] = [
        "backlog": "待办",
        "planned": "已规划",
        "in_progress": "进行中",
        "testing": "验收中",
        "verified": "已验证",
        "released": "已发布",
        "abnormal": "异常",
    ]

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("看板")
                    .font(.system(size: 16, weight: .semibold))
                if let ws = model.boardWorkspaceLabel {
                    Text(ws)
                        .font(.system(size: 12))
                        .foregroundStyle(CCCTheme.faint)
                }
                Spacer()
                if model.boardBusy {
                    ProgressView().controlSize(.mini)
                }
                Button("刷新") {
                    Task { await model.refreshBoard() }
                }
                .buttonStyle(.plain)
                .foregroundStyle(CCCTheme.accent)
                .font(.system(size: 12, weight: .medium))
                Button("回对话") {
                    model.selectDestination(.chat)
                }
                .buttonStyle(.plain)
                .foregroundStyle(CCCTheme.secondary)
                .font(.system(size: 12))
            }
            .padding(.horizontal, 20)
            .padding(.top, 12)
            .padding(.bottom, 10)

            if let err = model.boardError {
                Text(err)
                    .font(.system(size: 12))
                    .foregroundStyle(CCCTheme.nodeFail)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 8)
            }

            ScrollView(.horizontal, showsIndicators: true) {
                HStack(alignment: .top, spacing: 10) {
                    ForEach(visibleColumns, id: \.self) { col in
                        columnPane(col)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 20)
            }
        }
        .background(CCCTheme.chatBg)
        .task { await model.refreshBoard() }
    }

    private var visibleColumns: [String] {
        let keys = Set(model.boardColumns.keys)
        let ordered = columnOrder.filter { keys.contains($0) }
        let extra = keys.subtracting(columnOrder).sorted()
        return ordered + extra
    }

    private func columnPane(_ col: String) -> some View {
        let tasks = model.boardColumns[col] ?? []
        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(columnTitles[col] ?? col)
                    .font(.system(size: 12, weight: .semibold))
                Spacer()
                Text("\(tasks.count)")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(CCCTheme.faint)
            }
            .padding(.horizontal, 4)

            ScrollView(showsIndicators: false) {
                LazyVStack(spacing: 6) {
                    if tasks.isEmpty {
                        Text("空")
                            .font(CCCTheme.caption)
                            .foregroundStyle(CCCTheme.faint)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(8)
                    }
                    ForEach(tasks) { task in
                        boardCard(task)
                    }
                }
            }
            .frame(width: 200, height: 520)
            .padding(8)
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(CCCTheme.surface)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .stroke(CCCTheme.border, lineWidth: 1)
            )
        }
    }

    private func boardCard(_ task: BoardTask) -> some View {
        let highlight = model.currentEpicId == task.id
            || (model.flowEpic?.id == task.id)
        return VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 4) {
                if task.isEpic {
                    Text("EPIC")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(CCCTheme.accent)
                }
                Spacer(minLength: 0)
            }
            Text(task.displayTitle)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(CCCTheme.ink)
                .lineLimit(3)
            if let note = task.note, !note.isEmpty {
                Text(note)
                    .font(.system(size: 10))
                    .foregroundStyle(CCCTheme.faint)
                    .lineLimit(2)
            }
            if let split = task.split_status, !split.isEmpty {
                Text(split)
                    .font(.system(size: 10))
                    .foregroundStyle(CCCTheme.secondary)
            }
        }
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(highlight ? CCCTheme.accent.opacity(0.12) : CCCTheme.chatBg)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(highlight ? CCCTheme.accent.opacity(0.55) : Color.clear, lineWidth: 1.5)
        )
    }
}
