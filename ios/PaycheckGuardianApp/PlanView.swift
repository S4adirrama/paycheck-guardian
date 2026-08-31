import PaycheckGuardianCore
import SwiftUI

struct PlanView: View {
    @ObservedObject var model: AppModel
    @State private var evidence: VerifiedRecommendation?
    @State private var pendingApprovalID: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Verified plan")
                            .font(.largeTitle.bold())
                            .accessibilityIdentifier("verified-plan-title")
                        Text("Up to three evidence-backed actions. You stay in control.")
                            .foregroundStyle(.secondary)
                    }

                    VStack(alignment: .leading, spacing: 7) {
                        Text("Potential before next paycheck")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.white.opacity(0.75))
                        Text(CurrencyText.usd(model.nextPaycheckTotal))
                            .font(.system(size: 44, weight: .bold, design: .rounded))
                            .foregroundStyle(.white)
                            .minimumScaleFactor(0.7)
                            .accessibilityIdentifier("next-paycheck-total")
                        Text("\(CurrencyText.usd(model.monthlyTotal)) estimated monthly • not guaranteed")
                            .font(.footnote)
                            .foregroundStyle(.white.opacity(0.8))
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(22)
                    .background(
                        LinearGradient(colors: [AppPalette.navy, AppPalette.blue], startPoint: .topLeading, endPoint: .bottomTrailing),
                        in: RoundedRectangle(cornerRadius: 25)
                    )

                    if model.activeRecommendations.isEmpty {
                        ContentUnavailableView(
                            "No active recommendations",
                            systemImage: "checkmark.shield",
                            description: Text("Dismissed items no longer count toward your totals.")
                        )
                    } else {
                        ForEach(Array(model.activeRecommendations.enumerated()), id: \.element.id) { index, recommendation in
                            RecommendationCard(
                                recommendation: recommendation,
                                index: index,
                                showEvidence: { evidence = recommendation },
                                approve: { pendingApprovalID = recommendation.id },
                                dismiss: { model.dismiss(recommendation.id) }
                            )
                        }
                    }

                    VStack(spacing: 12) {
                        Label("Simulation only — no bank or merchant is contacted.", systemImage: "hand.raised.fill")
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(.secondary)
                        Button("See how the agent decided") { model.showTrace() }
                            .buttonStyle(.bordered)
                            .accessibilityIdentifier("show-agent-trace")
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                }
                .padding(20)
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Reset", action: model.reset)
                }
            }
        }
        .sheet(item: $evidence) { recommendation in
            EvidenceView(recommendation: recommendation, transactions: model.transactions)
        }
        .confirmationDialog(
            "Approve local simulation?",
            isPresented: Binding(
                get: { pendingApprovalID != nil },
                set: { if !$0 { pendingApprovalID = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button("Confirm local simulation") {
                if let id = pendingApprovalID { model.approve(id) }
                pendingApprovalID = nil
            }
            .accessibilityIdentifier("confirm-simulation")
            Button("Cancel", role: .cancel) { pendingApprovalID = nil }
        } message: {
            Text("This records a simulation inside the app. It never contacts a merchant.")
        }
    }
}
