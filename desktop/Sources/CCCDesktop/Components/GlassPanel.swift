import SwiftUI

struct ToastBanner: View {
    let message: String
    var isError: Bool = false
    let onDismiss: () -> Void

    var body: some View {
        HStack(spacing: 10) {
            Text(message)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(CCCTheme.ink)
                .lineLimit(3)
            Spacer(minLength: 8)
            Button(action: onDismiss) {
                Image(systemName: "xmark")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(CCCTheme.faint)
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(CCCTheme.border, lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.1), radius: 24, y: 8)
        .padding(.horizontal, 28)
        .frame(maxWidth: 420)
    }
}
