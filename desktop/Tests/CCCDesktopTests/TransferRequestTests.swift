import XCTest
@testable import CCCDesktop

/// 行为锁 · 请求层：TransferRequest 编码契约
/// 锁定 Desktop → Hub 实际收到的 JSON 字段形状（hub-api-v1 transfer 契约）
final class TransferRequestTests: XCTestCase {

    private func encodeObject(_ req: TransferRequest) throws -> [String: Any] {
        let data = try JSONEncoder().encode(req)
        let obj = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        return obj
    }

    func testAllFieldsEncoded() throws {
        let req = TransferRequest(
            project_id: "proj",
            thread_id: "proj::abc12345",
            title: "Fix login",
            goal: "Make login work",
            acceptance: ["A", "B"],
            pipeline: "dev",
            feasibility: "ok",
            feasibility_reason: "clear",
            executor_intent: "opencode",
            skills_hint: ["write-code"],
            skill_ref: "skills/write-code",
            prompt_ref: "prompts/write-code-prompt",
            plan_md: "plan body",
            complexity: "medium",
            client_request_id: "c1"
        )
        let obj = try encodeObject(req)

        XCTAssertEqual(obj["project_id"] as? String, "proj")
        XCTAssertEqual(obj["thread_id"] as? String, "proj::abc12345")
        XCTAssertEqual(obj["title"] as? String, "Fix login")
        XCTAssertEqual(obj["goal"] as? String, "Make login work")
        XCTAssertEqual(obj["acceptance"] as? [String], ["A", "B"])
        XCTAssertEqual(obj["pipeline"] as? String, "dev")
        XCTAssertEqual(obj["feasibility"] as? String, "ok")
        XCTAssertEqual(obj["feasibility_reason"] as? String, "clear")
        XCTAssertEqual(obj["executor_intent"] as? String, "opencode")
        XCTAssertEqual(obj["skills_hint"] as? [String], ["write-code"])
        XCTAssertEqual(obj["skill_ref"] as? String, "skills/write-code")
        XCTAssertEqual(obj["prompt_ref"] as? String, "prompts/write-code-prompt")
        XCTAssertEqual(obj["plan_md"] as? String, "plan body")
        XCTAssertEqual(obj["complexity"] as? String, "medium")
        XCTAssertEqual(obj["client_request_id"] as? String, "c1")
    }

    func testNilOptionalsOmittedFromJSON() throws {
        let req = TransferRequest(
            project_id: "p",
            thread_id: nil,
            title: "t",
            goal: "g",
            acceptance: [],
            pipeline: "dev",
            feasibility: "ok",
            feasibility_reason: nil,
            executor_intent: "opencode",
            skills_hint: [],
            skill_ref: "skills/write-code",
            prompt_ref: "prompts/write-code-prompt",
            plan_md: "",
            complexity: "medium",
            client_request_id: nil
        )
        let obj = try encodeObject(req)
        XCTAssertNil(obj["thread_id"])
        XCTAssertNil(obj["feasibility_reason"])
        XCTAssertNil(obj["client_request_id"])
        // 空数组仍显式编码（Hub 侧缺省语义：空数组 = 未提供 hints）
        XCTAssertEqual(obj["skills_hint"] as? [String], [])
        XCTAssertEqual(obj["acceptance"] as? [String], [])
    }

    func testFieldsPassThroughVerbatim() throws {
        // TransferRequest 是哑载体：超长 title 不在此截断（截断是 builder 层职责）
        let longTitle = String(repeating: "x", count: 100)
        let req = TransferRequest(
            project_id: "p", thread_id: "p::t", title: longTitle, goal: "g",
            acceptance: ["a"], pipeline: "dev", feasibility: "ok",
            feasibility_reason: nil, executor_intent: "opencode", skills_hint: [],
            skill_ref: "s", prompt_ref: "p", plan_md: "", complexity: "medium",
            client_request_id: "c"
        )
        let obj = try encodeObject(req)
        XCTAssertEqual(obj["title"] as? String, longTitle)
    }

    func testAllEncodingKeysAreSnakeCase() throws {
        let req = TransferRequest(
            project_id: "p", thread_id: "p::t", title: "t", goal: "g",
            acceptance: ["a"], pipeline: "dev", feasibility: "ok",
            feasibility_reason: nil, executor_intent: "opencode", skills_hint: [],
            skill_ref: "s", prompt_ref: "p", plan_md: "", complexity: "medium",
            client_request_id: "c"
        )
        let keys = try encodeObject(req).keys
        // 不允许出现 camelCase 键（Desktop → Hub 契约是 snake_case）
        XCTAssertFalse(keys.contains { $0.contains(where: \.isUppercase) })
        XCTAssertTrue(keys.contains("project_id"))
        XCTAssertTrue(keys.contains("executor_intent"))
        XCTAssertTrue(keys.contains("client_request_id"))
    }
}
