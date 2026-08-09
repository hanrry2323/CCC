import SwiftUI
import AppKit

/// Claude 色调 + 现代中栏节奏（字号上调、对比加强，减轻糊眼）
enum CCCTheme {
    /// 对话区：略深暖色，贴近侧栏，避免刺眼白
    static let chatBg = DynamicColor.make(
        light: 0.948, 0.932, 0.908,
        dark: 0.12, 0.11, 0.10
    )
    static let sidebar = DynamicColor.make(
        light: 0.938, 0.920, 0.896,
        dark: 0.10, 0.09, 0.09
    )
    /// 输入框 / 卡片底
    static let surface = DynamicColor.make(
        light: 0.985, 0.978, 0.965,
        dark: 0.16, 0.15, 0.14
    )

    /// 正文更深，提高对比
    static let ink = DynamicColor.make(
        light: 0.10, 0.09, 0.08,
        dark: 0.90, 0.89, 0.88
    )
    static let secondary = DynamicColor.make(
        light: 0.34, 0.31, 0.28,
        dark: 0.70, 0.67, 0.64
    )
    static let faint = DynamicColor.make(
        light: 0.52, 0.48, 0.44,
        dark: 0.50, 0.47, 0.44
    )
    static let muted = DynamicColor.make(
        light: 0.34, 0.31, 0.28,
        dark: 0.65, 0.62, 0.59
    )

    static let accent = DynamicColor.make(
        light: 0.851, 0.455, 0.333,
        dark: 0.88, 0.52, 0.42
    )
    static let accentSoft = DynamicColor.make(
        light: 0.90, 0.58, 0.45,
        dark: 0.40, 0.25, 0.18
    )

    static let hover = DynamicColor.make(
        light: 0.10, 0.09, 0.08, alphaL: 0.06,
        dark: 1.0, 1.0, 1.0, alphaD: 0.08
    )
    static let selected = DynamicColor.make(
        light: 0.10, 0.09, 0.08, alphaL: 0.10,
        dark: 1.0, 1.0, 1.0, alphaD: 0.12
    )
    static let border = DynamicColor.make(
        light: 0.10, 0.09, 0.08, alphaL: 0.12,
        dark: 1.0, 1.0, 1.0, alphaD: 0.15
    )
    static let borderStrong = DynamicColor.make(
        light: 0.10, 0.09, 0.08, alphaL: 0.18,
        dark: 1.0, 1.0, 1.0, alphaD: 0.22
    )

    static let bubbleUser = DynamicColor.make(
        light: 0.88, 0.83, 0.77,
        dark: 0.26, 0.23, 0.20
    )
    static let bubbleAssistant = DynamicColor.make(
        light: 0.978, 0.968, 0.952,
        dark: 0.15, 0.14, 0.13
    )

    static let nodePending = DynamicColor.make(
        light: 0.72, 0.66, 0.60,
        dark: 0.45, 0.42, 0.38
    )
    static let nodeRunning = DynamicColor.make(
        light: 0.851, 0.455, 0.333,
        dark: 0.88, 0.52, 0.42
    )
    static let nodeDone = DynamicColor.make(
        light: 0.35, 0.55, 0.40,
        dark: 0.42, 0.68, 0.48
    )
    static let nodeWarn = DynamicColor.make(
        light: 0.82, 0.54, 0.18,
        dark: 0.88, 0.62, 0.22
    )
    static let nodeFail = DynamicColor.make(
        light: 0.78, 0.28, 0.22,
        dark: 0.85, 0.35, 0.28
    )

    static let unread = DynamicColor.make(
        light: 0.20, 0.48, 0.95,
        dark: 0.35, 0.58, 0.98
    )

    /// 顶栏调用次数：有调用绿 +N；零次红 0
    static let usageActive = DynamicColor.make(
        light: 0.28, 0.58, 0.38,
        dark: 0.35, 0.68, 0.45
    )
    static let usageIdle = DynamicColor.make(
        light: 0.78, 0.28, 0.22,
        dark: 0.85, 0.35, 0.28
    )

