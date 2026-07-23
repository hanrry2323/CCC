import SwiftUI
import AppKit

/// 原生运维：一眼红绿灯（绿敢开发 / 橙可忽略 / 红复制交 Agent）
struct OpsView: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState
    @State private var showAdoptSheet = false
    @State private var adoptTitle = ""
    @State private var adoptDesc = ""
    @State private var adoptWorkspace = ""
    @State private var showFleet = false
    @State private var showReports = false
    @State private var showActions = false

    private var preferredAmmoWorkspace: String {
        if let p = model.selectedProject, p.isDispatchable {
            return p.workspace ?? p.id
        }
        if let p = model.projects.first(where: \.isDispatchable) {
            return p.workspace ?? p.id
        }
        return ""
    }

    private var canAdoptAmmo: Bool {
        let ws = adoptWorkspace.trimmingCharacters(in: .whitespacesAndNewlines)
        return !ws.isEmpty && ws.uppercased() != "CCC"
    }

    private let machineColumns = [
        GridItem(.adaptive(minimum: 220, maximum: 320), spacing: 12),
    ]

    var body: some View {
        VStack(spacing: 0) {
            header
            if let err = model.opsError {
                Label(err, systemImage: "exclamationmark.triangle.fill")
                    .font(CCCTheme.callout)
                    .foregroundStyle(CCCTheme.nodeFail)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 8)
            }
            if let adoptErr = model.opsAdoptError {
                Text(adoptErr)
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.nodeFail)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 6)
            }
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 22) {
                    healthLampSection
                    redAlertsSection
                    domainsSection
                    failuresSection
                    DisclosureGroup("后勤与舰队", isExpanded: $showFleet) {
                        VStack(alignment: .leading, spacing: 22) {
                            logisticsSection
                            overviewSection
                            resourcesSection
                            workspacesSection
                            downPortsSection
                        }
                        .padding(.top, 8)
                    }
                    .font(.system(size: 15, weight: .semibold))
                    DisclosureGroup("报告与债", isExpanded: $showReports) {
                        VStack(alignment: .leading, spacing: 22) {
                            dailyReviewSection
                            qualitySection
                            docsDebtSection
                            risksSection
                        }
                        .padding(.top, 8)
                    }
                    .font(.system(size: 15, weight: .semibold))
                    inboxProposalsSection
                    DisclosureGroup("例外动作", isExpanded: $showActions) {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("日审默认 dry-run；采纳须业务仓（禁 CCC）。日常不必点。")
                                .font(CCCTheme.caption)
                                .foregroundStyle(CCCTheme.faint)
                            Button {
                                Task { await model.runDailyReview(workspace: "") }
                            } label: {
                                Label("跑日审（dry-run）", systemImage: "play.fill")
                            }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                            .disabled(model.opsAdoptBusy)
                        }
                        .padding(.top, 8)
                    }
                    .font(.system(size: 15, weight: .semibold))
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 28)
            }
        }
        .background(CCCTheme.chatBg)
        .task {
            if adoptWorkspace.isEmpty {
                adoptWorkspace = preferredAmmoWorkspace
            }
            await model.refreshOps()
        }
        .sheet(isPresented: $showAdoptSheet) {
            adoptSheet
                .onAppear {
                    if adoptWorkspace.isEmpty || adoptWorkspace.uppercased() == "CCC" {
                        adoptWorkspace = preferredAmmoWorkspace
                    }
                }
        }
    }

    private var header: some View {
        HStack {
            Label("运维", systemImage: "heart.text.square.fill")
                .font(.system(size: 18, weight: .semibold))
            let redN = displayAlerts.count
            if redN > 0 {
                Text("\(redN)")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 7)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(CCCTheme.nodeFail))
            }
            Spacer()
            if let hint = model.opsCopiedHint {
                Text(hint)
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.secondary)
            }
            if model.opsAdoptBusy || model.opsBusy {
                ProgressView().controlSize(.small)
            }
            Menu {
                Button("采纳建议…", systemImage: "plus.circle") {
                    adoptWorkspace = preferredAmmoWorkspace
                    showAdoptSheet = true
                }
                .disabled(preferredAmmoWorkspace.isEmpty)
                Button("刷新", systemImage: "arrow.clockwise") {
                    Task { await model.refreshOps() }
                }
            } label: {
                Image(systemName: "ellipsis.circle")
                    .font(.system(size: 16))
                    .foregroundStyle(CCCTheme.secondary)
            }
            .menuStyle(.borderlessButton)
            Button("回对话") {
                window.destination = .chat
                model.selectDestination(.chat, projectId: window.projectId)
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
        }
        .padding(.horizontal, 20)
        .padding(.top, 12)
        .padding(.bottom, 10)
    }

    // MARK: - Health lamp (homepage)

    /// Hub severity + 本机 Agent 合并后的总灯
    private var displaySeverity: String {
        let hub = (model.opsSummary?.severity ?? "").lowercased()
        let agentDown = model.opsAgentOk == false
        if agentDown { return "red" }
        if hub == "red" { return "red" }
        if hub == "amber" || hub == "orange" { return "amber" }
        if hub == "green" { return "green" }
        // 无 summary 时用 ready 兜底
        if model.opsSummary?.ready_to_dispatch?.ok == false { return "red" }
        if model.opsSummary != nil { return "green" }
        return "amber"
    }

    private var displayHumanLine: String {
        if model.opsAgentOk == false {
            return "本机对话 Agent 未就绪 · 请交给 Agent（或先启动 sidecar）"
        }
        if let line = model.opsSummary?.human_line, !line.isEmpty {
            return line
        }
        switch displaySeverity {
        case "green": return "系统健康 · 可以放心开发和下任务"
        case "red": return "请交给 Agent 处理红灯"
        default: return "有轻度提示，不挡开发"
        }
    }

    private var displayAlerts: [OpsHealthAlert] {
        var list = model.opsSummary?.alerts ?? []
        if model.opsAgentOk == false {
            let payload = """
            【CCC 运维红灯】请排查并修复（系统/配置问题，不是业务意图）
            标题：本机 Agent Sidecar 未就绪
            影响：无法对话 / 无法承接红灯修复
            来源：sidecar
            详情：GET http://127.0.0.1:7788/health 失败或 ok≠true
            建议：查 com.ccc.agent-sidecar / 本机 :7788
            机器字段：{"id":"sidecar-down","source":"sidecar","port":7788}
            """
            let local = OpsHealthAlert(
                id: "sidecar-down",
                title: "本机 Agent Sidecar 未就绪",
                detail: "对话面 :7788 不可用",
                source: "sidecar",
                severity: "red",
                copy_payload: payload
            )
            if !list.contains(where: { $0.id == "sidecar-down" }) {
                list.insert(local, at: 0)
            }
        }
        return list
    }

    private var healthLampSection: some View {
        let sev = displaySeverity
        let color: Color = {
            switch sev {
            case "green": return CCCTheme.nodeDone
            case "red": return CCCTheme.nodeFail
            default: return Color.orange
            }
        }()
        let title: String = {
            switch sev {
            case "green": return "可以开发"
            case "red": return "请交给 Agent"
            default: return "可忽略"
            }
        }()
        let icon: String = {
            switch sev {
            case "green": return "checkmark.circle.fill"
            case "red": return "exclamationmark.octagon.fill"
            default: return "exclamationmark.circle.fill"
            }
        }()
        return VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 16) {
                Image(systemName: icon)
                    .font(.system(size: 44))
                    .foregroundStyle(color)
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.system(size: 22, weight: .bold))
                        .foregroundStyle(color)
                    Text(displayHumanLine)
                        .font(.system(size: 15))
                        .foregroundStyle(CCCTheme.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
            }
            if sev == "amber", let notes = model.opsSummary?.amber_notes, !notes.isEmpty {
                Text(notes.prefix(3).joined(separator: " · "))
                    .font(CCCTheme.caption)
                    .foregroundStyle(Color.orange.opacity(0.9))
            }
            if sev == "green" {
                Text("看一眼绿灯就可以去定稿下任务。不必在这里修东西。")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.faint)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(color.opacity(0.12))
        )
    }

    private var redAlertsSection: some View {
        let alerts = displayAlerts
        return Group {
            if !alerts.isEmpty {
                VStack(alignment: .leading, spacing: 10) {
                    sectionTitle("红灯 · 一键交给 Agent", systemImage: "doc.on.clipboard")
                    Text("红灯是系统问题。复制后回对话粘贴，让 Agent 处理。你不用当维修工。")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                    ForEach(alerts) { alert in
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: "light.beacon.max.fill")
                                .foregroundStyle(CCCTheme.nodeFail)
                                .padding(.top, 2)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(alert.title)
                                    .font(.system(size: 14, weight: .semibold))
                                if let d = alert.detail, !d.isEmpty {
                                    Text(d)
                                        .font(CCCTheme.caption)
                                        .foregroundStyle(CCCTheme.secondary)
                                        .lineLimit(3)
                                }
                            }
                            Spacer(minLength: 8)
                            Button("复制给 Agent") {
                                copyOpsAlert(alert)
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(CCCTheme.nodeFail)
                            .controlSize(.small)
                        }
                        .padding(12)
                        .background(
                            RoundedRectangle(cornerRadius: 10, style: .continuous)
                                .fill(CCCTheme.nodeFail.opacity(0.08))
                        )
                    }
                }
            }
        }
    }

    private func copyOpsAlert(_ alert: OpsHealthAlert) {
        let text = (alert.copy_payload?.trimmingCharacters(in: .whitespacesAndNewlines)).flatMap { $0.isEmpty ? nil : $0 }
            ?? """
            【CCC 运维红灯】\(alert.title)
            \(alert.detail ?? "")
            来源：\(alert.source ?? "ops")
            """
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        model.opsCopiedHint = "已复制"
        model.fillComposer(text: text, threadId: model.selectedThreadId)
        window.destination = .chat
        model.selectDestination(.chat, projectId: window.projectId)
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            if model.opsCopiedHint == "已复制" {
                model.opsCopiedHint = nil
            }
        }
    }

    private var domainsSection: some View {
        let cluster = model.opsSummary?.domains?.cluster
        let cap = model.opsSummary?.domains?.capacity
        let agentOk = model.opsAgentOk
        return VStack(alignment: .leading, spacing: 10) {
            sectionTitle("一览", systemImage: "square.grid.2x2")
            HStack(spacing: 10) {
                domainChip(
                    title: "集群",
                    ok: cluster?.engine_running == true
                        && (cluster?.mode == "enabled")
                        && (cluster?.hub_port_7777 != false)
                        && (cluster?.down_ports_n ?? 0) == 0,
                    subtitle: {
                        let eng = cluster?.engine_running == true ? "Engine" : "Engine停"
                        let mode = cluster?.mode ?? "—"
                        return "\(eng) · \(mode)"
                    }()
                )
                domainChip(
                    title: "Agent",
                    ok: agentOk == true,
                    subtitle: {
                        if agentOk == true {
                            let rt = model.opsAgentRuntime ?? "sidecar"
                            let m = model.opsAgentModel ?? ""
                            return m.isEmpty ? rt : "\(rt) · \(m)"
                        }
                        if agentOk == false { return "本机未就绪" }
                        return "探测中"
                    }()
                )
                domainChip(
                    title: "容量",
                    ok: (cap?.verdict ?? "headroom") != "saturated",
                    subtitle: cap?.verdict ?? "—"
                )
            }
            if let ports = cluster?.ports, !ports.isEmpty {
                Text(
                    "端口 "
                        + ports.map { p in
                            let n = p.port.map(String.init) ?? "?"
                            let mark = p.ok == true ? "✓" : (p.ok == false ? "✗" : "?")
                            return ":\(n)\(mark)"
                        }.joined(separator: "  ")
                )
                .font(CCCTheme.caption)
                .foregroundStyle(CCCTheme.faint)
            }
            Text("MCP 清单探针后续接入；当前以 Agent 在线代表对话能力。")
                .font(CCCTheme.caption)
                .foregroundStyle(CCCTheme.faint)
        }
    }

    private func domainChip(title: String, ok: Bool, subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(CCCTheme.faint)
            Text(subtitle)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(ok ? CCCTheme.nodeDone : CCCTheme.nodeFail)
                .lineLimit(2)
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill((ok ? CCCTheme.nodeDone : CCCTheme.nodeFail).opacity(0.1))
        )
    }

    // MARK: - Failures / abnormal (reopen)

    private var failuresSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("失败与异常", systemImage: "arrow.uturn.backward.circle")
            Text("归档仍须人确认；此处仅 reopen → planned。")
                .font(CCCTheme.caption)
                .foregroundStyle(CCCTheme.faint)
            let cards = model.opsSummary?.abnormal_cards ?? []
            if cards.isEmpty {
                emptyHint("无 abnormal 卡")
            } else {
                ForEach(cards.prefix(12)) { card in
                    HStack(alignment: .top, spacing: 10) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(card.title ?? card.task_id ?? "—")
                                .font(.system(size: 13, weight: .semibold))
                            Text("\(card.workspace) · \((card.note?.isEmpty == false) ? (card.note ?? "") : "abnormal")")
                                .font(CCCTheme.caption)
                                .foregroundStyle(CCCTheme.secondary)
                                .lineLimit(2)
                        }
                        Spacer(minLength: 8)
                        Button("重开") {
                            Task {
                                await model.reopenOpsTask(
                                    taskId: card.task_id ?? card.id,
                                    workspace: card.workspace
                                )
                            }
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.mini)
                        .disabled(model.opsBusy || model.opsAdoptBusy)
                        Button("看板") {
                            model.openBoardFromOps(workspace: card.workspace)
                            window.destination = .board
                        }
                        .buttonStyle(.borderless)
                        .controlSize(.mini)
                    }
                    .padding(10)
                    .background(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .fill(CCCTheme.nodeFail.opacity(0.06))
                    )
                }
            }
            let fails = model.opsSummary?.recent_failures ?? []
            if !fails.isEmpty {
                Text("最近失败账本")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(CCCTheme.secondary)
                    .padding(.top, 4)
                ForEach(fails.prefix(8)) { fr in
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(fr.workspace ?? "?") · \(fr.task_id ?? "?") · \(fr.role ?? "")")
                            .font(.system(size: 11, design: .monospaced))
                        Text(fr.reason ?? "—")
                            .font(CCCTheme.caption)
                            .foregroundStyle(CCCTheme.secondary)
                            .lineLimit(2)
                    }
                    .padding(.vertical, 2)
                }
            }
        }
    }

    // MARK: - Logistics heartbeat (read-only)

    private var logisticsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("后勤供弹", systemImage: "shippingbox.fill")
            if let log = model.opsSummary?.logistics {
                VStack(alignment: .leading, spacing: 8) {
                    if let headline = log.headline {
                        Text(headline)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(log.needs_attention == true ? Color.orange : CCCTheme.ink)
                    }
                    HStack {
                        Label("\(log.ammo_workspaces?.count ?? 0) 弹药仓", systemImage: "tray.full")
                        Spacer()
                        if let n = log.ops_auto_backlog {
                            Text("ops-auto \(n)")
                                .font(CCCTheme.caption)
                                .foregroundStyle(CCCTheme.secondary)
                        }
                    }
                    if let ammo = log.ammo_workspaces, !ammo.isEmpty {
                        Text(ammo.compactMap(\.workspace).joined(separator: " · "))
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(CCCTheme.faint)
                            .lineLimit(2)
                    }
                    Text("CCC orch 不在供弹名单")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                    if let agents = log.plist?.agents, !agents.isEmpty {
                        ForEach(agents) { a in
                            HStack {
                                Image(systemName: (a.loaded == true) ? "checkmark.circle.fill" : "circle")
                                    .foregroundStyle((a.loaded == true) ? CCCTheme.nodeDone : CCCTheme.faint)
                                Text(a.label)
                                    .font(.system(size: 12, design: .monospaced))
                                Spacer()
                                Text(a.apply_ammo == true ? "apply" : "dry")
                                    .font(CCCTheme.caption)
                                    .foregroundStyle(CCCTheme.secondary)
                            }
                        }
                    }
                    if let daily = log.daily_today, !daily.isEmpty {
                        ForEach(daily) { d in
                            Text("\(d.workspace) · \(d.decision ?? "—")")
                                .font(.system(size: 12, design: .monospaced))
                                .foregroundStyle(CCCTheme.secondary)
                        }
                    } else {
                        emptyHint("今日尚无日审报告")
                    }
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(CCCTheme.surface)
                )
            } else {
                emptyHint("后勤心跳未返回（刷新或升级 Hub）")
            }
        }
    }

    // MARK: - Inbox proposals (Hub-Shell P2)

    private var inboxProposalsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("待采纳提案", systemImage: "tray.and.arrow.down")
            if model.inboxProposals.isEmpty {
                emptyHint("inbox/ 无 pending 提案")
            } else {
                ForEach(model.inboxProposals) { p in
                    HStack(alignment: .top, spacing: 10) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(p.title ?? p.id)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(CCCTheme.ink)
                            Text("\(p.project_id ?? "—") · \(p.complexity ?? "small")")
                                .font(CCCTheme.caption)
                                .foregroundStyle(CCCTheme.secondary)
                        }
                        Spacer()
                        Button("采纳") {
                            Task { await model.adoptInboxProposal(p.id) }
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                        .disabled(model.inboxAdoptBusy)
                    }
                    .padding(10)
                    .background(RoundedRectangle(cornerRadius: 8).fill(CCCTheme.surface.opacity(0.9)))
                }
            }
        }
    }

    // MARK: - Overview machines

    private var overviewSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("集群", systemImage: "desktopcomputer")
            if let machines = model.opsOverview?.machines, !machines.isEmpty {
                LazyVGrid(columns: machineColumns, spacing: 12) {
                    ForEach(machines) { m in
                        machineCard(m)
                    }
                }
            } else {
                emptyHint("暂无机器数据")
            }
        }
    }

    private func machineCard(_ m: OpsMachine) -> some View {
        let up = m.reachable ?? false
        return VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: up ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .font(.system(size: 18))
                    .foregroundStyle(up ? CCCTheme.nodeDone : CCCTheme.nodeFail)
                VStack(alignment: .leading, spacing: 2) {
                    Text(m.name)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(CCCTheme.ink)
                    Text(m.role ?? "—")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                }
                Spacer(minLength: 0)
            }
            Divider()
            LabeledContent("地址") {
                Text(m.ip)
                    .font(.system(size: 13, design: .monospaced))
                    .foregroundStyle(CCCTheme.secondary)
            }
            .font(CCCTheme.callout)
            if let alive = m.alive_ports, let total = m.port_count {
                LabeledContent("端口") {
                    Text("\(alive)/\(total)")
                        .font(.system(size: 13, design: .monospaced))
                        .foregroundStyle(alive == total ? CCCTheme.nodeDone : CCCTheme.accent)
                }
                .font(CCCTheme.callout)
                ProgressView(value: total > 0 ? Double(alive) / Double(total) : 0)
                    .tint(alive == total ? CCCTheme.nodeDone : CCCTheme.accent)
            }
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(.regularMaterial)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(CCCTheme.border, lineWidth: 1)
        )
    }

    // MARK: - Resources gauges

    private var resourcesSection: some View {
        Group {
            if let res = model.opsSummary?.resources {
                VStack(alignment: .leading, spacing: 12) {
                    sectionTitle("资源", systemImage: "chart.bar.fill")
                    if let hist = model.opsSummary?.resources_history?.summary {
                        let verdict = hist.verdict ?? "—"
                        HStack {
                            Text("并行容量：\(verdict)")
                                .font(.system(size: 13, weight: .semibold))
                                .foregroundStyle(verdict == "saturated" ? CCCTheme.nodeFail : CCCTheme.nodeDone)
                            if let spark = model.opsSummary?.resources_history?.sparklines?.load_ratio {
                                Text(spark)
                                    .font(.system(size: 11, design: .monospaced))
                                    .foregroundStyle(CCCTheme.faint)
                            }
                        }
                        if let note = hist.note ?? hist.reason, !note.isEmpty {
                            Text(note)
                                .font(CCCTheme.caption)
                                .foregroundStyle(CCCTheme.secondary)
                        }
                    }
                    HStack(spacing: 16) {
                        if let cpu = res.cpu {
                            resourceGauge(
                                title: "CPU",
                                value: cpu,
                                symbol: "cpu",
                                unit: String(format: "%.0f%%", cpu * 100)
                            )
                        }
                        if let mem = res.mem_pct {
                            resourceGauge(
                                title: "内存",
                                value: mem / 100.0,
                                symbol: "memorychip",
                                unit: String(format: "%.0f%%", mem)
                            )
                        }
                        if let disk = res.disk_pct {
                            resourceGauge(
                                title: "磁盘",
                                value: disk / 100.0,
                                symbol: "externaldrive.fill",
                                unit: String(format: "%.0f%%", disk)
                            )
                        }
                    }
                }
            }
        }
    }

    private func resourceGauge(title: String, value: Double, symbol: String, unit: String) -> some View {
        let clamped = min(max(value, 0), 1)
        return VStack(spacing: 8) {
            Gauge(value: clamped) {
                Image(systemName: symbol)
            } currentValueLabel: {
                Text(unit)
                    .font(.system(size: 13, weight: .semibold, design: .rounded))
            }
            .gaugeStyle(.accessoryCircularCapacity)
            .tint(clamped > 0.85 ? CCCTheme.nodeFail : (clamped > 0.65 ? CCCTheme.accent : CCCTheme.nodeDone))
            Text(title)
                .font(CCCTheme.caption)
                .foregroundStyle(CCCTheme.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(.regularMaterial)
        )
    }

    // MARK: - Risks

    private var risksSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                sectionTitle("风险", systemImage: "exclamationmark.shield.fill")
                if let high = model.opsRisksHigh, high > 0 {
                    Text("高 \(high)")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Capsule().fill(CCCTheme.nodeFail))
                }
                Spacer()
                if let c = model.opsRisksCount {
                    Text("共 \(c)")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                }
            }
            if model.opsRisks.isEmpty {
                emptyHint("暂无风险")
            } else {
                ForEach(model.opsRisks) { risk in
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: severityIcon(risk.severity))
                            .font(.system(size: 16))
                            .foregroundStyle(severityColor(risk.severity))
                            .frame(width: 22)
                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                Text(risk.title)
                                    .font(.system(size: 14, weight: .semibold))
                                Spacer()
                                Text(risk.severity.uppercased())
                                    .font(.system(size: 10, weight: .bold))
                                    .foregroundStyle(severityColor(risk.severity))
                                    .padding(.horizontal, 7)
                                    .padding(.vertical, 2)
                                    .background(
                                        Capsule().fill(severityColor(risk.severity).opacity(0.14))
                                    )
                            }
                            if !risk.detail.isEmpty {
                                Text(risk.detail)
                                    .font(CCCTheme.callout)
                                    .foregroundStyle(CCCTheme.secondary)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    .padding(12)
                    .background(
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .fill(CCCTheme.surface)
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .stroke(severityColor(risk.severity).opacity(0.25), lineWidth: 1)
                    )
                }
            }
        }
    }

    // MARK: - Workspaces

    private var workspacesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("工作区", systemImage: "folder.fill")
            if let wss = model.opsSummary?.workspaces?.workspaces, !wss.isEmpty {
                ForEach(wss) { ws in
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Label(ws.workspace, systemImage: "shippingbox.fill")
                                .font(.system(size: 14, weight: .semibold))
                            Spacer()
                            if let abnormal = ws.abnormal, abnormal > 0 {
                                Label("异常 \(abnormal)", systemImage: "flame.fill")
                                    .font(.system(size: 12, weight: .semibold))
                                    .foregroundStyle(CCCTheme.nodeFail)
                            }
                        }
                        HStack(spacing: 8) {
                            boardChip("待办", ws.backlog)
                            boardChip("规划", ws.planned)
                            boardChip("进行", ws.in_progress)
                            boardChip("验收", ws.testing)
                            boardChip("异常", ws.abnormal)
                            boardChip("已验", ws.verified)
                            boardChip("发布", ws.released)
                        }
                        if let ev = ws.last_event, !ev.isEmpty {
                            Text(ev)
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(CCCTheme.faint)
                                .lineLimit(1)
                        }
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(.regularMaterial)
                    )
                }
            } else {
                emptyHint("暂无工作区数据")
            }
        }
    }

    private func boardChip(_ label: String, _ n: Int?) -> some View {
        Group {
            if let n {
                VStack(spacing: 2) {
                    Text("\(n)")
                        .font(.system(size: 14, weight: .semibold, design: .rounded))
                        .foregroundStyle(CCCTheme.ink)
                    Text(label)
                        .font(.system(size: 10))
                        .foregroundStyle(CCCTheme.faint)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 6)
                .background(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .fill(CCCTheme.chatBg)
                )
            }
        }
    }

    // MARK: - Daily / quality / docs / ports

    private var dailyReviewSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("日审", systemImage: "calendar")
            if let daily = model.opsSummary?.daily {
                if let latest = daily.latest {
                    VStack(alignment: .leading, spacing: 6) {
                        Label("\(latest.workspace) · \(latest.name)", systemImage: "doc.text")
                            .font(.system(size: 14, weight: .medium))
                        if let mt = latest.mtime {
                            Text(mt)
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(CCCTheme.faint)
                        }
                        if let body = daily.latest_body, !body.isEmpty {
                            Text(body)
                                .font(.system(size: 12, design: .monospaced))
                                .foregroundStyle(CCCTheme.secondary)
                                .lineLimit(16)
                                .textSelection(.enabled)
                        }
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(CCCTheme.surface)
                    )
                } else {
                    emptyHint("暂无日审报告")
                }
            }
        }
    }

    private var qualitySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("质量", systemImage: "checkmark.seal.fill")
            if let digests = model.opsSummary?.quality?.workspaces, !digests.isEmpty {
                ForEach(digests) { d in
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text(d.workspace)
                                .font(.system(size: 14, weight: .semibold))
                            Spacer()
                            if let c = d.commits_24h {
                                Label("\(c)", systemImage: "arrow.triangle.branch")
                                    .font(CCCTheme.caption)
                                    .foregroundStyle(CCCTheme.secondary)
                            }
                            if let r = d.released_total {
                                Label("\(r)", systemImage: "flag.checkered")
                                    .font(CCCTheme.caption)
                                    .foregroundStyle(CCCTheme.nodeDone)
                            }
                        }
                        if let sample = d.commit_sample, !sample.isEmpty {
                            Text(sample.prefix(4).joined(separator: "\n"))
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(CCCTheme.faint)
                                .lineLimit(4)
                        }
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(.regularMaterial)
                    )
                }
            } else {
                emptyHint("暂无质量摘要")
            }
        }
    }

    private var docsDebtSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                sectionTitle("文档债", systemImage: "books.vertical.fill")
                Spacer()
                if let c = model.opsSummary?.docs?.count {
                    Text("共 \(c)")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                }
            }
            if let items = model.opsSummary?.docs?.items, !items.isEmpty {
                ForEach(items.prefix(10)) { item in
                    VStack(alignment: .leading, spacing: 4) {
                        if let f = item.file {
                            Label("\(item.workspace ?? "?") · \(f)", systemImage: "doc")
                                .font(.system(size: 13, design: .monospaced))
                                .lineLimit(1)
                        }
                        if let issue = item.issue, !issue.isEmpty {
                            Text(issue)
                                .font(CCCTheme.callout)
                                .foregroundStyle(CCCTheme.faint)
                                .lineLimit(2)
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
                emptyHint("暂无文档债")
            }
        }
    }

    private var downPortsSection: some View {
        Group {
            if let ports = model.opsOverview?.down_ports, !ports.isEmpty {
                VStack(alignment: .leading, spacing: 10) {
                    sectionTitle("宕口", systemImage: "network.slash")
                    ForEach(ports) { p in
                        Label("\(p.host):\(p.port) · \(p.name)", systemImage: "antenna.radiowaves.left.and.right.slash")
                            .font(.system(size: 13, design: .monospaced))
                            .foregroundStyle(CCCTheme.nodeFail)
                            .padding(10)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(
                                RoundedRectangle(cornerRadius: 8, style: .continuous)
                                    .fill(CCCTheme.nodeFail.opacity(0.08))
                            )
                    }
                }
            }
        }
    }

    private var adoptSheet: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("采纳建议 → 业务仓 backlog")
                .font(.system(size: 16, weight: .semibold))
            LabeledContent("工作区") {
                TextField("ccc-demo（禁 CCC）", text: $adoptWorkspace)
                    .textFieldStyle(.roundedBorder)
            }
            if preferredAmmoWorkspace.isEmpty {
                Text("无 engine-eligible 业务仓，无法采纳")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.nodeFail)
            } else if adoptWorkspace.uppercased() == "CCC" {
                Text("禁止对 CCC orch 供弹")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.nodeFail)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("标题").font(CCCTheme.callout).foregroundStyle(CCCTheme.faint)
                TextField("一句话建议", text: $adoptTitle)
                    .textFieldStyle(.roundedBorder)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("描述").font(CCCTheme.callout).foregroundStyle(CCCTheme.faint)
                TextEditor(text: $adoptDesc)
                    .font(CCCTheme.callout)
                    .frame(height: 80)
                    .border(CCCTheme.border)
            }
            HStack {
                Spacer()
                Button("取消") { showAdoptSheet = false }
                    .buttonStyle(.bordered)
                Button("采纳") {
                    Task {
                        guard canAdoptAmmo else {
                            model.opsAdoptError = "须指定业务仓（禁 CCC orch）"
                            return
                        }
                        await model.adoptSuggestion(
                            workspace: adoptWorkspace.trimmingCharacters(in: .whitespacesAndNewlines),
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
                .tint(CCCTheme.accent)
                .disabled(adoptTitle.isEmpty || model.opsAdoptBusy || !canAdoptAmmo)
            }
        }
        .padding(20)
        .frame(width: 440, height: 340, alignment: .topLeading)
        .background(CCCTheme.chatBg)
    }

    private func sectionTitle(_ title: String, systemImage: String) -> some View {
        Label(title, systemImage: systemImage)
            .font(.system(size: 15, weight: .semibold))
            .foregroundStyle(CCCTheme.ink)
    }

    private func emptyHint(_ text: String) -> some View {
        Text(text)
            .font(CCCTheme.caption)
            .foregroundStyle(CCCTheme.faint)
            .padding(.vertical, 4)
    }

    private func severityColor(_ s: String) -> Color {
        switch s.lowercased() {
        case "high", "critical": return CCCTheme.nodeFail
        case "medium", "warn", "warning": return Color.orange
        default: return CCCTheme.faint
        }
    }

    private func severityIcon(_ s: String) -> String {
        switch s.lowercased() {
        case "high", "critical": return "exclamationmark.octagon.fill"
        case "medium", "warn", "warning": return "exclamationmark.triangle.fill"
        default: return "info.circle.fill"
        }
    }
}
