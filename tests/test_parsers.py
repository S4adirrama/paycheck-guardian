from io import StringIO
from pathlib import Path
import subprocess
import sys

import pytest

from paycheck_guardian.parsers import InputValidationError, parse_bank_csv, parse_receipt_fixture
from paycheck_guardian.models import money


def test_csv_parsing_normalizes_known_alias() -> None:
    """A recognized merchant must receive its canonical name and category."""
    rows = parse_bank_csv(
        StringIO("date,description,amount\n2026-05-01,NETFLIX.COM 866-579-7172,15.49\n"),
        "sample.csv",
    )

    assert rows[0].merchant_normalized == "Netflix"
    assert rows[0].category == "streaming"
    assert rows[0].source_reference == "sample.csv:2"


def test_csv_transaction_id_is_stable_for_identical_input() -> None:
    """The deterministic source hash must not change between parser runs."""
    contents = "date,description,amount\n2026-05-01,NETFLIX.COM,15.49\n"

    first = parse_bank_csv(StringIO(contents), "sample.csv")
    second = parse_bank_csv(StringIO(contents), "sample.csv")

    assert first[0].transaction_id == "87ebef344fa8"
    assert second[0].transaction_id == first[0].transaction_id


def test_missing_csv_columns_reports_filename_and_row() -> None:
    """A malformed CSV header must identify the source location to repair."""
    with pytest.raises(InputValidationError, match=r"broken\.csv:1.*description"):
        parse_bank_csv(StringIO("date,amount\n2026-05-01,15.49\n"), "broken.csv")


def test_invalid_csv_date_reports_filename_and_row() -> None:
    """Invalid ISO dates must be rejected at their data row."""
    with pytest.raises(InputValidationError, match=r"dates\.csv:2"):
        parse_bank_csv(
            StringIO("date,description,amount\nMay 1,Netflix,15.49\n"), "dates.csv"
        )


def test_negative_csv_amount_reports_filename_and_row() -> None:
    """Outflows are positive spending amounts; negatives are not accepted."""
    with pytest.raises(InputValidationError, match=r"amounts\.csv:2"):
        parse_bank_csv(
            StringIO("date,description,amount\n2026-05-01,Netflix,-15.49\n"), "amounts.csv"
        )


def test_non_usd_csv_currency_reports_filename_and_row() -> None:
    """The offline parser only accepts transactions explicitly marked USD."""
    with pytest.raises(InputValidationError, match=r"currency\.csv:2"):
        parse_bank_csv(
            StringIO("date,description,amount,currency\n2026-05-01,Netflix,15.49,EUR\n"),
            "currency.csv",
        )


@pytest.mark.parametrize("amount", ["NaN", "Infinity"])
def test_non_finite_csv_amount_reports_filename_and_row(amount: str) -> None:
    """Non-finite Decimal values must not bypass location-rich validation."""
    with pytest.raises(InputValidationError, match=r"nonfinite\.csv:2"):
        parse_bank_csv(
            StringIO(f"date,description,amount\n2026-05-01,Netflix,{amount}\n"),
            "nonfinite.csv",
        )


def test_receipt_fixture_is_deterministic() -> None:
    """A text receipt must produce the same normalized, cent-accurate transaction."""
    text = "DATE: 2026-05-02\nMERCHANT: DoorDash\nTOTAL: 28.40\n"

    rows = parse_receipt_fixture(text, "receipt-01.txt")

    assert rows[0].amount_usd == money("28.40")
    assert rows[0].merchant_normalized == "DoorDash"
    assert rows[0].source_reference == "receipt-01.txt:1"


@pytest.mark.parametrize("amount", ["NaN", "Infinity"])
def test_non_finite_receipt_amount_reports_filename_and_reference(amount: str) -> None:
    """Receipt fixture values receive the same safe, source-qualified rejection."""
    with pytest.raises(InputValidationError, match=r"receipt-nonfinite\.txt:1"):
        parse_receipt_fixture(
            f"DATE: 2026-05-02\nMERCHANT: DoorDash\nTOTAL: {amount}\n",
            "receipt-nonfinite.txt",
        )


