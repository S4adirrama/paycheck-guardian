import SwiftUI
import UniformTypeIdentifiers

struct WelcomeView: View {
    @ObservedObject var model: AppModel
    @State private var showingImporter = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 26) {
                HStack {
                    Image(systemName: "shield.lefthalf.filled")
                        .font(.system(size: 34, weight: .semibold))
                        .foregroundStyle(AppPalette.mint)
                    Spacer()
                    Text("LOCAL • SYNTHETIC DEMO")
                        .font(.caption2.weight(.bold))
                        .padding(.horizontal, 10)
                        .padding(.vertical, 7)
                        .background(AppPalette.mint.opacity(0.15), in: Capsule())
                }

                VStack(alignment: .leading, spacing: 12) {
                    Text("Make your paycheck go further.")
                        .font(.system(.largeTitle, design: .rounded, weight: .bold))
                    Text("Paycheck Guardian finds evidence-backed spending opportunities, verifies every estimate, and leaves every decision to you.")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                        .lineSpacing(4)
                }

                VStack(alignment: .leading, spacing: 14) {
                    Label("No bank connection", systemImage: "building.columns")
                    Label("No data leaves the device", systemImage: "lock.shield")
                    Label("No real cancellation", systemImage: "hand.raised")
                }
                .font(.headline)
                .cardSurface()

                Button {
                    Task { await model.runDemo() }
                } label: {
                    Label("Run the hackathon demo", systemImage: "play.fill")
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .accessibilityIdentifier("run-demo")

                Button {
                    showingImporter = true
                } label: {
                    Label("Import CSV or receipt", systemImage: "square.and.arrow.down")
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                }
                .buttonStyle(.bordered)
                .controlSize(.large)
                .accessibilityIdentifier("import-files")

                Text("Educational prototype — not financial advice.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
            }
            .padding(24)
        }
        .fileImporter(
            isPresented: $showingImporter,
            allowedContentTypes: [.commaSeparatedText, .plainText, .png, .jpeg],
            allowsMultipleSelection: true
        ) { result in
            if case .success(let urls) = result {
                Task { await model.importFiles(urls) }
            }
        }
    }
}
