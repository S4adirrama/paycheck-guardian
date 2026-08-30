import Foundation

public indirect enum TraceValue: Codable, Hashable, Sendable {
    case string(String)
    case int(Int)
    case bool(Bool)
    case decimal(String)
    case array([TraceValue])
    case object([String: TraceValue])
    case null

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() { self = .null }
        else if let value = try? container.decode(Bool.self) { self = .bool(value) }
        else if let value = try? container.decode(Int.self) { self = .int(value) }
        else if let value = try? container.decode(String.self) { self = .string(value) }
        else if let value = try? container.decode([TraceValue].self) { self = .array(value) }
        else { self = .object(try container.decode([String: TraceValue].self)) }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value), .decimal(let value): try container.encode(value)
        case .int(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }
}

public enum TrajectoryEventType: String, Codable, Hashable, Sendable {
    case runStarted = "run_started"
    case toolCalled = "tool_called"
    case toolResult = "tool_result"
    case verification
    case retry
    case humanCheckpoint = "human_checkpoint"
    case runCompleted = "run_completed"
}

public struct TrajectoryEvent: Codable, Hashable, Identifiable, Sendable {
    public let id: String
    public let sequence: Int
    public let runID: String
    public let component: String
    public let type: TrajectoryEventType
    public let toolName: String?
    public let payload: TraceValue
}

public enum TrajectoryRedactor {
    private static let sensitiveTerms = [
        "token", "secret", "password", "authorization", "account", "merchant", "filename", "source_reference",
    ]

    public static func redact(_ value: TraceValue) -> TraceValue {
        switch value {
        case .object(let object):
            return .object(Dictionary(uniqueKeysWithValues: object.map { key, child in
                let normalized = key.lowercased().replacingOccurrences(of: "-", with: "_")
                if sensitiveTerms.contains(where: normalized.contains) {
                    return (key, .string("[REDACTED]"))
                }
                return (key, redact(child))
            }))
        case .array(let values):
            return .array(values.map(redact))
        default:
            return value
        }
    }
}

public struct TrajectoryRecorder: Sendable {
    public let runID: String
    public private(set) var events: [TrajectoryEvent]

    public init(seed: String, events: [TrajectoryEvent] = []) {
        runID = Self.opaqueID(seed: "run|\(seed)")
        self.events = events
    }

    init(runID: String, events: [TrajectoryEvent]) {
        self.runID = runID
        self.events = events
    }

    public static func opaqueID(seed: String) -> String {
        OpaqueID.digest(seed)
    }

    mutating func record(
        component: String,
        type: TrajectoryEventType,
        toolName: String? = nil,
        payload: TraceValue = .object([:])
    ) {
        let sequence = events.count + 1
        events.append(
            TrajectoryEvent(
                id: Self.opaqueID(seed: "\(runID)|\(sequence)"),
                sequence: sequence,
                runID: runID,
                component: component,
                type: type,
                toolName: toolName,
                payload: TrajectoryRedactor.redact(payload)
            )
        )
    }

    mutating func recordCall(tool: String, transactionCount: Int, attempt: Int = 1) {
        record(
            component: tool == "recommendation_verifier" ? "verifier" : "analysis",
            type: .toolCalled,
            toolName: tool,
            payload: .object(["transaction_count": .int(transactionCount), "attempt": .int(attempt)])
        )
    }

    mutating func recordResult(tool: String, candidateCount: Int, accepted: Bool? = nil, attempt: Int = 1) {
        var values: [String: TraceValue] = [
            "candidate_count": .int(candidateCount),
            "attempt": .int(attempt),
        ]
        if let accepted { values["accepted"] = .bool(accepted) }
        record(
            component: tool == "recommendation_verifier" ? "verifier" : "analysis",
            type: .toolResult,
            toolName: tool,
            payload: .object(values)
        )
    }
}
