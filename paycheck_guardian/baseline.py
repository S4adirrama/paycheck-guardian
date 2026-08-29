"""Public fair-baseline entry point kept separate from evaluation orchestration."""

from .evaluation import PredictedOpportunity, run_baseline

__all__ = ["PredictedOpportunity", "run_baseline"]
