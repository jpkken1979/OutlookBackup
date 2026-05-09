---
name: redis-caching-patterns
description: "Master redis caching patterns with expert patterns and practices."
type: feature
---

# Redis Caching Patterns

> Patrones de caching con Redis para aplicaciones de alto rendimiento.

---

## Descripción

Esta skill cubre estrategias de caching con Redis, incluyendo patrones de invalidación, clustering, y casos de uso avanzados como rate limiting, sessions, y pub/sub.

---

## Patrones de Caching

### 1. Cache-Aside (Lazy Loading)

El patrón más común. La aplicación gestiona el cache.

```typescript
import Redis from 'ioredis';

const redis = new Redis(process.env.REDIS_URL);

async function getUser(userId: string): Promise<User> {
  const cacheKey = `user:${userId}`;

  // 1. Intentar obtener del cache
  const cached = await redis.get(cacheKey);
  if (cached) {
    return JSON.parse(cached);
  }

  // 2. Si no está, obtener de DB
  const user = await db.users.findById(userId);

  // 3. Guardar en cache
  if (user) {
    await redis.set(cacheKey, JSON.stringify(user), 'EX', 3600); // 1 hora
  }

  return user;
}

// Invalidación cuando se actualiza
async function updateUser(userId: string, data: Partial<User>): Promise<User> {
  const user = await db.users.update(userId, data);

  // Invalidar cache
  await redis.del(`user:${userId}`);

  return user;
}
```

### 2. Write-Through

Escritura simultánea a cache y DB.

```typescript
async function createOrder(orderData: CreateOrderDTO): Promise<Order> {
  // 1. Guardar en DB
  const order = await db.orders.create(orderData);

  // 2. Guardar en cache inmediatamente
  await redis.set(
    `order:${order.id}`,
    JSON.stringify(order),
    'EX',
    86400 // 24 horas
  );

  return order;
}
```

### 3. Write-Behind (Write-Back)

Escritura asíncrona a DB para mayor performance.

```typescript
async function updateInventory(productId: string, quantity: number): Promise<void> {
  const key = `inventory:${productId}`;

  // 1. Actualizar cache inmediatamente
  await redis.set(key, quantity.toString());

  // 2. Encolar escritura a DB
  await redis.rpush('inventory:write-queue', JSON.stringify({
    productId,
    quantity,
    timestamp: Date.now(),
  }));
}

// Worker que procesa la cola
async function processWriteQueue(): Promise<void> {
  while (true) {
    const item = await redis.blpop('inventory:write-queue', 0);
    if (item) {
      const { productId, quantity } = JSON.parse(item[1]);
      await db.inventory.update(productId, { quantity });
    }
  }
}
```

### 4. Read-Through

Cache como capa intermedia (similar a cache-aside pero con abstracción).

```typescript
class CacheRepository<T> {
  constructor(
    private redis: Redis,
    private repository: Repository<T>,
    private keyPrefix: string,
    private ttl: number = 3600
  ) {}

  async get(id: string): Promise<T | null> {
    const key = `${this.keyPrefix}:${id}`;
    const cached = await this.redis.get(key);

    if (cached) {
      return JSON.parse(cached);
    }

    const entity = await this.repository.findById(id);
    if (entity) {
      await this.redis.set(key, JSON.stringify(entity), 'EX', this.ttl);
    }

    return entity;
  }

  async invalidate(id: string): Promise<void> {
    await this.redis.del(`${this.keyPrefix}:${id}`);
  }
}

// Uso
const userCache = new CacheRepository(redis, userRepository, 'user', 3600);
const user = await userCache.get('123');
```

---

## Estrategias de Invalidación

### 1. Time-To-Live (TTL)

```typescript
// TTL fijo
await redis.set(key, value, 'EX', 3600);

// TTL con refresh on read
async function getWithRefresh(key: string, ttl: number): Promise<string | null> {
  const value = await redis.get(key);
  if (value) {
    await redis.expire(key, ttl); // Renovar TTL
  }
  return value;
}
```

### 2. Event-Based Invalidation

