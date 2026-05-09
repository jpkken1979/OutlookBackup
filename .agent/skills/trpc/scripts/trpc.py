#!/usr/bin/env python3
"""
tRPC Skill

Genera routers, procedures, y configuración para tRPC.
"""

import argparse
import json
import sys
from pathlib import Path


# Templates de tRPC
ROUTER_TEMPLATE = """import {{ z }} from 'zod';
import {{ router, publicProcedure, protectedProcedure }} from '../trpc';

export const {name}Router = router({{
  // Query: Get all {name}s
  getAll: publicProcedure
    .query(async ({{ ctx }}) => {{
      return ctx.db.{name}.findMany();
    }}),

  // Query: Get {name} by ID
  getById: publicProcedure
    .input(z.object({{ id: z.string() }}))
    .query(async ({{ ctx, input }}) => {{
      return ctx.db.{name}.findUnique({{
        where: {{ id: input.id }},
      }});
    }}),

  // Mutation: Create {name}
  create: protectedProcedure
    .input(z.object({{
      // Implementar: validación de input
      name: z.string().min(1),
    }}))
    .mutation(async ({{ ctx, input }}) => {{
      return ctx.db.{name}.create({{
        data: input,
      }});
    }}),

  // Mutation: Update {name}
  update: protectedProcedure
    .input(z.object({{
      id: z.string(),
      // Implementar: campos de actualización
      name: z.string().min(1).optional(),
    }}))
    .mutation(async ({{ ctx, input }}) => {{
      const {{ id, ...data }} = input;
      return ctx.db.{name}.update({{
        where: {{ id }},
        data,
      }});
    }}),

  // Mutation: Delete {name}
  delete: protectedProcedure
    .input(z.object({{ id: z.string() }}))
    .mutation(async ({{ ctx, input }}) => {{
      return ctx.db.{name}.delete({{
        where: {{ id: input.id }},
      }});
    }}),
}});
"""

PROCEDURE_TEMPLATES = {
    "query": """  {name}: publicProcedure
    .input(z.object({{
      {input_schema}
    }}))
    .query(async ({{ ctx, input }}) => {{
      // Implementar: lógica de query
      return {{ success: true }};
    }}),
""",
    "mutation": """  {name}: protectedProcedure
    .input(z.object({{
      {input_schema}
    }}))
    .mutation(async ({{ ctx, input }}) => {{
      // Implementar: lógica de mutation
      return {{ success: true }};
    }}),
""",
    "subscription": """  {name}: publicProcedure
    .subscription(() => {{
      return observable<{{ data: string }}>((emit) => {{
        // Implementar: lógica de subscription
        const interval = setInterval(() => {{
          emit.next({{ data: 'update' }});
        }}, 1000);

        return () => clearInterval(interval);
      }});
    }}),
""",
}

TRPC_SETUP_NEXTJS = """// server/trpc.ts
import {{ initTRPC, TRPCError }} from '@trpc/server';
import {{ type Context }} from './context';
import superjson from 'superjson';

const t = initTRPC.context<Context>().create({{
  transformer: superjson,
  errorFormatter({{ shape, error }}) {{
    return {{
      ...shape,
      data: {{
        ...shape.data,
        zodError:
          error.cause instanceof ZodError ? error.cause.flatten() : null,
      }},
    }};
  }},
}});

export const router = t.router;
export const publicProcedure = t.procedure;
export const protectedProcedure = t.procedure.use(({{ ctx, next }}) => {{
  if (!ctx.session?.user) {{
    throw new TRPCError({{ code: 'UNAUTHORIZED' }});
  }}
  return next({{
    ctx: {{
      ...ctx,
      session: ctx.session,
    }},
  }});
}});
"""

TRPC_CONTEXT = """// server/context.ts
import {{ type inferAsyncReturnType }} from '@trpc/server';
import {{ type CreateNextContextOptions }} from '@trpc/server/adapters/next';
import {{ getServerSession }} from 'next-auth';
import {{ authOptions }} from './auth';
import {{ db }} from './db';

export async function createContext(opts: CreateNextContextOptions) {{
  const session = await getServerSession(opts.req, opts.res, authOptions);

  return {{
    session,
    db,
  }};
}}

export type Context = inferAsyncReturnType<typeof createContext>;
"""

TRPC_APP_ROUTER = """// app/api/trpc/[trpc]/route.ts
import {{ fetchRequestHandler }} from '@trpc/server/adapters/fetch';
import {{ appRouter }} from '@/server/routers/_app';
import {{ createContext }} from '@/server/context';

const handler = (req: Request) =>
  fetchRequestHandler({{
    endpoint: '/api/trpc',
    req,
    router: appRouter,
    createContext: () => createContext({{ req }}),
  }});

export {{ handler as GET, handler as POST }};
"""

TRPC_CLIENT = """// utils/trpc.ts
import {{ createTRPCReact }} from '@trpc/react-query';
import {{ type AppRouter }} from '@/server/routers/_app';

export const trpc = createTRPCReact<AppRouter>();
"""

TRPC_PROVIDER = """// components/providers/trpc-provider.tsx
'use client';

import {{ QueryClient, QueryClientProvider }} from '@tanstack/react-query';
import {{ httpBatchLink }} from '@trpc/client';
import {{ useState }} from 'react';
import {{ trpc }} from '@/utils/trpc';
import superjson from 'superjson';

function getBaseUrl() {{
  if (typeof window !== 'undefined') return '';
  if (process.env.VERCEL_URL) return `https://${{process.env.VERCEL_URL}}`;
  return `http://localhost:${{process.env.PORT ?? 3000}}`;
}}

export function TRPCProvider({{ children }}: {{ children: React.ReactNode }}) {{
  const [queryClient] = useState(() => new QueryClient({{
    defaultOptions: {{
      queries: {{
        staleTime: 60 * 1000,
      }},
    }},
  }}));

  const [trpcClient] = useState(() =>
    trpc.createClient({{
      links: [
        httpBatchLink({{
          url: `${{getBaseUrl()}}/api/trpc`,
          transformer: superjson,
        }}),
      ],
    }})
  );

  return (
    <trpc.Provider client={{trpcClient}} queryClient={{queryClient}}>
      <QueryClientProvider client={{queryClient}}>
        {{children}}
      </QueryClientProvider>
    </trpc.Provider>
  );
}}
"""

