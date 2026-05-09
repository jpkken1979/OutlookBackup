---
type: feature
name: graphql-subscriptions
description: "Master graphql subscriptions with expert patterns and practices."
---

# GraphQL Subscriptions

> Real-time data con GraphQL Subscriptions y WebSockets.

---

## Descripción

Esta skill cubre implementación de GraphQL Subscriptions para datos en tiempo real usando WebSockets con Apollo Server y Apollo Client.

---

## Apollo Server Setup

### Instalación

```bash
npm install @apollo/server graphql graphql-subscriptions graphql-ws ws
```

### Server con Subscriptions

```typescript
import { ApolloServer } from '@apollo/server';
import { expressMiddleware } from '@apollo/server/express4';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';
import { useServer } from 'graphql-ws/lib/use/ws';
import { makeExecutableSchema } from '@graphql-tools/schema';
import { PubSub } from 'graphql-subscriptions';
import express from 'express';

const app = express();
const httpServer = createServer(app);

// PubSub para eventos
const pubsub = new PubSub();

// Schema
const typeDefs = `#graphql
  type Message {
    id: ID!
    content: String!
    author: User!
    createdAt: String!
  }

  type User {
    id: ID!
    name: String!
    status: String!
  }

  type Query {
    messages(roomId: ID!): [Message!]!
    users: [User!]!
  }

  type Mutation {
    sendMessage(roomId: ID!, content: String!): Message!
    updateUserStatus(status: String!): User!
  }

  type Subscription {
    messageAdded(roomId: ID!): Message!
    userStatusChanged: User!
    typingIndicator(roomId: ID!): TypingEvent!
  }

  type TypingEvent {
    userId: ID!
    userName: String!
    isTyping: Boolean!
  }
`;

// Resolvers
const resolvers = {
  Query: {
    messages: async (_, { roomId }, { dataSources }) => {
      return dataSources.messages.getByRoom(roomId);
    },
    users: async (_, __, { dataSources }) => {
      return dataSources.users.getAll();
    },
  },

  Mutation: {
    sendMessage: async (_, { roomId, content }, { user, dataSources }) => {
      const message = await dataSources.messages.create({
        roomId,
        content,
        authorId: user.id,
      });

      // Publicar a suscriptores
      pubsub.publish(`MESSAGE_ADDED_${roomId}`, {
        messageAdded: message,
      });

      return message;
    },

    updateUserStatus: async (_, { status }, { user, dataSources }) => {
      const updatedUser = await dataSources.users.updateStatus(user.id, status);

      pubsub.publish('USER_STATUS_CHANGED', {
        userStatusChanged: updatedUser,
      });

      return updatedUser;
    },
  },

  Subscription: {
    messageAdded: {
      subscribe: (_, { roomId }) => {
        return pubsub.asyncIterator(`MESSAGE_ADDED_${roomId}`);
      },
    },

    userStatusChanged: {
      subscribe: () => pubsub.asyncIterator('USER_STATUS_CHANGED'),
    },

    typingIndicator: {
      subscribe: (_, { roomId }) => {
        return pubsub.asyncIterator(`TYPING_${roomId}`);
      },
    },
  },
};

const schema = makeExecutableSchema({ typeDefs, resolvers });

// WebSocket Server
const wsServer = new WebSocketServer({
  server: httpServer,
  path: '/graphql',
});

const serverCleanup = useServer({
  schema,
  context: async (ctx) => {
    // Autenticación desde connection params
    const token = ctx.connectionParams?.authToken;
    const user = await authenticateToken(token);
    return { user, pubsub };
  },
  onConnect: async (ctx) => {
    console.log('Client connected');
    // Validar autenticación
    if (!ctx.connectionParams?.authToken) {
      throw new Error('Missing auth token');
    }
  },
  onDisconnect: (ctx) => {
    console.log('Client disconnected');
  },
}, wsServer);

// Apollo Server
const server = new ApolloServer({
  schema,
  plugins: [{
    async serverWillStart() {
      return {
        async drainServer() {
          await serverCleanup.dispose();
        },
      };
    },
  }],
});

await server.start();

app.use('/graphql', expressMiddleware(server, {
  context: async ({ req }) => {
    const user = await authenticateRequest(req);
    return { user, pubsub };
  },
}));

httpServer.listen(4000, () => {
  console.log('Server running at http://localhost:4000/graphql');
});
```