```typescript
// Cuando cambia un usuario
eventBus.on('user.updated', async (userId: string) => {
  await redis.del(`user:${userId}`);
  await redis.del(`user:${userId}:profile`);
  await redis.del(`user:${userId}:settings`);
});

// Invalidación en cascada
eventBus.on('product.price.changed', async (productId: string) => {
  // Invalidar producto
  await redis.del(`product:${productId}`);

  // Invalidar categorías relacionadas
  const categories = await db.products.getCategories(productId);
  for (const catId of categories) {
    await redis.del(`category:${catId}:products`);
  }

  // Invalidar carritos que contienen el producto
  const pattern = `cart:*:items:${productId}`;
  const keys = await redis.keys(pattern);
  if (keys.length > 0) {
    await redis.del(...keys);
  }
});
```

### 3. Version-Based (Cache Tags)

```typescript
// Guardar con versión
async function setWithVersion(key: string, value: any, version: string): Promise<void> {
  await redis.hset(key, {
    data: JSON.stringify(value),
    version,
  });
}

// Verificar versión antes de usar
async function getIfValid(key: string, currentVersion: string): Promise<any | null> {
  const result = await redis.hgetall(key);

  if (result.version === currentVersion) {
    return JSON.parse(result.data);
  }

  // Cache inválido, eliminar
  await redis.del(key);
  return null;
}
```

---

## Cache Patterns Avanzados

### 1. Cache Stampede Prevention (Mutex)

```typescript
async function getWithMutex(key: string, fetchFn: () => Promise<any>): Promise<any> {
  // Intentar obtener del cache
  const cached = await redis.get(key);
  if (cached) {
    return JSON.parse(cached);
  }

  const lockKey = `lock:${key}`;

  // Intentar adquirir lock
  const acquired = await redis.set(lockKey, '1', 'NX', 'EX', 10);

  if (acquired) {
    try {
      // Este proceso regenera el cache
      const value = await fetchFn();
      await redis.set(key, JSON.stringify(value), 'EX', 3600);
      return value;
    } finally {
      await redis.del(lockKey);
    }
  } else {
    // Otro proceso está regenerando, esperar
    await sleep(100);
    return getWithMutex(key, fetchFn); // Retry
  }
}
```

### 2. Probabilistic Early Expiration (PER)

```typescript
async function getWithPER(
  key: string,
  ttl: number,
  beta: number = 1,
  fetchFn: () => Promise<any>
): Promise<any> {
  const data = await redis.hgetall(key);

  if (data.value) {
    const delta = parseFloat(data.delta);
    const expiry = parseFloat(data.expiry);
    const now = Date.now() / 1000;

    // Probabilistic early recomputation
    const shouldRecompute = now - delta * beta * Math.log(Math.random()) >= expiry;

    if (!shouldRecompute) {
      return JSON.parse(data.value);
    }
  }

  // Recompute
  const start = Date.now();
  const value = await fetchFn();
  const computeTime = (Date.now() - start) / 1000;

  await redis.hset(key, {
    value: JSON.stringify(value),
    delta: computeTime.toString(),
    expiry: (Date.now() / 1000 + ttl).toString(),
  });
  await redis.expire(key, ttl + 60); // Extra buffer

  return value;
}
```

### 3. Multi-Level Cache (L1 + L2)

```typescript
import NodeCache from 'node-cache';

const l1Cache = new NodeCache({ stdTTL: 60 }); // In-memory, 1 min
const l2Cache = redis; // Redis, longer TTL

async function multiLevelGet<T>(key: string): Promise<T | null> {
  // L1: In-memory (fastest)
  const l1 = l1Cache.get<T>(key);
  if (l1) {
    return l1;
  }

  // L2: Redis
  const l2 = await l2Cache.get(key);
  if (l2) {
    const parsed = JSON.parse(l2) as T;
    l1Cache.set(key, parsed); // Populate L1
    return parsed;
  }

  return null;
}

async function multiLevelSet<T>(key: string, value: T, ttl: number): Promise<void> {
  // Set in both levels
  l1Cache.set(key, value, Math.min(ttl, 60)); // L1 max 1 min
  await l2Cache.set(key, JSON.stringify(value), 'EX', ttl);
}

async function multiLevelInvalidate(key: string): Promise<void> {
  l1Cache.del(key);
  await l2Cache.del(key);
}
```

