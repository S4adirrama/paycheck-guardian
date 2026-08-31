import CoreGraphics
import Foundation
import ImageIO
import PaycheckGuardianCore
import Vision

enum VisionReceiptImporter {
    static func recognize(data: Data) throws -> String {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil)
        else {
            throw DomainError.invalidCSV("receipt image could not be decoded")
        }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        request.recognitionLanguages = ["en-US"]
        let handler = VNImageRequestHandler(cgImage: image)
        try handler.perform([request])
        let lines = request.results?.compactMap { $0.topCandidates(1).first?.string } ?? []
        guard !lines.isEmpty else {
            throw DomainError.invalidCSV("receipt image contains no readable text")
        }
        return lines.joined(separator: "\n")
    }
}
