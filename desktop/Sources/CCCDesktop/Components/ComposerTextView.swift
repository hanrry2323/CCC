import AppKit
import SwiftUI

/// 可输入的矮输入框：直接包 NSTextView（不用 ScrollView 外壳），点击即聚焦。
struct ComposerTextView: NSViewRepresentable {
    @Binding var text: String
    var placeholder: String = "问任何问题…"
    var onCommandReturn: (() -> Void)?

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeNSView(context: Context) -> CCCComposerNSTextView {
        let tv = CCCComposerNSTextView()
        tv.delegate = context.coordinator
        tv.isRichText = false
        tv.allowsUndo = true
        tv.isEditable = true
        tv.isSelectable = true
        tv.isFieldEditor = false
        tv.font = .systemFont(ofSize: 14)
        tv.textColor = .labelColor
        tv.insertionPointColor = .labelColor
        tv.backgroundColor = .clear
        tv.drawsBackground = false
        tv.focusRingType = .none
        tv.textContainerInset = NSSize(width: 0, height: 4)
        tv.isHorizontallyResizable = true
        tv.isVerticallyResizable = true
        tv.autoresizingMask = [.width, .height]
        tv.textContainer?.widthTracksTextView = true
        tv.textContainer?.heightTracksTextView = false
        tv.textContainer?.lineFragmentPadding = 0
        tv.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        tv.minSize = .zero
        tv.string = text
        tv.placeholderText = placeholder
        tv.onCommandReturn = { context.coordinator.parent.onCommandReturn?() }
        context.coordinator.textView = tv
        return tv
    }

    func updateNSView(_ tv: CCCComposerNSTextView, context: Context) {
        context.coordinator.parent = self
        tv.placeholderText = placeholder
        tv.onCommandReturn = { context.coordinator.parent.onCommandReturn?() }
        if tv.string != text {
            let ranges = tv.selectedRanges
            tv.string = text
            tv.selectedRanges = ranges
        }
    }

    final class Coordinator: NSObject, NSTextViewDelegate {
        var parent: ComposerTextView
        weak var textView: CCCComposerNSTextView?

        init(_ parent: ComposerTextView) { self.parent = parent }

        func textDidChange(_ notification: Notification) {
            guard let tv = notification.object as? NSTextView else { return }
            parent.text = tv.string
        }
    }
}

final class CCCComposerNSTextView: NSTextView {
    var onCommandReturn: (() -> Void)?
    var placeholderText: String = "问任何问题…"

    override var acceptsFirstResponder: Bool { true }

    override func becomeFirstResponder() -> Bool {
        let ok = super.becomeFirstResponder()
        needsDisplay = true
        return ok
    }

    override func mouseDown(with event: NSEvent) {
        window?.makeFirstResponder(self)
        super.mouseDown(with: event)
    }

    override func keyDown(with event: NSEvent) {
        if event.modifierFlags.contains(.command),
           event.charactersIgnoringModifiers == "\r" {
            onCommandReturn?()
            return
        }
        super.keyDown(with: event)
    }

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        guard string.isEmpty else { return }
        let attrs: [NSAttributedString.Key: Any] = [
            .font: font ?? NSFont.systemFont(ofSize: 14),
            .foregroundColor: NSColor.tertiaryLabelColor,
        ]
        let r = bounds.insetBy(dx: textContainerInset.width, dy: textContainerInset.height)
        (placeholderText as NSString).draw(in: r, withAttributes: attrs)
    }
}
