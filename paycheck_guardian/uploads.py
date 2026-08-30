"""Deterministic, in-memory composition of local upload inputs."""

from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Protocol, Sequence

from .models import Transaction
from .parsers import (
    InputValidationError,
    parse_bank_csv,
    parse_receipt_fixture,
    parse_receipt_image,
)


class UploadedInput(Protocol):
    name: str

    def getvalue(self) -> bytes: ...


@dataclass(frozen=True)
class ParsedUploadBatch:
    transactions: list[Transaction]
    content_digest: str
    source_label: str


def _text(content: bytes, source_name: str) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InputValidationError(f"{source_name}: upload must be UTF-8 text.") from error


def _parse_one(name: str, content: bytes) -> list[Transaction]:
    suffix = Path(name).suffix.lower()
    if suffix == ".csv":
        return parse_bank_csv(StringIO(_text(content, name)), name, is_synthetic=False)
    if suffix == ".txt":
        return parse_receipt_fixture(_text(content, name), name, is_synthetic=False)
    if suffix == ".png":
        return parse_receipt_image(content, name, is_synthetic=False)
    if suffix in {".jpg", ".jpeg"}:
        raise InputValidationError(
            f"{name}: JPEG receipt images are not supported offline. Upload a bundled PNG, "
            "its paired .txt fixture, or a bank CSV."
        )
    raise InputValidationError(
        f"{name}: upload a .csv bank export, deterministic .txt receipt fixture, or "
        "supported bundled .png receipt."
    )


def parse_upload_batch(uploads: Sequence[UploadedInput]) -> ParsedUploadBatch:
    """Merge every selected input and remove semantic CSV/receipt duplicates."""
    if not uploads:
        raise InputValidationError("Select at least one local input file.")
    fingerprints: list[tuple[str, str]] = []
    merged: list[Transaction] = []
    retained_occurrences: dict[tuple[object, ...], int] = {}
    for upload in uploads:
        name = upload.name or "uploaded file"
        content = upload.getvalue()
        fingerprints.append((name, sha256(content).hexdigest()))
        source_occurrences: dict[tuple[object, ...], int] = {}
        for transaction in _parse_one(name, content):
            identity = (
                transaction.date,
                transaction.merchant_normalized.casefold(),
                transaction.amount_usd,
            )
            occurrence = source_occurrences.get(identity, 0) + 1
            source_occurrences[identity] = occurrence
            if occurrence <= retained_occurrences.get(identity, 0):
                continue
            merged.append(transaction)
        for identity, count in source_occurrences.items():
            retained_occurrences[identity] = max(
                retained_occurrences.get(identity, 0), count
            )
    if not merged:
        raise InputValidationError("Selected inputs contain no transactions to analyze.")
    digest_input = "\n".join(f"{name}\0{digest}" for name, digest in sorted(fingerprints))
    return ParsedUploadBatch(
        transactions=merged,
        content_digest=sha256(digest_input.encode("utf-8")).hexdigest(),
        source_label=f"{len(uploads)} local file{'s' if len(uploads) != 1 else ''}",
    )
