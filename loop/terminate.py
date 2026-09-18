"""
Loop termination logic: quality gate with no-improvement detection.
Stops when quality metrics pass AND no improvement for N runs.
"""

from typing import Dict, List
import yaml
from dataclasses import dataclass


@dataclass
class RunMetrics:
    """Metrics from a single scraping run."""
    deduplication_rate: float  # 0-1
    lead_validation_rate: float  # 0-1
    processing_time: float  # seconds
    lead_count: int
    error_count: int
    run_id: str


class LoopTerminator:
    """Quality gate for loop termination."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Load termination rules from config."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.loop_config = self.config.get("loop", {})
        self.term_config = self.config.get("termination", {})
        
        self.max_iterations = self.loop_config.get("max_iterations", 10)
        self.no_improvement_threshold = self.loop_config.get("no_improvement_threshold", 2)
        self.quality_metrics = self.loop_config.get("quality_metrics", [])
        
        self.run_history: List[RunMetrics] = []
        self.iteration_count = 0
    
    def add_run(self, metrics: RunMetrics) -> None:
        """Add metrics from completed run."""
        self.run_history.append(metrics)
        self.iteration_count += 1
    
    def should_terminate(self, verbose: bool = False) -> tuple[bool, str]:
        """
        Determine if loop should terminate.
        
        Returns:
            (should_stop: bool, reason: str)
        """
        if not self.run_history:
            return False, "No runs yet"
        
        # Check max iterations
        if self.iteration_count >= self.max_iterations:
            return True, f"Reached max_iterations ({self.max_iterations})"
        
        # Get latest run
        latest = self.run_history[-1]
        
        # Check quality metrics thresholds
        quality_pass = self._check_quality_thresholds(latest)
        if not quality_pass:
            reason = f"Quality metrics not met: {quality_pass}"
            if verbose:
                print(f"  ⚠ {reason}")
            return False, reason
        
        # Check no-improvement condition
        no_improvement_runs = self._count_no_improvement_runs()
        if no_improvement_runs >= self.no_improvement_threshold:
            return True, f"No improvement for {no_improvement_runs} runs"
        
        return False, "Continue (quality OK, still improving)"
    
    def _check_quality_thresholds(self, metrics: RunMetrics) -> bool:
        """
        Check if metrics meet quality thresholds.
        Returns True if all pass, False otherwise.
        """
        # Default thresholds
        dedup_threshold = 0.95
        validation_threshold = 0.98
        
        if metrics.deduplication_rate < dedup_threshold:
            return False
        if metrics.lead_validation_rate < validation_threshold:
            return False
        
        return True
    
    def _count_no_improvement_runs(self) -> int:
        """Count consecutive runs with no improvement."""
        if len(self.run_history) < 2:
            return 0
        
        count = 0
        for i in range(len(self.run_history) - 1, 0, -1):
            prev = self.run_history[i - 1]
            curr = self.run_history[i]
            
            # Define improvement: dedup_rate or validation_rate increased
            if (curr.deduplication_rate <= prev.deduplication_rate and
                curr.lead_validation_rate <= prev.lead_validation_rate):
                count += 1
            else:
                break
        
        return count
    
    def summary(self) -> Dict:
        """Return summary of all runs."""
        if not self.run_history:
            return {"runs": 0}
        
        latest = self.run_history[-1]
        return {
            "total_runs": len(self.run_history),
            "max_iterations": self.max_iterations,
            "latest_dedup_rate": latest.deduplication_rate,
            "latest_validation_rate": latest.lead_validation_rate,
            "latest_lead_count": latest.lead_count,
            "latest_error_count": latest.error_count,
        }


if __name__ == "__main__":
    # Test terminator
    terminator = LoopTerminator()
    
    # Simulate runs
    runs = [
        RunMetrics("run_1", 0.92, 0.95, 5.2, 1200, 3),
        RunMetrics("run_2", 0.94, 0.96, 5.1, 1250, 2),
        RunMetrics("run_3", 0.95, 0.97, 5.0, 1300, 1),
        RunMetrics("run_4", 0.955, 0.975, 5.05, 1305, 1),
        RunMetrics("run_5", 0.955, 0.975, 5.1, 1304, 1),  # No improvement
    ]
    
    for run in runs:
        terminator.add_run(run)
        should_stop, reason = terminator.should_terminate(verbose=True)
        print(f"{run.run_id}: {reason}")
    
    print(f"\nFinal summary: {terminator.summary()}")
