# Self-Improving Lead Scraper - Quick Start Guide

## Overview

This is a complete self-improving AI agent for lead scraping using Apify. It automatically:
- Detects errors and proposes fixes
- Evaluates quality improvements
- Retrieves similar successful runs via RAG
- Compresses memory with Claude API
- Terminates when quality plateaus

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
export OPENAI_API_KEY="sk-..."  # For embeddings
export ANTHROPIC_API_KEY="sk-ant-..."  # For memory compression
export APIFY_API_TOKEN="apify_..."  # For Apify actors
```

### 3. Verify Setup
```bash
python -m pytest tests/  # Run tests (if available)
```

## Usage

### Option A: Test with Mock Client (No API Keys Needed)

```python
from orchestrator import SelfImprovingOrchestrator
from apify_integration import MockApifyClient

# Create mock client (simulates Apify actor)
mock_client = MockApifyClient(failure_rate=0.1)

# Initial config
config = {
    "search_query": "tech startup founders",
    "batch_size": 100,
    "timeout": 30,
}

# Run improvement loop
orchestrator = SelfImprovingOrchestrator(
    apify_client=mock_client,
    initial_config=config,
    actor_name="apollo_google_search",
    max_iterations=5,
)

result = orchestrator.run_improvement_loop()
print(result)
```

### Option B: Use Real Apify Actor

```python
from orchestrator import SelfImprovingOrchestrator
from apify_integration import ApifyClient

# Create real Apify client
apify_client = ApifyClient()

# Your Apify actor config
config = {
    "search_query": "tech founders in Silicon Valley",
    "batch_size": 100,
    "timeout": 30,
}

# Run improvement loop
orchestrator = SelfImprovingOrchestrator(
    apify_client=apify_client,
    initial_config=config,
    actor_name="your-actor-name",
    max_iterations=10,
    conversation_pointer="https://claude.ai/conversation/abc123",  # For memory compression
    api_key=os.getenv("ANTHROPIC_API_KEY"),
)

result = orchestrator.run_improvement_loop()

# View final config and metrics
print(f"Final config: {result['final_config']}")
print(f"Final leads: {result['final_metrics']['lead_count']}")
print(f"Deduplication rate: {result['final_metrics']['deduplication_rate']:.2%}")
```

## How It Works

### Main Loop (orchestrator.py)

```
ITERATION 1:
  ✅ Run actor with config
  ⚠️ Detect error (if any)
    ├─ Propose fix
    ├─ Version fix
    └─ Retry with improved config
  📊 Evaluate improvement vs previous run
  🧠 Retrieve similar successful runs (RAG)
  ✅ Apply best config from RAG
  💾 Compress memory (if needed)
  🛑 Check: Continue or terminate?

ITERATION 2, 3, ...: Repeat until convergence
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| **Orchestrator** | `orchestrator.py` | Main loop coordinator |
| **Evaluation** | `loop/evaluation.py` | Compare quality metrics |
| **Error Handling** | `error_fix/detect.py`, `fix_prompt.py` | Auto-fix errors |
| **RAG** | `rag/embed.py`, `retrieve.py` | Find similar successful runs |
| **Memory** | `memory/compress.py` | Claude-powered summarization |
| **Apify Integration** | `apify_integration.py` | Actor runner + mock client |

## Example Flow

```
Config v1:
  batch_size=100, search_query="tech founders"
  → Run actor → 1200 leads, Dedup=92%, Valid=95%, 1 error
  → Detect rate_limit error
  → Propose: reduce batch_size to 50 + add backoff
  → Config v2

Config v2:
  batch_size=50, retry_strategy={...}
  → Run actor → 1250 leads, Dedup=94%, Valid=96%, 0 errors
  → ✅ Improvement! Quality: 0.95 (was 0.935)
  → Retrieve RAG: Found 3 similar runs with higher dedup rates
  → Apply best practice: add dedup_filter=True
  → Config v3

Config v3:
  batch_size=50, retry_strategy={...}, dedup_filter=True
  → Run actor → 1300 leads, Dedup=96%, Valid=97%, 0 errors
  → ✅ Improvement! Quality: 0.965
  → 2 consecutive runs with improvement → Keep iterating

Config v4, v5:
  [Small improvements, eventually plateau]
  → No improvement for 2 consecutive runs
  → 🛑 TERMINATE: Converged
  
Final Summary:
  ✅ 5 iterations → Final config produces 1300 leads @ 96% dedup
  💾 Memory compressed into snapshot
```

## Configuration

### loop/config.yaml
```yaml
loop:
  max_iterations: 10            # Safeguard max
  no_improvement_threshold: 2   # Stop after 2 non-improving runs
  quality_metrics:
    - deduplication_rate        # Must be > 95%
    - lead_validation_rate      # Must be > 98%
    - processing_time_consistency

termination:
  triggers:
    - all_actors_exhausted
    - dedup_rate_below_threshold
    - api_rate_limit_hit
    - no_quality_improvement_for_n_runs: 2
```

### rag/config.yaml
```yaml
embedding:
  model: "text-embedding-3-small"
  dimensions: 1536

retrieval:
  top_k: 20  # Retrieve top-20 similar runs (tunable)
  min_similarity_score: 0.7
```

## Evaluation Metrics

The agent optimizes for a **weighted quality score**:
```
Quality = 0.35×Dedup + 0.35×Validation + 0.20×Volume + 0.10×ErrorRecovery
```

- **Deduplication Rate** (35%): No duplicate emails
- **Validation Rate** (35%): All required fields present
- **Volume** (20%): Lead count
- **Error Recovery** (10%): Fewer errors

## Cost Estimates

| Component | Cost | Frequency |
|-----------|------|-----------|
| OpenAI embeddings | ~$0.00002 per 1K tokens | Per RAG retrieval (every iteration) |
| Claude summarization | ~$0.01 | Per memory compression (every 50 runs) |
| Apify actor | Varies | Per run (depends on actor) |
| **Total per 50 runs** | ~$0.50 | Budget-friendly |

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### "rate limit error" loops infinitely
- Check `error_fix/config.yaml`: max_retries and backoff_base
- Reduce `batch_size` in actor config
- Implement exponential backoff

### RAG not finding similar runs
- Ensure `rag/config.yaml` has proper embedding model
- Check `min_similarity_score` (lower = more results)
- Increase history size (need 10+ runs for good retrieval)

### Memory compression fails
- Check `ANTHROPIC_API_KEY` is valid
- Monitor API rate limits
- Use fallback local summary if API fails

## Next Steps

1. **Customize soul.md** for your use case
2. **Connect to real Apify actor** (replace mock client)
3. **Tune evaluation weights** in `loop/evaluation.py`
4. **Run improvement loop** and monitor logs
5. **Save final config** for production deployment

## Architecture Alignment with @precisox Guide

✅ **soul.md**: Agent identity + accountability loop  
✅ **RAG**: Semantic retrieval (top-20 similar runs)  
✅ **Loop Termination**: Quality gate (no improvement → stop)  
✅ **Error Fixing**: Detect → Propose → Version → Re-execute  
✅ **Memory Compression**: Claude API + snapshots  

---

**Author**: Based on @precisox's self-improving agent framework  
**Status**: Production-ready with mock testing, ready for Apify integration
