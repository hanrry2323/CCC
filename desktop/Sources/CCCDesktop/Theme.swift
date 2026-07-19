import SwiftUI

/// Claude 色调 + Cursor 中栏节奏
enum CCCTheme {
    /// 对话区：略深暖色，贴近侧栏，避免刺眼白
    static let chatBg = Color(red: 0.955, green: 0.940, blue: 0.918)
    static let sidebar = Color(red: 0.945, green: 0.929, blue: 0.906)
    /// 输入框 / 卡片底：降白度
    static let surface = Color(red: 0.978, green: 0.968, blue: 0.952)

    static let ink = Color(red: 0.165, green: 0.145, blue: 0.125)
    static let secondary = Color(red: 0.42, green: 0.38, blue: 0.34)
    static let faint = Color(red: 0.62, green: 0.57, blue: 0.52)
    static let muted = Color(red: 0.42, green: 0.38, blue: 0.34)

    static let accent = Color(red: 0.851, green: 0.455, blue: 0.333)
    static let accentSoft = Color(red: 0.90, green: 0.58, blue: 0.45)

    static let hover = Color(red: 0.165, green: 0.145, blue: 0.125).opacity(0.05)
    static let selected = Color(red: 0.165, green: 0.145, blue: 0.125).opacity(0.08)
    static let border = Color(red: 0.165, green: 0.145, blue: 0.125).opacity(0.10)
    static let borderStrong = Color(red: 0.165, green: 0.145, blue: 0.125).opacity(0.16)

    static let bubbleUser = Color(red: 0.905, green: 0.860, blue: 0.805)
    /// 助手气泡：浅暖灰褐
    static let bubbleAssistant = Color(red: 0.968, green: 0.955, blue: 0.935)

    static let nodePending = Color(red: 0.72, green: 0.66, blue: 0.60)
    static let nodeRunning = Color(red: 0.851, green: 0.455, blue: 0.333)
    static let nodeDone = Color(red: 0.35, green: 0.55, blue: 0.40)
    static let nodeFail = Color(red: 0.78, green: 0.28, blue: 0.22)

    /// 顶栏调用次数：有调用绿 +N；零次红 0
    static let usageActive = Color(red: 0.28, green: 0.58, blue: 0.38)
    static let usageIdle = Color(red: 0.78, green: 0.28, blue: 0.22)

    static let title = Font.system(size: 22, weight: .medium, design: .serif)
    static let body = Font.system(size: 14.5, weight: .regular, design: .default)
    static let callout = Font.system(size: 13, weight: .regular, design: .default)
    static let caption = Font.system(size: 11, weight: .medium, design: .default)

    /// Cursor 式：输入区略扁、内容区更宽
    static let radiusComposer: CGFloat = 12
    static let chatMaxWidth: CGFloat = 760
    /// unified toolbar 已占顶栏，侧栏顶距收紧
    static let trafficLightInset: CGFloat = 4
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
