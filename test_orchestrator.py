"""
Example: Run the self-improving orchestrator with mock Apify client.
Demonstrates complete self-improving loop without needing API keys.

Usage:
    python test_orchestrator.py
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator import SelfImprovingOrchestrator
from apify_integration import MockApifyClient


def main():
    """Run a complete improvement loop demonstration."""
    
    print("\n" + "="*70)
    print("🤖 SELF-IMPROVING LEAD SCRAPER - DEMONSTRATION")
    print("="*70)
    print("\nThis example uses MockApifyClient (no API keys required)")
    print("to demonstrate the complete self-improving loop.\n")
    
    # Initialize mock Apify client
    # failure_rate=0.15 means ~15% of runs will fail (simulating real-world errors)
    mock_client = MockApifyClient(failure_rate=0.15)
    
    # Define initial actor configuration
    initial_config = {
        "search_query": "tech startup founders silicon valley",
        "batch_size": 100,
        "timeout": 30,
        "max_retries": 3,
    }
    
    print("📋 INITIAL CONFIGURATION:")
    print(json.dumps(initial_config, indent=2))
    print()
    
    # Create orchestrator
    orchestrator = SelfImprovingOrchestrator(
        apify_client=mock_client,
        initial_config=initial_config,
        actor_name="apollo_google_search",
        max_iterations=7,  # Allow up to 7 iterations
        conversation_pointer="https://claude.ai/conversation/demo",
        # Note: api_key is None, so memory compression will be skipped
        # To enable: api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    # Run the improvement loop
    print("\n" + "="*70)
    print("🚀 STARTING IMPROVEMENT LOOP")
    print("="*70 + "\n")
    
    result = orchestrator.run_improvement_loop()
    
    # Display results
    print("\n" + "="*70)
    print("📊 FINAL RESULTS")
    print("="*70)
    
    print(f"\n✅ Status: {result['status']}")
    print(f"📈 Total iterations: {result['total_runs']}")
    print(f"\n🎯 Final Configuration:")
    print(json.dumps(result['final_config'], indent=2))
    
    print(f"\n📉 Final Metrics:")
    for metric, value in result['final_metrics'].items():
        if isinstance(value, float):
            if metric.endswith('rate'):
                print(f"  {metric}: {value:.2%}")
            else:
                print(f"  {metric}: {value:.2f}")
        else:
            print(f"  {metric}: {value}")
    
    print(f"\n💡 Convergence Reason: {result['convergence_reason']}")
    
    # Detailed run history
    print(f"\n📋 Run History:")
    print(f"{'Iter':<5} {'Leads':<7} {'Dedup':<8} {'Valid':<8} {'Errors':<7} {'Status':<12}")
    print("-" * 57)
    
    for run in result['run_history']:
        status = "✅ Success" if not run.get('error') else f"❌ {run['error_type']}"
        print(
            f"{run['iteration']:<5} "
            f"{run['lead_count']:<7} "
            f"{run['deduplication_rate']:<7.1%} "
            f"{run['lead_validation_rate']:<7.1%} "
            f"{run['error_count']:<7} "
            f"{status:<12}"
        )
    
    # Key achievements
    print(f"\n🏆 Key Achievements:")
    initial_run = result['run_history'][0]
    final_run = result['run_history'][-1]
    
    dedup_improvement = (
        (final_run['deduplication_rate'] - initial_run['deduplication_rate']) /
        initial_run['deduplication_rate'] * 100
    )
    
    lead_improvement = (
        (final_run['lead_count'] - initial_run['lead_count']) /
        initial_run['lead_count'] * 100
    )
    
    print(f"  • Deduplication improved by {dedup_improvement:+.1f}%")
    print(f"  • Lead volume improved by {lead_improvement:+.1f}%")
    print(f"  • Error recovery: {initial_run['error_count']} errors → {final_run['error_count']} errors")
    
    print("\n" + "="*70)
    print("✨ DEMONSTRATION COMPLETE")
    print("="*70)
    print("\nNext steps:")
    print("1. Review QUICKSTART.md for setup instructions")
    print("2. Connect to real Apify actors")
    print("3. Set up Claude API for memory compression")
    print("4. Deploy to production")
    print()


if __name__ == "__main__":
    main()