---

## Apollo Client Setup

### Instalación

```bash
npm install @apollo/client graphql graphql-ws
```

### Cliente con Subscriptions

```typescript
import {
  ApolloClient,
  InMemoryCache,
  HttpLink,
  split,
} from '@apollo/client';
import { GraphQLWsLink } from '@apollo/client/link/subscriptions';
import { createClient } from 'graphql-ws';
import { getMainDefinition } from '@apollo/client/utilities';

const httpLink = new HttpLink({
  uri: 'http://localhost:4000/graphql',
  headers: {
    authorization: `Bearer ${getToken()}`,
  },
});

const wsLink = new GraphQLWsLink(
  createClient({
    url: 'ws://localhost:4000/graphql',
    connectionParams: {
      authToken: getToken(),
    },
    on: {
      connected: () => console.log('WebSocket connected'),
      closed: () => console.log('WebSocket closed'),
      error: (err) => console.error('WebSocket error:', err),
    },
    retryAttempts: 5,
    shouldRetry: () => true,
  })
);

// Split: HTTP para queries/mutations, WebSocket para subscriptions
const splitLink = split(
  ({ query }) => {
    const definition = getMainDefinition(query);
    return (
      definition.kind === 'OperationDefinition' &&
      definition.operation === 'subscription'
    );
  },
  wsLink,
  httpLink
);

const client = new ApolloClient({
  link: splitLink,
  cache: new InMemoryCache(),
});
```

---

## React Hooks

### useSubscription

```tsx
import { gql, useSubscription, useQuery } from '@apollo/client';

const MESSAGES_QUERY = gql`
  query GetMessages($roomId: ID!) {
    messages(roomId: $roomId) {
      id
      content
      author {
        id
        name
      }
      createdAt
    }
  }
`;

const MESSAGE_SUBSCRIPTION = gql`
  subscription OnMessageAdded($roomId: ID!) {
    messageAdded(roomId: $roomId) {
      id
      content
      author {
        id
        name
      }
      createdAt
    }
  }
`;

function ChatRoom({ roomId }: { roomId: string }) {
  const { data, loading } = useQuery(MESSAGES_QUERY, {
    variables: { roomId },
  });

  // Suscribirse a nuevos mensajes
  useSubscription(MESSAGE_SUBSCRIPTION, {
    variables: { roomId },
    onData: ({ client, data }) => {
      // Actualizar cache con nuevo mensaje
      const newMessage = data.data.messageAdded;

      client.cache.modify({
        fields: {
          messages(existingMessages = []) {
            const newMessageRef = client.cache.writeFragment({
              data: newMessage,
              fragment: gql`
                fragment NewMessage on Message {
                  id
                  content
                  author {
                    id
                    name
                  }
                  createdAt
                }
              `,
            });
            return [...existingMessages, newMessageRef];
          },
        },
      });
    },
  });

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      {data.messages.map((message) => (
        <MessageItem key={message.id} message={message} />
      ))}
    </div>
  );
}
```

### subscribeToMore

```tsx
function ChatRoom({ roomId }: { roomId: string }) {
  const { data, loading, subscribeToMore } = useQuery(MESSAGES_QUERY, {
    variables: { roomId },
  });

  useEffect(() => {
    const unsubscribe = subscribeToMore({
      document: MESSAGE_SUBSCRIPTION,
      variables: { roomId },
      updateQuery: (prev, { subscriptionData }) => {
        if (!subscriptionData.data) return prev;
        const newMessage = subscriptionData.data.messageAdded;

        return {
          ...prev,
          messages: [...prev.messages, newMessage],
        };
      },
    });

    return () => unsubscribe();
  }, [roomId, subscribeToMore]);

  // render...
}
```

---

## Patrones Avanzados

### Typing Indicator

