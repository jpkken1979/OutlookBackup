---
name: websocket-realtime-patterns
type: feature
description: "Master websocket realtime patterns with expert patterns and practices."
---

# WebSocket & Real-Time Patterns

> Patrones y mejores prácticas para comunicación bidireccional en tiempo real.

---

## Descripción

Esta skill cubre arquitecturas y patrones para aplicaciones en tiempo real usando WebSockets, Socket.io, Server-Sent Events (SSE), y otras tecnologías de comunicación bidireccional.

---

## Cuándo Usar Cada Tecnología

| Tecnología | Caso de Uso | Dirección | Soporte |
|------------|-------------|-----------|---------|
| **WebSocket** | Chat, gaming, trading | Bidireccional | Universal |
| **Socket.io** | Apps web con fallback | Bidireccional | Browsers + Node |
| **SSE** | Notificaciones, feeds | Server → Client | Browsers |
| **Long Polling** | Legacy, firewalls | Pseudo-bidireccional | Universal |
| **WebRTC** | Video/audio, P2P | Peer-to-Peer | Browsers |

---

## Arquitectura WebSocket

### Flujo de Conexión

```
┌─────────┐      HTTP Upgrade       ┌─────────┐
│ Cliente │ ───────────────────────▶│ Server  │
└─────────┘      101 Switching      └─────────┘
     │                                    │
     │◄────── WebSocket Frame ───────────▶│
     │◄────── WebSocket Frame ───────────▶│
     │                                    │
     │         Connection Close           │
     └────────────────────────────────────┘
```

### Estructura de Mensaje

```typescript
interface WebSocketMessage<T = unknown> {
  type: string;           // Tipo de evento
  payload: T;             // Datos del mensaje
  timestamp: number;      // Unix timestamp
  id?: string;            // ID único para ACK
  correlationId?: string; // Para request-response
}

// Ejemplos de tipos
type MessageType =
  | 'chat:message'
  | 'chat:typing'
  | 'user:online'
  | 'user:offline'
  | 'notification:new'
  | 'data:update'
  | 'error'
  | 'ping'
  | 'pong';
```

---

## Implementación con Socket.io

### Server (Node.js)

```typescript
import { Server } from 'socket.io';
import { createServer } from 'http';
import { instrument } from '@socket.io/admin-ui';

const httpServer = createServer();
const io = new Server(httpServer, {
  cors: {
    origin: process.env.CORS_ORIGIN?.split(',') || ['http://localhost:3000'],
    credentials: true,
  },
  pingTimeout: 60000,
  pingInterval: 25000,
  transports: ['websocket', 'polling'],
});

// Middleware de autenticación
io.use(async (socket, next) => {
  const token = socket.handshake.auth.token;

  try {
    const user = await verifyToken(token);
    socket.data.user = user;
    next();
  } catch (error) {
    next(new Error('Authentication failed'));
  }
});

// Namespaces para separar funcionalidades
const chatNamespace = io.of('/chat');
const notificationsNamespace = io.of('/notifications');

// Conexión principal
io.on('connection', (socket) => {
  const userId = socket.data.user.id;

  // Unir a sala personal
  socket.join(`user:${userId}`);

  console.log(`User ${userId} connected`);

  // Broadcast de estado online
  socket.broadcast.emit('user:online', { userId });

  // Handlers de eventos
  socket.on('chat:message', async (data, callback) => {
    try {
      const message = await saveMessage(data);

      // Enviar a destinatario
      io.to(`user:${data.recipientId}`).emit('chat:message', message);

      // ACK al emisor
      callback({ success: true, messageId: message.id });
    } catch (error) {
      callback({ success: false, error: error.message });
    }
  });

  socket.on('chat:typing', (data) => {
    socket.to(`user:${data.recipientId}`).emit('chat:typing', {
      userId,
      isTyping: data.isTyping,
    });
  });

  socket.on('room:join', (roomId) => {
    socket.join(`room:${roomId}`);
    io.to(`room:${roomId}`).emit('room:user_joined', { userId });
  });

  socket.on('room:leave', (roomId) => {
    socket.leave(`room:${roomId}`);
    io.to(`room:${roomId}`).emit('room:user_left', { userId });
  });

  socket.on('disconnect', (reason) => {
    console.log(`User ${userId} disconnected: ${reason}`);
    socket.broadcast.emit('user:offline', { userId });
  });

  socket.on('error', (error) => {
    console.error(`Socket error for user ${userId}:`, error);
  });
});

// Admin UI (development)
if (process.env.NODE_ENV === 'development') {
  instrument(io, { auth: false });
}

httpServer.listen(3001);
```

### Client (React)