    // MARK: - State Tone colors
    static let tonePendingFG = DynamicColor.make(light: 0.42, 0.40, 0.37, dark: 0.75, 0.72, 0.68)
    static let tonePendingBG = DynamicColor.make(light: 0.92, 0.91, 0.89, dark: 0.22, 0.21, 0.20)
    static let tonePendingBar = DynamicColor.make(light: 0.69, 0.67, 0.62, dark: 0.45, 0.43, 0.40)

    static let toneRunningFG = DynamicColor.make(light: 0.24, 0.42, 0.27, dark: 0.60, 0.85, 0.65)
    static let toneRunningBG = DynamicColor.make(light: 0.91, 0.94, 0.89, dark: 0.15, 0.25, 0.18)
    static let toneRunningBar = DynamicColor.make(light: 0.35, 0.60, 0.43, dark: 0.40, 0.70, 0.50)

    static let toneWrittenFG = DynamicColor.make(light: 0.29, 0.42, 0.35, dark: 0.65, 0.85, 0.75)
    static let toneWrittenBG = DynamicColor.make(light: 0.89, 0.92, 0.91, dark: 0.16, 0.24, 0.22)
    static let toneWrittenBar = DynamicColor.make(light: 0.42, 0.54, 0.48, dark: 0.45, 0.65, 0.55)

    static let toneClosedFG = DynamicColor.make(light: 0.29, 0.31, 0.34, dark: 0.70, 0.72, 0.75)
    static let toneClosedBG = DynamicColor.make(light: 0.88, 0.90, 0.91, dark: 0.18, 0.19, 0.20)
    static let toneClosedBar = DynamicColor.make(light: 0.54, 0.56, 0.60, dark: 0.45, 0.47, 0.50)

    static let toneReturnedFG = DynamicColor.make(light: 0.64, 0.23, 0.17, dark: 0.90, 0.50, 0.45)
    static let toneReturnedBG = DynamicColor.make(light: 0.95, 0.87, 0.85, dark: 0.28, 0.16, 0.15)
    static let toneReturnedBar = DynamicColor.make(light: 0.77, 0.36, 0.29, dark: 0.75, 0.45, 0.40)

    /// 现代式：偏细字重 + 略松行距
    static let title = Font.system(size: 22, weight: .light, design: .serif)
    static let body = Font.system(size: 14.5, weight: .light, design: .default)
    static let callout = Font.system(size: 13, weight: .light, design: .default)
    static let caption = Font.system(size: 12, weight: .light, design: .default)
    /// 正文行距增量（pt）
    static let bodyLineSpacing: CGFloat = 4
    /// 消息列表块间距
    static let messageStackSpacing: CGFloat = 22

    /// 现代式：输入区略扁、内容区更宽
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

// MARK: - Dynamic Color Adaptor
public struct DynamicColor {
    public static func make(
        light rL: Double, _ gL: Double, _ bL: Double, alphaL: Double = 1.0,
        dark rD: Double, _ gD: Double, _ bD: Double, alphaD: Double = 1.0
    ) -> Color {
        Color(nsColor: NSColor(name: nil) { appearance in
            let isDark = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            if isDark {
                return NSColor(red: CGFloat(rD), green: CGFloat(gD), blue: CGFloat(bD), alpha: CGFloat(alphaD))
            } else {
                return NSColor(red: CGFloat(rL), green: CGFloat(gL), blue: CGFloat(bL), alpha: CGFloat(alphaL))
            }
        })
    }
}

// MARK: - Pow Signature Animations (Spring Scale-Effects)
public struct PowHoverSpringModifier: ViewModifier {
    @State private var isHovered = false
    
    public init() {}
    
