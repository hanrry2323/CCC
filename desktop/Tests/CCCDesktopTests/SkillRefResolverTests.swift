import XCTest
@testable import CCCDesktop

/// 行为锁 · 映射层：SkillRefResolver
/// 锁定 executor_intent → skill_ref / skill_ref → prompt_ref 的映射契约
/// （对齐 transfer_gate.py _EXECUTOR_INTENT_TO_SKILL_REF 与 web dispatchCard.js SKILL_TO_PROMPT_REF）
final class SkillRefResolverTests: XCTestCase {

    // MARK: - skillRef(forExecutor:fallback:)

    func testExplicitFallbackWins() {
        XCTAssertEqual(
            SkillRefResolver.skillRef(forExecutor: "opencode", fallback: "skills/custom"),
            "skills/custom"
        )
        // 即使 executor 也有映射，显式 fallback 优先
        XCTAssertEqual(
            SkillRefResolver.skillRef(forExecutor: "python", fallback: "skills/custom"),
            "skills/custom"
        )
    }

    func testFallbackTrimmedAndWhitespaceTreatedAsEmpty() {
        XCTAssertEqual(
            SkillRefResolver.skillRef(forExecutor: "opencode", fallback: "  skills/x  "),
            "skills/x"
        )
        // 全空白 fallback = 未提供 → 走 executor 映射
        XCTAssertEqual(
            SkillRefResolver.skillRef(forExecutor: "python", fallback: "   "),
            "skills/script-seed"
        )
    }

    func testExecutorMapping() {
        XCTAssertEqual(SkillRefResolver.skillRef(forExecutor: "opencode", fallback: nil), "skills/write-code")
        XCTAssertEqual(SkillRefResolver.skillRef(forExecutor: "python", fallback: nil), "skills/script-seed")
        XCTAssertEqual(SkillRefResolver.skillRef(forExecutor: "cli", fallback: nil), "skills/ops")
        XCTAssertEqual(SkillRefResolver.skillRef(forExecutor: "ollama", fallback: nil), "skills/write-code")
        XCTAssertEqual(SkillRefResolver.skillRef(forExecutor: "auto", fallback: nil), "skills/write-code")
        XCTAssertEqual(SkillRefResolver.skillRef(forExecutor: "bug", fallback: nil), "skills/bug-fix")
    }

    func testUnknownExecutorDefaultsToWriteCode() {
        XCTAssertEqual(SkillRefResolver.skillRef(forExecutor: "nonsense", fallback: nil), "skills/write-code")
        XCTAssertEqual(SkillRefResolver.skillRef(forExecutor: "", fallback: nil), "skills/write-code")
    }

    func testExecutorCaseInsensitive() {
        XCTAssertEqual(SkillRefResolver.skillRef(forExecutor: "OpenCode", fallback: nil), "skills/write-code")
        XCTAssertEqual(SkillRefResolver.skillRef(forExecutor: "PYTHON", fallback: nil), "skills/script-seed")
    }

    // MARK: - promptRef(forSkill:)

    func testPromptRefMapping() {
        XCTAssertEqual(SkillRefResolver.promptRef(forSkill: "skills/write-code"), "prompts/write-code-prompt")
        XCTAssertEqual(SkillRefResolver.promptRef(forSkill: "skills/bug-fix"), "prompts/bug-fix-prompt")
        XCTAssertEqual(SkillRefResolver.promptRef(forSkill: "skills/code-review"), "prompts/code-review-prompt")
        XCTAssertEqual(SkillRefResolver.promptRef(forSkill: "skills/ops"), "prompts/write-code-prompt")
        XCTAssertEqual(SkillRefResolver.promptRef(forSkill: "skills/script-seed"), "prompts/write-code-prompt")
    }

    func testUnknownSkillDefaultsToWriteCodePrompt() {
        XCTAssertEqual(SkillRefResolver.promptRef(forSkill: "skills/nope"), "prompts/write-code-prompt")
        XCTAssertEqual(SkillRefResolver.promptRef(forSkill: ""), "prompts/write-code-prompt")
    }

    func testPromptRefTrimsInput() {
        XCTAssertEqual(SkillRefResolver.promptRef(forSkill: "  skills/bug-fix  "), "prompts/bug-fix-prompt")
    }

    // MARK: - defaults

    func testDefaults() {
        XCTAssertEqual(SkillRefResolver.defaultSkillRef, "skills/write-code")
        XCTAssertEqual(SkillRefResolver.defaultPromptRef, "prompts/write-code-prompt")
    }

    /// 三处 AppModel 内联构建用的组合路径（stage5 硬切换契约）
    func testCompositeResolve() {
        // executor=python 无显式 → script-seed + write-code-prompt
        let s = SkillRefResolver.skillRef(forExecutor: "python", fallback: nil)
        XCTAssertEqual(s, "skills/script-seed")
        XCTAssertEqual(SkillRefResolver.promptRef(forSkill: s), "prompts/write-code-prompt")
        // executor=bug → bug-fix + bug-fix-prompt
        let b = SkillRefResolver.skillRef(forExecutor: "bug", fallback: nil)
        XCTAssertEqual(b, "skills/bug-fix")
        XCTAssertEqual(SkillRefResolver.promptRef(forSkill: b), "prompts/bug-fix-prompt")
        // 显式 skill_ref → 对应 prompt_ref
        let explicit = SkillRefResolver.skillRef(forExecutor: "opencode", fallback: "skills/code-review")
        XCTAssertEqual(explicit, "skills/code-review")
        XCTAssertEqual(SkillRefResolver.promptRef(forSkill: explicit), "prompts/code-review-prompt")
    }
}
