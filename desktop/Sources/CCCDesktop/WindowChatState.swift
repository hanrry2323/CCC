import Foundation
import SwiftUI

/// 每个 macOS 窗口独立的项目焦点（多窗可同时看不同项目、并行流式）。
/// 共享 AppModel 的 threadMessages / chatTasks；本对象只绑「本窗在看谁」。
@MainActor
final class WindowChatState: ObservableObject {
    @Published var projectId: String?
}
