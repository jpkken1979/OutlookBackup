---
name: oauth-social-auth
description: "Master oauth social auth with expert patterns and practices."
type: feature
---

# OAuth & Social Authentication

> Patrones para autenticación OAuth 2.0 y login social con Google, GitHub, Apple, etc.

---

## Descripción

Esta skill cubre implementación de autenticación OAuth 2.0 y login con proveedores sociales, incluyendo flujos de autorización, tokens, refresh y mejores prácticas de seguridad.

---

## OAuth 2.0 Flujos

### Authorization Code Flow (Recomendado para Web)

```
┌──────────┐          ┌──────────┐          ┌──────────┐
│  Usuario │          │   App    │          │ Provider │
└────┬─────┘          └────┬─────┘          └────┬─────┘
     │ 1. Click Login      │                     │
     │────────────────────>│                     │
     │                     │ 2. Redirect to      │
     │                     │    /authorize       │
     │<─────────────────────────────────────────>│
     │ 3. User authorizes  │                     │
     │<────────────────────────────────────────>│
     │                     │ 4. Redirect with    │
     │                     │    auth code        │
     │<─────────────────────────────────────────│
     │                     │ 5. Exchange code    │
     │                     │    for tokens       │
     │                     │<───────────────────>│
     │                     │ 6. Access token +   │
     │                     │    Refresh token    │
     │                     │<───────────────────│
     │ 7. Authenticated    │                     │
     │<────────────────────│                     │
```

### PKCE Flow (Recomendado para SPAs/Mobile)

```typescript
// Generar PKCE challenge
import crypto from 'crypto';

function generateCodeVerifier(): string {
  return crypto.randomBytes(32).toString('base64url');
}

function generateCodeChallenge(verifier: string): string {
  return crypto
    .createHash('sha256')
    .update(verifier)
    .digest('base64url');
}

// Flujo PKCE
const codeVerifier = generateCodeVerifier();
const codeChallenge = generateCodeChallenge(codeVerifier);

// 1. Redirect con challenge
const authUrl = new URL('https://provider.com/authorize');
authUrl.searchParams.set('client_id', CLIENT_ID);
authUrl.searchParams.set('redirect_uri', REDIRECT_URI);
authUrl.searchParams.set('response_type', 'code');
authUrl.searchParams.set('scope', 'openid email profile');
authUrl.searchParams.set('code_challenge', codeChallenge);
authUrl.searchParams.set('code_challenge_method', 'S256');
authUrl.searchParams.set('state', generateState());

// Guardar verifier en session
sessionStorage.setItem('code_verifier', codeVerifier);

// 2. Intercambiar código por tokens (incluir verifier)
const tokenResponse = await fetch('https://provider.com/token', {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: CLIENT_ID,
    code: authCode,
    redirect_uri: REDIRECT_URI,
    code_verifier: sessionStorage.getItem('code_verifier')!,
  }),
});
```

---

## Proveedores Sociales

### Google OAuth

```typescript
// next-auth configuration
import NextAuth from 'next-auth';
import GoogleProvider from 'next-auth/providers/google';

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      authorization: {
        params: {
          prompt: 'consent',
          access_type: 'offline',
          response_type: 'code',
          scope: 'openid email profile',
        },
      },
    }),
  ],
  callbacks: {
    async jwt({ token, account, profile }) {
      if (account) {
        token.accessToken = account.access_token;
        token.refreshToken = account.refresh_token;
        token.expiresAt = account.expires_at;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken;
      return session;
    },
  },
});
```

### GitHub OAuth

```typescript
import GitHubProvider from 'next-auth/providers/github';

GitHubProvider({
  clientId: process.env.GITHUB_CLIENT_ID!,
  clientSecret: process.env.GITHUB_CLIENT_SECRET!,
  authorization: {
    params: {
      scope: 'read:user user:email',
    },
  },
})
```

### Apple Sign In

```typescript
import AppleProvider from 'next-auth/providers/apple';

AppleProvider({
  clientId: process.env.APPLE_CLIENT_ID!,
  clientSecret: process.env.APPLE_CLIENT_SECRET!,
  // Apple requiere generar JWT como client_secret
})

// Generar Apple Client Secret (JWT)
import jwt from 'jsonwebtoken';

function generateAppleClientSecret(): string {
  const privateKey = process.env.APPLE_PRIVATE_KEY!;

  return jwt.sign({}, privateKey, {
    algorithm: 'ES256',
    expiresIn: '180d',
    audience: 'https://appleid.apple.com',
    issuer: process.env.APPLE_TEAM_ID!,
    subject: process.env.APPLE_CLIENT_ID!,
    keyid: process.env.APPLE_KEY_ID!,
  });
}
```

