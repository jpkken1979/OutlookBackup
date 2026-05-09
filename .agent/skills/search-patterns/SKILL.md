---
name: search-patterns
description: "Master search patterns with expert patterns and practices."
type: feature
---

# Search Patterns

> Patrones de búsqueda con Elasticsearch, Algolia y OpenSearch.

---

## Descripción

Esta skill cubre implementación de búsqueda full-text, faceted search, autocomplete, y búsqueda semántica para aplicaciones modernas.

---

## Comparativa de Soluciones

| Feature | Elasticsearch | Algolia | OpenSearch | Meilisearch |
|---------|--------------|---------|------------|-------------|
| **Tipo** | Self-hosted | SaaS | Self-hosted | Self-hosted |
| **Latencia** | ~50ms | ~5ms | ~50ms | ~20ms |
| **Full-text** | ✅ Excelente | ✅ Excelente | ✅ Excelente | ✅ Bueno |
| **Facets** | ✅ Sí | ✅ Sí | ✅ Sí | ✅ Sí |
| **Typo tolerance** | ⚠️ Config | ✅ Auto | ⚠️ Config | ✅ Auto |
| **Escalabilidad** | ✅ Alta | ✅ Alta | ✅ Alta | ⚠️ Media |
| **Costo** | Infra | Por búsqueda | Infra | Infra |
| **Setup** | Complejo | Simple | Complejo | Simple |

---

## Elasticsearch

### Setup con Node.js

```typescript
import { Client } from '@elastic/elasticsearch';

const client = new Client({
  node: process.env.ELASTICSEARCH_URL || 'http://localhost:9200',
  auth: {
    username: process.env.ES_USER || 'elastic',
    password: process.env.ES_PASSWORD || '',
  },
});

// Verificar conexión
await client.ping();
```

### Crear Índice con Mappings

```typescript
async function createProductIndex() {
  await client.indices.create({
    index: 'products',
    body: {
      settings: {
        number_of_shards: 3,
        number_of_replicas: 1,
        analysis: {
          analyzer: {
            product_analyzer: {
              type: 'custom',
              tokenizer: 'standard',
              filter: ['lowercase', 'asciifolding', 'edge_ngram_filter'],
            },
          },
          filter: {
            edge_ngram_filter: {
              type: 'edge_ngram',
              min_gram: 2,
              max_gram: 20,
            },
          },
        },
      },
      mappings: {
        properties: {
          name: {
            type: 'text',
            analyzer: 'product_analyzer',
            fields: {
              keyword: { type: 'keyword' },
              suggest: { type: 'completion' },
            },
          },
          description: { type: 'text' },
          category: { type: 'keyword' },
          brand: { type: 'keyword' },
          price: { type: 'float' },
          rating: { type: 'float' },
          in_stock: { type: 'boolean' },
          tags: { type: 'keyword' },
          created_at: { type: 'date' },
          location: { type: 'geo_point' },
        },
      },
    },
  });
}
```

### Indexar Documentos

```typescript
// Individual
async function indexProduct(product: Product) {
  await client.index({
    index: 'products',
    id: product.id,
    body: product,
    refresh: 'wait_for', // Para testing, en prod usar false
  });
}

// Bulk (más eficiente)
async function bulkIndexProducts(products: Product[]) {
  const body = products.flatMap((product) => [
    { index: { _index: 'products', _id: product.id } },
    product,
  ]);

  const { body: result } = await client.bulk({ body, refresh: true });

  if (result.errors) {
    const errors = result.items.filter((item: any) => item.index?.error);
    console.error('Bulk index errors:', errors);
  }

  return result;
}
```

### Búsqueda Full-Text

