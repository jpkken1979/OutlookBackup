#!/usr/bin/env python3
"""
Search Patterns Demo - Elasticsearch, Algolia, Full-text Search

Este script demuestra patrones de búsqueda incluyendo:
- Indexación de documentos
- Búsqueda full-text
- Búsqueda facetada
- Autocompletado
- Fuzzy search

Uso:
    python search_demo.py --demo basic
    python search_demo.py --demo faceted
    python search_demo.py --demo autocomplete
"""

import argparse
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Resultado de búsqueda."""

    id: str
    score: float
    document: dict
    highlights: list[str] = field(default_factory=list)


@dataclass
class FacetBucket:
    """Bucket de faceta."""

    value: str
    count: int


@dataclass
class SearchResponse:
    """Respuesta de búsqueda."""

    hits: list[SearchResult]
    total: int
    took_ms: float
    facets: dict[str, list[FacetBucket]] = field(default_factory=dict)


class InMemorySearchEngine:
    """
    Motor de búsqueda en memoria para demostración.

    Implementa patrones básicos de búsqueda sin dependencias externas.
    En producción, usar Elasticsearch, Algolia u OpenSearch.
    """

    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}
        self.inverted_index: dict[str, set[str]] = {}
        logger.info("Motor de búsqueda inicializado")

    def index_document(self, doc_id: str, document: dict) -> None:
        """Indexar un documento."""
        self.documents[doc_id] = document

        # Construir índice invertido
        for _field_name, value in document.items():
            if isinstance(value, str):
                tokens = self._tokenize(value)
                for token in tokens:
                    if token not in self.inverted_index:
                        self.inverted_index[token] = set()
                    self.inverted_index[token].add(doc_id)

        logger.debug(f"Documento indexado: {doc_id}")

    def bulk_index(self, documents: list[dict]) -> int:
        """Indexar múltiples documentos."""
        count = 0
        for doc in documents:
            doc_id = doc.get("id", str(count))
            self.index_document(doc_id, doc)
            count += 1
        logger.info(f"Indexados {count} documentos")
        return count

    def search(
        self,
        query: str,
        fields: list[str] | None = None,
        filters: dict | None = None,
        facet_fields: list[str] | None = None,
        size: int = 10,
        fuzzy: bool = False,
    ) -> SearchResponse:
        """
        Búsqueda full-text con filtros y facetas.

        Args:
            query: Término de búsqueda
            fields: Campos donde buscar
            filters: Filtros exactos
            facet_fields: Campos para generar facetas
            size: Número de resultados
            fuzzy: Habilitar búsqueda fuzzy

        Returns:
            SearchResponse con resultados
        """
        start_time = datetime.now()

        tokens = self._tokenize(query)
        matching_docs: dict[str, float] = {}

        for token in tokens:
            # Búsqueda exacta o fuzzy
            matching_tokens = [token]
            if fuzzy:
                matching_tokens.extend(self._fuzzy_matches(token))

            for match_token in matching_tokens:
                if match_token in self.inverted_index:
                    for doc_id in self.inverted_index[match_token]:
                        score = 1.0 if match_token == token else 0.5  # Fuzzy tiene menor score
                        matching_docs[doc_id] = matching_docs.get(doc_id, 0) + score

        # Aplicar filtros
        if filters:
            filtered_docs = {}
            for doc_id, score in matching_docs.items():
                doc = self.documents[doc_id]
                if self._matches_filters(doc, filters):
                    filtered_docs[doc_id] = score
            matching_docs = filtered_docs

        # Ordenar por score
        sorted_docs = sorted(matching_docs.items(), key=lambda x: x[1], reverse=True)[:size]

        # Construir resultados
        hits = []
        for doc_id, score in sorted_docs:
            doc = self.documents[doc_id]
            highlights = self._generate_highlights(doc, tokens)
            hits.append(SearchResult(id=doc_id, score=score, document=doc, highlights=highlights))

        # Generar facetas
        facets = {}
        if facet_fields:
            for facet_field in facet_fields:
                facets[facet_field] = self._compute_facets(
                    [doc_id for doc_id, _ in sorted_docs], facet_field
                )

        elapsed = (datetime.now() - start_time).total_seconds() * 1000

        response = SearchResponse(
            hits=hits, total=len(matching_docs), took_ms=elapsed, facets=facets
        )

        logger.info(
            f"Búsqueda '{query}' completada: {response.total} resultados en {elapsed:.2f}ms"
        )
        return response

    def autocomplete(self, prefix: str, field: str = "title", size: int = 5) -> list[str]:
        """Autocompletado basado en prefijo."""
        suggestions = set()
        prefix_lower = prefix.lower()

        for doc in self.documents.values():
            if field in doc:
                value = str(doc[field])
                words = value.split()
                for word in words:
                    if word.lower().startswith(prefix_lower):
                        suggestions.add(word)

        result = sorted(suggestions)[:size]
        logger.info(f"Autocompletado '{prefix}': {len(result)} sugerencias")
        return result

    def _tokenize(self, text: str) -> list[str]:
        """Tokenizar texto en palabras."""
        text = text.lower()
        tokens = re.findall(r"\w+", text)
        # Filtrar stopwords básicos
        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "and",
            "or",
        }
        return [t for t in tokens if t not in stopwords and len(t) > 1]

    def _fuzzy_matches(self, token: str) -> list[str]:
        """Encontrar tokens similares (distancia de edición 1)."""
        matches = []
        for indexed_token in self.inverted_index:
            if self._levenshtein_distance(token, indexed_token) == 1:
                matches.append(indexed_token)
        return matches

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calcular distancia de Levenshtein."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def _matches_filters(self, doc: dict, filters: dict) -> bool:
        """Verificar si documento cumple filtros."""
        for field, value in filters.items():
            if field not in doc:
                return False
            if isinstance(value, list):
                if doc[field] not in value:
                    return False
            elif doc[field] != value:
                return False
        return True

    def _generate_highlights(self, doc: dict, tokens: list[str]) -> list[str]:
        """Generar highlights de coincidencias."""
        highlights = []
        for field, value in doc.items():
            if isinstance(value, str):
                for token in tokens:
                    pattern = re.compile(f"({re.escape(token)})", re.IGNORECASE)
                    if pattern.search(value):
                        highlighted = pattern.sub(r"<em>\1</em>", value)
                        highlights.append(f"{field}: {highlighted}")
                        break
        return highlights

    def _compute_facets(self, doc_ids: list[str], field: str) -> list[FacetBucket]:
        """Computar facetas para un campo."""
        counts: dict[str, int] = {}
        for doc_id in doc_ids:
            doc = self.documents.get(doc_id, {})
            value = doc.get(field)
            if value:
                str_value = str(value)
                counts[str_value] = counts.get(str_value, 0) + 1

        buckets = [
            FacetBucket(value=v, count=c) for v, c in sorted(counts.items(), key=lambda x: -x[1])
        ]
        return buckets


def demo_basic_search() -> None:
    """Demostrar búsqueda básica."""
    logger.info("=== Demo: Búsqueda Básica ===")

    engine = InMemorySearchEngine()

    # Datos de ejemplo: productos
    products = [
        {
            "id": "1",
            "title": "iPhone 15 Pro",
            "category": "Electronics",
            "price": 999,
            "brand": "Apple",
        },
        {
            "id": "2",
            "title": "Samsung Galaxy S24",
            "category": "Electronics",
            "price": 899,
            "brand": "Samsung",
        },
        {
            "id": "3",
            "title": "MacBook Pro 16",
            "category": "Computers",
            "price": 2499,
            "brand": "Apple",
        },
        {"id": "4", "title": "iPad Air", "category": "Tablets", "price": 599, "brand": "Apple"},
        {"id": "5", "title": "Sony WH-1000XM5", "category": "Audio", "price": 349, "brand": "Sony"},
        {
            "id": "6",
            "title": "Apple Watch Ultra",
            "category": "Wearables",
            "price": 799,
            "brand": "Apple",
        },
        {
            "id": "7",
            "title": "Dell XPS 15",
            "category": "Computers",
            "price": 1799,
            "brand": "Dell",
        },
        {
            "id": "8",
            "title": "Google Pixel 8",
            "category": "Electronics",
            "price": 699,
            "brand": "Google",
        },
    ]

    engine.bulk_index(products)

    # Búsqueda simple
    print("\n1. Búsqueda simple: 'apple'")
    results = engine.search("apple")
    for hit in results.hits:
        print(f"  - {hit.document['title']} (score: {hit.score:.2f})")

    # Búsqueda con filtros
    print("\n2. Búsqueda con filtro: 'pro' en categoría 'Electronics'")
    results = engine.search("pro", filters={"category": "Electronics"})
    for hit in results.hits:
        print(f"  - {hit.document['title']}")

    # Búsqueda fuzzy
    print("\n3. Búsqueda fuzzy: 'aplle' (typo)")
    results = engine.search("aplle", fuzzy=True)
    for hit in results.hits:
        print(f"  - {hit.document['title']} (score: {hit.score:.2f})")


def demo_faceted_search() -> None:
    """Demostrar búsqueda facetada."""
    logger.info("=== Demo: Búsqueda Facetada ===")

    engine = InMemorySearchEngine()

    # Datos de ejemplo
    products = [
        {"id": "1", "title": "iPhone 15", "category": "Phones", "brand": "Apple", "price": 999},
        {"id": "2", "title": "iPhone 14", "category": "Phones", "brand": "Apple", "price": 799},
        {"id": "3", "title": "MacBook", "category": "Laptops", "brand": "Apple", "price": 1299},
        {"id": "4", "title": "Galaxy S24", "category": "Phones", "brand": "Samsung", "price": 899},
        {
            "id": "5",
            "title": "Galaxy Book",
            "category": "Laptops",
            "brand": "Samsung",
            "price": 1099,
        },
        {"id": "6", "title": "Pixel 8", "category": "Phones", "brand": "Google", "price": 699},
    ]

    engine.bulk_index(products)

    print("\n1. Búsqueda con facetas:")
    results = engine.search(query="phone laptop", facet_fields=["category", "brand"])

    print(f"   Total: {results.total} resultados")
    print("\n   Facetas por categoría:")
    for bucket in results.facets.get("category", []):
        print(f"     - {bucket.value}: {bucket.count}")

    print("\n   Facetas por marca:")
    for bucket in results.facets.get("brand", []):
        print(f"     - {bucket.value}: {bucket.count}")


def demo_autocomplete() -> None:
    """Demostrar autocompletado."""
    logger.info("=== Demo: Autocompletado ===")

    engine = InMemorySearchEngine()

    products = [
        {"id": "1", "title": "iPhone 15 Pro Max"},
        {"id": "2", "title": "iPhone 14 Pro"},
        {"id": "3", "title": "iPad Pro 12.9"},
        {"id": "4", "title": "iPad Air"},
        {"id": "5", "title": "iMac 24"},
        {"id": "6", "title": "MacBook Pro"},
        {"id": "7", "title": "Mac Mini"},
        {"id": "8", "title": "AirPods Pro"},
    ]

    engine.bulk_index(products)

    prefixes = ["ip", "mac", "air", "pr"]

    for prefix in prefixes:
        suggestions = engine.autocomplete(prefix)
        print(f"\n  Prefijo '{prefix}': {', '.join(suggestions)}")


def main() -> None:
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Search Patterns Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python search_demo.py --demo basic
    python search_demo.py --demo faceted
    python search_demo.py --demo autocomplete
    python search_demo.py --demo all
        """,
    )

    parser.add_argument(
        "--demo",
        choices=["basic", "faceted", "autocomplete", "all"],
        default="all",
        help="Tipo de demo a ejecutar",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("         SEARCH PATTERNS DEMO")
    print("=" * 60)

    if args.demo in ("basic", "all"):
        demo_basic_search()

    if args.demo in ("faceted", "all"):
        demo_faceted_search()

    if args.demo in ("autocomplete", "all"):
        demo_autocomplete()

    print("\n" + "=" * 60)
    print("Demo completada. Ver SKILL.md para patrones de producción")
    print("con Elasticsearch, Algolia y OpenSearch.")
    print("=" * 60)


if __name__ == "__main__":
    main()
