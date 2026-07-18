import SwiftUI

/// 高级感：系统材质 + 发丝线 + 精确字重 + 留白。不堆阴影/圆角/胶囊。
enum CCCTheme {
    static let chatBg = Color(nsColor: .textBackgroundColor)
    static let ink = Color(nsColor: .labelColor)
    static let secondary = Color(nsColor: .secondaryLabelColor)
    static let faint = Color(nsColor: .tertiaryLabelColor)
    static let muted = Color(nsColor: .secondaryLabelColor)

    /// 主操作近黑（跟随系统，暗色下自动变浅）
    static let accent = Color(nsColor: .labelColor)
    static let accentSoft = Color(red: 0.22, green: 0.42, blue: 0.95)

    static let hover = Color.primary.opacity(0.05)
    static let selected = Color.primary.opacity(0.08)
    static let border = Color.primary.opacity(0.08)
    static let borderStrong = Color.primary.opacity(0.12)

    static let bubbleUser = Color.primary.opacity(0.06)

    static let nodePending = Color.secondary.opacity(0.55)
    static let nodeRunning = Color(red: 0.22, green: 0.42, blue: 0.95)
    static let nodeDone = Color(red: 0.20, green: 0.55, blue: 0.38)
    static let nodeFail = Color(red: 0.86, green: 0.28, blue: 0.24)

    static let title = Font.system(size: 28, weight: .semibold, design: .default)
    static let body = Font.system(size: 15, weight: .regular, design: .default)
    static let callout = Font.system(size: 13, weight: .regular, design: .default)
    static let caption = Font.system(size: 11, weight: .medium, design: .default)

    static let radiusComposer: CGFloat = 18
    static let chatMaxWidth: CGFloat = 720
    /// 隐藏标题栏后，为交通灯预留
    static let trafficLightInset: CGFloat = 52
}

extension View {
    func cccHairline(_ edges: Edge.Set = .trailing) -> some View {
        overlay {
            if edges.contains(.trailing) {
                HStack {
                    Spacer(minLength: 0)
                    Rectangle().fill(CCCTheme.border).frame(width: 1)
                }
            }
            if edges.contains(.leading) {
                HStack {
                    Rectangle().fill(CCCTheme.border).frame(width: 1)
                    Spacer(minLength: 0)
                }
            }
            if edges.contains(.bottom) {
                VStack {
                    Spacer(minLength: 0)
                    Rectangle().fill(CCCTheme.border).frame(height: 1)
                }
            }
        }
    }
}