PATTERNS = {
    "optimistic-update": """// Optimistic Update Pattern
const utils = trpc.useUtils();

const mutation = trpc.{router}.update.useMutation({{
  onMutate: async (newData) => {{
    // Cancel outgoing refetches
    await utils.{router}.getById.cancel({{ id: newData.id }});

    // Snapshot previous value
    const previousData = utils.{router}.getById.getData({{ id: newData.id }});

    // Optimistically update
    utils.{router}.getById.setData({{ id: newData.id }}, (old) => ({{
      ...old,
      ...newData,
    }}));

    return {{ previousData }};
  }},
  onError: (err, newData, context) => {{
    // Rollback on error
    utils.{router}.getById.setData(
      {{ id: newData.id }},
      context?.previousData
    );
  }},
  onSettled: () => {{
    // Always refetch after error or success
    utils.{router}.getById.invalidate();
  }},
}});
""",
    "infinite-query": """// Infinite Query Pattern
const {{ data, fetchNextPage, hasNextPage, isFetchingNextPage }} =
  trpc.{router}.getAll.useInfiniteQuery(
    {{ limit: 10 }},
    {{
      getNextPageParam: (lastPage) => lastPage.nextCursor,
    }}
  );

// Flatten pages
const items = data?.pages.flatMap((page) => page.items) ?? [];
""",
    "dependent-query": """// Dependent Query Pattern
const {{ data: user }} = trpc.user.getById.useQuery({{ id: userId }});

// Only fetch posts if user exists
const {{ data: posts }} = trpc.post.getByAuthor.useQuery(
  {{ authorId: user?.id! }},
  {{ enabled: !!user?.id }}
);
""",
    "prefetch": """// Prefetch Pattern (Server Component)
import {{ createServerSideHelpers }} from '@trpc/react-query/server';
import {{ appRouter }} from '@/server/routers/_app';

export async function Page() {{
  const helpers = createServerSideHelpers({{
    router: appRouter,
    ctx: await createContext(),
  }});

  // Prefetch data
  await helpers.{router}.getAll.prefetch();

  return (
    <HydrationBoundary state={{dehydrate(helpers.queryClient)}}>
      <ClientComponent />
    </HydrationBoundary>
  );
}}
""",
}


def generate_router(name: str) -> str:
    """Genera un router tRPC."""
    return ROUTER_TEMPLATE.format(name=name)


def generate_procedure(name: str, proc_type: str, input_schema: str = "id: z.string()") -> str:
    """Genera un procedure tRPC."""
    template = PROCEDURE_TEMPLATES.get(proc_type, PROCEDURE_TEMPLATES["query"])
    return template.format(name=name, input_schema=input_schema)


def generate_setup(framework: str = "nextjs") -> dict:
    """Genera setup completo de tRPC."""
    if framework == "nextjs":
        return {
            "server/trpc.ts": TRPC_SETUP_NEXTJS,
            "server/context.ts": TRPC_CONTEXT,
            "app/api/trpc/[trpc]/route.ts": TRPC_APP_ROUTER,
            "utils/trpc.ts": TRPC_CLIENT,
            "components/providers/trpc-provider.tsx": TRPC_PROVIDER,
        }
    return {}


def main():
    parser = argparse.ArgumentParser(description="tRPC Skill - Genera APIs type-safe")

    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # router
    router_parser = subparsers.add_parser("router", help="Genera router")
    router_parser.add_argument("--name", "-n", required=True, help="Nombre del router")

    # procedure
    proc_parser = subparsers.add_parser("procedure", help="Genera procedure")
    proc_parser.add_argument("--router", "-r", required=True, help="Nombre del router")
    proc_parser.add_argument("--name", "-n", required=True, help="Nombre del procedure")
    proc_parser.add_argument(
        "--type", "-t", choices=["query", "mutation", "subscription"], default="query"
    )
    proc_parser.add_argument("--input", "-i", default="id: z.string()", help="Input schema")

    # setup
    setup_parser = subparsers.add_parser("setup", help="Genera setup completo")
    setup_parser.add_argument("--framework", "-f", choices=["nextjs", "express"], default="nextjs")

    # patterns
    subparsers.add_parser("patterns", help="Lista patterns comunes")

    # Común
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--output", "-o", help="Archivo de salida")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    output = None

    if args.command == "router":
        output = generate_router(args.name)

    elif args.command == "procedure":
        output = generate_procedure(args.name, args.type, args.input)

    elif args.command == "setup":
        files = generate_setup(args.framework)
        if args.json:
            output = json.dumps(files, indent=2)
        else:
            for filename, content in files.items():
                print(f"\n{'=' * 60}")
                print(f" {filename}")
                print(f"{'=' * 60}\n")
                print(content)

    elif args.command == "patterns":
        if args.json:
            output = json.dumps(list(PATTERNS.keys()), indent=2)
        else:
            print(f"\n{'=' * 60}")
            print(" TRPC PATTERNS")
            print(f"{'=' * 60}\n")
            for name, code in PATTERNS.items():
                print(f"📘 {name}")
                print("-" * 40)
                print(code)
                print()

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