```typescript
interface SearchParams {
  query: string;
  category?: string;
  minPrice?: number;
  maxPrice?: number;
  inStock?: boolean;
  page?: number;
  limit?: number;
  sort?: 'relevance' | 'price_asc' | 'price_desc' | 'rating';
}

async function searchProducts(params: SearchParams) {
  const {
    query,
    category,
    minPrice,
    maxPrice,
    inStock,
    page = 1,
    limit = 20,
    sort = 'relevance',
  } = params;

  const must: any[] = [];
  const filter: any[] = [];

  // Full-text search
  if (query) {
    must.push({
      multi_match: {
        query,
        fields: ['name^3', 'description', 'brand^2', 'tags'],
        type: 'best_fields',
        fuzziness: 'AUTO',
      },
    });
  }

  // Filters
  if (category) {
    filter.push({ term: { category } });
  }

  if (minPrice !== undefined || maxPrice !== undefined) {
    filter.push({
      range: {
        price: {
          ...(minPrice !== undefined && { gte: minPrice }),
          ...(maxPrice !== undefined && { lte: maxPrice }),
        },
      },
    });
  }

  if (inStock !== undefined) {
    filter.push({ term: { in_stock: inStock } });
  }

  // Sort
  const sortOptions: Record<string, any> = {
    relevance: [{ _score: 'desc' }],
    price_asc: [{ price: 'asc' }],
    price_desc: [{ price: 'desc' }],
    rating: [{ rating: 'desc' }, { _score: 'desc' }],
  };

  const { body } = await client.search({
    index: 'products',
    body: {
      from: (page - 1) * limit,
      size: limit,
      query: {
        bool: {
          must: must.length > 0 ? must : [{ match_all: {} }],
          filter,
        },
      },
      sort: sortOptions[sort],
      highlight: {
        fields: {
          name: {},
          description: { fragment_size: 150 },
        },
        pre_tags: ['<mark>'],
        post_tags: ['</mark>'],
      },
      aggs: {
        categories: { terms: { field: 'category', size: 20 } },
        brands: { terms: { field: 'brand', size: 20 } },
        price_ranges: {
          range: {
            field: 'price',
            ranges: [
              { to: 50 },
              { from: 50, to: 100 },
              { from: 100, to: 500 },
              { from: 500 },
            ],
          },
        },
        avg_price: { avg: { field: 'price' } },
        avg_rating: { avg: { field: 'rating' } },
      },
    },
  });

  return {
    hits: body.hits.hits.map((hit: any) => ({
      ...hit._source,
      _score: hit._score,
      _highlight: hit.highlight,
    })),
    total: body.hits.total.value,
    aggregations: body.aggregations,
    page,
    limit,
    totalPages: Math.ceil(body.hits.total.value / limit),
  };
}
```

### Autocomplete / Suggestions

```typescript
async function autocomplete(prefix: string, limit: number = 5) {
  const { body } = await client.search({
    index: 'products',
    body: {
      suggest: {
        product_suggest: {
          prefix,
          completion: {
            field: 'name.suggest',
            size: limit,
            skip_duplicates: true,
            fuzzy: {
              fuzziness: 'AUTO',
            },
          },
        },
      },
    },
  });

  return body.suggest.product_suggest[0].options.map((opt: any) => ({
    text: opt.text,
    score: opt._score,
  }));
}
```

---

## Algolia

### Setup

```typescript
import algoliasearch from 'algoliasearch';

const client = algoliasearch(
  process.env.ALGOLIA_APP_ID!,
  process.env.ALGOLIA_ADMIN_KEY!
);

const index = client.initIndex('products');
```

### Configurar Índice

```typescript
await index.setSettings({
  searchableAttributes: [
    'name',
    'description',
    'brand',
    'tags',
  ],
  attributesForFaceting: [
    'filterOnly(category)',
    'searchable(brand)',
    'price',
    'rating',
    'in_stock',
  ],
  customRanking: [
    'desc(rating)',
    'desc(popularity)',
  ],
  typoTolerance: true,
  minWordSizefor1Typo: 4,
  minWordSizefor2Typos: 8,
});
```

### Indexar

```typescript
// Batch indexing
await index.saveObjects(products, {
  autoGenerateObjectIDIfNotExist: false,
});

// Partial update
await index.partialUpdateObject({
  objectID: 'product-123',
  price: 29.99,
  in_stock: false,
});
```

### Búsqueda

```typescript
const results = await index.search('laptop', {
  filters: 'category:electronics AND price < 1000',
  facets: ['brand', 'category'],
  hitsPerPage: 20,
  page: 0,
  attributesToHighlight: ['name', 'description'],
  attributesToRetrieve: ['name', 'price', 'image', 'brand'],
});
```

