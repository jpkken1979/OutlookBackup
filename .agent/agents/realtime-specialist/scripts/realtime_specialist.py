#!/usr/bin/env python3
"""
Realtime Specialist Agent

Implementa WebSockets, SSE, y arquitecturas pub/sub para tiempo real.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RealtimeRequirements:
    """Requisitos de un sistema realtime."""

    max_connections: int
    messages_per_second: int
    message_size_bytes: int
    latency_requirement_ms: int
    bidirectional: bool
    persistence_required: bool


# Templates de servidor
SERVER_TEMPLATES = {
    "socketio_node": """import {{ Server }} from 'socket.io';
import {{ createServer }} from 'http';
import {{ createAdapter }} from '@socket.io/redis-adapter';
import {{ createClient }} from 'redis';

const httpServer = createServer();
const io = new Server(httpServer, {{
  cors: {{
    origin: process.env.CORS_ORIGIN || '*',
    methods: ['GET', 'POST'],
  }},
  pingTimeout: 60000,
  pingInterval: 25000,
}});

// Redis adapter for horizontal scaling
if (process.env.REDIS_URL) {{
  const pubClient = createClient({{ url: process.env.REDIS_URL }});
  const subClient = pubClient.duplicate();

  Promise.all([pubClient.connect(), subClient.connect()]).then(() => {{
    io.adapter(createAdapter(pubClient, subClient));
    console.log('Redis adapter connected');
  }});
}}

// Middleware
io.use((socket, next) => {{
  const token = socket.handshake.auth.token;
  // TODO: Validate token
  next();
}});

// Connection handling
io.on('connection', (socket) => {{
  console.log(`Client connected: ${{socket.id}}`);

  // Join rooms
  socket.on('join', (room: string) => {{
    socket.join(room);
    console.log(`${{socket.id}} joined ${{room}}`);
  }});

  // Leave rooms
  socket.on('leave', (room: string) => {{
    socket.leave(room);
  }});

  // Handle messages
  socket.on('message', (data) => {{
    // Broadcast to room
    const room = data.room || 'general';
    socket.to(room).emit('message', {{
      ...data,
      from: socket.id,
      timestamp: Date.now(),
    }});
  }});

  // Disconnect
  socket.on('disconnect', (reason) => {{
    console.log(`Client disconnected: ${{socket.id}}, reason: ${{reason}}`);
  }});
}});

const PORT = process.env.PORT || 3001;
httpServer.listen(PORT, () => {{
  console.log(`Socket.IO server running on port ${{PORT}}`);
}});
""",
    "ws_node": """import {{ WebSocketServer, WebSocket }} from 'ws';
import {{ createServer }} from 'http';
import {{ parse }} from 'url';

const server = createServer();
const wss = new WebSocketServer({{ server }});

// Connection tracking
const clients = new Map<string, WebSocket>();
const rooms = new Map<string, Set<string>>();

function generateId(): string {{
  return Math.random().toString(36).substring(2, 15);
}}

wss.on('connection', (ws, req) => {{
  const clientId = generateId();
  clients.set(clientId, ws);

  console.log(`Client connected: ${{clientId}}`);

  // Send welcome message
  ws.send(JSON.stringify({{
    type: 'connected',
    clientId,
  }}));

  ws.on('message', (data) => {{
    try {{
      const message = JSON.parse(data.toString());

      switch (message.type) {{
        case 'join':
          joinRoom(clientId, message.room);
          break;

        case 'leave':
          leaveRoom(clientId, message.room);
          break;

        case 'broadcast':
          broadcastToRoom(message.room, {{
            type: 'message',
            from: clientId,
            data: message.data,
            timestamp: Date.now(),
          }});
          break;

        case 'ping':
          ws.send(JSON.stringify({{ type: 'pong' }}));
          break;
      }}
    }} catch (err) {{
      console.error('Invalid message:', err);
    }}
  }});

  ws.on('close', () => {{
    clients.delete(clientId);
    // Remove from all rooms
    rooms.forEach((members, room) => {{
      members.delete(clientId);
    }});
    console.log(`Client disconnected: ${{clientId}}`);
  }});

  ws.on('error', (err) => {{
    console.error(`WebSocket error for ${{clientId}}:`, err);
  }});
}});

