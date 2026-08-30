import SwiftUI

enum AppPalette {
    static let navy = Color(red: 0.05, green: 0.11, blue: 0.20)
    static let blue = Color(red: 0.12, green: 0.42, blue: 0.96)
    static let mint = Color(red: 0.18, green: 0.76, blue: 0.62)
    static let background = Color(uiColor: .systemGroupedBackground)
}

struct CardSurface: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(18)
            .background(Color(uiColor: .secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 22))
            .overlay(
                RoundedRectangle(cornerRadius: 22)
                    .stroke(Color.primary.opacity(0.07), lineWidth: 1)
            )
    }
}

extension View {
    func cardSurface() -> some View { modifier(CardSurface()) }
}

enum CurrencyText {
    static func usd(_ value: Decimal) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = "USD"
        formatter.locale = Locale(identifier: "en_US")
        formatter.minimumFractionDigits = 2
        formatter.maximumFractionDigits = 2
        return formatter.string(from: NSDecimalNumber(decimal: value)) ?? "$0.00"
    }
}
