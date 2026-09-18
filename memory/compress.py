"""
Memory compression: periodically summarize runs into snapshots.
Keeps pointers back to full conversations for detailed review.
Integrates Claude API for information-dense summarization.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import anthropic


class MemoryCompressor:
    """Compress and summarize scraping runs using Claude."""
    
    def __init__(
        self,
        snapshot_dir: str = "snapshots",
        trigger_count: int = 50,
        api_key: Optional[str] = None,
        max_summary_tokens: int = 500
    ):
        self.snapshot_dir = snapshot_dir
        self.trigger_count = trigger_count  # Compress every N runs
        self.max_summary_tokens = max_summary_tokens
        os.makedirs(snapshot_dir, exist_ok=True)
        self.run_counter = 0
        
        # Initialize Claude API client
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self.client = anthropic.Anthropic(api_key=api_key)
    
    def should_compress(self) -> bool:
        """Check if compression is needed."""
        self.run_counter += 1
        return self.run_counter % self.trigger_count == 0
    
    def compress(
        self,
        runs: List[Dict],
        conversation_pointer: str
    ) -> str:
        """
        Compress a batch of runs into a summary snapshot.
        Uses Claude API for information-dense summarization.
        
        Args:
            runs: List of run records (full details from each scraping run)
            conversation_pointer: URL/path to full conversation for reference
        
        Returns:
            snapshot_id (timestamped)
        """
        if not runs:
            raise ValueError("Runs list cannot be empty")
        
        snapshot_id = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Step 1: Extract quantitative metrics (fast, local)
        metrics = {
            "avg_dedup_rate": self._mean([r.get("deduplication_rate", 0) for r in runs]),
            "avg_validation_rate": self._mean([r.get("lead_validation_rate", 0) for r in runs]),
            "avg_processing_time": self._mean([r.get("processing_time", 0) for r in runs]),
            "total_leads_scraped": sum([r.get("lead_count", 0) for r in runs]),
            "total_errors": sum([r.get("error_count", 0) for r in runs]),
        }
        
        # Step 2: Generate Claude-powered summary (information-dense, semantic)
        claude_summary = self._generate_claude_summary(runs)
        
        # Step 3: Extract patterns (local processing)
        patterns = {
            "top_actors": self._extract_top_actors(runs),
            "error_patterns": self._extract_error_patterns(runs),
            "dedup_rules": self._extract_dedup_rules(runs),
        }
        
        # Step 4: Assemble snapshot with metadata
        snapshot = {
            "snapshot_id": snapshot_id,
            "timestamp": datetime.now().isoformat(),
            "run_count": len(runs),
            "run_ids": [run.get("run_id") for run in runs],
            
            # Quantitative metrics
            "metrics": metrics,
            
            # Claude-powered semantic summary (up to 500 tokens)
            "claude_summary": claude_summary,
            
            # Pattern analysis
            "patterns": patterns,
            
            # Pointer to full conversation for detailed review
            "conversation_pointer": conversation_pointer,
            "note": "Claude summary is information-dense. Full details in conversation_pointer.",
        }
        
        # Save snapshot
        snapshot_file = os.path.join(self.snapshot_dir, f"{snapshot_id}.json")
        with open(snapshot_file, 'w') as f:
            json.dump(snapshot, f, indent=2)
        
        return snapshot_id
    
    def _generate_claude_summary(self, runs: List[Dict]) -> str:
        """
        Use Claude to generate information-dense summary from runs.
        
        Args:
            runs: List of run records
        
        Returns:
            Compressed summary (up to 500 tokens)
        """
        # Format runs data for Claude
        runs_text = self._format_runs_for_summarization(runs)
        
        prompt = f"""Summarize this lead scraping session into the most important insights and decisions.
Focus on:
1. What worked well (best actors, highest quality output)
2. What failed and why (error patterns, trends)
3. Key learnings for next iteration (recommended fixes, actor improvements)
4. Open questions or anomalies

Be terse. Output ONLY the summary, max 500 tokens. No preamble.

---
{runs_text}
"""
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=self.max_summary_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            summary = response.content[0].text
            return summary
            
        except Exception as e:
            # Fallback if API fails
            print(f"⚠️ Claude API call failed: {e}. Using local summary.")
            return self._generate_local_summary(runs)
    
    def _format_runs_for_summarization(self, runs: List[Dict]) -> str:
        """Format runs data for Claude summarization."""
        lines = []
        
        for i, run in enumerate(runs, 1):
            lines.append(f"Run {i} ({run.get('run_id', 'unknown')}):")
            lines.append(f"  Actor: {run.get('actor_name', 'unknown')}")
            lines.append(f"  Leads: {run.get('lead_count', 0)} | Dedup: {run.get('deduplication_rate', 0):.2%} | Valid: {run.get('lead_validation_rate', 0):.2%}")
            lines.append(f"  Time: {run.get('processing_time', 0):.1f}s | Errors: {run.get('error_count', 0)}")
            
            errors = run.get("errors", [])
            if errors:
                lines.append(f"  Errors: {', '.join([e.get('type', 'unknown') for e in errors[:3]])}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_local_summary(self, runs: List[Dict]) -> str:
        """Fallback: Generate summary using local metrics only."""
        best_actor = max(
            self._extract_top_actors(runs),
            key=lambda x: x["total_leads"],
            default=None
        )
        
        errors = self._extract_error_patterns(runs)
        
        summary = f"""