function joinRoom(clientId: string, room: string) {{
  if (!rooms.has(room)) {{
    rooms.set(room, new Set());
  }}
  rooms.get(room)!.add(clientId);
}}

function leaveRoom(clientId: string, room: string) {{
  rooms.get(room)?.delete(clientId);
}}

function broadcastToRoom(room: string, message: object) {{
  const members = rooms.get(room);
  if (!members) return;

  const data = JSON.stringify(message);
  members.forEach((clientId) => {{
    const client = clients.get(clientId);
    if (client && client.readyState === WebSocket.OPEN) {{
      client.send(data);
    }}
  }});
}}

const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {{
  console.log(`WebSocket server running on port ${{PORT}}`);
}});
""",
    "sse_node": """import express from 'express';
import cors from 'cors';

const app = express();
app.use(cors());
app.use(express.json());

// Store active connections
const clients = new Map<string, express.Response>();

// SSE endpoint
app.get('/events', (req, res) => {{
  const clientId = req.query.clientId as string || generateId();

  // Set SSE headers
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');

  // Send initial connection event
  res.write(`event: connected\\ndata: {{"clientId":"${{clientId}}"}}\\n\\n`);

  // Store client
  clients.set(clientId, res);
  console.log(`SSE client connected: ${{clientId}}`);

  // Heartbeat to keep connection alive
  const heartbeat = setInterval(() => {{
    res.write(': heartbeat\\n\\n');
  }}, 30000);

  // Cleanup on close
  req.on('close', () => {{
    clearInterval(heartbeat);
    clients.delete(clientId);
    console.log(`SSE client disconnected: ${{clientId}}`);
  }});
}});

// Broadcast endpoint
app.post('/broadcast', (req, res) => {{
  const {{ event, data }} = req.body;

  clients.forEach((client, clientId) => {{
    try {{
      client.write(`event: ${{event}}\\ndata: ${{JSON.stringify(data)}}\\n\\n`);
    }} catch (err) {{
      console.error(`Error sending to ${{clientId}}:`, err);
      clients.delete(clientId);
    }}
  }});

  res.json({{ sent: clients.size }});
}});

// Send to specific client
app.post('/send/:clientId', (req, res) => {{
  const {{ clientId }} = req.params;
  const {{ event, data }} = req.body;

  const client = clients.get(clientId);
  if (client) {{
    client.write(`event: ${{event}}\\ndata: ${{JSON.stringify(data)}}\\n\\n`);
    res.json({{ sent: true }});
  }} else {{
    res.status(404).json({{ error: 'Client not found' }});
  }}
}});

function generateId(): string {{
  return Math.random().toString(36).substring(2, 15);
}}

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {{
  console.log(`SSE server running on port ${{PORT}}`);
}});
""",
    "python_websocket": '''import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Set
import websockets
from websockets.server import WebSocketServerProtocol

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ConnectionManager:
    """Manages WebSocket connections and rooms."""
    clients: Dict[str, WebSocketServerProtocol] = field(default_factory=dict)
    rooms: Dict[str, Set[str]] = field(default_factory=dict)
    _counter: int = 0

    def generate_id(self) -> str:
        self._counter += 1
        return f"client_{self._counter}"

    async def connect(self, websocket: WebSocketServerProtocol) -> str:
        client_id = self.generate_id()
        self.clients[client_id] = websocket
        logger.info(f"Client connected: {client_id}")
        return client_id

    def disconnect(self, client_id: str):
        self.clients.pop(client_id, None)
        for room in self.rooms.values():
            room.discard(client_id)
        logger.info(f"Client disconnected: {client_id}")

    def join_room(self, client_id: str, room: str):
        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(client_id)
        logger.info(f"{client_id} joined room {room}")

    def leave_room(self, client_id: str, room: str):
        if room in self.rooms:
            self.rooms[room].discard(client_id)

    async def broadcast_to_room(self, room: str, message: dict, exclude: str = None):
        if room not in self.rooms:
            return

        data = json.dumps(message)
        for client_id in self.rooms[room]:
            if client_id == exclude:
                continue
            websocket = self.clients.get(client_id)
            if websocket:
                try:
                    await websocket.send(data)
                except websockets.ConnectionClosed:
                    self.disconnect(client_id)


manager = ConnectionManager()


async def handler(websocket: WebSocketServerProtocol):
    client_id = await manager.connect(websocket)

    try:
        # Send welcome
        await websocket.send(json.dumps({
            "type": "connected",
            "client_id": client_id
        }))

        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "join":
                    manager.join_room(client_id, data["room"])

                elif msg_type == "leave":
                    manager.leave_room(client_id, data["room"])

                elif msg_type == "broadcast":
                    await manager.broadcast_to_room(
                        data["room"],
                        {
                            "type": "message",
                            "from": client_id,
                            "data": data.get("data"),
                        },
                        exclude=client_id
                    )

                elif msg_type == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))

            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from {client_id}")

    except websockets.ConnectionClosed:
        pass
    finally:
        manager.disconnect(client_id)


async def main():
    port = 3001
    async with websockets.serve(handler, "0.0.0.0", port):
        logger.info(f"WebSocket server running on port {port}")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())
''',
}

# Templates de cliente
CLIENT_TEMPLATES = {
    "react_socketio": """import {{ useEffect, useState, useCallback }} from 'react';
