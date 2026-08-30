import SwiftUI

struct SetupView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Review window")
                            .font(.largeTitle.bold())
                        Text("Choose when you’re reviewing spending and when the next paycheck arrives.")
                            .foregroundStyle(.secondary)
                    }

                    VStack(spacing: 6) {
                        DatePicker("Analysis date", selection: $model.analysisDate, displayedComponents: .date)
                        Divider()
                        DatePicker("Next paycheck", selection: $model.nextPaycheck, displayedComponents: .date)
                    }
                    .cardSurface()

                    Label("\(model.importedTransactionCount) transactions ready", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(model.importedTransactionCount > 0 ? AppPalette.mint : .secondary)
                        .font(.headline)

                    if let error = model.presentedError {
                        VStack(alignment: .leading, spacing: 5) {
                            Text(error.title).font(.headline)
                            Text(error.message).font(.subheadline)
                        }
                        .foregroundStyle(.red)
                        .cardSurface()
                        .accessibilityIdentifier("validation-error")
                    }

                    Button {
                        Task { await model.analyzeCurrentTransactions() }
                    } label: {
                        Label("Build verified plan", systemImage: "sparkles")
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .accessibilityIdentifier("analyze-transactions")
                }
                .padding(24)
            }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Start over", action: model.reset)
                }
            }
        }
    }
}