Lead Scraping Batch Summary ({len(runs)} runs)

Best Performer: {best_actor["name"] if best_actor else "N/A"} ({best_actor["total_leads"] if best_actor else 0} leads)
Average Dedup Rate: {self._mean([r.get("deduplication_rate", 0) for r in runs]):.2%}
Total Leads: {sum([r.get("lead_count", 0) for r in runs])}
Total Errors: {sum([r.get("error_count", 0) for r in runs])}

Top Error Type: {errors[0]["type"] if errors else "None"} ({errors[0]["count"] if errors else 0} occurrences)

Recommendation: {'Continue with improvements' if errors else 'Stable performance'}
"""
        return summary.strip()

    
    def _mean(self, values: List[float]) -> float:
        """Calculate mean of numeric values."""
        if not values:
            return 0.0
        return sum(values) / len(values)
    
    def _extract_top_actors(self, runs: List[Dict]) -> List[Dict]:
        """Extract most successful actor configurations."""
        actor_stats = {}
        
        for run in runs:
            actor = run.get("actor_name", "unknown")
            if actor not in actor_stats:
                actor_stats[actor] = {
                    "name": actor,
                    "runs": 0,
                    "total_leads": 0,
                    "total_errors": 0,
                    "avg_dedup_rate": 0,
                }
            
            actor_stats[actor]["runs"] += 1
            actor_stats[actor]["total_leads"] += run.get("lead_count", 0)
            actor_stats[actor]["total_errors"] += run.get("error_count", 0)
        
        # Sort by total leads (descending)
        sorted_actors = sorted(
            actor_stats.values(),
            key=lambda x: x["total_leads"],
            reverse=True
        )
        
        return sorted_actors[:5]  # Top 5 actors
    
    def _extract_error_patterns(self, runs: List[Dict]) -> List[Dict]:
        """Extract common error patterns."""
        error_counts = {}
        
        for run in runs:
            errors = run.get("errors", [])
            for error in errors:
                error_type = error.get("type", "unknown")
                if error_type not in error_counts:
                    error_counts[error_type] = {
                        "type": error_type,
                        "count": 0,
                        "examples": [],
                    }
                
                error_counts[error_type]["count"] += 1
                # Keep first 3 examples
                if len(error_counts[error_type]["examples"]) < 3:
                    error_counts[error_type]["examples"].append(error.get("message"))
        
        # Sort by frequency (descending)
        sorted_errors = sorted(
            error_counts.values(),
            key=lambda x: x["count"],
            reverse=True
        )
        
        return sorted_errors
    
    def _extract_dedup_rules(self, runs: List[Dict]) -> List[str]:
        """Extract deduplication rules learned."""
        rules = []
        
        for run in runs:
            extracted_rules = run.get("dedup_rules_discovered", [])
            rules.extend(extracted_rules)
        
        # Deduplicate and return unique rules
        unique_rules = list(set(rules))
        return unique_rules[:10]  # Top 10 rules
    
    def load_snapshot(self, snapshot_id: str) -> Dict:
        """Load a specific snapshot."""
        snapshot_file = os.path.join(self.snapshot_dir, f"{snapshot_id}.json")
        
        if not os.path.exists(snapshot_file):
            raise FileNotFoundError(f"Snapshot {snapshot_id} not found")
        
        with open(snapshot_file, 'r') as f:
            return json.load(f)
    
    def list_snapshots(self) -> List[Dict]:
        """List all snapshots."""
        snapshots = []
        
        for filename in os.listdir(self.snapshot_dir):
            if not filename.endswith(".json"):
                continue
            
            snapshot_file = os.path.join(self.snapshot_dir, filename)
            with open(snapshot_file, 'r') as f:
                snapshot = json.load(f)
            
            snapshots.append(snapshot)
        
        return sorted(snapshots, key=lambda x: x["timestamp"], reverse=True)


if __name__ == "__main__":
    compressor = MemoryCompressor()
    
    # Test compression
    sample_runs = [
        {
            "run_id": "run_001",
            "actor_name": "apollo_actor",
            "deduplication_rate": 0.95,
            "lead_validation_rate": 0.97,
            "processing_time": 5.2,
            "lead_count": 1200,
            "error_count": 2,
            "errors": [
                {"type": "rate_limit", "message": "429 error"},
            ],
        },
        {
            "run_id": "run_002",
            "actor_name": "apollo_actor",
            "deduplication_rate": 0.96,
            "lead_validation_rate": 0.98,
            "processing_time": 5.0,
            "lead_count": 1250,
            "error_count": 1,
            "errors": [],
        },
    ]
    
    snapshot_id = compressor.compress(
        sample_runs,
        "https://claude.ai/conversation/abc123"
    )
    
    print(f"Compressed to snapshot: {snapshot_id}")
    
    loaded = compressor.load_snapshot(snapshot_id)
    print(f"Snapshot metrics: {loaded['metrics']}")
