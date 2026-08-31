import PaycheckGuardianCore
import SwiftUI

struct TraceView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        NavigationStack {
            List {
                Text("Agent trace")
                    .font(.largeTitle.bold())
                    .accessibilityAddTraits(.isHeader)
                    .accessibilityIdentifier("agent-trace-title")
                    .listRowInsets(EdgeInsets(top: 8, leading: 20, bottom: 4, trailing: 20))

                Section {
                    Text("This trace shows local tool calls and verification decisions. Merchant names, filenames, credentials, and account identifiers are never recorded here.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                Section("Run events") {
                    ForEach(model.run?.trajectory ?? []) { event in
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: icon(event.type))
                                .foregroundStyle(color(event.type))
                                .frame(width: 24)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(event.type.rawValue.replacingOccurrences(of: "_", with: " ").capitalized)
                                    .font(.headline)
                                Text(event.toolName ?? event.component)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                Text("Step \(event.sequence) • opaque ID \(event.id)")
                                    .font(.caption2.monospaced())
                                    .foregroundStyle(.tertiary)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
            .navigationTitle("Trace")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Plan") { model.showPlan() }
                }
            }
        }
    }

    private func icon(_ type: TrajectoryEventType) -> String {
        switch type {
        case .toolCalled: "arrow.up.circle"
        case .toolResult: "arrow.down.circle"
        case .verification: "checkmark.seal"
        case .retry: "arrow.clockwise"
        case .humanCheckpoint: "person.crop.circle.badge.checkmark"
        case .runStarted, .runCompleted: "flag.checkered"
        }
    }

    private func color(_ type: TrajectoryEventType) -> Color {
        switch type {
        case .verification, .humanCheckpoint, .runCompleted: AppPalette.mint
        case .retry: .orange
        default: AppPalette.blue
        }
    }
}
