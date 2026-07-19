import SwiftUI

/// 原生运维：聚合 summary + 风险 + 工作区 + 日审 + 质量 + 文档债 + 采纳
struct OpsView: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState
    @State private var showAdoptSheet = false
    @State private var adoptTitle = ""
    @State private var adoptDesc = ""
    @State private var adoptWorkspace = "CCC"

    var body: some View {
        VStack(spacing: 0) {
            header
            if let err = model.opsError {
                Text(err)
                    .font(.system(size: 12))
                    .foregroundStyle(CCCTheme.nodeFail)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 8)
            }
            if let adoptErr = model.opsAdoptError {
                Text(adoptErr)
                    .font(.system(size: 11))
                    .foregroundStyle(CCCTheme.nodeFail)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 6)
            }
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    overviewSection
                    risksSection
                    workspacesSection
                    dailyReviewSection
                    qualitySection
                    docsDebtSection
                    downPortsSection
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 28)
            }
        }
        .background(CCCTheme.chatBg)
        .task { await model.refreshOps() }
        .sheet(isPresented: $showAdoptSheet) { adoptSheet }
    }

    private var header: some View {
        HStack {
            Text("运维")
                .font(.system(size: 16, weight: .semibold))
            Spacer()
            if model.opsAdoptBusy { ProgressView().controlSize(.mini) }
            else if model.opsBusy { ProgressView().controlSize(.mini) }
            Menu {
                Button("采纳建议…") { showAdoptSheet = true }
                Button("刷新") { Task { await model.refreshOps() } }
            } label: {
                Image(systemName: "ellipsis.circle")
                    .font(.system(size: 14))
                    .foregroundStyle(CCCTheme.secondary)
            }
            .menuStyle(.borderlessButton)
            Button("回对话") {
                window.destination = .chat
                model.selectDestination(.chat, projectId: window.projectId)
            }
                .buttonStyle(.plain)
                .foregroundStyle(CCCTheme.secondary)
                .font(.system(size: 12))
        }
        .padding(.horizontal, 20)
        .padding(.top, 12)
        .padding(.bottom, 10)
    }

    private var overviewSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("集群概览")
                .font(.system(size: 13, weight: .semibold))
            if let machines = model.opsOverview?.machines, !machines.isEmpty {
                ForEach(machines) { m in
                    HStack(spacing: 10) {
                        Circle()
                            .fill((m.reachable ?? false) ? CCCTheme.nodeDone : CCCTheme.nodeFail)
                            .frame(width: 7, height: 7)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(m.name)
                                .font(.system(size: 13, weight: .medium))
                            Text("\(m.ip) · \(m.role ?? "—")")
                                .font(.system(size: 11))
                                .foregroundStyle(CCCTheme.faint)
                        }
                        Spacer()
                        if let alive = m.alive_ports, let total = m.port_count {
                            Text("\(alive)/\(total)")
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(CCCTheme.secondary)
                        }
                    }
                    .padding(10)
                    .background(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .fill(CCCTheme.surface)
                    )
                }
            } else {
                Text("暂无机器数据")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.faint)
            }
            if let n = model.opsOverview?.alert_count, n > 0 {
                Text("告警 \(n)")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(CCCTheme.nodeFail)
            }
            if let res = model.opsSummary?.resources {
                HStack(spacing: 16) {
                    if let cpu = res.cpu {
                        Label(String(format: "CPU %.0f%%", cpu * 100), systemImage: "cpu")
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(CCCTheme.faint)
                    }
                    if let mem = res.mem_pct {
                        Label(String(format: "MEM %.0f%%", mem), systemImage: "memorychip")
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(CCCTheme.faint)
                    }
                    if let disk = res.disk_pct {
                        Label(String(format: "DISK %.0f%%", disk), systemImage: "externaldrive")
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(CCCTheme.faint)
                    }
                }
            }
        }
    }

    private var risksSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("风险")
                    .font(.system(size: 13, weight: .semibold))
                if let high = model.opsRisksHigh, high > 0 {
                    Text("高 \(high)")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(CCCTheme.nodeFail)
                }
                Spacer()
                if let c = model.opsRisksCount {
                    Text("共 \(c)")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                }
            }
            if model.opsRisks.isEmpty {
                Text("暂无风险")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.faint)
            } else {
                ForEach(model.opsRisks) { risk in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(risk.title)
                                .font(.system(size: 13, weight: .medium))
                            Spacer()
                            Text(risk.severity)
                                .font(.system(size: 10, weight: .semibold))
                                .foregroundStyle(severityColor(risk.severity))
                        }
                        if !risk.detail.isEmpty {
                            Text(risk.detail)
                                .font(.system(size: 12))
                                .foregroundStyle(CCCTheme.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .fill(CCCTheme.surface)
                    )
                }
            }
        }
    }

    private var workspacesSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("工作区")
                .font(.system(size: 13, weight: .semibold))
            if let wss = model.opsSummary?.workspaces?.workspaces, !wss.isEmpty {
                ForEach(wss) { ws in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(ws.workspace)
                                .font(.system(size: 12, weight: .medium))
                                .foregroundStyle(CCCTheme.ink)
                            Spacer()
                            if let abnormal = ws.abnormal, abnormal > 0 {
                                Text("异常 \(abnormal)")
                                    .font(.system(size: 10, weight: .semibold))
                                    .foregroundStyle(CCCTheme.nodeFail)
                            }
                        }
                        HStack(spacing: 10) {
                            ForEach([
                                ("待", ws.backlog), ("规", ws.planned), ("进", ws.in_progress),
                                ("测", ws.testing), ("验", ws.verified), ("发", ws.released),
                            ], id: \.0) { pair in
                                let (label, n) = pair
                                if let n = n {
                                    Text("\(label)\(n)")
                                        .font(.system(size: 10, design: .monospaced))
                                        .foregroundStyle(CCCTheme.faint)
                                }
                            }
                        }
                        if let ev = ws.last_event, !ev.isEmpty {
                            Text(ev)
                                .font(.system(size: 9, design: .monospaced))
                                .foregroundStyle(CCCTheme.faint.opacity(0.8))
                                .lineLimit(1)
                        }
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .fill(CCCTheme.surface)
                    )
                }
            } else {
                Text("暂无工作区数据")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.faint)
            }
        }
    }

    private var dailyReviewSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("日审")
                    .font(.system(size: 13, weight: .semibold))
                Spacer()
                Button("跑日审") {
                    let ws = model.boardWorkspaceLabel
                        ?? model.selectedProject?.workspace
                        ?? "CCC"
                    Task { await model.runDailyReview(workspace: ws) }
                }
                    .buttonStyle(.bordered)
                    .controlSize(.mini)
                    .disabled(model.opsAdoptBusy)
            }
            if let daily = model.opsSummary?.daily {
                if let latest = daily.latest {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("\(latest.workspace) · \(latest.name)")
                            .font(.system(size: 11, weight: .medium))
                            .foregroundStyle(CCCTheme.ink)
                        if let mt = latest.mtime {
                            Text(mt)
                                .font(.system(size: 9, design: .monospaced))
                                .foregroundStyle(CCCTheme.faint)
                        }
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .fill(CCCTheme.surface)
                    )
                    if let body = daily.latest_body, !body.isEmpty {
                        Text(body)
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundStyle(CCCTheme.faint)
                            .lineLimit(20)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(10)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(
                                RoundedRectangle(cornerRadius: 8, style: .continuous)
                                    .fill(CCCTheme.surface.opacity(0.6))
                            )
                    }
                } else {
                    Text("暂无日审报告")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                }
            }
        }
    }

    private var qualitySection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("质量")
                .font(.system(size: 13, weight: .semibold))
            if let digests = model.opsSummary?.quality?.workspaces, !digests.isEmpty {
                ForEach(digests) { d in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(d.workspace)
                                .font(.system(size: 12, weight: .medium))
                            Spacer()
                            if let c = d.commits_24h {
                                Text("24h \(c) commits")
                                    .font(.system(size: 10, design: .monospaced))
                                    .foregroundStyle(CCCTheme.faint)
                            }
                            if let r = d.released_total {
                                Text("released \(r)")
                                    .font(.system(size: 10, design: .monospaced))
                                    .foregroundStyle(CCCTheme.secondary)
                            }
                        }
                        if let sample = d.commit_sample, !sample.isEmpty {
                            Text(sample.prefix(4).joined(separator: "\n"))
                                .font(.system(size: 9, design: .monospaced))
                                .foregroundStyle(CCCTheme.faint.opacity(0.85))
                                .lineLimit(4)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .fill(CCCTheme.surface)
                    )
                }
            } else {
                Text("暂无质量摘要")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.faint)
            }
        }
    }

    private var docsDebtSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("文档债")
                    .font(.system(size: 13, weight: .semibold))
                Spacer()
                if let c = model.opsSummary?.docs?.count {
                    Text("共 \(c)")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                }
            }
            if let items = model.opsSummary?.docs?.items, !items.isEmpty {
                ForEach(items.prefix(10)) { item in
                    VStack(alignment: .leading, spacing: 2) {
                        if let f = item.file {
                            Text("\(item.workspace ?? "?") · \(f)")
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(CCCTheme.ink)
                                .lineLimit(1)
                        }
                        if let issue = item.issue, !issue.isEmpty {
                            Text(issue)
                                .font(.system(size: 10))
                                .foregroundStyle(CCCTheme.faint)
                                .lineLimit(2)
                        }
                    }
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 6, style: .continuous)
                            .fill(CCCTheme.surface)
                    )
                }
            } else {
                Text("暂无文档债")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.faint)
            }
        }
    }

    private var downPortsSection: some View {
        Group {
            if let ports = model.opsOverview?.down_ports, !ports.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("宕口")
                        .font(.system(size: 13, weight: .semibold))
                    ForEach(ports) { p in
                        Text("\(p.host):\(p.port) · \(p.name)")
                            .font(.system(size: 12, design: .monospaced))
                            .foregroundStyle(CCCTheme.secondary)
                    }
                }
            }
        }
    }

    private var adoptSheet: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("采纳建议 → backlog")
                .font(.system(size: 14, weight: .semibold))
            HStack {
                Text("工作区").font(.system(size: 12)).foregroundStyle(CCCTheme.faint)
                TextField("CCC", text: $adoptWorkspace)
                    .textFieldStyle(.roundedBorder)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("标题").font(.system(size: 12)).foregroundStyle(CCCTheme.faint)
                TextField("一句话建议", text: $adoptTitle)
                    .textFieldStyle(.roundedBorder)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("描述").font(.system(size: 12)).foregroundStyle(CCCTheme.faint)
                TextEditor(text: $adoptDesc)
                    .font(.system(size: 12))
                    .frame(height: 80)
                    .border(CCCTheme.border)
            }
            HStack {
                Spacer()
                Button("取消") { showAdoptSheet = false }
                    .buttonStyle(.bordered)
                Button("采纳") {
                    Task {
                        await model.adoptSuggestion(
                            workspace: adoptWorkspace.isEmpty ? "CCC" : adoptWorkspace,
                            title: adoptTitle,
                            description: adoptDesc
                        )
                        if model.opsAdoptError == nil {
                            showAdoptSheet = false
                            adoptTitle = ""
                            adoptDesc = ""
                        }
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(adoptTitle.isEmpty || model.opsAdoptBusy)
            }
        }
        .padding(20)
        .frame(width: 440, height: 320, alignment: .topLeading)
        .background(CCCTheme.chatBg)
    }

    private func severityColor(_ s: String) -> Color {
        switch s.lowercased() {
        case "high", "critical": return CCCTheme.nodeFail
        case "medium", "warn", "warning": return Color.orange
        default: return CCCTheme.faint
        }
    }
}