```typescript
import { io, Socket } from 'socket.io-client';
import { useEffect, useRef, useCallback, useState } from 'react';

// Singleton de conexión
let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    socket = io(process.env.NEXT_PUBLIC_WS_URL!, {
      autoConnect: false,
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });
  }
  return socket;
}

// Hook de conexión
export function useSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    const socket = getSocket();
    socketRef.current = socket;

    // Autenticación
    const token = localStorage.getItem('token');
    socket.auth = { token };

    socket.connect();

    socket.on('connect', () => {
      setIsConnected(true);
      setConnectionError(null);
      console.log('Socket connected');
    });

    socket.on('disconnect', (reason) => {
      setIsConnected(false);
      console.log('Socket disconnected:', reason);
    });

    socket.on('connect_error', (error) => {
      setConnectionError(error.message);
      console.error('Connection error:', error);
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  const emit = useCallback(<T>(event: string, data: T): Promise<any> => {
    return new Promise((resolve, reject) => {
      socketRef.current?.emit(event, data, (response: any) => {
        if (response.success) {
          resolve(response);
        } else {
          reject(new Error(response.error));
        }
      });
    });
  }, []);

  const on = useCallback((event: string, handler: (...args: any[]) => void) => {
    socketRef.current?.on(event, handler);
    return () => socketRef.current?.off(event, handler);
  }, []);

  return { socket: socketRef.current, isConnected, connectionError, emit, on };
}

// Hook de chat
export function useChat(recipientId: string) {
  const { emit, on, isConnected } = useSocket();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);

  useEffect(() => {
    const unsubMessage = on('chat:message', (message: Message) => {
      setMessages((prev) => [...prev, message]);
    });

    const unsubTyping = on('chat:typing', (data: { userId: string; isTyping: boolean }) => {
      if (data.userId === recipientId) {
        setIsTyping(data.isTyping);
      }
    });

    return () => {
      unsubMessage();
      unsubTyping();
    };
  }, [on, recipientId]);

  const sendMessage = useCallback(async (content: string) => {
    const response = await emit('chat:message', {
      recipientId,
      content,
      timestamp: Date.now(),
    });
    return response;
  }, [emit, recipientId]);

  const sendTyping = useCallback((isTyping: boolean) => {
    emit('chat:typing', { recipientId, isTyping });
  }, [emit, recipientId]);

  return { messages, isTyping, sendMessage, sendTyping, isConnected };
}
```

---

## Patrones de Escalabilidad

### 1. Sticky Sessions con Redis Adapter

```typescript
import { Server } from 'socket.io';
import { createAdapter } from '@socket.io/redis-adapter';
import { createClient } from 'redis';

const pubClient = createClient({ url: process.env.REDIS_URL });
const subClient = pubClient.duplicate();

await Promise.all([pubClient.connect(), subClient.connect()]);

const io = new Server(httpServer);
io.adapter(createAdapter(pubClient, subClient));

// Ahora múltiples instancias comparten estado
// Load balancer necesita sticky sessions por IP o cookie
```

### 2. Rooms para Broadcast Eficiente

```typescript
// ✅ CORRECTO: Usar rooms
io.to('room:123').emit('update', data);  // Solo a usuarios en la sala

// ❌ INCORRECTO: Broadcast a todos
io.emit('update', data);  // A TODOS los conectados
```

### 3. Namespace para Separar Dominios

```typescript
// Chat
const chat = io.of('/chat');
chat.on('connection', handleChat);

// Notificaciones
const notifications = io.of('/notifications');
notifications.on('connection', handleNotifications);

// Trading (alta frecuencia)
const trading = io.of('/trading');
trading.on('connection', handleTrading);
```

---

## Patrones de Reconexión

### Client-Side Reconnection

```typescript
const socket = io(url, {
  reconnection: true,
  reconnectionAttempts: Infinity,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 30000,
  randomizationFactor: 0.5,
});

// Estado de reconexión
socket.on('reconnect_attempt', (attemptNumber) => {
  console.log(`Reconnection attempt ${attemptNumber}`);
  showReconnectingUI();
});

socket.on('reconnect', (attemptNumber) => {
  console.log(`Reconnected after ${attemptNumber} attempts`);
  hideReconnectingUI();
  resyncState();  // Re-sincronizar estado
});

socket.on('reconnect_failed', () => {
  showConnectionFailedUI();
});
```

### Resync de Estado

```typescript
socket.on('reconnect', async () => {
  // Obtener mensajes perdidos desde última desconexión
  const lastMessageId = getLastMessageId();

  socket.emit('sync:messages', { since: lastMessageId }, (messages) => {
    mergeMessages(messages);
  });

  // Re-unirse a salas
  const rooms = getJoinedRooms();
  rooms.forEach((roomId) => {
    socket.emit('room:join', roomId);
  });
});
```

---

## Server-Sent Events (SSE)

Para comunicación unidireccional server → client:

### Server