---

## Casos de Uso Específicos

### 1. Session Storage

```typescript
interface Session {
  userId: string;
  email: string;
  roles: string[];
  createdAt: number;
  lastAccess: number;
}

class SessionManager {
  private prefix = 'session';
  private ttl = 86400; // 24 hours

  constructor(private redis: Redis) {}

  async create(userId: string, userData: Partial<Session>): Promise<string> {
    const sessionId = crypto.randomUUID();
    const session: Session = {
      userId,
      email: userData.email || '',
      roles: userData.roles || [],
      createdAt: Date.now(),
      lastAccess: Date.now(),
    };

    await this.redis.hset(`${this.prefix}:${sessionId}`, session as any);
    await this.redis.expire(`${this.prefix}:${sessionId}`, this.ttl);

    // Index por usuario (para logout de todas las sesiones)
    await this.redis.sadd(`${this.prefix}:user:${userId}`, sessionId);

    return sessionId;
  }

  async get(sessionId: string): Promise<Session | null> {
    const session = await this.redis.hgetall(`${this.prefix}:${sessionId}`);

    if (Object.keys(session).length === 0) {
      return null;
    }

    // Refresh TTL on access
    await this.redis.expire(`${this.prefix}:${sessionId}`, this.ttl);

    // Update last access
    await this.redis.hset(`${this.prefix}:${sessionId}`, 'lastAccess', Date.now());

    return session as unknown as Session;
  }

  async destroy(sessionId: string): Promise<void> {
    const session = await this.get(sessionId);
    if (session) {
      await this.redis.srem(`${this.prefix}:user:${session.userId}`, sessionId);
    }
    await this.redis.del(`${this.prefix}:${sessionId}`);
  }

  async destroyAllForUser(userId: string): Promise<void> {
    const sessionIds = await this.redis.smembers(`${this.prefix}:user:${userId}`);

    if (sessionIds.length > 0) {
      await this.redis.del(...sessionIds.map((id) => `${this.prefix}:${id}`));
      await this.redis.del(`${this.prefix}:user:${userId}`);
    }
  }
}
```

### 2. Rate Limiting

```typescript
// Sliding Window Rate Limiter
class RateLimiter {
  constructor(
    private redis: Redis,
    private windowMs: number = 60000,
    private maxRequests: number = 100
  ) {}

  async isAllowed(identifier: string): Promise<{ allowed: boolean; remaining: number }> {
    const key = `ratelimit:${identifier}`;
    const now = Date.now();
    const windowStart = now - this.windowMs;

    // Usar transacción
    const multi = this.redis.multi();

    // Eliminar requests fuera de la ventana
    multi.zremrangebyscore(key, 0, windowStart);

    // Contar requests en la ventana
    multi.zcard(key);

    // Agregar request actual
    multi.zadd(key, now, `${now}:${Math.random()}`);

    // Establecer expiración
    multi.expire(key, Math.ceil(this.windowMs / 1000));

    const results = await multi.exec();
    const requestCount = results![1][1] as number;

    const allowed = requestCount < this.maxRequests;
    const remaining = Math.max(0, this.maxRequests - requestCount - 1);

    return { allowed, remaining };
  }
}

// Token Bucket Rate Limiter
class TokenBucketLimiter {
  constructor(
    private redis: Redis,
    private bucketSize: number = 100,
    private refillRate: number = 10 // tokens per second
  ) {}

  async consume(identifier: string, tokens: number = 1): Promise<boolean> {
    const key = `bucket:${identifier}`;
    const now = Date.now();

    const script = `
      local bucket = redis.call('HGETALL', KEYS[1])
      local tokens = tonumber(bucket[2]) or ${this.bucketSize}
      local lastRefill = tonumber(bucket[4]) or ${now}

      local elapsed = (${now} - lastRefill) / 1000
      local refill = math.floor(elapsed * ${this.refillRate})
      tokens = math.min(${this.bucketSize}, tokens + refill)

      if tokens >= ${tokens} then
        tokens = tokens - ${tokens}
        redis.call('HSET', KEYS[1], 'tokens', tokens, 'lastRefill', ${now})
        redis.call('EXPIRE', KEYS[1], 3600)
        return 1
      else
        return 0
      end
    `;

    const result = await this.redis.eval(script, 1, key);
    return result === 1;
  }
}
```

