# Self-Improving Lead Scraper — Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (Main Loop)                     │
│                      orchestrator.py                            │
└──────────────┬──────────────────────────────────────────────────┘
               │
        Coordinates Loop
               │
    ┌──────────┼──────────┬──────────┬──────────┬─────────────┐
    │          │          │          │          │             │
    ▼          ▼          ▼          ▼          ▼             ▼
┌────────┐┌────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
│ Run    ││ Detect ││ Evaluate ││ RAG      ││ Compress ││Terminate │
│ Actor  ││ Error  ││ Quality  ││ Retrieve ││ Memory   ││ Loop     │
├────────┤├────────┤├──────────┤├──────────┤├──────────┤├──────────┤
│apify   ││error   ││loop/eval ││rag/      ││memory/   ││loop/term │
│_integ  ││_fix/   ││uation   ││          ││compress  ││inate     │
│        ││detect  ││          ││          ││          ││          │
└────────┘└────────┘└──────────┘└──────────┘└──────────┘└──────────┘
    │          │          │          │          │             │
    └──────────┴──────────┴──────────┴──────────┴─────────────┘
               │
        Returns to Orchestrator
               │
               ▼
        Continue Loop or Exit?
```

---

## Component Interactions

### 1️⃣ Actor Execution

```
┌──────────────────────────┐
│   Orchestrator.run_actor │
└────────┬─────────────────┘
         │
         ▼
    ApifyClient (real) or MockApifyClient (test)
         │
         ├─ Run Apify actor with current config
         ├─ Collect results (leads, metrics)
         ├─ Calculate dedup_rate & validation_rate
         └─ Return RunResult dict
         
    RunResult = {
        run_id, actor_name, config,
        lead_count, dedup_rate, validation_rate,
        processing_time, error, error_count
    }
```

### 2️⃣ Error Detection & Fix

```
┌──────────────────────────────────┐
│ Orchestrator._handle_error(result)
└────────┬─────────────────────────┘
         │
         ▼
    ErrorDetector.detect(error_msg)
         ├─ Regex pattern matching
         ├─ Classify: rate_limit | config | parsing | validation
         └─ Return error_info dict
         
         ▼
    PromptFixer.propose_fix(error_info, current_config)
         ├─ Analyze error type
         ├─ Generate fix (adjust config, retry logic, etc)
         └─ Return fix_proposal dict
         
         ▼
    PromptFixer.version_and_commit(fix_proposal, run_id)
         ├─ Create timestamped JSON version
         ├─ Store in prompt_history/
         └─ Return version_id
         
         ▼
    Return improved_config to orchestrator
```

### 3️⃣ Quality Evaluation

```
┌────────────────────────────────────────┐
│ Orchestrator._evaluate_and_check_term  │
└────────┬─────────────────────────────────┘
         │
         ▼
    EvaluationEngine.evaluate_improvement(run_a, run_b)
         ├─ Normalize metrics to 0-1
         ├─ Calculate weighted quality score:
         │  Quality = 0.35×Dedup + 0.35×Valid + 0.20×Volume + 0.10×Errors
         ├─ Compare: score_b - score_a → improvement_delta
         └─ Return EvaluationScore (delta, components, recommendation)
         
         ▼
    LoopTerminator.add_run(metrics)
    LoopTerminator.should_terminate()
         ├─ Check quality thresholds (dedup>95%, valid>98%)
         ├─ Count consecutive non-improving runs
         ├─ Check max_iterations
         └─ Return (should_stop, reason)
         
         ▼
    Return (should_continue, reason) to orchestrator
```

### 4️⃣ Semantic Retrieval (RAG)

```
┌──────────────────────────────────────┐
│ Orchestrator._apply_rag_improvements  │
└────────┬──────────────────────────────┘
         │
         ▼
    embed(current_config_text)
         ├─ Use OpenAI text-embedding-3-small
         └─ Return 1536-dim vector
         
         ▼
    Build stored_embeddings from run_history[:-1]
         ├─ Embed each past run's config
         └─ Collect [(run_id, embedding), ...]
         
         ▼
    retrieve_with_scores(query_emb, stored_embeddings, top_k=5)
         ├─ Calculate cosine_similarity for each
         ├─ Filter by min_similarity_score (0.7)
         ├─ Sort by similarity descending
         └─ Return [(run_id, score), ...] top_k
         
         ▼
    Extract best_config from similar successful runs
         ├─ Filter: error_count == 0
         ├─ Rank by quality score
         └─ Return config with highest quality
         
         ▼
    Return improved_config to orchestrator
