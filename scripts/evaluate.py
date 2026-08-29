"""Run the retained offline comparison and write all evaluation artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from paycheck_guardian.evaluation import evaluate_cases, load_cases, write_artifacts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["offline"], default="offline")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="artifact output directory (default: artifacts/evaluation)",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cases = load_cases(root / "data" / "evaluation" / "cases.json")
    summary = evaluate_cases(cases)
    output_dir = args.output_dir if args.output_dir is not None else root / "artifacts" / "evaluation"
    write_artifacts(cases, summary, output_dir)
    print(f"evaluated {len(cases)} cases in {args.mode} mode")


if __name__ == "__main__":
    main()