### 3. Leaderboard

```typescript
class Leaderboard {
  constructor(
    private redis: Redis,
    private key: string
  ) {}

  async addScore(userId: string, score: number): Promise<void> {
    await this.redis.zadd(this.key, score, userId);
  }

  async incrementScore(userId: string, increment: number): Promise<number> {
    return this.redis.zincrby(this.key, increment, userId);
  }

  async getTop(count: number): Promise<Array<{ userId: string; score: number; rank: number }>> {
    const results = await this.redis.zrevrange(this.key, 0, count - 1, 'WITHSCORES');

    const leaderboard: Array<{ userId: string; score: number; rank: number }> = [];
    for (let i = 0; i < results.length; i += 2) {
      leaderboard.push({
        userId: results[i],
        score: parseFloat(results[i + 1]),
        rank: i / 2 + 1,
      });
    }

    return leaderboard;
  }

  async getRank(userId: string): Promise<number | null> {
    const rank = await this.redis.zrevrank(this.key, userId);
    return rank !== null ? rank + 1 : null;
  }

  async getAroundUser(userId: string, range: number = 5): Promise<Array<{ userId: string; score: number; rank: number }>> {
    const rank = await this.redis.zrevrank(this.key, userId);
    if (rank === null) return [];

    const start = Math.max(0, rank - range);
    const end = rank + range;

    const results = await this.redis.zrevrange(this.key, start, end, 'WITHSCORES');

    const leaderboard: Array<{ userId: string; score: number; rank: number }> = [];
    for (let i = 0; i < results.length; i += 2) {
      leaderboard.push({
        userId: results[i],
        score: parseFloat(results[i + 1]),
        rank: start + i / 2 + 1,
      });
    }

    return leaderboard;
  }
}
```

---

## Redis Cluster

### Configuración

```typescript
import Redis from 'ioredis';

const cluster = new Redis.Cluster([
  { host: 'redis-node-1', port: 6379 },
  { host: 'redis-node-2', port: 6379 },
  { host: 'redis-node-3', port: 6379 },
], {
  redisOptions: {
    password: process.env.REDIS_PASSWORD,
  },
  scaleReads: 'slave', // Leer de replicas
  natMap: {
    // Si hay NAT entre cliente y cluster
  },
});
```

### Hash Tags para Colocación

```typescript
// Misma slot para operaciones multi-key
const userKey = '{user:123}:profile';
const settingsKey = '{user:123}:settings';

// Ahora podemos hacer MGET
const [profile, settings] = await redis.mget(userKey, settingsKey);
```

---

## Monitoreo

```typescript
// Métricas de cache
async function getCacheStats() {
  const info = await redis.info('stats');
  const memory = await redis.info('memory');

  // Parse hit/miss
  const hitMatch = info.match(/keyspace_hits:(\d+)/);
  const missMatch = info.match(/keyspace_misses:(\d+)/);

  const hits = hitMatch ? parseInt(hitMatch[1]) : 0;
  const misses = missMatch ? parseInt(missMatch[1]) : 0;
  const hitRate = hits / (hits + misses) || 0;

  return {
    hitRate: (hitRate * 100).toFixed(2) + '%',
    hits,
    misses,
    memoryUsed: memory.match(/used_memory_human:(.+)/)?.[1],
    connectedClients: info.match(/connected_clients:(\d+)/)?.[1],
  };
}
```

---

## Referencias

- [Redis Documentation](https://redis.io/documentation)
- [ioredis](https://github.com/redis/ioredis)
- [Caching Strategies](https://aws.amazon.com/caching/best-practices/)
- [Redis Patterns](https://redis.io/docs/manual/patterns/)

---

*Skill creada: 2026-02-01*
*Versión: 1.0.0*
