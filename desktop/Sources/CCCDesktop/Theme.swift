import SwiftUI

enum CCCTheme {
    static let bg = Color(red: 0.98, green: 0.96, blue: 0.93)
    static let panel = Color(red: 0.96, green: 0.94, blue: 0.90)
    static let ink = Color(red: 0.16, green: 0.14, blue: 0.12)
    static let muted = Color(red: 0.45, green: 0.40, blue: 0.36)
    static let accent = Color(red: 0.78, green: 0.42, blue: 0.22)
    static let border = Color(red: 0.86, green: 0.82, blue: 0.76)
    static let card = Color.white.opacity(0.78)
    static let rail = Color(red: 0.94, green: 0.91, blue: 0.86)
    static let nodePending = Color(red: 0.72, green: 0.68, blue: 0.62)
    static let nodeRunning = Color(red: 0.85, green: 0.55, blue: 0.25)
    static let nodeDone = Color(red: 0.35, green: 0.55, blue: 0.40)
    static let nodeFail = Color(red: 0.70, green: 0.28, blue: 0.22)

    static let brandFont = Font.system(size: 20, weight: .semibold, design: .serif)
    static let bodyFont = Font.system(size: 14, weight: .regular, design: .default)
    static let mono = Font.system(size: 11, weight: .medium, design: .monospaced)
}
