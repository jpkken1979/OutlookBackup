---
type: feature
name: hybrid-search-implementation
description: "Master hybrid search combining vector embeddings and keyword/BM25 matching for improved RAG recall. Covers combining semantic and lexical search, ranking fusion algorithms (RRF, linear combination), reranking with LLMs, vector database query optimization, and handling sparse vs dense embeddings. Includes patterns for product search (exact SKU matching + semantic similarity), support tickets (category keywords + semantic), code search (exact symbol + semantic), and domain-specific search. Use when building RAG systems with improved recall, searching product catalogs with exact SKUs, handling queries with specific terms/codes, improving domain-specific vocabulary matching, or when vector-only search misses important lexical matches."
---

# Hybrid Search: Vector + Keyword Fusion

Master combining vector embeddings and keyword matching for high-recall, precise retrieval.

---

## Core Challenge: Vector vs Keyword Search

| Aspect | Vector Search | Keyword Search | Hybrid |
|--------|---------------|----------------|--------|
| **How it works** | Semantic similarity in embedding space | Exact/substring matching (BM25) | Both simultaneously |
| **Excels at** | Semantically similar items | Exact terms, numbers, codes | Everything |
| **Misses** | Exact matches (e.g., SKU-123) | Related meanings | Rare |
| **Latency** | 10-100ms | 1-10ms | 20-150ms (combined) |
| **Index size** | Large (dense vectors) | Small (inverted index) | Both needed |
| **Example** | Find docs about "unauthorized access" | Find doc containing "SKU-ABC-789" | Both cases work |

---

## Pattern 1: BM25 Keyword Search Baseline

### TF-IDF Ranking with BM25

```python
from rank_bm25 import BM25Okapi
from typing import List, Tuple

class KeywordSearcher:
    """BM25-based lexical search for exact term matching."""

    def __init__(self, documents: List[str]):
        # Tokenize documents
        self.corpus = [doc.split() for doc in documents]
        self.bm25 = BM25Okapi(self.corpus)
        self.documents = documents

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Search documents by keyword relevance."""
        query_tokens = query.split()
        scores = self.bm25.get_scores(query_tokens)

        # Get top K results with scores
        ranked = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        return [
            (self.documents[idx], score)
            for idx, score in ranked
        ]

# Example: Support ticket search
tickets = [
    "User cannot login to account - password reset failed",
    "Database connection timeout in production",
    "Feature request: Add dark mode to UI",
]

searcher = KeywordSearcher(tickets)
results = searcher.search("password login issue", top_k=2)
# Returns: [("User cannot login...", 2.15), ("Feature request...", 0.3)]
```

---

## Pattern 2: Vector Search with Embeddings

### Semantic Similarity Retrieval

```python
import numpy as np
from typing import List, Tuple
from sentence_transformers import SentenceTransformer

class VectorSearcher:
    """Semantic search using embeddings."""

    def __init__(self, documents: List[str], model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.documents = documents
        self.embeddings = self.model.encode(documents)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Find semantically similar documents."""
        query_embedding = self.model.encode(query)

        # Cosine similarity
        scores = np.dot(self.embeddings, query_embedding) / (
            np.linalg.norm(self.embeddings, axis=1) *
            np.linalg.norm(query_embedding)
        )

        ranked = np.argsort(-scores)[:top_k]
        return [
            (self.documents[idx], float(scores[idx]))
            for idx in ranked
        ]

# Example
docs = [
    "The cat sat on the mat",
    "Dogs are loyal pets",
    "Feline animals are independent",
]

searcher = VectorSearcher(docs)
results = searcher.search("cats are independent", top_k=2)
# Returns: semantically similar docs even if keyword doesn't match
```

---

## Pattern 3: Hybrid Search - Reciprocal Rank Fusion (RRF)

### Combining BM25 & Vector Rankings