import {{ io, Socket }} from 'socket.io-client';

const SOCKET_URL = process.env.REACT_APP_SOCKET_URL || 'http://localhost:3001';

export function useSocket() {{
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);

  useEffect(() => {{
    const newSocket = io(SOCKET_URL, {{
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    }});

    newSocket.on('connect', () => {{
      console.log('Connected to socket');
      setIsConnected(true);
    }});

    newSocket.on('disconnect', (reason) => {{
      console.log('Disconnected:', reason);
      setIsConnected(false);
    }});

    newSocket.on('message', (data) => {{
      setLastMessage(data);
    }});

    setSocket(newSocket);

    return () => {{
      newSocket.close();
    }};
  }}, []);

  const joinRoom = useCallback((room: string) => {{
    socket?.emit('join', room);
  }}, [socket]);

  const leaveRoom = useCallback((room: string) => {{
    socket?.emit('leave', room);
  }}, [socket]);

  const sendMessage = useCallback((room: string, data: any) => {{
    socket?.emit('message', {{ room, data }});
  }}, [socket]);

  return {{
    socket,
    isConnected,
    lastMessage,
    joinRoom,
    leaveRoom,
    sendMessage,
  }};
}}
""",
    "react_websocket": """import {{ useEffect, useState, useCallback, useRef }} from 'react';

const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:3001';

interface UseWebSocketOptions {{
  onMessage?: (data: any) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  reconnect?: boolean;
  reconnectInterval?: number;
  reconnectAttempts?: number;
}}

