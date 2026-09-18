"""
Main orchestrator: Self-improving lead scraper loop.
Coordinates RAG, error detection/fix, evaluation, and loop termination.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from rag.embed import embed, embed_batch
from rag.retrieve import retrieve_with_scores
from loop.evaluation import EvaluationEngine, EvaluationScore
from loop.terminate import LoopTerminator, RunMetrics
from error_fix.detect import ErrorDetector
from error_fix.fix_prompt import PromptFixer
from memory.compress import MemoryCompressor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class SelfImprovingOrchestrator:
    """
    Main orchestration loop for self-improving lead scraper.
    
    Flow:
    1. Run Apify actor with current config
    2. Evaluate results (quality metrics)
    3. Detect errors if any
    4. Propose and apply fixes
    5. Retrieve relevant configs via RAG
    6. Re-run improved config
    7. Compare improvements
    8. Update memory, check termination
    """
    
    def __init__(
        self,
        apify_client,
        initial_config: Dict,
        actor_name: str,
        max_iterations: int = 10,
        conversation_pointer: str = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize orchestrator.
        
        Args:
            apify_client: Apify Python client (or mock)
            initial_config: Starting actor config
            actor_name: Apify actor name
            max_iterations: Max improvement iterations
            conversation_pointer: URL to full conversation (for memory compression)
            api_key: Anthropic API key (for memory compression)
        """
        self.apify_client = apify_client
        self.config = initial_config.copy()
        self.actor_name = actor_name
        self.conversation_pointer = conversation_pointer or "N/A"
        
        # Initialize components
        self.evaluator = EvaluationEngine()
        self.terminator = LoopTerminator()
        self.error_detector = ErrorDetector()
        self.prompt_fixer = PromptFixer()
        self.memory_compressor = MemoryCompressor(api_key=api_key) if api_key else None
        
        # State tracking
        self.run_history: List[Dict] = []
        self.max_iterations = max_iterations
        self.stored_embeddings: List[Tuple[int, List[float]]] = []  # For RAG retrieval
    
    def run_improvement_loop(self) -> Dict:
        """
        Execute the self-improving loop.
        
        Returns:
            Summary dict with final results and convergence info
        """
        logger.info(f"🚀 Starting improvement loop for actor: {self.actor_name}")
        logger.info(f"Initial config: {json.dumps(self.config, indent=2)}")
        
        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"ITERATION {iteration}/{self.max_iterations}")
            logger.info(f"{'='*60}")
            
            # Step 1: Run actor with current config
            result = self._run_actor(iteration)
            if result is None:
                logger.error(f"❌ Actor execution failed at iteration {iteration}")
                break
            
            # Step 2: Detect errors
            if result.get("error"):
                logger.warning(f"⚠️ Error detected: {result['error']}")
                
                # Step 3: Propose and apply fix
                fixed_config = self._handle_error(result, iteration)
                if fixed_config:
                    self.config = fixed_config
                    logger.info(f"✅ Applied fix. Retrying with new config...")
                    continue
                else:
                    logger.error(f"❌ Error handling failed. Terminating.")
                    break
            
            # Step 4: Evaluate improvement
            should_continue, reason = self._evaluate_and_check_termination(result, iteration)
            
            logger.info(f"📊 Termination check: {reason}")
            if not should_continue:
                logger.info(f"🛑 Loop terminated: {reason}")
                break
            
            # Step 5: Retrieve and apply RAG improvements
            improved_config = self._apply_rag_improvements(result)
            if improved_config:
                self.config = improved_config
                logger.info(f"🧠 Applied RAG-suggested improvements")
            
            # Step 6: Check if compression needed
            if self.memory_compressor and self.memory_compressor.should_compress():
                logger.info(f"💾 Compressing memory (run count: {len(self.run_history)})...")
                self._compress_memory()
        
        # Final summary
        return self._generate_summary()
    
    def _run_actor(self, iteration: int) -> Optional[Dict]:
        """
        Execute Apify actor with current config.
        
        Returns:
            Run result dict with metrics and status
        """
        logger.info(f"Running actor with config: {json.dumps(self.config, indent=2)}")
        
        try:
            # Call Apify actor
            result = self.apify_client.run_actor(
                actor_name=self.actor_name,
                config=self.config
            )
            
            # Parse result
            run_result = {
                "run_id": f"run_{iteration:03d}",
                "iteration": iteration,
                "actor_name": self.actor_name,
                "config": self.config.copy(),
                "lead_count": result.get("lead_count", 0),
                "deduplication_rate": result.get("deduplication_rate", 0.0),
                "lead_validation_rate": result.get("lead_validation_rate", 0.0),
                "processing_time": result.get("processing_time", 0.0),
                "error": result.get("error"),
                "error_count": result.get("error_count", 0),
                "timestamp": datetime.now().isoformat(),
            }
            
            self.run_history.append(run_result)
            
            # Log metrics
            logger.info(f"✅ Run completed: {run_result['lead_count']} leads, "
                       f"Dedup: {run_result['deduplication_rate']:.2%}, "
                       f"Valid: {run_result['lead_validation_rate']:.2%}")
            
            return run_result
            
        except Exception as e:
            logger.error(f"❌ Actor execution failed: {str(e)}")
            return None
    
    def _handle_error(self, run_result: Dict, iteration: int) -> Optional[Dict]:
        """
        Detect, analyze, and fix errors.
        
        Returns:
            Improved config or None if fix failed
        """
        error_msg = run_result.get("error", "")
        
        # Step 1: Detect error type
        error_info = self.error_detector.detect(error_msg)
        logger.info(f"Error type: {error_info['error_type']} "
                   f"(confidence: {error_info['confidence']:.2f})")
        
        # Step 2: Propose fix
        fix_proposal = self.prompt_fixer.propose_fix(
            error_msg,
            json.dumps(self.config),
            self.config
        )
        
        logger.info(f"Proposed fix: {fix_proposal['reasoning']}")
        
        # Step 3: Version and commit
        version_id = self.prompt_fixer.version_and_commit(
            fix_proposal,
            f"run_{iteration:03d}",
            self.config
        )
        logger.info(f"Versioned fix: {version_id}")
        
        # Step 4: Extract improved config
        improved_config = fix_proposal.get("proposed_fix", {}).get("new_config")
        return improved_config
    
    def _evaluate_and_check_termination(
        self,
        run_result: Dict,
        iteration: int
    ) -> Tuple[bool, str]:
        """
        Evaluate improvement and check termination conditions.
        
        Returns:
            (should_continue: bool, reason: str)
        """
        # Add to terminator's history
        metrics = RunMetrics(
            run_id=run_result["run_id"],
            deduplication_rate=run_result["deduplication_rate"],
            lead_validation_rate=run_result["lead_validation_rate"],
            processing_time=run_result["processing_time"],
            lead_count=run_result["lead_count"],
            error_count=run_result["error_count"],
        )
        self.terminator.add_run(metrics)
        
        # Check termination
        should_stop, reason = self.terminator.should_terminate(verbose=True)
        
        return not should_stop, reason
    
    def _apply_rag_improvements(self, run_result: Dict) -> Optional[Dict]:
        """
        Use RAG to find similar successful runs and suggest improvements.
        
        Returns:
            Improved config or None if no improvements found
        """
        # Embed current config
        config_text = f"Actor: {self.actor_name}. Config: {json.dumps(self.config)}"
        current_embedding = embed(config_text)
        
        # Retrieve top-20 similar successful runs
        if len(self.run_history) < 2:
            logger.info("🧠 RAG: Not enough history yet")
            return None
        
        # Build stored embeddings from history
        stored_embeddings = []
        for i, run in enumerate(self.run_history[:-1]):  # Exclude current
            run_text = f"Actor: {run['actor_name']}. Config: {json.dumps(run['config'])}"
            try:
                run_embedding = embed(run_text)
                stored_embeddings.append((i, run_embedding))
            except Exception as e:
                logger.warning(f"Failed to embed run {i}: {e}")
        
        if not stored_embeddings:
            return None
        
        # Retrieve similar runs
        similar_ids = retrieve_with_scores(
            current_embedding,
            stored_embeddings,
            top_k=5,  # Get top 5 similar runs
            min_similarity=0.7
        )
        
        if not similar_ids:
            logger.info("🧠 RAG: No similar successful runs found")
            return None
        
        # Extract best config from similar runs
        best_config = None
        best_quality = 0
        
        for run_id, similarity in similar_ids[:3]:  # Top 3
            run = self.run_history[run_id]
            quality = (run["deduplication_rate"] + run["lead_validation_rate"]) / 2
            
            if quality > best_quality and run.get("error_count", 0) == 0:
                best_config = run["config"].copy()
                best_quality = quality
        
        if best_config:
            logger.info(f"🧠 RAG: Found similar run with quality {best_quality:.2%}")
            logger.info(f"Suggested config improvements: {json.dumps(best_config, indent=2)}")
            return best_config
        
        return None
    
    def _compress_memory(self) -> None:
        """Compress run history into snapshot."""
        if not self.memory_compressor:
            return
        
        try:
            snapshot_id = self.memory_compressor.compress(
                self.run_history,
                self.conversation_pointer
            )
            logger.info(f"✅ Memory compressed: {snapshot_id}")
        except Exception as e:
            logger.error(f"❌ Memory compression failed: {e}")
    
    def _generate_summary(self) -> Dict:
        """Generate final summary of improvement loop."""
        if not self.run_history:
            return {"status": "failed", "reason": "No runs completed"}
        
        latest = self.run_history[-1]
        
        summary = {
            "status": "completed",
            "total_runs": len(self.run_history),
            "final_config": self.config,
            "final_metrics": {
                "lead_count": latest["lead_count"],
                "deduplication_rate": latest["deduplication_rate"],
                "lead_validation_rate": latest["lead_validation_rate"],
                "processing_time": latest["processing_time"],
                "error_count": latest["error_count"],
            },
            "run_history": self.run_history,
            "convergence_reason": self.terminator.should_terminate()[1],
        }
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📈 FINAL SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total iterations: {summary['total_runs']}")
        logger.info(f"Final leads: {summary['final_metrics']['lead_count']}")
        logger.info(f"Final quality: Dedup {summary['final_metrics']['deduplication_rate']:.2%}, "
                   f"Valid {summary['final_metrics']['lead_validation_rate']:.2%}")
        logger.info(f"Convergence: {summary['convergence_reason']}")
        
        return summary


if __name__ == "__main__":
    # Example usage with mock Apify client
    from apify_integration import MockApifyClient
    
    mock_client = MockApifyClient()
    
    initial_config = {
        "search_query": "tech startup founders",
        "batch_size": 100,
        "timeout": 30,
    }
    
    orchestrator = SelfImprovingOrchestrator(
        apify_client=mock_client,
        initial_config=initial_config,
        actor_name="apollo_google_search",
        max_iterations=5,
    )
    
    result = orchestrator.run_improvement_loop()
    print("\n📊 Final Result:")
    print(json.dumps(result, indent=2, default=str))