```python
class HybridSearcher:
    """Combine keyword and vector search with rank fusion."""

    def __init__(self, documents: List[str]):
        self.bm25_searcher = KeywordSearcher(documents)
        self.vector_searcher = VectorSearcher(documents)

    def search_rrf(
        self,
        query: str,
        top_k: int = 5,
        k_constant: int = 60,  # RRF parameter
    ) -> List[Tuple[str, float]]:
        """Reciprocal Rank Fusion combining both results."""

        # Get results from both methods
        bm25_results = self.bm25_searcher.search(query, top_k=20)
        vector_results = self.vector_searcher.search(query, top_k=20)

        # Create rank dictionary
        ranks = {}

        for rank, (doc, score) in enumerate(bm25_results, 1):
            ranks[doc] = ranks.get(doc, 0) + 1 / (k_constant + rank)

        for rank, (doc, score) in enumerate(vector_results, 1):
            ranks[doc] = ranks.get(doc, 0) + 1 / (k_constant + rank)

        # Sort by combined RRF score
        sorted_results = sorted(
            [(doc, score) for doc, score in ranks.items()],
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        return sorted_results

# Usage
searcher = HybridSearcher(documents)
results = searcher.search_rrf("product SKU-123 not working")
# Combines: "SKU-123" exact match + "not working" semantic similarity
```

---

## Pattern 4: Weighted Combination (Linear Interpolation)

### Flexible Score Weighting

```python
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class SearchResult:
    document: str
    bm25_score: float
    vector_score: float
    combined_score: float

class WeightedHybridSearcher:
    """Hybrid search with tunable weights."""

    def __init__(
        self,
        documents: List[str],
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
    ):
        self.bm25_searcher = KeywordSearcher(documents)
        self.vector_searcher = VectorSearcher(documents)
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self.documents = documents

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[SearchResult]:
        """Combined weighted search."""

        # Get scores from both
        bm25_results = dict(self.bm25_searcher.search(query, top_k=20))
        vector_results = dict(self.vector_searcher.search(query, top_k=20))

        # Normalize scores to [0, 1]
        bm25_max = max(bm25_results.values()) if bm25_results else 1
        vector_max = max(vector_results.values()) if vector_results else 1

        bm25_norm = {k: v / bm25_max for k, v in bm25_results.items()}
        vector_norm = {k: v / vector_max for k, v in vector_results.items()}

        # Combine with weights
        combined = {}
        for doc in set(list(bm25_norm.keys()) + list(vector_norm.keys())):
            combined[doc] = (
                self.bm25_weight * bm25_norm.get(doc, 0) +
                self.vector_weight * vector_norm.get(doc, 0)
            )

        # Sort and return
        results = sorted(
            combined.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        return [
            SearchResult(
                document=doc,
                bm25_score=bm25_norm.get(doc, 0),
                vector_score=vector_norm.get(doc, 0),
                combined_score=score,
            )
            for doc, score in results
        ]

# Tune weights based on domain
# Product search (exact SKUs matter): bm25_weight=0.7, vector_weight=0.3
# Article search (semantic matters): bm25_weight=0.3, vector_weight=0.7
searcher = WeightedHybridSearcher(
    documents,
    bm25_weight=0.5,
    vector_weight=0.5,
)
```

---

## Pattern 5: LLM-Based Reranking

### Using LLM to Rerank Hybrid Results

```python
import anthropic

class RerankedHybridSearcher:
    """Use Claude to rerank hybrid search results."""

    def __init__(self, documents: List[str]):
        self.hybrid_searcher = WeightedHybridSearcher(documents)
        self.client = anthropic.Anthropic()

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Hybrid search with LLM reranking."""

        # Get initial results from hybrid search
        candidates = self.hybrid_searcher.search(query, top_k=10)

        # Rerank with Claude
        rankings = self._rerank_with_claude(query, candidates)

        return rankings[:top_k]

    def _rerank_with_claude(
        self,
        query: str,
        candidates: List[SearchResult],
    ) -> List[SearchResult]:
        """Ask Claude to rerank results by relevance."""

        candidates_text = "\n".join([
            f"{i+1}. {c.document}"
            for i, c in enumerate(candidates)
        ])

        prompt = f"""
        Query: {query}

        Candidate documents:
        {candidates_text}

        Rank these documents by relevance to the query.
        Return a newline-separated list of document numbers in order of relevance.
        """

        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse ranking
        ranking_text = response.content[0].text
        ranked_indices = [int(x.strip()) - 1 for x in ranking_text.strip().split()]

        return [candidates[i] for i in ranked_indices if i < len(candidates)]
```

