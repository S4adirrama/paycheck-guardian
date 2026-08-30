"""Run the retained offline comparison and write all evaluation artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from paycheck_guardian.evaluation import evaluate_cases, load_cases, write_artifacts


def main(selected_mode: str | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["offline"], default="offline")
    parser.add_argument("--case", help="run one named case without rewriting retained artifacts")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="artifact output directory (default: artifacts/evaluation)",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cases = load_cases(root / "data" / "evaluation" / "cases.json")
    if args.case is not None:
        if selected_mode is None:
            parser.error("--case is available through run_baseline.py or run_solution.py")
        case = next((item for item in cases if item.case_id == args.case), None)
        if case is None:
            parser.error(f"unknown case: {args.case}")
        summary = evaluate_cases([case])
        predictions = summary.modes[selected_mode].predictions[case.case_id]
        print(
            json.dumps(
                {
                    "case_id": case.case_id,
                    "mode": selected_mode,
                    "predictions": [item.model_dump(mode="json") for item in predictions],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    summary = evaluate_cases(cases)
    output_dir = args.output_dir if args.output_dir is not None else root / "artifacts" / "evaluation"
    write_artifacts(cases, summary, output_dir)
    print(f"evaluated {len(cases)} cases in {args.mode} mode")


if __name__ == "__main__":
    main()