```

### 5️⃣ Memory Compression

```
┌────────────────────────────────────────┐
│ Orchestrator._compress_memory()         │
└────────┬────────────────────────────────┘
         │
         ▼
    MemoryCompressor.should_compress()
         ├─ Increment run_counter
         └─ Check: run_counter % trigger_count == 0?
         
         ▼ (if yes)
    MemoryCompressor.compress(run_history, conversation_pointer)
         │
         ├─ Extract quantitative metrics (local)
         │   - avg dedup, validation, volume, errors
         │
         ├─ Call Claude API (if api_key available)
         │   ├─ Format runs for Claude
         │   ├─ Send summarization prompt
         │   └─ Receive 500-token information-dense summary
         │
         ├─ Extract patterns (local)
         │   - top_actors, error_patterns, dedup_rules
         │
         └─ Assemble snapshot JSON
             ├─ Metrics, claude_summary, patterns
             ├─ conversation_pointer (for retrieval)
             └─ Save to snapshots/snapshot_TIMESTAMP.json
             
         ▼
    Return snapshot_id to orchestrator
```

---

## Data Flow Example

### Single Iteration

```
INPUT: Current Config
  {search_query: "tech founders", batch_size: 100}

│
├─→ RUN ACTOR
│   └─→ Apify returns: {leads: 1200, dedup: 92%, valid: 95%, error: "rate_limit"}
│
├─→ DETECT ERROR
│   └─→ ErrorDetector: "rate_limit" (confidence: 0.95)
│
├─→ PROPOSE FIX
│   └─→ PromptFixer: "reduce batch_size to 50 + add backoff"
│
├─→ VERSION FIX
│   └─→ Saved: prompt_history/fix_run_001_20260918_120000.json
│
├─→ Apply fix, RETRY (next iteration)
│   └─→ New Config: {search_query: ..., batch_size: 50, backoff: {...}}
│
├─→ RUN ACTOR (fixed config)
│   └─→ Apify returns: {leads: 1250, dedup: 94%, valid: 96%, error: None}
│
├─→ EVALUATE QUALITY
│   ├─→ prev quality: (0.92 + 0.95) / 2 = 0.935
│   ├─→ curr quality: (0.94 + 0.96) / 2 = 0.95
│   └─→ delta: +0.015 ✅ IMPROVEMENT
│
├─→ RAG RETRIEVAL
│   ├─→ Embed: "batch_size: 50, backoff: {...}"
│   ├─→ Retrieve: 5 similar past runs with high dedup
│   └─→ Best practice: "Add dedup_filter=True from run_042"
│
├─→ APPLY RAG IMPROVEMENT
│   └─→ New Config: {..., dedup_filter: True}
│
├─→ COMPRESS MEMORY (if trigger)
│   └─→ Claude summarizes 50 runs → 500-token snapshot
│
├─→ CHECK TERMINATION
│   └─→ Quality good, improvements continuing → Continue
│
└─→ OUTPUT: {should_continue: True, next_config: {...}}

NEXT ITERATION STARTS WITH NEW CONFIG
```

---

## File Dependencies

```
orchestrator.py (main)
├── imports from rag/
│   ├── rag/embed.py
│   └── rag/retrieve.py
├── imports from loop/
│   ├── loop/evaluation.py
│   └── loop/terminate.py
├── imports from error_fix/
│   ├── error_fix/detect.py
│   └── error_fix/fix_prompt.py
├── imports from memory/
│   └── memory/compress.py
└── imports from apify_integration.py

apify_integration.py
├── ApifyClient (external: apify_client)
└── MockApifyClient (internal)

