import PaycheckGuardianCore
import SwiftUI

struct EvidenceView: View {
    @Environment(\.dismiss) private var dismiss
    let recommendation: VerifiedRecommendation
    let transactions: [PaycheckGuardianCore.Transaction]

    var body: some View {
        NavigationStack {
            List {
                Section("Verified calculation") {
                    LabeledContent("Monthly estimate", value: CurrencyText.usd(recommendation.monthlySavingsUSD.amount))
                    LabeledContent("Before next paycheck", value: CurrencyText.usd(recommendation.nextPaycheckSavingsUSD.amount))
                    Text("Monthly estimate × days to paycheck × 12 ÷ 365, rounded to cents.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .accessibilityIdentifier("calculation-detail")
                }
                Section("Evidence") {
                    ForEach(transactions.filter { recommendation.evidenceIDs.contains($0.id) }) { transaction in
                        VStack(alignment: .leading, spacing: 5) {
                            HStack {
                                Text(transaction.merchantNormalized).font(.headline)
                                Spacer()
                                Text(CurrencyText.usd(transaction.amountUSD.amount)).bold()
                            }
                            Text(transaction.date, format: .dateTime.month(.abbreviated).day().year())
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                if let caveat = recommendation.caveat {
                    Section("Caveat") { Text(caveat) }
                }
            }
            .navigationTitle("Why this is verified")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done", action: dismiss.callAsFunction)
                        .accessibilityIdentifier("close-evidence")
                }
            }
        }
    }
}
