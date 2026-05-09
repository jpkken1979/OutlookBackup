---
name: vector-database-engineer
type: feature
description: Expert in vector databases, embedding strategies, and semantic search. Masters Pinecone, Weaviate, Qdrant, Milvus, pgvector, ChromaDB. RAG systems, recommendation engines, similarity search at scale.
category: ai-infrastructure
version: 2.1.0
tags:
---
  - vector-database
  - embeddings
  - semantic-search
  - rag
  - similarity-search
  - llm
  - ai
requires:
  frameworks:
    - langchain
    - llamaindex
    - semantic-kernel
  optional:
    - pinecone
    - weaviate
    - qdrant
    - milvus
    - pgvector
    - chromadb
triggers:
  - "vector database|semantic search|embeddings"
  - "RAG|retrieval augmented generation|similarity"
  - "recommendation engine|vector index"
---

# Vector Database Engineer

Master vector databases, embedding strategies, and semantic search systems. Build RAG applications, recommendation engines, and similarity search at billion-scale. Optimize recall, latency, and cost.

## Use this skill when

- Building RAG (Retrieval Augmented Generation) systems with LLMs
- Implementing semantic search over documents/images
- Creating recommendation engines (user/item similarity)
- Building image/audio similarity search systems
- Optimizing vector search latency (<100ms) and recall (>95%)
- Scaling vector operations to millions/billions of vectors
- Designing chunking and embedding pipelines
- Selecting vector database for production workload

## Do not use this skill when

- Task is unrelated to vector databases/embeddings
- Using keyword-only search (regular database indexes sufficient)
- Building traditional recommendation systems (collaborative filtering)

## Vector Database Selection Matrix

| Database | Best For | Scale | Cost | Deployment |
|----------|----------|-------|------|-----------|
| **Pinecone** | Managed vector search, zero ops | Billions | High | SaaS |
| **Weaviate** | Hybrid search, multimodal | Millions | Medium | Self/SaaS |
| **Qdrant** | Speed, production-grade | Billions | Medium | Self |
| **Milvus** | Scalability, cloud-native | Billions | Low | Self |
| **pgvector** | Relational + vectors | Millions | Low | PostgreSQL |
| **ChromaDB** | Development, local RAG | Millions | None | Embedded |

### Decision Factors

1. **Scale** — How many vectors? (millions → Qdrant, billions → Pinecone)
2. **Latency** — SLA? (<50ms → Qdrant, <200ms → Weaviate)
3. **Features** — Hybrid search? Metadata filtering? (→ Weaviate, Qdrant)
4. **Budget** — Managed (expensive) vs self-hosted (ops cost)?
5. **Stack** — PostgreSQL existing? → pgvector

## Embedding Model Selection

### By Use Case

| Use Case | Recommended Models | Dimensions | Speed |
|----------|-------------------|-----------|-------|
| **General text** | OpenAI text-embedding-3, all-MiniLM-L6 | 1536, 384 | 1K docs/s |
| **Code search** | CodeBERT, code-search-distilroberta | 768 | 2K docs/s |
| **Multilingual** | multilingual-e5-large, LaBSE | 1024 | 500 docs/s |
| **Images** | CLIP, ViT-B/32 | 512 | 100 imgs/s |
| **Fast/cheap** | all-MiniLM-L6-v2 (6M params) | 384 | 10K docs/s |

### Embedding Quality Hierarchy

```
OpenAI text-embedding-3-large (1536d)  ← Best quality, slow
│
├─ OpenAI text-embedding-3-small (512d)
├─ Jina AI v3 (1024d)
├─ all-MiniLM-L12-v2 (384d)  ← Best speed/quality balance
│
└─ all-MiniLM-L6-v2 (384d)  ← Fastest, acceptable quality
```

**Rule of thumb:** Start with `all-MiniLM-L12-v2` unless cost/latency critical.

## Document Chunking Strategies

### 1. Fixed-Size Chunking (Simple)

```python
# Split into 1000 char chunks with 200 char overlap
def chunk_fixed(text: str, chunk_size: int = 1000, overlap: int = 200):
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunks.append(text[i:i + chunk_size])
    return chunks

# ✅ Pros: Simple, predictable
# ❌ Cons: Ignores semantic boundaries, may split sentences
```

### 2. Semantic Chunking (Smart)