### Microsoft/Azure AD

```typescript
import AzureADProvider from 'next-auth/providers/azure-ad';

AzureADProvider({
  clientId: process.env.AZURE_AD_CLIENT_ID!,
  clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
  tenantId: process.env.AZURE_AD_TENANT_ID!,
  authorization: {
    params: {
      scope: 'openid email profile User.Read',
    },
  },
})
```

---

## Implementación Manual (Express)

### OAuth Controller

```typescript
import { Router } from 'express';
import { OAuth2Client } from 'google-auth-library';
import jwt from 'jsonwebtoken';

const router = Router();
const googleClient = new OAuth2Client(
  process.env.GOOGLE_CLIENT_ID,
  process.env.GOOGLE_CLIENT_SECRET,
  process.env.GOOGLE_REDIRECT_URI
);

// Estado para prevenir CSRF
const states = new Map<string, { createdAt: Date; redirectTo?: string }>();

// Iniciar flujo OAuth
router.get('/auth/google', (req, res) => {
  const state = crypto.randomUUID();
  states.set(state, {
    createdAt: new Date(),
    redirectTo: req.query.redirectTo as string
  });

  const authUrl = googleClient.generateAuthUrl({
    access_type: 'offline',
    scope: ['openid', 'email', 'profile'],
    state,
    prompt: 'consent',
  });

  res.redirect(authUrl);
});

// Callback OAuth
router.get('/auth/google/callback', async (req, res) => {
  const { code, state, error } = req.query;

  if (error) {
    return res.redirect(`/login?error=${error}`);
  }

  // Validar state
  const stateData = states.get(state as string);
  if (!stateData) {
    return res.redirect('/login?error=invalid_state');
  }
  states.delete(state as string);

  // Verificar expiración del state (5 min)
  if (Date.now() - stateData.createdAt.getTime() > 5 * 60 * 1000) {
    return res.redirect('/login?error=state_expired');
  }

  try {
    // Intercambiar código por tokens
    const { tokens } = await googleClient.getToken(code as string);
    googleClient.setCredentials(tokens);

    // Verificar ID token
    const ticket = await googleClient.verifyIdToken({
      idToken: tokens.id_token!,
      audience: process.env.GOOGLE_CLIENT_ID,
    });

    const payload = ticket.getPayload()!;

    // Buscar o crear usuario
    let user = await prisma.user.findUnique({
      where: { email: payload.email },
    });

    if (!user) {
      user = await prisma.user.create({
        data: {
          email: payload.email!,
          name: payload.name,
          picture: payload.picture,
          googleId: payload.sub,
          emailVerified: payload.email_verified,
        },
      });
    } else if (!user.googleId) {
      // Vincular cuenta Google existente
      await prisma.user.update({
        where: { id: user.id },
        data: {
          googleId: payload.sub,
          picture: user.picture || payload.picture,
        },
      });
    }

    // Guardar refresh token si lo tenemos
    if (tokens.refresh_token) {
      await prisma.account.upsert({
        where: {
          provider_providerAccountId: {
            provider: 'google',
            providerAccountId: payload.sub,
          },
        },
        update: {
          refresh_token: tokens.refresh_token,
          access_token: tokens.access_token,
          expires_at: tokens.expiry_date,
        },
        create: {
          userId: user.id,
          provider: 'google',
          providerAccountId: payload.sub,
          refresh_token: tokens.refresh_token,
          access_token: tokens.access_token,
          expires_at: tokens.expiry_date,
        },
      });
    }

    // Crear sesión/JWT
    const sessionToken = jwt.sign(
      { userId: user.id, email: user.email },
      process.env.JWT_SECRET!,
      { expiresIn: '7d' }
    );

    res.cookie('session', sessionToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 7 * 24 * 60 * 60 * 1000, // 7 días
    });

    res.redirect(stateData.redirectTo || '/dashboard');
  } catch (error) {
    console.error('OAuth error:', error);
    res.redirect('/login?error=authentication_failed');
  }
});

// Logout
router.post('/auth/logout', (req, res) => {
  res.clearCookie('session');
  res.json({ success: true });
});
```

### Refresh Token Rotation

