---
name: cloudflare-agents-sdk
description: >
type: feature
---
  Build stateful AI agents on Cloudflare Workers with persistent SQLite-backed
  state, RPC methods, scheduling (delay/cron/interval), AgentWorkflow, MCP
  integration, and React hooks. Use when building AI agents that need persistent
  state, real-time communication, or complex multi-step workflows.
source: Cloudflare
---

# Cloudflare Agents SDK

Build stateful AI agents with persistent state, real-time communication, and scheduling.

## Core Concepts

### Agent Class
```typescript
import { Agent } from 'agents';

export class MyAgent extends Agent<Env, State> {
  // Persistent state (SQLite-backed, survives restarts)
  initialState = { counter: 0, messages: [] };

  // Handle incoming messages
  async onMessage(message: string) {
    this.setState({ ...this.state, counter: this.state.counter + 1 });
    return `Received: ${message}`;
  }
}
```

### Persistent State
- Backed by Durable Objects + SQLite
- Survives Worker restarts and redeployments
- Automatically synced across connections

```typescript
// Read state
const count = this.state.counter;

// Update state (triggers sync to all connected clients)
this.setState({ ...this.state, counter: count + 1 });
```

### RPC Methods
```typescript
export class MyAgent extends Agent<Env, State> {
  // Callable from client or other Workers
  @callable()
  async processTask(input: string): Promise<string> {
    // Process and return result
    return `Processed: ${input}`;
  }

  @callable()
  async getStatus(): Promise<{ status: string; count: number }> {
    return { status: 'active', count: this.state.counter };
  }
}
```

### Scheduling
```typescript
export class MyAgent extends Agent<Env, State> {
  // Schedule delayed execution
  async scheduleTask() {
    // Run after 5 minutes
    await this.schedule({ delay: '5m' }, 'processQueue');

    // Run on cron schedule
    await this.schedule({ cron: '0 */6 * * *' }, 'dailyReport');

    // Run at interval
    await this.schedule({ interval: '30s' }, 'heartbeat');
  }

  // Handler for scheduled tasks
  async onScheduled(taskName: string) {
    switch (taskName) {
      case 'processQueue': await this.processQueue(); break;
      case 'dailyReport': await this.generateReport(); break;
      case 'heartbeat': await this.sendHeartbeat(); break;
    }
  }
}
```

### AgentWorkflow
Multi-step workflows with human-in-the-loop:
```typescript
import { AgentWorkflow } from 'agents/workflow';

const workflow = new AgentWorkflow({
  steps: [
    { name: 'analyze', handler: async (input) => analyzeData(input) },
    { name: 'confirm', handler: async (input) => waitForApproval(input) },
    { name: 'execute', handler: async (input) => executeAction(input) },
  ],
});
```

### MCP Integration
Agents can serve as MCP servers:
```typescript
import { MCPAgent } from 'agents/mcp';

export class MyMCPAgent extends MCPAgent<Env> {
  tools = [
    {
      name: 'search',
      description: 'Search documents',
      parameters: { query: { type: 'string' } },
      handler: async ({ query }) => searchDocs(query),
    },
  ];
}
```

## React Hooks (Client-Side)

```typescript
import { useAgent, useAgentChat } from 'agents/react';

function ChatComponent() {
  const agent = useAgent({ name: 'my-agent' });

  // Real-time chat with AI agent
  const { messages, sendMessage, isLoading } = useAgentChat({
    agent,
    onMessage: (msg) => console.log('Received:', msg),
  });

  return (
    <div>
      {messages.map((m) => <p key={m.id}>{m.content}</p>)}
      <button onClick={() => sendMessage('Hello!')}>Send</button>
    </div>
  );
}
```

## Deployment

```toml
# wrangler.toml
name = "my-agent"
main = "src/index.ts"
compatibility_date = "2024-01-01"

[[durable_objects.bindings]]
name = "MY_AGENT"
class_name = "MyAgent"

[[migrations]]
tag = "v1"
new_classes = ["MyAgent"]
```

```bash
npx wrangler deploy
```