    public func body(content: Content) -> some View {
        content
            .scaleEffect(isHovered ? 1.02 : 1.0)
            .animation(.spring(response: 0.3, dampingFraction: 0.5, blendDuration: 0), value: isHovered)
            .onHover { hovering in
                isHovered = hovering
            }
    }
}

public struct PowSpringClickModifier: ViewModifier {
    @State private var isPressed = false
    
    public init() {}
    
    public func body(content: Content) -> some View {
        content
            .scaleEffect(isPressed ? 0.95 : 1.0)
            .animation(.spring(response: 0.2, dampingFraction: 0.4, blendDuration: 0), value: isPressed)
            .simultaneousGesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in isPressed = true }
                    .onEnded { _ in isPressed = false }
            )
    }
}

public struct PowSpringButtonStyle: ButtonStyle {
    public init() {}
    
    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.95 : 1.0)
            .animation(.spring(response: 0.25, dampingFraction: 0.5, blendDuration: 0), value: configuration.isPressed)
    }
}

extension ButtonStyle where Self == PowSpringButtonStyle {
    public static var powSpring: PowSpringButtonStyle { PowSpringButtonStyle() }
}

extension View {
    public func powHoverSpring() -> some View {
        self.modifier(PowHoverSpringModifier())
    }
    
    public func powSpringClick() -> some View {
        self.modifier(PowSpringClickModifier())
    }
    
    public func shimmer() -> some View {
        self.modifier(ShimmerModifier())
    }
    
    /// 关键面板磨砂质感：统一走系统 material（macOS 12+ 稳定编译）。
    /// macOS 15 原生 `.glassEffect` 是 ViewModifier（非 `.background(_:)` 可用的 View/ShapeStyle），
    /// 且桌面仓 SDK 目前为 macOS 13（Package.swift 目标 .macOS(.v13)），无法编译期引用该符号；
    /// 待 SDK/部署目标升到 15 后再接线原生玻璃，此处以 `.ultraThinMaterial` 兜底（验收标准 3 既有的回退路径）。
    public func glassEffect() -> some View {
        self.background(.ultraThinMaterial)
    }
}

// MARK: - Shimmer Loading Animation
public struct ShimmerModifier: ViewModifier {
    @State private var phase: CGFloat = 0
    
    public init() {}
    
    public func body(content: Content) -> some View {
        content
            .overlay(
                GeometryReader { geo in
                    LinearGradient(
                        colors: [.clear, Color.white.opacity(0.25), .clear],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                    .scaleEffect(1.5)
                    .offset(x: -geo.size.width + (phase * geo.size.width * 2))
                    .onAppear {
                        withAnimation(.linear(duration: 1.6).repeatForever(autoreverses: false)) {
                            phase = 1.0
                        }
                    }
                }
                .mask(content)
            )
    }
}

// MARK: - SkeletonUI Shimmer Block
public struct SkeletonView: View {
    var width: CGFloat? = nil
    var height: CGFloat = 16
    var cornerRadius: CGFloat = 4
    
    public init(width: CGFloat? = nil, height: CGFloat = 16, cornerRadius: CGFloat = 4) {
        self.width = width
        self.height = height
        self.cornerRadius = cornerRadius
    }
    
    public var body: some View {
        RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
            .fill(CCCTheme.hover)
            .frame(width: width, height: height)
            .shimmer()
    }
}

// MARK: - FluidGradient Animated Mesh Background
public struct FluidGradientView: View {
    @State private var animate = false
    
    public init() {}
    
    public var body: some View {
        let colors: [Color] = [
            CCCTheme.accent.opacity(0.12),
            CCCTheme.unread.opacity(0.08),
            CCCTheme.bubbleUser.opacity(0.1),
            CCCTheme.chatBg.opacity(0.15)
        ]
        
        LinearGradient(
            colors: colors,
            startPoint: animate ? .topLeading : .bottomLeading,
            endPoint: animate ? .bottomTrailing : .topTrailing
        )
        .animation(.linear(duration: 8.0).repeatForever(autoreverses: true), value: animate)
        .onAppear {
            animate = true
        }
    }
}