```typescript
// Server
const TYPING_TIMEOUT = 3000;
const typingUsers = new Map<string, NodeJS.Timeout>();

const resolvers = {
  Mutation: {
    setTyping: (_, { roomId, isTyping }, { user }) => {
      const key = `${roomId}:${user.id}`;

      // Limpiar timeout anterior
      if (typingUsers.has(key)) {
        clearTimeout(typingUsers.get(key));
      }

      if (isTyping) {
        // Auto-clear después de timeout
        typingUsers.set(key, setTimeout(() => {
          pubsub.publish(`TYPING_${roomId}`, {
            typingIndicator: { userId: user.id, userName: user.name, isTyping: false },
          });
          typingUsers.delete(key);
        }, TYPING_TIMEOUT));
      }

      pubsub.publish(`TYPING_${roomId}`, {
        typingIndicator: { userId: user.id, userName: user.name, isTyping },
      });

      return true;
    },
  },
};

// Client Hook
function useTypingIndicator(roomId: string) {
  const [typingUsers, setTypingUsers] = useState<string[]>([]);

  useSubscription(TYPING_SUBSCRIPTION, {
    variables: { roomId },
    onData: ({ data }) => {
      const { userId, userName, isTyping } = data.data.typingIndicator;

      setTypingUsers((prev) => {
        if (isTyping && !prev.includes(userName)) {
          return [...prev, userName];
        }
        if (!isTyping) {
          return prev.filter((name) => name !== userName);
        }
        return prev;
      });
    },
  });

  return typingUsers;
}
```

### Presencia Online

```typescript
// Server
const onlineUsers = new Set<string>();

useServer({
  schema,
  context: async (ctx) => {
    const user = await authenticateToken(ctx.connectionParams?.authToken);
    return { user };
  },
  onConnect: async (ctx) => {
    const user = ctx.extra.user;
    onlineUsers.add(user.id);
    pubsub.publish('PRESENCE_CHANGED', {
      presenceChanged: { userId: user.id, isOnline: true },
    });
  },
  onDisconnect: async (ctx) => {
    const user = ctx.extra.user;
    onlineUsers.delete(user.id);
    pubsub.publish('PRESENCE_CHANGED', {
      presenceChanged: { userId: user.id, isOnline: false },
    });
  },
}, wsServer);
```

### Filtrado de Subscriptions

```typescript
import { withFilter } from 'graphql-subscriptions';

const resolvers = {
  Subscription: {
    messageAdded: {
      subscribe: withFilter(
        () => pubsub.asyncIterator('MESSAGE_ADDED'),
        (payload, variables, context) => {
          // Solo recibir mensajes del room correcto
          return payload.messageAdded.roomId === variables.roomId;
        }
      ),
    },

    // Filtrar por permisos
    orderUpdated: {
      subscribe: withFilter(
        () => pubsub.asyncIterator('ORDER_UPDATED'),
        async (payload, variables, context) => {
          // Solo el dueño de la orden puede ver updates
          const order = payload.orderUpdated;
          return order.userId === context.user.id;
        }
      ),
    },
  },
};
```

---

## Escalabilidad con Redis PubSub

```typescript
import { RedisPubSub } from 'graphql-redis-subscriptions';
import Redis from 'ioredis';

const options = {
  host: process.env.REDIS_HOST,
  port: parseInt(process.env.REDIS_PORT || '6379'),
  retryStrategy: (times: number) => Math.min(times * 50, 2000),
};

const pubsub = new RedisPubSub({
  publisher: new Redis(options),
  subscriber: new Redis(options),
});

// Ahora múltiples instancias del server comparten subscriptions
```

---

## Referencias

- [Apollo Server Subscriptions](https://www.apollographql.com/docs/apollo-server/data/subscriptions/)
- [Apollo Client Subscriptions](https://www.apollographql.com/docs/react/data/subscriptions/)
- [graphql-ws](https://github.com/enisdenjo/graphql-ws)
- [graphql-subscriptions](https://github.com/apollographql/graphql-subscriptions)

---

*Skill creada: 2026-02-01*
*Versión: 1.0.0*
