import AppKit
import SwiftUI

/// 真·系统侧栏材质（Cursor/Codex 同款）。比平铺灰高级得多。
struct VibrancyBackground: NSViewRepresentable {
    var material: NSVisualEffectView.Material = .sidebar

    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = material
        view.blendingMode = .behindWindow
        view.state = .followsWindowActiveState
        view.isEmphasized = true
        return view
    }

    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {
        nsView.material = material
    }
}

/// 侧栏行：hover 才显底，选中极淡——避免「按钮感」
struct SoftRow: View {
    let title: String
    var icon: String? = nil
    var selected: Bool = false
    var prominent: Bool = false
    var trailingBusy: Bool = false
    let action: () -> Void

    @State private var hovering = false

    var body: some View {
        Button(action: action) {
            HStack(spacing: 9) {
                if let icon {
                    Image(systemName: icon)
                        .font(.system(size: 13.5, weight: .regular))
                        .foregroundStyle(selected || prominent ? CCCTheme.ink : CCCTheme.faint)
                        .frame(width: 18, alignment: .center)
                }
                Text(title)
                    .font(.system(size: 14, weight: selected || prominent ? .medium : .regular))
                    .foregroundStyle(selected || prominent ? CCCTheme.ink : CCCTheme.secondary)
                    .lineLimit(1)
                Spacer(minLength: 0)
                if trailingBusy {
                    ProgressView()
                        .controlSize(.mini)
                }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, prominent ? 8 : 6)
            .contentShape(Rectangle())
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(fill)
            )
        }
        .buttonStyle(.plain)
        .onHover { hovering = $0 }
        .animation(.easeOut(duration: 0.12), value: hovering)
        .accessibilityLabel(title)
        .accessibilityAddTraits(selected ? .isSelected : [])
        .accessibilityHint(prominent ? "主要操作" : "")
    }

    private var fill: Color {
        if selected { return CCCTheme.selected }
        if hovering { return CCCTheme.hover }
        return .clear
    }
}