export function useWebSocket(options: UseWebSocketOptions = {{}}) {{
  const {{
    onMessage,
    onConnect,
    onDisconnect,
    reconnect = true,
    reconnectInterval = 3000,
    reconnectAttempts = 5,
  }} = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  const connect = useCallback(() => {{
    try {{
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {{
        console.log('WebSocket connected');
        setIsConnected(true);
        reconnectCountRef.current = 0;
        onConnect?.();
      }};

      ws.onmessage = (event) => {{
        try {{
          const data = JSON.parse(event.data);
          setLastMessage(data);
          onMessage?.(data);
        }} catch (e) {{
          console.error('Failed to parse message:', e);
        }}
      }};

      ws.onclose = () => {{
        console.log('WebSocket disconnected');
        setIsConnected(false);
        onDisconnect?.();

        // Reconnect logic
        if (reconnect && reconnectCountRef.current < reconnectAttempts) {{
          reconnectCountRef.current++;
          reconnectTimeoutRef.current = setTimeout(() => {{
            console.log(`Reconnecting... attempt ${{reconnectCountRef.current}}`);
            connect();
          }}, reconnectInterval);
        }}
      }};

      ws.onerror = (error) => {{
        console.error('WebSocket error:', error);
      }};

      wsRef.current = ws;
    }} catch (error) {{
      console.error('Failed to connect:', error);
    }}
  }}, [onMessage, onConnect, onDisconnect, reconnect, reconnectInterval, reconnectAttempts]);

  useEffect(() => {{
    connect();

    return () => {{
      if (reconnectTimeoutRef.current) {{
        clearTimeout(reconnectTimeoutRef.current);
      }}
      wsRef.current?.close();
    }};
  }}, [connect]);

  const send = useCallback((data: any) => {{
    if (wsRef.current?.readyState === WebSocket.OPEN) {{
      wsRef.current.send(JSON.stringify(data));
    }}
  }}, []);

  const joinRoom = useCallback((room: string) => {{
    send({{ type: 'join', room }});
  }}, [send]);

  const leaveRoom = useCallback((room: string) => {{
    send({{ type: 'leave', room }});
  }}, [send]);

  const broadcast = useCallback((room: string, data: any) => {{
    send({{ type: 'broadcast', room, data }});
  }}, [send]);

  return {{
    isConnected,
    lastMessage,
    send,
    joinRoom,
    leaveRoom,
    broadcast,
  }};
}}
""",
}


def analyze_requirements(reqs: RealtimeRequirements) -> dict:
    """Analiza requisitos y recomienda tecnología."""
    recommendations = []

    # Análisis de conexiones
    if reqs.max_connections > 100000:
        recommendations.append(
            {
                "aspect": "Scale",
                "recommendation": "Usar Elixir/Phoenix o Go para mejor concurrencia",
                "reason": f"{reqs.max_connections} conexiones requieren lenguaje optimizado para concurrencia",
            }
        )
    elif reqs.max_connections > 10000:
        recommendations.append(
            {
                "aspect": "Scale",
                "recommendation": "Usar Node.js con Redis adapter para horizontal scaling",
                "reason": "Socket.IO + Redis puede manejar 10k+ conexiones distribuidas",
            }
        )

    # Análisis de latencia
    if reqs.latency_requirement_ms < 50:
        recommendations.append(
            {
                "aspect": "Latency",
                "recommendation": "WebSocket nativo sobre Socket.IO",
                "reason": "WebSocket tiene menos overhead que Socket.IO",
            }
        )

    # Bidireccionalidad
    if not reqs.bidirectional:
        recommendations.append(
            {
                "aspect": "Protocol",
                "recommendation": "Server-Sent Events (SSE)",
                "reason": "SSE es más simple y eficiente para comunicación unidireccional",
            }
        )
    else:
        recommendations.append(
            {
                "aspect": "Protocol",
                "recommendation": "WebSocket",
                "reason": "WebSocket permite comunicación bidireccional",
            }
        )

    # Persistencia
    if reqs.persistence_required:
        recommendations.append(
            {
                "aspect": "Persistence",
                "recommendation": "Agregar Redis o Kafka para message replay",
                "reason": "Permite recuperar mensajes perdidos durante desconexión",
            }
        )

    # Estimación de recursos
    memory_per_conn_kb = 50  # Aproximado
    estimated_memory_gb = (reqs.max_connections * memory_per_conn_kb) / (1024 * 1024)

    bandwidth_mbps = (reqs.messages_per_second * reqs.message_size_bytes * 8) / 1_000_000

    return {
        "recommendations": recommendations,
        "estimated_resources": {
            "memory_gb": round(estimated_memory_gb, 2),
            "bandwidth_mbps": round(bandwidth_mbps, 2),
            "suggested_instances": max(1, reqs.max_connections // 50000),
        },
        "suggested_stack": get_suggested_stack(reqs),
    }


def get_suggested_stack(reqs: RealtimeRequirements) -> dict:
    """Determina el stack recomendado."""
    if reqs.max_connections > 100000:
        return {
            "server": "Elixir/Phoenix or Go",
            "protocol": "WebSocket",
            "adapter": "Redis Cluster",
            "infrastructure": "Kubernetes with HPA",
        }
    elif reqs.bidirectional:
        return {
            "server": "Node.js + Socket.IO",
            "protocol": "WebSocket with fallback",
            "adapter": "Redis",
            "infrastructure": "Multiple instances behind LB",
        }
    else:
        return {
            "server": "Node.js + Express",
            "protocol": "Server-Sent Events",
            "adapter": "Redis Pub/Sub",
            "infrastructure": "Single instance or simple LB",
        }


def generate_events_schema(events: list) -> str:
    """Genera schema de eventos en JSON Schema."""
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Realtime Events Schema",
        "definitions": {},
    }

    for event in events:
        schema["definitions"][event["name"]] = {
            "type": "object",
            "properties": {
                "type": {"const": event["name"]},
                "timestamp": {"type": "integer"},
                "data": event.get("schema", {"type": "object"}),
            },
            "required": ["type", "timestamp", "data"],
        }

    return json.dumps(schema, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Realtime Specialist - Implementa sistemas de tiempo real"
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analiza requisitos")
    analyze_parser.add_argument("--connections", "-c", type=int, default=1000)
    analyze_parser.add_argument("--messages-per-sec", "-m", type=int, default=100)
    analyze_parser.add_argument("--message-size", "-s", type=int, default=1024)
    analyze_parser.add_argument("--latency", "-l", type=int, default=100)
    analyze_parser.add_argument("--bidirectional", "-b", action="store_true")
    analyze_parser.add_argument("--persistence", "-p", action="store_true")

    # generate
    gen_parser = subparsers.add_parser("generate", help="Genera servidor")
    gen_parser.add_argument("--type", "-t", choices=["websocket", "socketio", "sse"], required=True)
    gen_parser.add_argument("--language", "-l", choices=["node", "python"], default="node")

    # client
    client_parser = subparsers.add_parser("client", help="Genera cliente")
    client_parser.add_argument(
        "--type", "-t", choices=["websocket", "socketio"], default="websocket"
    )
    client_parser.add_argument("--framework", "-f", choices=["react", "vue"], default="react")

    # events
    events_parser = subparsers.add_parser("events", help="Genera schema de eventos")
    events_parser.add_argument("--events", "-e", nargs="+", help="Lista de eventos")

    # Común
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--output", "-o", help="Archivo de salida")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    output = None

    if args.command == "analyze":
        reqs = RealtimeRequirements(
            max_connections=args.connections,
            messages_per_second=args.messages_per_sec,
            message_size_bytes=args.message_size,
            latency_requirement_ms=args.latency,
            bidirectional=args.bidirectional,
            persistence_required=args.persistence,
        )

        analysis = analyze_requirements(reqs)

        if args.json:
            output = json.dumps(analysis, indent=2)
        else:
            print(f"\n{'=' * 60}")
            print(" ANÁLISIS DE REQUISITOS REALTIME")
            print(f"{'=' * 60}")

            print("\n📊 Parámetros:")
            print(f"   Conexiones máx: {reqs.max_connections:,}")
            print(f"   Mensajes/seg: {reqs.messages_per_second:,}")
            print(f"   Tamaño mensaje: {reqs.message_size_bytes} bytes")
            print(f"   Latencia req: {reqs.latency_requirement_ms}ms")
            print(f"   Bidireccional: {'Sí' if reqs.bidirectional else 'No'}")

            print("\n💡 Recomendaciones:")
            for rec in analysis["recommendations"]:
                print(f"\n   [{rec['aspect']}]")
                print(f"   → {rec['recommendation']}")
                print(f"   📝 {rec['reason']}")

            print("\n📈 Recursos estimados:")
            res = analysis["estimated_resources"]
            print(f"   Memoria: ~{res['memory_gb']} GB")
            print(f"   Bandwidth: ~{res['bandwidth_mbps']} Mbps")
            print(f"   Instancias sugeridas: {res['suggested_instances']}")

            print("\n🔧 Stack sugerido:")
            stack = analysis["suggested_stack"]
            for key, value in stack.items():
                print(f"   {key}: {value}")

    elif args.command == "generate":
        template_key = f"{args.type}_{args.language}"
        if args.type == "websocket" and args.language == "python":
            template_key = "python_websocket"
        elif args.type == "websocket":
            template_key = "ws_node"
        elif args.type == "socketio":
            template_key = "socketio_node"
        elif args.type == "sse":
            template_key = "sse_node"

        output = SERVER_TEMPLATES.get(template_key, "# Template not found")

    elif args.command == "client":
        template_key = f"{args.framework}_{args.type}"
        output = CLIENT_TEMPLATES.get(template_key, "// Template not found")

    elif args.command == "events":
        events = [{"name": e, "schema": {"type": "object"}} for e in (args.events or ["message"])]
        output = generate_events_schema(events)

    # Output
    if output:
        if hasattr(args, "output") and args.output:
            Path(args.output).write_text(output)
            print(f"✓ Escrito en {args.output}")
        else:
            print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
