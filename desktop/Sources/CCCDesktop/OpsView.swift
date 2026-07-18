import SwiftUI

/// 原生运维：概览 + 风险列表
struct OpsView: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("运维")
                    .font(.system(size: 16, weight: .semibold))
                Spacer()
                if model.opsBusy {
                    ProgressView().controlSize(.mini)
                }
                Button("刷新") {
                    Task { await model.refreshOps() }
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

            if let err = model.opsError {
                Text(err)
                    .font(.system(size: 12))
                    .foregroundStyle(CCCTheme.nodeFail)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 8)
            }

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    overviewSection
                    risksSection
                    downPortsSection
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 28)
            }
        }
        .background(CCCTheme.chatBg)
        .task { await model.refreshOps() }
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

    private func severityColor(_ s: String) -> Color {
        switch s.lowercased() {
        case "high", "critical": return CCCTheme.nodeFail
        case "medium", "warn", "warning": return Color.orange
        default: return CCCTheme.faint
        }
    }
}