```typescript
async function refreshAccessToken(userId: string): Promise<string | null> {
  const account = await prisma.account.findFirst({
    where: { userId, provider: 'google' },
  });

  if (!account?.refresh_token) {
    return null;
  }

  try {
    googleClient.setCredentials({
      refresh_token: account.refresh_token,
    });

    const { credentials } = await googleClient.refreshAccessToken();

    // Actualizar tokens en BD
    await prisma.account.update({
      where: { id: account.id },
      data: {
        access_token: credentials.access_token,
        expires_at: credentials.expiry_date,
        // Si hay nuevo refresh token (rotation)
        ...(credentials.refresh_token && {
          refresh_token: credentials.refresh_token,
        }),
      },
    });

    return credentials.access_token!;
  } catch (error) {
    // Refresh token inválido, desconectar cuenta
    await prisma.account.delete({ where: { id: account.id } });
    return null;
  }
}
```

---

## Next.js App Router + NextAuth v5

### Configuration

```typescript
// auth.ts
import NextAuth from 'next-auth';
import { PrismaAdapter } from '@auth/prisma-adapter';
import { prisma } from '@/lib/prisma';
import Google from 'next-auth/providers/google';
import GitHub from 'next-auth/providers/github';
import Credentials from 'next-auth/providers/credentials';
import bcrypt from 'bcryptjs';

export const { handlers, signIn, signOut, auth } = NextAuth({
  adapter: PrismaAdapter(prisma),
  session: { strategy: 'jwt' },
  pages: {
    signIn: '/login',
    error: '/auth/error',
  },
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
      allowDangerousEmailAccountLinking: true, // Permite vincular cuentas
    }),
    GitHub({
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
    }),
    Credentials({
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        const user = await prisma.user.findUnique({
          where: { email: credentials.email as string },
        });

        if (!user || !user.password) {
          throw new Error('Invalid credentials');
        }

        const isValid = await bcrypt.compare(
          credentials.password as string,
          user.password
        );

        if (!isValid) {
          throw new Error('Invalid credentials');
        }

        return {
          id: user.id,
          email: user.email,
          name: user.name,
          image: user.image,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user, account }) {
      if (user) {
        token.id = user.id;
      }
      if (account) {
        token.provider = account.provider;
      }
      return token;
    },
    async session({ session, token }) {
      if (token) {
        session.user.id = token.id as string;
      }
      return session;
    },
    async signIn({ user, account, profile }) {
      // Bloquear dominios específicos
      const blockedDomains = ['spam.com', 'temp-mail.org'];
      const emailDomain = user.email?.split('@')[1];

      if (emailDomain && blockedDomains.includes(emailDomain)) {
        return false;
      }

      return true;
    },
  },
  events: {
    async signIn({ user, account, isNewUser }) {
      if (isNewUser) {
        // Enviar email de bienvenida
        await sendWelcomeEmail(user.email!);
      }

      // Logging de auditoría
      await prisma.auditLog.create({
        data: {
          userId: user.id,
          action: 'SIGN_IN',
          provider: account?.provider,
          metadata: { isNewUser },
        },
      });
    },
  },
});
```

### Route Handlers

```typescript
// app/api/auth/[...nextauth]/route.ts
import { handlers } from '@/auth';
export const { GET, POST } = handlers;
```

### Middleware Protection

```typescript
// middleware.ts
import { auth } from '@/auth';
import { NextResponse } from 'next/server';

export default auth((req) => {
  const isLoggedIn = !!req.auth;
  const isOnDashboard = req.nextUrl.pathname.startsWith('/dashboard');
  const isOnAuth = req.nextUrl.pathname.startsWith('/login');

  if (isOnDashboard && !isLoggedIn) {
    return NextResponse.redirect(new URL('/login', req.url));
  }

  if (isOnAuth && isLoggedIn) {
    return NextResponse.redirect(new URL('/dashboard', req.url));
  }

  return NextResponse.next();
});

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
};
```

### Server Components

```typescript
// app/dashboard/page.tsx
import { auth } from '@/auth';
import { redirect } from 'next/navigation';

export default async function DashboardPage() {
  const session = await auth();

  if (!session) {
    redirect('/login');
  }

  return (
    <div>
      <h1>Welcome, {session.user.name}</h1>
      <img src={session.user.image} alt="Profile" />
    </div>
  );
}
```

### Client Components