```typescript
import { Router } from 'express';

const router = Router();

router.get('/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');  // Para Nginx

  const userId = req.user.id;

  // Enviar heartbeat cada 30s
  const heartbeat = setInterval(() => {
    res.write(': heartbeat\n\n');
  }, 30000);

  // Suscribirse a eventos del usuario
  const unsubscribe = eventBus.subscribe(`user:${userId}`, (event) => {
    res.write(`event: ${event.type}\n`);
    res.write(`data: ${JSON.stringify(event.data)}\n`);
    res.write(`id: ${event.id}\n\n`);
  });

  req.on('close', () => {
    clearInterval(heartbeat);
    unsubscribe();
  });
});
```

### Client

```typescript
function useSSE(url: string) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const eventSource = new EventSource(url, { withCredentials: true });

    eventSource.onmessage = (event) => {
      setData(JSON.parse(event.data));
    };

    eventSource.addEventListener('notification', (event) => {
      const notification = JSON.parse(event.data);
      showNotification(notification);
    });

    eventSource.onerror = (error) => {
      setError(new Error('SSE connection failed'));
      eventSource.close();
    };

    return () => eventSource.close();
  }, [url]);

  return { data, error };
}
```

---

## Seguridad

### 1. Autenticación

```typescript
// SIEMPRE autenticar en handshake
io.use(async (socket, next) => {
  const token = socket.handshake.auth.token
    || socket.handshake.headers.authorization?.split(' ')[1];

  if (!token) {
    return next(new Error('Authentication required'));
  }

  try {
    const user = await verifyJWT(token);
    socket.data.user = user;
    next();
  } catch {
    next(new Error('Invalid token'));
  }
});
```

### 2. Rate Limiting

```typescript
import { RateLimiterMemory } from 'rate-limiter-flexible';

const rateLimiter = new RateLimiterMemory({
  points: 10,    // 10 mensajes
  duration: 1,   // por segundo
});

socket.on('chat:message', async (data, callback) => {
  try {
    await rateLimiter.consume(socket.data.user.id);
    // Procesar mensaje
  } catch {
    callback({ success: false, error: 'Rate limit exceeded' });
  }
});
```

### 3. Validación de Input

```typescript
import { z } from 'zod';

const messageSchema = z.object({
  recipientId: z.string().uuid(),
  content: z.string().min(1).max(5000),
  type: z.enum(['text', 'image', 'file']).default('text'),
});

socket.on('chat:message', async (data, callback) => {
  const result = messageSchema.safeParse(data);

  if (!result.success) {
    return callback({
      success: false,
      error: 'Invalid message format',
      details: result.error.flatten(),
    });
  }

  // Procesar mensaje validado
  const message = result.data;
});
```

---

## Monitoreo

### Métricas Clave

```typescript
import { Counter, Gauge, Histogram } from 'prom-client';

const connectedClients = new Gauge({
  name: 'websocket_connected_clients',
  help: 'Number of connected WebSocket clients',
});

const messagesTotal = new Counter({
  name: 'websocket_messages_total',
  help: 'Total WebSocket messages',
  labelNames: ['type', 'direction'],
});

const messageLatency = new Histogram({
  name: 'websocket_message_latency_seconds',
  help: 'WebSocket message processing latency',
  buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1],
});

io.on('connection', (socket) => {
  connectedClients.inc();

  socket.onAny((event, ...args) => {
    messagesTotal.inc({ type: event, direction: 'in' });
  });

  socket.on('disconnect', () => {
    connectedClients.dec();
  });
});
```

---

## Casos de Uso Comunes

### 1. Chat en Tiempo Real
- Mensajes privados y grupales
- Indicador de "escribiendo..."
- Confirmación de lectura
- Historial con paginación

### 2. Notificaciones Push
- Alertas instantáneas
- Badges de contador
- Toast notifications

### 3. Dashboards en Vivo
- Métricas actualizadas
- Gráficos en tiempo real
- Alertas de threshold

### 4. Colaboración
- Edición simultánea
- Cursores de otros usuarios
- Presencia online

### 5. Gaming
- Estado del juego
- Movimientos de jugadores
- Sincronización de física

---

## Anti-Patterns

```typescript
// ❌ NO: Broadcast masivo
io.emit('update', largeData);  // Mata el server

// ✅ SÍ: Usar rooms específicas
io.to('interested-users').emit('update', data);

// ❌ NO: Guardar estado en socket
socket.userData = { ... };  // Se pierde en reconexión

// ✅ SÍ: Usar socket.data o Redis
socket.data.user = user;

// ❌ NO: Callbacks sin timeout
socket.emit('action', data, callback);  // Puede colgarse

// ✅ SÍ: Timeout en callbacks
socket.timeout(5000).emit('action', data, (err, response) => {
  if (err) {
    // Timeout o error
  }
});
```

---

## Referencias

- [Socket.io Documentation](https://socket.io/docs/v4/)
- [WebSocket API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [Redis Adapter](https://socket.io/docs/v4/redis-adapter/)
- [Scaling Socket.io](https://socket.io/docs/v4/using-multiple-nodes/)

---

*Skill creada: 2026-02-01*
*Versión: 1.0.0*