loop/evaluation.py (standalone, no internal imports)
loop/terminate.py (standalone, no internal imports)

error_fix/detect.py (standalone, uses: re, enum)
error_fix/fix_prompt.py (imports from error_fix/detect.py)

rag/embed.py (external: openai)
rag/retrieve.py (external: numpy)

memory/compress.py (external: anthropic, json, yaml)
```

---

## Configuration Files

### rag/config.yaml
```yaml
embedding:
  model: "text-embedding-3-small"  # 1536 dimensions
  dimensions: 1536

retrieval:
  top_k: 20                        # Retrieve top-20 similar configs
  min_similarity_score: 0.7        # Filter by similarity threshold
```

### loop/config.yaml
```yaml
loop:
  max_iterations: 10               # Safeguard max
  no_improvement_threshold: 2      # Stop after N non-improving runs
  quality_metrics:
    - deduplication_rate           # Must exceed 95%
    - lead_validation_rate         # Must exceed 98%

termination:
  triggers:
    - no_quality_improvement_for_n_runs: 2
```

### memory/config.yaml
```yaml
memory:
  compression:
    strategy: "periodic_summarize"
    trigger: "every_50_runs"       # Compress after 50 scraping runs
```

### error_fix/config.yaml
```yaml
error_detection:
  types:
    - validation_error
    - actor_config_error
    - rate_limit_error
    - parsing_error
```

---

## API Integrations

| Service | Module | Usage | Cost |
|---------|--------|-------|------|
| **OpenAI** | rag/embed.py | text-embedding-3-small | ~$0.00002 per 1K tokens |
| **Anthropic** | memory/compress.py | Claude 3.5 Sonnet summarization | ~$0.01 per compression |
| **Apify** | apify_integration.py | Actor execution | Variable (per actor) |

---

## Execution Timeline

```
ORCHESTRATOR LOOP (Max 10 iterations or until convergence)

Iteration 1:
  T=0.0s   Start
  T=0.1s   Run actor (Apify) → ~5-6 seconds
  T=5.1s   Detect error (if any)
  T=5.2s   Propose fix (if error)
  T=5.3s   Evaluate quality
  T=5.4s   RAG retrieval & embedding (~1s per retrieval)
  T=6.4s   Termination check
  T=6.5s   Memory compression (if triggered, ~2-3s with Claude)
  ────────────────────────────────────────────────────
  T=6.5s   DECISION: Continue? Yes → Next iteration

Iteration 2:
  T=6.6s   Run actor with improved config
  T=11.7s  [Repeat above]
  ...

Iteration N (Convergence):
  T=X.Xs   Termination check → No improvement for 2 runs
  T=X.Xs   🛑 STOP: Return summary
```

**Estimated runtime for full loop (5 iterations)**: ~35-40 seconds  
**Estimated cost** (with Claude): ~$0.05-0.10

---

## Error Recovery Paths

```
ERROR DETECTED IN RESULT
    ↓
    ├─ Rate Limit Error
    │   ├─ Fix: reduce batch_size, add exponential backoff
    │   └─ Retry: reduce by 50%
    │
    ├─ Config Error
    │   ├─ Fix: validate schema, check required fields
    │   └─ Retry: after manual review
    │
    ├─ Parsing Error
    │   ├─ Fix: add error handling for malformed responses
    │   └─ Retry: with fallback field values
    │
    └─ Validation Error
        ├─ Fix: enable deduplication, remove nulls
        └─ Retry: with stricter validation
```

---

## Scaling Considerations

### Horizontal Scaling
- Run multiple orchestrators for different actors in parallel
- Use `ApifyBatchRunner` to test multiple strategies simultaneously
- Compare results and pick best converged config

### Vertical Scaling
- Increase `top_k` in RAG for more comprehensive search
- Increase `max_iterations` for deeper optimization
- Add more evaluation metrics (beyond dedup + validation)

### Cost Optimization
- Cache embeddings to reduce OpenAI API calls
- Batch memory compression across multiple agents
- Use MockApifyClient for testing/development

---

**Last Updated**: 2026-09-18  
**Status**: ✅ Production-Ready
