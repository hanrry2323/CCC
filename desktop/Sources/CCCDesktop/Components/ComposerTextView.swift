import AppKit
import SwiftUI

/// Codex/Cursor 式输入：回车发送 · Shift+回车换行 · 可点选聚焦 · 矮条高度
///
/// IME 注意：中文等组字期间 `string` 含 marked 拼音，但 SwiftUI `@Binding` 往往仍是上屏前的正文。
/// 若 `updateNSView` 用 binding 回写 `tv.string`，会直接打断输入法（表现为打到十几/二十来字「闪一下」丢拼音）。
struct ComposerTextView: NSViewRepresentable {
    @Binding var text: String
    var placeholder: String = "问任何问题…"
    var isEnabled: Bool = true
    var onSubmit: (() -> Void)?

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeNSView(context: Context) -> ComposerScrollView {
        let scroll = ComposerScrollView()
        scroll.drawsBackground = false
        scroll.borderType = .noBorder
        scroll.hasVerticalScroller = true
        scroll.hasHorizontalScroller = false
        scroll.autohidesScrollers = true
        scroll.scrollerStyle = .overlay

        let tv = CCCComposerNSTextView()
        tv.delegate = context.coordinator
        tv.isRichText = false
        tv.allowsUndo = true
        tv.isEditable = isEnabled
        tv.isSelectable = true
        tv.font = .systemFont(ofSize: 14)
        tv.textColor = .labelColor
        tv.insertionPointColor = .labelColor
        tv.backgroundColor = .clear
        tv.drawsBackground = false
        tv.focusRingType = .none
        tv.textContainerInset = NSSize(width: 4, height: 6)
        tv.isHorizontallyResizable = false
        tv.isVerticallyResizable = true
        tv.autoresizingMask = [.width]
        tv.textContainer?.widthTracksTextView = true
        tv.textContainer?.containerSize = NSSize(
            width: 0,
            height: CGFloat.greatestFiniteMagnitude
        )
        tv.minSize = .zero
        tv.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        tv.string = text
        tv.placeholderText = placeholder
        tv.onSubmit = {
            context.coordinator.parent.onSubmit?()
        }
        context.coordinator.textView = tv
        context.coordinator.lastEmitted = text
        scroll.documentView = tv
        scroll.composerTextView = tv
        return scroll
    }

    func updateNSView(_ scroll: ComposerScrollView, context: Context) {
        context.coordinator.parent = self
        guard let tv = scroll.composerTextView else { return }
        tv.placeholderText = placeholder
        tv.isEditable = isEnabled
        tv.onSubmit = {
            context.coordinator.parent.onSubmit?()
        }

        // 组字中禁止任何 string 回写（即使内容「看起来」该同步）
        if tv.hasMarkedText() {
            return
        }

        // 仅外部改动（发送清空、失败回填）才写回；避免与 textDidChange 闭环
        guard tv.string != text else {
            context.coordinator.lastEmitted = text
            return
        }
        let selected = tv.selectedRanges
        tv.string = text
        tv.selectedRanges = selected
        context.coordinator.lastEmitted = text
        tv.needsDisplay = true
    }

    final class Coordinator: NSObject, NSTextViewDelegate {
        var parent: ComposerTextView
        weak var textView: CCCComposerNSTextView?
        /// 最近一次推给 SwiftUI 的正文（不含正在组字的 marked）
        var lastEmitted: String = ""

        init(_ parent: ComposerTextView) { self.parent = parent }

        func textDidChange(_ notification: Notification) {
            guard let tv = notification.object as? NSTextView else { return }
            // 组字中不推 Binding：否则父视图刷新 → updateNSView 用旧 Binding 冲掉拼音
            if tv.hasMarkedText() {
                return
            }
            let next = tv.string
            guard next != lastEmitted else { return }
            lastEmitted = next
            parent.text = next
        }
    }
}

/// 点击空白也能把焦点交给内部 TextView
final class ComposerScrollView: NSScrollView {
    weak var composerTextView: CCCComposerNSTextView?

    override func mouseDown(with event: NSEvent) {
        window?.makeFirstResponder(composerTextView)
        super.mouseDown(with: event)
    }
}

final class CCCComposerNSTextView: NSTextView {
    var onSubmit: (() -> Void)?
    var placeholderText: String = "问任何问题…"
    /// 同一击回车：IME 上屏后还会走 insertNewline，用此挡误发
    private var suppressSubmitFromIME = false

    override var acceptsFirstResponder: Bool { true }
    override var canBecomeKeyView: Bool { true }

    override func becomeFirstResponder() -> Bool {
        let ok = super.becomeFirstResponder()
        needsDisplay = true
        return ok
    }

    override func mouseDown(with event: NSEvent) {
        window?.makeFirstResponder(self)
        super.mouseDown(with: event)
    }

    /// 回车发送；Shift+回车换行。输入法组字中（中文拼音等）回车只上屏，不发送。
    override func keyDown(with event: NSEvent) {
        let isReturn = event.keyCode == 36 || event.keyCode == 76
        if isReturn {
            if hasMarkedText() {
                suppressSubmitFromIME = true
                super.keyDown(with: event)
                DispatchQueue.main.async { [weak self] in
                    self?.suppressSubmitFromIME = false
                }
                return
            }
            if event.modifierFlags.contains(.shift) {
                insertText("\n", replacementRange: selectedRange())
                return
            }
            onSubmit?()
            return
        }
        super.keyDown(with: event)
    }

    override func insertNewline(_ sender: Any?) {
        if suppressSubmitFromIME || hasMarkedText() {
            suppressSubmitFromIME = false
            return
        }
        if NSEvent.modifierFlags.contains(.shift) {
            insertText("\n", replacementRange: selectedRange())
        } else {
            onSubmit?()
        }
    }

    override func insertNewlineIgnoringFieldEditor(_ sender: Any?) {
        insertText("\n", replacementRange: selectedRange())
    }

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        guard string.isEmpty else { return }
        let attrs: [NSAttributedString.Key: Any] = [
            .font: font ?? NSFont.systemFont(ofSize: 14),
            .foregroundColor: NSColor.tertiaryLabelColor,
        ]
        let inset = textContainerInset
        let r = NSRect(
            x: inset.width + 5,
            y: inset.height,
            width: max(0, bounds.width - inset.width * 2 - 10),
            height: 20
        )
        (placeholderText as NSString).draw(in: r, withAttributes: attrs)
    }
}
