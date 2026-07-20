import SwiftUI

/// Claude 色调 + Cursor 中栏节奏（字号上调、对比加强，减轻糊眼）
enum CCCTheme {
    /// 对话区：略深暖色，贴近侧栏，避免刺眼白
    static let chatBg = Color(red: 0.948, green: 0.932, blue: 0.908)
    static let sidebar = Color(red: 0.938, green: 0.920, blue: 0.896)
    /// 输入框 / 卡片底
    static let surface = Color(red: 0.985, green: 0.978, blue: 0.965)

    /// 正文更深，提高对比
    static let ink = Color(red: 0.10, green: 0.09, blue: 0.08)
    static let secondary = Color(red: 0.34, green: 0.31, blue: 0.28)
    static let faint = Color(red: 0.52, green: 0.48, blue: 0.44)
    static let muted = Color(red: 0.34, green: 0.31, blue: 0.28)

    static let accent = Color(red: 0.851, green: 0.455, blue: 0.333)
    static let accentSoft = Color(red: 0.90, green: 0.58, blue: 0.45)

    static let hover = Color(red: 0.10, green: 0.09, blue: 0.08).opacity(0.06)
    static let selected = Color(red: 0.10, green: 0.09, blue: 0.08).opacity(0.10)
    static let border = Color(red: 0.10, green: 0.09, blue: 0.08).opacity(0.12)
    static let borderStrong = Color(red: 0.10, green: 0.09, blue: 0.08).opacity(0.18)

    static let bubbleUser = Color(red: 0.88, green: 0.83, blue: 0.77)
    static let bubbleAssistant = Color(red: 0.978, green: 0.968, blue: 0.952)

    static let nodePending = Color(red: 0.72, green: 0.66, blue: 0.60)
    static let nodeRunning = Color(red: 0.851, green: 0.455, blue: 0.333)
    static let nodeDone = Color(red: 0.35, green: 0.55, blue: 0.40)
    static let nodeFail = Color(red: 0.78, green: 0.28, blue: 0.22)

    static let unread = Color(red: 0.20, green: 0.48, blue: 0.95)

    /// 顶栏调用次数：有调用绿 +N；零次红 0
    static let usageActive = Color(red: 0.28, green: 0.58, blue: 0.38)
    static let usageIdle = Color(red: 0.78, green: 0.28, blue: 0.22)

    /// Cursor 式：偏细字重 + 略松行距
    static let title = Font.system(size: 22, weight: .light, design: .serif)
    static let body = Font.system(size: 14.5, weight: .light, design: .default)
    static let callout = Font.system(size: 13, weight: .light, design: .default)
    static let caption = Font.system(size: 12, weight: .light, design: .default)
    /// 正文行距增量（pt）
    static let bodyLineSpacing: CGFloat = 4
    /// 消息列表块间距
    static let messageStackSpacing: CGFloat = 22

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
