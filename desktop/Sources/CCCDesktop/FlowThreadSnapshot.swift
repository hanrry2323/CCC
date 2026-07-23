import Foundation

/// 单会话右栏编排快照（本地缓存，与对话消息隔离）
struct FlowThreadSnapshot: Codable, Equatable {
    var epicId: String?
    var epic: FlowEpic?
    var works: [FlowWork]
    var headline: String
    var recentEpics: [FlowEpicRef]
    var emptyMessage: String
    var fanoutHint: String?
    /// Phase9：abnormal / user_stage=failed 时右栏止损条（复制给对话 → Agent）
    var stopLossHint: String?
}