### Frontend con InstantSearch

```tsx
import { InstantSearch, SearchBox, Hits, RefinementList } from 'react-instantsearch';
import algoliasearch from 'algoliasearch/lite';

const searchClient = algoliasearch('APP_ID', 'SEARCH_KEY');

function SearchPage() {
  return (
    <InstantSearch searchClient={searchClient} indexName="products">
      <SearchBox placeholder="Search products..." />

      <div className="flex">
        <aside>
          <h3>Category</h3>
          <RefinementList attribute="category" />

          <h3>Brand</h3>
          <RefinementList attribute="brand" searchable />
        </aside>

        <main>
          <Hits hitComponent={ProductHit} />
        </main>
      </div>
    </InstantSearch>
  );
}
```

---

## Patrones Comunes

### 1. Search-as-you-type con Debounce

```typescript
function useSearch(initialQuery = '') {
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const debouncedQuery = useDebounce(query, 300);

  useEffect(() => {
    if (!debouncedQuery) {
      setResults([]);
      return;
    }

    setLoading(true);
    searchProducts({ query: debouncedQuery })
      .then(setResults)
      .finally(() => setLoading(false));
  }, [debouncedQuery]);

  return { query, setQuery, results, loading };
}
```

### 2. Faceted Search

```typescript
interface Facets {
  categories: Array<{ value: string; count: number }>;
  brands: Array<{ value: string; count: number }>;
  priceRanges: Array<{ range: string; count: number }>;
}

function parseFacets(aggregations: any): Facets {
  return {
    categories: aggregations.categories.buckets.map((b: any) => ({
      value: b.key,
      count: b.doc_count,
    })),
    brands: aggregations.brands.buckets.map((b: any) => ({
      value: b.key,
      count: b.doc_count,
    })),
    priceRanges: aggregations.price_ranges.buckets.map((b: any) => ({
      range: `${b.from || 0}-${b.to || '∞'}`,
      count: b.doc_count,
    })),
  };
}
```

### 3. Geo Search

```typescript
async function searchNearby(lat: number, lon: number, radiusKm: number) {
  const { body } = await client.search({
    index: 'stores',
    body: {
      query: {
        bool: {
          filter: {
            geo_distance: {
              distance: `${radiusKm}km`,
              location: { lat, lon },
            },
          },
        },
      },
      sort: [
        {
          _geo_distance: {
            location: { lat, lon },
            order: 'asc',
            unit: 'km',
          },
        },
      ],
    },
  });

  return body.hits.hits.map((hit: any) => ({
    ...hit._source,
    distance: hit.sort[0],
  }));
}
```

---

## Sincronización de Datos

### Patrón: Change Data Capture

```typescript
// Listener de cambios en DB
db.on('product.created', async (product) => {
  await searchIndex.index(product);
});

db.on('product.updated', async (product) => {
  await searchIndex.update(product.id, product);
});

db.on('product.deleted', async (productId) => {
  await searchIndex.delete(productId);
});
```

### Reindexación sin Downtime

```typescript
async function reindexWithZeroDowntime() {
  const newIndex = `products_${Date.now()}`;
  const alias = 'products';

  // 1. Crear nuevo índice
  await createIndex(newIndex);

  // 2. Indexar todos los documentos
  await bulkIndex(newIndex, await getAllProducts());

  // 3. Cambiar alias atómicamente
  await client.indices.updateAliases({
    body: {
      actions: [
        { remove: { index: '*', alias } },
        { add: { index: newIndex, alias } },
      ],
    },
  });

  // 4. Eliminar índices viejos
  const oldIndices = await client.indices.get({ index: 'products_*' });
  for (const idx of Object.keys(oldIndices.body)) {
    if (idx !== newIndex) {
      await client.indices.delete({ index: idx });
    }
  }
}
```

---

## Referencias

- [Elasticsearch Guide](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [Algolia Documentation](https://www.algolia.com/doc/)
- [OpenSearch](https://opensearch.org/docs/latest/)
- [Meilisearch](https://docs.meilisearch.com/)

---

*Skill creada: 2026-02-01*
*Versión: 1.0.0*
