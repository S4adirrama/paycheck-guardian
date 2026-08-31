import PaycheckGuardianCore
import SwiftUI

struct RecommendationCard: View {
    let recommendation: VerifiedRecommendation
    let index: Int
    let showEvidence: () -> Void
    let approve: () -> Void
    let dismiss: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 5) {
                    Text(recommendation.title)
                        .font(.headline)
                    Label("Verifier accepted", systemImage: "checkmark.seal.fill")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(AppPalette.mint)
                }
                Spacer()
                Text(CurrencyText.usd(recommendation.nextPaycheckSavingsUSD.amount))
                    .font(.title3.bold())
            }

            Text(recommendation.rationale)
                .font(.subheadline)
                .foregroundStyle(.secondary)

            if recommendation.status == .approvedForSimulation {
                Label("Local simulation confirmed", systemImage: "checkmark.circle.fill")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(AppPalette.mint)
                    .accessibilityIdentifier("simulation-confirmed")
            }

            HStack {
                Button("Evidence", action: showEvidence)
                    .buttonStyle(.bordered)
                    .accessibilityIdentifier("recommendation-evidence-\(index)")
                Spacer()
                Button("Dismiss", role: .destructive, action: dismiss)
                    .accessibilityIdentifier("dismiss-recommendation-\(index)")
                if recommendation.status == .proposed {
                    Button("Approve", action: approve)
                        .buttonStyle(.borderedProminent)
                        .accessibilityIdentifier("approve-recommendation-\(index)")
                }
            }
            .font(.subheadline.weight(.semibold))
        }
        .cardSurface()
    }
}