---

## Pattern 6: Database Integration (PostgreSQL + pgvector)

### Production Hybrid Search with Database

```python
import psycopg
from pgvector.psycopg import register_vector

class ProductSearchDB:
    """Production hybrid search in PostgreSQL."""

    def __init__(self, conn_string: str):
        self.conn_string = conn_string
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def search_hybrid(
        self,
        query: str,
        top_k: int = 10,
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
    ) -> List[Dict]:
        """Hybrid search: keyword + semantic."""

        with psycopg.connect(self.conn_string) as conn:
            # BM25 full-text search
            bm25_query = """
            SELECT id, product_name, description,
                   ts_rank(search_vec, plainto_tsquery('english', %s)) as bm25_score
            FROM products
            WHERE search_vec @@ plainto_tsquery('english', %s)
            LIMIT 20
            """

            # Vector similarity search
            query_embedding = self.model.encode(query)
            vector_query = """
            SELECT id, product_name, description,
                   1 - (embedding <=> %s::vector) as vector_score
            FROM products
            ORDER BY embedding <=> %s::vector
            LIMIT 20
            """

            with conn.cursor() as cur:
                # Get BM25 results
                cur.execute(bm25_query, (query, query))
                bm25_results = {row[0]: row[3] for row in cur.fetchall()}

                # Get vector results
                cur.execute(vector_query, (query_embedding, query_embedding))
                vector_results = {row[0]: row[3] for row in cur.fetchall()}

            # Combine with weights
            all_ids = set(list(bm25_results.keys()) + list(vector_results.keys()))
            combined = {}

            for product_id in all_ids:
                bm25_score = bm25_results.get(product_id, 0)
                vector_score = vector_results.get(product_id, 0)

                # Normalize and combine
                combined[product_id] = (
                    bm25_weight * (bm25_score / max(bm25_results.values() or [1])) +
                    vector_weight * (vector_score / max(vector_results.values() or [1]))
                )

            # Fetch top results
            top_ids = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:top_k]

            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, product_name, description FROM products WHERE id = ANY(%s)",
                    ([id for id, _ in top_ids],)
                )
                return cur.fetchall()
```

---

## When to Use Each Strategy

| Strategy | Best For | Trade-offs |
|----------|----------|-----------|
| **BM25 only** | Exact keywords, codes, SKUs | Misses semantic similarity |
| **Vector only** | Semantic understanding, recommendations | Misses exact matches |
| **RRF Hybrid** | Balanced approach, unknown query type | Requires both indexes |
| **Weighted Hybrid** | Domain tuning (adjust weights) | Needs tuning per domain |
| **LLM Reranking** | High-quality results needed | Slow (LLM API calls) |
| **Database Hybrid** | Production at scale | Infrastructure complexity |

---

## Best Practices Checklist

| Practice | Why | How |
|----------|-----|-----|
| **Test with real queries** | Avoid dataset bias | Use actual user search logs |
| **Normalize scores** | Fair weighting | Divide by max score or softmax |
| **Tune weights per domain** | Each domain differs | A/B test different weights |
| **Cache embeddings** | Fast retrieval | Store in vector DB or cache |
| **Rerank top-K only** | Efficiency | Don't rerank all results |
| **Monitor latency** | User experience | Vector search + keyword = slower |
| **Version embeddings** | Reproducibility | Track embedding model version |
| **Feedback loop** | Continuous improvement | Log queries + user clicks |

---

## Implementation Checklist

- [ ] Implement BM25 keyword search baseline
- [ ] Add embedding model and vector search
- [ ] Implement RRF or weighted fusion
- [ ] Set up database (PostgreSQL + pgvector or Pinecone)
- [ ] Add caching for embeddings
- [ ] Implement LLM reranking (optional)
- [ ] A/B test weight tuning
- [ ] Monitor search latency
- [ ] Log queries and results for analysis
- [ ] Create feedback mechanism for ranking improvements