def test_generated_receipt_text_and_transactions_are_repeatable() -> None:
    """Rebuilding offline fixtures must preserve their bytes and parsed records."""
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "generate_receipts.py"
    fixture_dir = root / "data" / "demo" / "receipts"

    subprocess.run([sys.executable, str(script)], cwd=root, check=True)
    text_paths = sorted(fixture_dir.glob("*.txt"))
    png_paths = sorted(fixture_dir.glob("*.png"))
    assert {path.stem for path in text_paths} == {path.stem for path in png_paths}
    before = {path.name: path.read_bytes() for path in text_paths}
    png_before = {path.name: path.read_bytes() for path in png_paths}
    parsed_before = [
        parse_receipt_fixture(contents.decode("utf-8"), name)[0].model_dump(mode="json")
        for name, contents in before.items()
    ]

    subprocess.run([sys.executable, str(script)], cwd=root, check=True)
    after = {path.name: path.read_bytes() for path in sorted(fixture_dir.glob("*.txt"))}
    png_after = {path.name: path.read_bytes() for path in sorted(fixture_dir.glob("*.png"))}
    parsed_after = [
        parse_receipt_fixture(contents.decode("utf-8"), name)[0].model_dump(mode="json")
        for name, contents in after.items()
    ]

    assert before == after
    assert png_before == png_after
    assert parsed_before == parsed_after


def test_csv_parser_marks_user_uploads_as_non_synthetic() -> None:
    """A real upload must not inherit the demo provenance flag."""
    rows = parse_bank_csv(
        StringIO("date,description,amount\n2026-05-01,LOCAL MERCHANT,15.49\n"),
        "payroll-export.csv",
        is_synthetic=False,
    )

    assert rows[0].is_synthetic is False


def test_punctuation_only_merchant_is_a_source_qualified_input_error() -> None:
    """A cleaned-empty merchant must not leak an internal Pydantic exception."""
    with pytest.raises(InputValidationError, match=r"punctuation\.csv:2.*merchant"):
        parse_bank_csv(
            StringIO("date,description,amount\n2026-05-01,---,15.49\n"),
            "punctuation.csv",
        )


def test_bundled_receipt_png_is_verified_by_content_and_arbitrary_image_is_actionable() -> None:
    """Only a byte-identical bundled receipt image may use its paired offline text fixture."""
    from paycheck_guardian.parsers import parse_receipt_image

    root = Path(__file__).resolve().parents[1]
    fixture = root / "data" / "demo" / "receipts" / "receipt-01.png"

    rows = parse_receipt_image(fixture.read_bytes(), "renamed-receipt.png")

    assert rows[0].merchant_normalized == "DoorDash"
    assert rows[0].source_reference == "renamed-receipt.png:1"
    assert rows[0].is_synthetic is True
    with pytest.raises(InputValidationError, match=r"unknown\.png:.*bundled.*paired.*\.txt"):
        parse_receipt_image(b"not a supported receipt", "unknown.png")


def test_multiple_uploads_merge_and_dedupe_csv_receipt_evidence_by_content() -> None:
    """Replacing batch merge with last-file-wins would lose valid local evidence."""
    from paycheck_guardian.uploads import parse_upload_batch

    class Upload:
        def __init__(self, name: str, value: bytes) -> None:
            self.name = name
            self._value = value

        def getvalue(self) -> bytes:
            return self._value

    root = Path(__file__).resolve().parents[1]
    receipt_png = (root / "data/demo/receipts/receipt-01.png").read_bytes()
    csv_bytes = (
        b"date,description,amount\n"
        b"2026-05-02,DOORDASH,28.40\n"
        b"2026-05-03,LOCAL MARKET,12.00\n"
    )

    first = parse_upload_batch(
        [Upload("bank.csv", csv_bytes), Upload("receipt.png", receipt_png)]
    )
    changed = parse_upload_batch(
        [Upload("bank.csv", csv_bytes.replace(b"12.00", b"13.00")), Upload("receipt.png", receipt_png)]
    )

    assert len(first.transactions) == 2
    assert {row.merchant_normalized for row in first.transactions} == {"DoorDash", "Local Market"}
    assert all(row.is_synthetic is False for row in first.transactions)
    assert first.content_digest != changed.content_digest


def test_upload_dedupe_preserves_identical_rows_within_one_bank_export() -> None:
    """Cross-file reconciliation must not erase a genuine duplicate charge in one CSV."""
    from paycheck_guardian.uploads import parse_upload_batch

    class Upload:
        name = "duplicate.csv"

        @staticmethod
        def getvalue() -> bytes:
            return (
                b"date,description,amount\n"
                b"2026-05-02,DOORDASH,28.40\n"
                b"2026-05-02,DOORDASH,28.40\n"
            )

    batch = parse_upload_batch([Upload()])

    assert len(batch.transactions) == 2
    assert len({row.transaction_id for row in batch.transactions}) == 2


def test_upload_batch_rejects_inputs_without_transactions() -> None:
    """An empty but schema-valid CSV needs an actionable error before date controls render."""
    from paycheck_guardian.uploads import parse_upload_batch

    class Upload:
        name = "empty.csv"

        @staticmethod
        def getvalue() -> bytes:
            return b"date,description,amount\n"

    with pytest.raises(InputValidationError, match=r"no transactions"):
        parse_upload_batch([Upload()])
