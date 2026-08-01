import Foundation

/// 转任务请求/载荷构建（纯函数；stage5 硬切换 skill/prompt ref 统一解析）。
/// 行为 = AppModel 三处内联构建原样搬迁：
/// - `outboxItem`：submitTransfer（表单 → outbox 持久化项）
/// - `gatePayload`：promoteIntentCardToBacklog（TransferDraft → gate dry-run 载荷）
/// - `request`：createManualEpic（ManualEpicForm → TransferRequest，字段原样）
enum TransferRequestBuilder {

    // MARK: - 规范化原语

    /// title：trim + Hub gate ≤80 软裁（submitTransfer / promote 用）
    static func normalizedTitle(_ raw: String) -> String {
        String(raw.trimmingCharacters(in: .whitespacesAndNewlines).prefix(80))
    }

    static func normalizedGoal(_ raw: String) -> String {
        raw.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    static func normalizedPipeline(_ raw: String) -> String {
        raw.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// complexity 归一：small/medium/large，否则 medium
    static func normalizedComplexity(_ raw: String) -> String {
        let cx = raw.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return ["small", "medium", "large"].contains(cx) ? cx : "medium"
    }

    static func resolvedSkillRef(executor: String, fallback: String?) -> String {
        SkillRefResolver.skillRef(forExecutor: executor, fallback: fallback)
    }

    static func resolvedPromptRef(skillRef: String) -> String {
        SkillRefResolver.promptRef(forSkill: skillRef)
    }

    // MARK: - outbox item（submitTransfer）

    static func outboxItem(
        projectId: String,
        threadId: String,
        form: TransferFormState,
        planBody: String,
        clientRequestId: String,
        savedAt: String
    ) -> LocalSessionStore.TransferOutboxItem {
        let skillRef = resolvedSkillRef(executor: form.executor, fallback: form.skillRef)
        return LocalSessionStore.TransferOutboxItem(
            client_request_id: clientRequestId,
            project_id: projectId,
            thread_id: threadId,
            title: normalizedTitle(form.title),
            goal: normalizedGoal(form.goal),
            acceptance: AcceptanceText.plainLines(form.acceptance),
            pipeline: normalizedPipeline(form.pipeline),
            feasibility: form.feasibility,
            feasibility_reason: form.feasibility == "blocked" ? form.feasibilityReason : nil,
            executor_intent: form.executor,
            plan_md: planBody,
            complexity: normalizedComplexity(form.complexity),
            bump_version: form.bumpVersion,
            human_note: form.humanNote.trimmingCharacters(in: .whitespacesAndNewlines),
            attempts: 0,
            saved_at: savedAt,
            skill_ref: skillRef,
            prompt_ref: resolvedPromptRef(skillRef: skillRef)
        )
    }

    // MARK: - gate dry-run payload（promoteIntentCardToBacklog）

    static func gatePayload(from draft: TransferDraft, projectId: String, supersedeGoals: Bool) -> [String: Any] {
        let title = normalizedTitle(draft.title)
        let goal = normalizedGoal(draft.goal)
        let skillRef = resolvedSkillRef(executor: draft.executorIntent, fallback: draft.skillRef)
        var payload: [String: Any] = [
            "project_id": projectId,
            "title": title,
            "goal": goal.isEmpty ? title : goal,
            "acceptance": draft.acceptanceLines,
            "pipeline": draft.pipeline,
            "feasibility": draft.feasibility,
            "feasibility_reason": draft.feasibilityReason,
            "executor_intent": draft.executorIntent,
            "skill_ref": skillRef,
            "prompt_ref": resolvedPromptRef(skillRef: skillRef),
            "complexity": draft.complexity,
            "bump_version": draft.bumpVersion,
            "plan_md": draft.planMd,
            "card_kind": "epic",
        ]
        if supersedeGoals {
            payload["supersede_goals"] = true
        }
        return payload
    }

    // MARK: - TransferRequest（createManualEpic；字段原样，验收行规范化）

    static func request(
        projectId: String,
        threadId: String?,
        form: ManualEpicForm,
        clientRequestId: String
    ) -> TransferRequest {
        let skillRef = resolvedSkillRef(executor: form.executor, fallback: nil)
        return TransferRequest(
            project_id: projectId,
            thread_id: threadId,
            title: form.title,
            goal: form.goal,
            acceptance: AcceptanceText.plainLines(form.acceptance),
            pipeline: form.pipeline,
            feasibility: "ok",
            feasibility_reason: nil,
            executor_intent: form.executor,
            skills_hint: [],
            skill_ref: skillRef,
            prompt_ref: resolvedPromptRef(skillRef: skillRef),
            plan_md: form.goal,
            complexity: form.complexity,
            client_request_id: clientRequestId
        )
    }
}
