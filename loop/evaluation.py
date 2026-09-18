"""
Evaluation function: Compare two runs and determine improvement.
Provides quality metrics and scoring for loop termination.
"""

from typing import Dict
from dataclasses import dataclass


@dataclass
class EvaluationScore:
    """Evaluation result from comparing two runs."""
    improvement_delta: float  # > 0 means run_b is better
    component_scores: Dict[str, float]
    overall_quality: float
    recommendation: str


class EvaluationEngine:
    """
    Evaluate improvement between two scraping runs.
    Combines multiple quality metrics into a single score.
    """
    
    def __init__(self):
        """Initialize evaluation weights."""
        # Weights for different metrics (sum = 1.0)
        self.weights = {
            "deduplication_rate": 0.35,      # Most important: no duplicates
            "lead_validation_rate": 0.35,    # Second: data quality
            "lead_count": 0.20,              # Volume matters but secondary
            "error_recovery": 0.10,          # Lower errors is good
        }
    
    def evaluate_improvement(
        self,
        run_a: Dict,
        run_b: Dict,
        verbose: bool = False
    ) -> EvaluationScore:
        """
        Compare two runs and return improvement score.
        
        Args:
            run_a: Previous run metrics
            run_b: Current run metrics
            verbose: Print detailed scoring
        
        Returns:
            EvaluationScore with delta and recommendation
        """
        # Normalize metrics to 0-1 scale
        scores_a = self._normalize_metrics(run_a)
        scores_b = self._normalize_metrics(run_b)
        
        if verbose:
            print(f"\nRun A normalized: {scores_a}")
            print(f"Run B normalized: {scores_b}")
        
        # Calculate weighted scores
        quality_a = self._calculate_quality(scores_a)
        quality_b = self._calculate_quality(scores_b)
        
        improvement_delta = quality_b - quality_a
        
        # Component scores for debugging
        component_scores = {
            "run_a_quality": quality_a,
            "run_b_quality": quality_b,
            "dedup_improvement": scores_b["deduplication_rate"] - scores_a["deduplication_rate"],
            "validation_improvement": scores_b["lead_validation_rate"] - scores_a["lead_validation_rate"],
            "volume_improvement": (run_b.get("lead_count", 0) - run_a.get("lead_count", 0)) / max(1, run_a.get("lead_count", 1)),
            "error_improvement": (run_a.get("error_count", 0) - run_b.get("error_count", 0)) / max(1, run_a.get("error_count", 1)),
        }
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            improvement_delta,
            component_scores,
            run_b
        )
        
        if verbose:
            print(f"\nQuality A: {quality_a:.4f}")
            print(f"Quality B: {quality_b:.4f}")
            print(f"Improvement: {improvement_delta:.4f}")
            print(f"Recommendation: {recommendation}")
        
        return EvaluationScore(
            improvement_delta=improvement_delta,
            component_scores=component_scores,
            overall_quality=quality_b,
            recommendation=recommendation
        )
    
    def _normalize_metrics(self, run: Dict) -> Dict[str, float]:
        """
        Normalize run metrics to 0-1 scale.
        
        Dedup & validation: already 0-1
        Lead count: normalize by comparing to typical range
        Error recovery: inverse (fewer errors = higher score)
        """
        return {
            "deduplication_rate": min(1.0, run.get("deduplication_rate", 0)),
            "lead_validation_rate": min(1.0, run.get("lead_validation_rate", 0)),
            "lead_count": self._normalize_volume(run.get("lead_count", 0)),
            "error_recovery": self._normalize_errors(run.get("error_count", 0)),
        }
    
    def _normalize_volume(self, lead_count: int) -> float:
        """
        Normalize lead count to 0-1 scale.
        Assume typical range: 500-2000 leads per run.
        """
        if lead_count < 500:
            return lead_count / 500
        elif lead_count > 2000:
            return 1.0
        else:
            return lead_count / 2000
    
    def _normalize_errors(self, error_count: int) -> float:
        """
        Normalize error count. Fewer = higher score.
        Assume typical range: 0-10 errors per run.
        """
        return max(0.0, 1.0 - (error_count / 10))
    
    def _calculate_quality(self, scores: Dict[str, float]) -> float:
        """Calculate weighted quality score."""
        quality = sum(
            scores[metric] * weight
            for metric, weight in self.weights.items()
        )
        return quality
    
    def _generate_recommendation(
        self,
        improvement_delta: float,
        component_scores: Dict[str, float],
        run_b: Dict
    ) -> str:
        """Generate actionable recommendation based on scores."""
        if improvement_delta > 0.05:
            return "✅ ACCEPT: Significant improvement. Continue iteration."
        elif improvement_delta > 0.01:
            return "⚠️ MARGINAL: Minor improvement. Continue if within improvement_threshold."
        elif improvement_delta >= -0.01:
            return "🔄 NEUTRAL: No meaningful change. Consider current run acceptable."
        else:
            return "❌ REGRESSION: Quality degraded. Revert and debug."
    
    def batch_evaluate(
        self,
        run_history: list,
        verbose: bool = False
    ) -> list:
        """
        Evaluate consecutive runs to track improvement trajectory.
        
        Returns:
            List of (run_id_pair, improvement_delta)
        """
        results = []
        
        for i in range(1, len(run_history)):
            run_a = run_history[i - 1]
            run_b = run_history[i]
            
            eval_result = self.evaluate_improvement(run_a, run_b, verbose)
            results.append({
                "run_pair": f"{run_a.get('run_id')} → {run_b.get('run_id')}",
                "improvement": eval_result.improvement_delta,
                "recommendation": eval_result.recommendation,
            })
        
        return results


if __name__ == "__main__":
    engine = EvaluationEngine()
    
    # Test evaluation
    run_a = {
        "run_id": "run_001",
        "deduplication_rate": 0.92,
        "lead_validation_rate": 0.95,
        "lead_count": 1200,
        "error_count": 3,
    }
    
    run_b = {
        "run_id": "run_002",
        "deduplication_rate": 0.95,
        "lead_validation_rate": 0.97,
        "lead_count": 1350,
        "error_count": 1,
    }
    
    result = engine.evaluate_improvement(run_a, run_b, verbose=True)
    print(f"\n📊 Final Delta: {result.improvement_delta:.4f}")
    print(f"📌 Recommendation: {result.recommendation}")