```tsx
'use client';

import { signIn, signOut, useSession } from 'next-auth/react';

export function AuthButtons() {
  const { data: session, status } = useSession();

  if (status === 'loading') {
    return <div>Loading...</div>;
  }

  if (session) {
    return (
      <div className="flex items-center gap-4">
        <span>Signed in as {session.user.email}</span>
        <button
          onClick={() => signOut({ callbackUrl: '/' })}
          className="btn btn-outline"
        >
          Sign out
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={() => signIn('google', { callbackUrl: '/dashboard' })}
        className="btn btn-primary flex items-center gap-2"
      >
        <GoogleIcon /> Continue with Google
      </button>
      <button
        onClick={() => signIn('github', { callbackUrl: '/dashboard' })}
        className="btn btn-secondary flex items-center gap-2"
      >
        <GitHubIcon /> Continue with GitHub
      </button>
    </div>
  );
}
```

---

## Account Linking

```typescript
// Vincular múltiples proveedores a una cuenta
async function linkAccount(userId: string, provider: string, code: string) {
  // Intercambiar código por tokens según el provider
  const tokens = await exchangeCode(provider, code);
  const profile = await getProfile(provider, tokens.access_token);

  // Verificar que el email coincide
  const user = await prisma.user.findUnique({ where: { id: userId } });

  if (user?.email !== profile.email) {
    throw new Error('Email mismatch. Cannot link accounts.');
  }

  // Crear account link
  await prisma.account.create({
    data: {
      userId,
      provider,
      providerAccountId: profile.id,
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
      expires_at: tokens.expires_at,
    },
  });

  return { success: true };
}

// Desvincular cuenta
async function unlinkAccount(userId: string, provider: string) {
  // Verificar que no es la única forma de login
  const accounts = await prisma.account.findMany({ where: { userId } });
  const user = await prisma.user.findUnique({ where: { id: userId } });

  const hasPassword = !!user?.password;
  const hasMultipleProviders = accounts.length > 1;

  if (!hasPassword && !hasMultipleProviders) {
    throw new Error('Cannot unlink only login method');
  }

  await prisma.account.delete({
    where: {
      provider_providerAccountId: {
        provider,
        providerAccountId: accounts.find(a => a.provider === provider)!.providerAccountId,
      },
    },
  });

  return { success: true };
}
```

---

## Security Best Practices

### State y CSRF Protection

```typescript
// Generar state seguro
function generateState(): string {
  return crypto.randomBytes(32).toString('base64url');
}

// Validar state
function validateState(state: string, storedState: string): boolean {
  return crypto.timingSafeEqual(
    Buffer.from(state),
    Buffer.from(storedState)
  );
}
```

### Token Storage

```typescript
// ❌ NO: localStorage (vulnerable a XSS)
localStorage.setItem('token', accessToken);

// ✅ SÍ: HttpOnly cookies
res.cookie('token', accessToken, {
  httpOnly: true,      // No accesible desde JS
  secure: true,        // Solo HTTPS
  sameSite: 'strict',  // Protección CSRF
  maxAge: 3600000,     // 1 hora
});

// ✅ SÍ: Para SPAs, usar BFF pattern
// El token se guarda en el backend, no en el cliente
```

### Validación de Tokens

```typescript
async function validateToken(idToken: string, provider: string) {
  switch (provider) {
    case 'google':
      const ticket = await googleClient.verifyIdToken({
        idToken,
        audience: process.env.GOOGLE_CLIENT_ID,
      });
      return ticket.getPayload();

    case 'apple':
      // Apple usa JWKS
      const jwks = await fetchAppleJWKS();
      return jwt.verify(idToken, jwks, {
        algorithms: ['RS256'],
        issuer: 'https://appleid.apple.com',
        audience: process.env.APPLE_CLIENT_ID,
      });

    default:
      throw new Error(`Unknown provider: ${provider}`);
  }
}
```

### Rate Limiting

```typescript
import rateLimit from 'express-rate-limit';

const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutos
  max: 10, // 10 intentos
  message: 'Too many login attempts, please try again later',
  standardHeaders: true,
  legacyHeaders: false,
});

app.use('/auth', authLimiter);
```

---

## Referencias

- [OAuth 2.0 RFC 6749](https://tools.ietf.org/html/rfc6749)
- [PKCE RFC 7636](https://tools.ietf.org/html/rfc7636)
- [NextAuth.js Docs](https://authjs.dev/)
- [Google OAuth](https://developers.google.com/identity/protocols/oauth2)
- [GitHub OAuth](https://docs.github.com/en/developers/apps/building-oauth-apps)
- [Apple Sign In](https://developer.apple.com/sign-in-with-apple/)

---

*Skill creada: 2026-02-01*
*Versión: 1.0.0*