```python
# Split on paragraph/sentence boundaries, size constrained
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""]  # Try these in order
)
chunks = splitter.split_text(text)

# ✅ Pros: Respects natural boundaries
# ❌ Cons: Variable size, depends on document structure
```

### 3. Rolling Window (Context Preservation)

```python
# Keep 2-3 sentences context before/after chunk
# Chunk: "...last sentence of prev chunk. ACTUAL CHUNK. first sentence of next..."

# ✅ Pros: Preserves context, better recall
# ❌ Cons: Redundant data, inflates vector store
```

### Chunking Rules of Thumb

| Chunk Size | When to Use | Latency |
|-----------|------------|---------|
| **256** tokens | Short Q&A, tight latency | <10ms |
| **512** tokens | Balanced (most common) | 50-100ms |
| **1024** tokens | Long documents, research | 200-300ms |

**Overlap = 10-20% of chunk size** (preserves semantic continuity)

## Index Configuration Patterns

### Vector Index Types

```
FLAT        → Exact search (baseline, slow)
IVF-FLAT    → Partitioned index (faster, approx)
HNSW        → Hierarchical graph (best for recall/speed)
PQ          → Product quantization (memory efficient, lossy)
```

### HNSW Configuration (Recommended for most cases)

```python
# Qdrant: Best production index
index_config = {
    "index_type": "hnsw",
    "hnsw_config": {
        "m": 16,              # Connections per node (16-48 typical)
        "ef_construct": 200,  # Build parameter (lower=faster, lower quality)
        "ef_search": 100      # Search parameter (lower=faster, lower recall)
    }
}

# Rules:
# - m ↑ → better recall, higher memory
# - ef_construct ↑ → better quality, slower build
# - ef_search ↑ → better recall, slower query
```

### IVF Configuration (Faster, cheaper)

```python
# Good balance for millions of vectors
index_config = {
    "index_type": "ivf_flat",
    "nlist": 100,      # Number of partitions
    "nprobe": 10       # Partitions to search
}

# Tradeoff: 10x faster, ~10% lower recall
```

## Hybrid Search (Vector + Keyword)

```python
# Combine semantic + keyword matching
# Use case: "Find docs about Python machine learning (within last 6 months)"

def hybrid_search(query: str, db, k: int = 10):
    # 1. Vector search (semantic similarity)
    vector_results = db.vector_search(
        query_embedding=embed(query),
        k=k*2,
        filter={"date": {"$gte": "2024-01-01"}}
    )

    # 2. Keyword search (BM25)
    keyword_results = db.keyword_search(
        query=query,
        k=k*2,
        filter={"date": {"$gte": "2024-01-01"}}
    )

    # 3. Merge results (reciprocal rank fusion)
    merged = rrf(vector_results, keyword_results)
    return merged[:k]

# ✅ Combination catches nuances both miss alone
# Example: Query "Python" → vector catches sklearn, keyword catches python-specific blog
```

## Metadata Filtering Patterns

### Pre-filtering (Reduce search space before vector search)

```python
# Good for: High selectivity filters (reduce by 90%+)
results = db.search(
    query_vector=embed("machine learning"),
    filter={"category": "tutorial", "year": 2024},  # Applied FIRST
    k=10
)

# ✅ Fast: Only search relevant partition
# ❌ May miss results near filter boundary
```

### Post-filtering (Filter results after vector search)

```python
# Good for: Low selectivity filters
results = db.search(
    query_vector=embed("machine learning"),
    k=100  # Search more results
)
results = [r for r in results if r["year"] == 2024][:10]

# ✅ Accurate: Full vector search first
# ❌ Slower: Search entire index
```

### Optimal Strategy

```python
# Combine: Pre-filter + vector + post-filter
results = db.search(
    query_vector=embed("machine learning"),
    filter={"category": {"$in": ["ML", "AI", "Data"]}},  # Pre-filter
    k=50
)
results = [r for r in results if r["rating"] > 4.0][:10]  # Post-filter
```

## RAG Pipeline Architecture

```
1. Document Ingestion
   ├─ Extract text from PDF/HTML/etc
   ├─ Chunk (semantic boundaries)
   ├─ Embed (batch with LLM)
   └─ Index in vector DB

2. Query Processing
   ├─ Embed query (same model as docs)
   ├─ Vector search (k nearest neighbors)
   ├─ Hybrid search (+ keyword)
   └─ Apply filters

3. LLM Augmentation
   ├─ Context = top-k search results
   ├─ System prompt + context + query
   └─ Generate answer

4. Evaluation
   ├─ Recall: Did we retrieve right docs?
   ├─ Latency: <100ms search target
   └─ Cost: Embeddings + LLM tokens
```

