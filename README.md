# Lead Scraper Agent

Self-improving agent for extracting high-quality leads via Apify actors with automatic error fixing, quality evaluation, semantic retrieval, and memory compression.

## ⚡ Quick Start

**For first-time users**: See [QUICKSTART.md](QUICKSTART.md)

```python
from orchestrator import SelfImprovingOrchestrator
from apify_integration import MockApifyClient

mock_client = MockApifyClient()
orchestrator = SelfImprovingOrchestrator(
    apify_client=mock_client,
    initial_config={"search_query": "tech founders", "batch_size": 100},
    actor_name="apollo_google_search",
    max_iterations=5,
)
result = orchestrator.run_improvement_loop()
```

## Project Structure

```
agent-lead-scraper/
├── README.md                      # This file
├── QUICKSTART.md                  # Quick start guide
├── soul.md                        # Agent identity + rules + accountability loop
├── orchestrator.py                # 🎯 Main self-improving loop coordinator
├── apify_integration.py           # Apify client wrapper + mock client
├── requirements.txt               # Python dependencies
├── rag/
│   ├── embed.py                   # Semantic embedding (OpenAI)
│   ├── retrieve.py                # Cosine similarity + top-k retrieval
│   └── config.yaml                # Embedding model, retrieval params
├── loop/
│   ├── evaluation.py              # ✅ Quality evaluation engine (NEW)
│   ├── terminate.py               # Quality gate: stop when no improvement
│   └── config.yaml                # max_iterations, termination rules
├── error_fix/
│   ├── detect.py                  # Error detection (4 types)
│   ├── fix_prompt.py              # Propose fix → version → commit
│   ├── config.yaml                # Error handling strategy
│   └── prompt_history/            # Versioned fixes (timestamped JSON)
└── memory/
    ├── compress.py                # ✅ Claude API summarization (NEW)
    ├── config.yaml                # Compression triggers, retention
    └── snapshots/                 # Compressed summaries + pointers
```

## Architecture & Features

### 1. **Self-Improving Loop** (orchestrator.py)
Coordinates all components in sequence:
```
Run Actor → Detect Error → Propose Fix → Evaluate Quality 
→ Retrieve Similar Runs (RAG) → Apply Best Practice → Compress Memory → Check Termination
```

### 2. **Quality Evaluation** (loop/evaluation.py) ✅ NEW
- Weighted quality score: 35% Dedup + 35% Validation + 20% Volume + 10% Error Recovery
- Compares run-to-run improvements
- Generates recommendations (ACCEPT/REJECT/RETRY)

### 3. **Error Handling** (error_fix/)
- Detects: rate_limit, actor_config, parsing, validation errors
- Proposes fixes automatically
- Versions all changes for reproducibility

### 4. **Semantic Retrieval** (rag/)
- Embeds successful actor configs
- Retrieves top-20 similar runs
- Applies best practices from similar successful runs

### 5. **Claude-Powered Memory Compression** (memory/compress.py) ✅ NEW
- Summarizes every 50 runs using Claude API
- Generates information-dense snapshots (500 tokens)
- Maintains pointer to full conversation
- Fallback local summary if API fails

### 6. **Apify Integration** (apify_integration.py) ✅ NEW
- Real Apify client wrapper
- Mock client for testing (no API keys needed)
- Batch runner for multi-actor experiments

## 📊 Improvement Flow Example

```
Iteration 1: Run actor
  → 1200 leads, Dedup=92%, Valid=95%
  → ERROR: Rate limit detected
  → Fix: Reduce batch_size + add backoff
  
Iteration 2: Re-run with fix
  → 1250 leads, Dedup=94%, Valid=96%
  → ✅ Improvement! (Quality: 0.935 → 0.95)
  → RAG: Found 3 similar runs with high dedup rates
  → Apply: Enable dedup_filter=True

Iteration 3: Re-run with both fixes
  → 1300 leads, Dedup=96%, Valid=97%
  → ✅ Improvement! (Quality: 0.95 → 0.965)
  → Continue...

Iteration 4-5: Marginal improvements, then plateau
  → 2 consecutive runs with no improvement
  → 🛑 TERMINATE: Converged at 96% dedup
  → 💾 Compress memory snapshot
  → ✅ Final config saved
```

## 🚀 Implementation Status

| Feature | Status | File |
|---------|--------|------|
| soul.md | ✅ Complete | `soul.md` |
| RAG Embedding | ✅ Complete | `rag/embed.py` |
| RAG Retrieval | ✅ Complete | `rag/retrieve.py` |
| Error Detection | ✅ Complete | `error_fix/detect.py` |
| Error Fix Generation | ✅ Complete | `error_fix/fix_prompt.py` |
| Quality Evaluation | ✅ Complete | `loop/evaluation.py` |
| Loop Termination | ✅ Complete | `loop/terminate.py` |
| Claude Memory Compression | ✅ Complete | `memory/compress.py` |
| Apify Integration | ✅ Complete | `apify_integration.py` |
| Main Orchestrator | ✅ Complete | `orchestrator.py` |
| **PRODUCTION READY** | ✅ **YES** | — |

## 💡 Alignment with @precisox Framework

✅ **soul.md** (slot #1): Identity + hard rules + accountability loop  
✅ **RAG**: Semantic retrieval (top-20 relevant configs, not 2,000)  
✅ **Loop Termination**: Quality gate (2 non-improving runs → stop)  
✅ **Error Detection & Fix**: Auto-detect, propose, version, re-execute  
✅ **Memory Compression**: Claude-powered summarization + snapshots  

---

See [QUICKSTART.md](QUICKSTART.md) for setup and usage.  
See [soul.md](soul.md) for agent rules and accountability loop.
