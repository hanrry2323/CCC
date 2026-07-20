import Foundation
import SwiftUI

/// 每个 macOS 窗口独立的项目焦点与线程选择（多窗可同时看不同项目/线程、并行流式）。
/// 对齐 OpenCode：UI 按 sessionID 绑定；共享 AppModel 的 `threadMessages[tid]` map，
/// 本对象只绑「本窗在看谁」。禁止用全局 `chat.messages` 当显示源。
@MainActor
final class WindowChatState: ObservableObject {
    @Published var projectId: String?
    /// 本窗选中的具体线程（多会话）
    @Published var threadId: String?
    /// 每窗独立导航（对话 / 看板 / 运维），禁止全局 destination 串窗
    @Published var destination: SidebarDestination = .chat

    /// 设置项目时自动选中最近线程；无活动线程则 threadId=nil（禁止绑已存档的 ::main）
    func bindProject(_ pid: String, availableThreads: [DesktopThread]) {
        projectId = pid
        if threadId == nil || !availableThreads.contains(where: { $0.thread_id == threadId }) {
            threadId = availableThreads.first?.thread_id
        }
    }
}