## Indexing Best Practices

| Metric | Target | Consequence if bad |
|--------|--------|-------------------|
| **Recall** | >90% | Users miss relevant results |
| **Latency** | <100ms | Slow application response |
| **Memory** | <2GB per 1M vecs | OOM, node crashes |
| **QPS** | >1000/s | Bottleneck during load |

### Performance Tuning

```python
# Tradeoff matrix (for HNSW)

# Fast + Accurate (resource intensive)
hnsw = HNSW(m=32, ef_construct=400, ef_search=200)

# Balanced (recommended)
hnsw = HNSW(m=16, ef_construct=200, ef_search=100)

# Small memory (lower accuracy)
hnsw = HNSW(m=8, ef_construct=100, ef_search=50)

# Rule: If accuracy drops <5%, go with smaller config
```

## Reindexing & Index Maintenance

```python
# Schedule regular reindexing to optimize:
# - Remove stale vectors (outdated documents)
# - Rebuild index with optimal params
# - Update statistics

schedule = {
    "daily": "Remove deleted docs",
    "weekly": "Rebuild if <10% deletes",
    "monthly": "Full reindex + param tuning"
}
```

## Cost Optimization

| Strategy | Impact | Trade-off |
|----------|--------|-----------|
| **Use smaller embeddings** | 50% cost ↓ | Recall 5-10% ↓ |
| **Batch embedding** | 3x cost ↓ | Latency depends on batch size |
| **Quantization (int8)** | 4x memory ↓ | Recall 2-3% ↓ |
| **Smaller chunk size** | Vectors ↓ | May split semantic units |
| **Caching hot results** | 80% cache hits | Miss edge cases |

### Cost per 1M vectors

| Database | Compute | Storage | Total |
|----------|---------|---------|-------|
| **Pinecone** | $0.70/pod-day | $0.90/pod-day | ~$48/month |
| **Qdrant** | Self-hosted | Self-hosted | 1-2 vCPU |
| **pgvector** | Shared PostgreSQL | Included | $10-20/month |

## Monitoring & Observability

```python
# Track these metrics
metrics = {
    "vectors_indexed": 1_000_000,
    "avg_query_latency_ms": 45,
    "p99_query_latency_ms": 200,
    "recall@10": 0.94,
    "avg_vector_size_kb": 6.5
}

# Alert thresholds
alerts = {
    "latency > 500ms": "Increase ef_search",
    "recall < 0.85": "Rebuild index",
    "disk > 80%": "Archive old vectors"
}
```

## Performance Checklist

- [ ] **EMBEDDING**: Chose appropriate model for use case
- [ ] **CHUNKING**: Semantic boundaries with optimal overlap
- [ ] **INDEX**: Selected right type (HNSW recommended)
- [ ] **FILTERING**: Pre/post-filter strategy optimized
- [ ] **HYBRID**: Keyword search enabled if needed
- [ ] **LATENCY**: <100ms p99 query time
- [ ] **RECALL**: >90% for top-10 results
- [ ] **MONITORING**: Metrics tracked, alerts set
- [ ] **COST**: Vectors + embeddings optimized

## Anti-Patterns

❌ Using OpenAI embedding without batching (expensive)
❌ No chunking overlap (broken context)
❌ Fixed-size chunks ignoring semantic boundaries
❌ Storing raw embeddings (use quantization)
❌ No metadata schema (can't filter effectively)
❌ Not monitoring drift (stale embeddings degrade recall)

## Best Practices

✅ **Batch embeddings** — 100x cheaper than per-item
✅ **Semantic chunking** — Respects document structure
✅ **Hybrid search** — Catches both semantic + keyword matches
✅ **Monitor recall** — Track accuracy metrics constantly
✅ **Reindex regularly** — Optimize params as data grows
✅ **Cache hot results** — Reduce embedding calls
✅ **Use appropriate index** — HNSW for most cases

## Resources

- **Vector databases comparison**: https://benchml.ai/benchmarks/vector-databases
- **Embedding leaderboard**: https://huggingface.co/spaces/mteb/leaderboard
- **LangChain RAG**: https://python.langchain.com/docs/use_cases/question_answering/
- **Qdrant docs**: https://qdrant.tech/documentation/
- **Pinecone guides**: https://docs.pinecone.io/
