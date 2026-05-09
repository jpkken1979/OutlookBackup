---
name: ui-blocks-layouts
type: feature
description: "Colección completa de bloques y layouts pre-construidos para acelerar el desarrollo de interfaces modernas"
---

---
name: ui-blocks-layouts
description: Bloques y layouts pre-construidos para dashboards, autenticación, landing pages, sidebars, headers, footers. Patrones de diseño reutilizables con shadcn/ui, Tailwind CSS v4.1 y Next.js 16. Usar para acelerar desarrollo de interfaces completas.
category: ui-components
displayName: UI Blocks & Layouts
color: indigo
version: 1.0
lastUpdate: 2026-02-02
---

# UI Blocks & Layouts

Colección completa de bloques y layouts pre-construidos para acelerar el desarrollo de interfaces modernas.

## Bloques Disponibles en shadcn/ui

### Dashboard Blocks

```bash
# Dashboard completo con sidebar, charts y data table
npx shadcn add dashboard-01

# Variantes de sidebar
npx shadcn add sidebar-01  # Sidebar básico
npx shadcn add sidebar-03  # Sidebar con submenús
npx shadcn add sidebar-07  # Sidebar colapsable a iconos
```

### Authentication Blocks

```bash
# Login pages
npx shadcn add login-01    # Login simple
npx shadcn add login-03    # Login con fondo muted
npx shadcn add login-04    # Login con imagen lateral
```

---

## Layouts Fundamentales

### 1. Dashboard Layout con Sidebar

```tsx
// app/(dashboard)/layout.tsx
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { AppSidebar } from "@/components/app-sidebar"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full">
        <AppSidebar />
        <main className="flex-1 flex flex-col">
          <header className="sticky top-0 z-10 flex h-14 items-center gap-4 border-b bg-background px-4">
            <SidebarTrigger />
            <div className="flex-1" />
            {/* Header content */}
          </header>
          <div className="flex-1 p-4 md:p-6">
            {children}
          </div>
        </main>
      </div>
    </SidebarProvider>
  )
}
```

### App Sidebar Component

```tsx
// components/app-sidebar.tsx
"use client"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import {
  LayoutDashboard,
  Users,
  Settings,
  BarChart3,
  FileText,
  LogOut,
} from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"

const menuItems = [
  { title: "Dashboard", icon: LayoutDashboard, href: "/dashboard" },
  { title: "Users", icon: Users, href: "/dashboard/users" },
  { title: "Analytics", icon: BarChart3, href: "/dashboard/analytics" },
  { title: "Reports", icon: FileText, href: "/dashboard/reports" },
  { title: "Settings", icon: Settings, href: "/dashboard/settings" },
]

export function AppSidebar() {
  const pathname = usePathname()

  return (
    <Sidebar>
      <SidebarHeader className="border-b px-6 py-4">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <span className="text-xl">🚀</span>
          <span>My App</span>
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {menuItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    asChild
                    isActive={pathname === item.href}
                  >
                    <Link href={item.href}>
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t p-4">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton>
              <LogOut className="h-4 w-4" />
              <span>Logout</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
```

### 2. Authentication Layout

```tsx
// app/(auth)/layout.tsx
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen flex">
      {/* Left side - Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {children}
        </div>
      </div>

      {/* Right side - Image/Branding (hidden on mobile) */}
      <div className="hidden lg:flex lg:flex-1 bg-muted items-center justify-center p-8">
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold">Welcome back</h1>
          <p className="text-muted-foreground">
            Sign in to continue to your dashboard
          </p>
        </div>
      </div>
    </div>
  )
}
```

### Login Page

```tsx
// app/(auth)/login/page.tsx
import { LoginForm } from "@/components/auth/login-form"

export default function LoginPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-bold">Login</h1>
        <p className="text-muted-foreground">
          Enter your credentials to access your account
        </p>
      </div>
      <LoginForm />
    </div>
  )
}
```

### Login Form Component

```tsx
// components/auth/login-form.tsx
"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import * as z from "zod"
import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import Link from "next/link"

const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
})

export function LoginForm() {
  const form = useForm<z.infer<typeof loginSchema>>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  })

  async function onSubmit(values: z.infer<typeof loginSchema>) {
    console.log(values)
    // Handle login
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input placeholder="email@example.com" type="email" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="password"
          render={({ field }) => (
            <FormItem>
              <div className="flex items-center justify-between">
                <FormLabel>Password</FormLabel>
                <Link
                  href="/forgot-password"
                  className="text-sm text-muted-foreground hover:text-primary"
                >
                  Forgot password?
                </Link>
              </div>
              <FormControl>
                <Input type="password" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" className="w-full">
          Sign in
        </Button>
      </form>

      <div className="relative my-6">
        <Separator />
        <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-background px-2 text-xs text-muted-foreground">
          OR CONTINUE WITH
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Button variant="outline">Google</Button>
        <Button variant="outline">GitHub</Button>
      </div>

      <p className="text-center text-sm text-muted-foreground">
        Don't have an account?{" "}
        <Link href="/register" className="text-primary hover:underline">
          Sign up
        </Link>
      </p>
    </Form>
  )
}
```

### 3. Landing Page Layout

```tsx
// app/(marketing)/layout.tsx
import { Header } from "@/components/marketing/header"
import { Footer } from "@/components/marketing/footer"

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  )
}
```

### Header Component

```tsx
// components/marketing/header.tsx
import Link from "next/link"
import { Button } from "@/components/ui/button"
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
} from "@/components/ui/navigation-menu"

const navItems = [
  {
    title: "Features",
    href: "/features",
    items: [
      { title: "Analytics", href: "/features/analytics", description: "Track your metrics" },
      { title: "Automation", href: "/features/automation", description: "Automate workflows" },
      { title: "Security", href: "/features/security", description: "Enterprise security" },
    ],
  },
  { title: "Pricing", href: "/pricing" },
  { title: "Blog", href: "/blog" },
  { title: "Docs", href: "/docs" },
]

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2 font-bold text-xl">
            <span>🚀</span>
            <span>MyApp</span>
          </Link>

          <NavigationMenu className="hidden md:flex">
            <NavigationMenuList>
              {navItems.map((item) => (
                <NavigationMenuItem key={item.title}>
                  {item.items ? (
                    <>
                      <NavigationMenuTrigger>{item.title}</NavigationMenuTrigger>
                      <NavigationMenuContent>
                        <ul className="grid w-[400px] gap-3 p-4 md:w-[500px] md:grid-cols-2">
                          {item.items.map((subItem) => (
                            <li key={subItem.href}>
                              <NavigationMenuLink asChild>
                                <Link
                                  href={subItem.href}
                                  className="block select-none space-y-1 rounded-md p-3 leading-none no-underline outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground"
                                >
                                  <div className="text-sm font-medium leading-none">
                                    {subItem.title}
                                  </div>
                                  <p className="line-clamp-2 text-sm leading-snug text-muted-foreground">
                                    {subItem.description}
                                  </p>
                                </Link>
                              </NavigationMenuLink>
                            </li>
                          ))}
                        </ul>
                      </NavigationMenuContent>
                    </>
                  ) : (
                    <NavigationMenuLink asChild>
                      <Link
                        href={item.href}
                        className="group inline-flex h-10 w-max items-center justify-center rounded-md bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground focus:outline-none"
                      >
                        {item.title}
                      </Link>
                    </NavigationMenuLink>
                  )}
                </NavigationMenuItem>
              ))}
            </NavigationMenuList>
          </NavigationMenu>
        </div>

        <div className="flex items-center gap-4">
          <Button variant="ghost" asChild>
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild>
            <Link href="/register">Get Started</Link>
          </Button>
        </div>
      </div>
    </header>
  )
}
```

### Hero Section

```tsx
// components/marketing/hero.tsx
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import Link from "next/link"
import { ArrowRight, Play } from "lucide-react"

export function Hero() {
  return (
    <section className="relative overflow-hidden py-24 md:py-32">
      {/* Background gradient */}
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(45%_40%_at_50%_60%,var(--color-primary)/0.1,transparent)]" />

      <div className="container">
        <div className="mx-auto max-w-3xl text-center">
          <Badge variant="secondary" className="mb-4">
            🎉 Announcing our Series A
          </Badge>

          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl lg:text-7xl">
            Build faster with{" "}
            <span className="text-primary">modern components</span>
          </h1>

          <p className="mt-6 text-lg text-muted-foreground md:text-xl">
            Beautiful, accessible components built with Radix UI and Tailwind CSS.
            Copy and paste into your apps. Open source.
          </p>

          <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:justify-center">
            <Button size="lg" asChild>
              <Link href="/register">
                Get Started
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="/demo">
                <Play className="mr-2 h-4 w-4" />
                Watch Demo
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </section>
  )
}
```

### Features Grid

```tsx
// components/marketing/features.tsx
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Zap, Shield, BarChart, Users, Code, Globe } from "lucide-react"

const features = [
  {
    icon: Zap,
    title: "Lightning Fast",
    description: "Optimized for performance with code splitting and lazy loading.",
  },
  {
    icon: Shield,
    title: "Secure by Default",
    description: "Enterprise-grade security with SOC 2 compliance.",
  },
  {
    icon: BarChart,
    title: "Analytics",
    description: "Track your metrics with real-time dashboards and reports.",
  },
  {
    icon: Users,
    title: "Team Collaboration",
    description: "Work together with your team in real-time.",
  },
  {
    icon: Code,
    title: "Developer Friendly",
    description: "Built with TypeScript and modern development practices.",
  },
  {
    icon: Globe,
    title: "Global Scale",
    description: "Deploy globally with edge computing and CDN.",
  },
]

export function Features() {
  return (
    <section className="py-24">
      <div className="container">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Everything you need
          </h2>
          <p className="mt-4 text-muted-foreground">
            All the features you need to build modern applications.
          </p>
        </div>

        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <Card key={feature.title}>
              <CardHeader>
                <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                  <feature.icon className="h-6 w-6 text-primary" />
                </div>
                <CardTitle>{feature.title}</CardTitle>
                <CardDescription>{feature.description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
```

### Pricing Section

```tsx
// components/marketing/pricing.tsx
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Check } from "lucide-react"

const plans = [
  {
    name: "Starter",
    description: "Perfect for side projects",
    price: "$0",
    period: "forever",
    features: [
      "Up to 3 projects",
      "Basic analytics",
      "Community support",
      "1GB storage",
    ],
    cta: "Get Started",
    variant: "outline" as const,
  },
  {
    name: "Pro",
    description: "For growing teams",
    price: "$29",
    period: "per month",
    popular: true,
    features: [
      "Unlimited projects",
      "Advanced analytics",
      "Priority support",
      "100GB storage",
      "Custom domains",
      "Team collaboration",
    ],
    cta: "Start Free Trial",
    variant: "default" as const,
  },
  {
    name: "Enterprise",
    description: "For large organizations",
    price: "Custom",
    period: "",
    features: [
      "Everything in Pro",
      "Unlimited storage",
      "24/7 phone support",
      "Custom integrations",
      "SLA guarantee",
      "Dedicated account manager",
    ],
    cta: "Contact Sales",
    variant: "outline" as const,
  },
]

export function Pricing() {
  return (
    <section className="py-24 bg-muted/50">
      <div className="container">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Simple, transparent pricing
          </h2>
          <p className="mt-4 text-muted-foreground">
            Choose the plan that works best for your team.
          </p>
        </div>

        <div className="mt-16 grid gap-8 lg:grid-cols-3">
          {plans.map((plan) => (
            <Card
              key={plan.name}
              className={plan.popular ? "border-primary shadow-lg" : ""}
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{plan.name}</CardTitle>
                  {plan.popular && <Badge>Popular</Badge>}
                </div>
                <CardDescription>{plan.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <span className="text-4xl font-bold">{plan.price}</span>
                  {plan.period && (
                    <span className="text-muted-foreground"> /{plan.period}</span>
                  )}
                </div>
                <ul className="space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-primary" />
                      <span className="text-sm">{feature}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
              <CardFooter>
                <Button variant={plan.variant} className="w-full">
                  {plan.cta}
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
```

### Footer Component

```tsx
// components/marketing/footer.tsx
import Link from "next/link"
import { Separator } from "@/components/ui/separator"

const footerLinks = {
  Product: [
    { title: "Features", href: "/features" },
    { title: "Pricing", href: "/pricing" },
    { title: "Changelog", href: "/changelog" },
    { title: "Roadmap", href: "/roadmap" },
  ],
  Company: [
    { title: "About", href: "/about" },
    { title: "Blog", href: "/blog" },
    { title: "Careers", href: "/careers" },
    { title: "Contact", href: "/contact" },
  ],
  Resources: [
    { title: "Documentation", href: "/docs" },
    { title: "Help Center", href: "/help" },
    { title: "Community", href: "/community" },
    { title: "Status", href: "/status" },
  ],
  Legal: [
    { title: "Privacy", href: "/privacy" },
    { title: "Terms", href: "/terms" },
    { title: "Cookies", href: "/cookies" },
  ],
}

export function Footer() {
  return (
    <footer className="border-t bg-muted/50">
      <div className="container py-12 md:py-16">
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-5">
          {/* Brand */}
          <div className="lg:col-span-1">
            <Link href="/" className="flex items-center gap-2 font-bold text-xl">
              <span>🚀</span>
              <span>MyApp</span>
            </Link>
            <p className="mt-4 text-sm text-muted-foreground">
              Building the future of modern web applications.
            </p>
          </div>

          {/* Links */}
          {Object.entries(footerLinks).map(([category, links]) => (
            <div key={category}>
              <h3 className="font-semibold">{category}</h3>
              <ul className="mt-4 space-y-2">
                {links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-muted-foreground hover:text-foreground"
                    >
                      {link.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <Separator className="my-8" />

        <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} MyApp. All rights reserved.
          </p>
          <div className="flex gap-4">
            <Link href="#" className="text-muted-foreground hover:text-foreground">
              Twitter
            </Link>
            <Link href="#" className="text-muted-foreground hover:text-foreground">
              GitHub
            </Link>
            <Link href="#" className="text-muted-foreground hover:text-foreground">
              Discord
            </Link>
          </div>
        </div>
      </div>
    </footer>
  )
}
```

---

## 4. Settings Page Layout

```tsx
// app/(dashboard)/settings/layout.tsx
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import Link from "next/link"

const settingsTabs = [
  { title: "Profile", href: "/settings" },
  { title: "Account", href: "/settings/account" },
  { title: "Appearance", href: "/settings/appearance" },
  { title: "Notifications", href: "/settings/notifications" },
  { title: "Security", href: "/settings/security" },
]

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account settings and preferences.
        </p>
      </div>

      <div className="flex flex-col space-y-8 lg:flex-row lg:space-x-12 lg:space-y-0">
        <aside className="lg:w-1/5">
          <nav className="flex space-x-2 lg:flex-col lg:space-x-0 lg:space-y-1">
            {settingsTabs.map((tab) => (
              <Link
                key={tab.href}
                href={tab.href}
                className="rounded-md px-3 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
              >
                {tab.title}
              </Link>
            ))}
          </nav>
        </aside>
        <div className="flex-1 lg:max-w-2xl">{children}</div>
      </div>
    </div>
  )
}
```

---

## 5. Empty States

```tsx
// components/empty-states.tsx
import { Button } from "@/components/ui/button"
import { FileX, Search, Users, FolderOpen } from "lucide-react"

interface EmptyStateProps {
  icon?: React.ComponentType<{ className?: string }>
  title: string
  description: string
  action?: {
    label: string
    onClick: () => void
  }
}

export function EmptyState({
  icon: Icon = FileX,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="rounded-full bg-muted p-4">
        <Icon className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="mt-4 text-lg font-semibold">{title}</h3>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
        {description}
      </p>
      {action && (
        <Button onClick={action.onClick} className="mt-4">
          {action.label}
        </Button>
      )}
    </div>
  )
}

// Pre-built empty states
export const NoResults = () => (
  <EmptyState
    icon={Search}
    title="No results found"
    description="Try adjusting your search or filters to find what you're looking for."
  />
)

export const NoUsers = () => (
  <EmptyState
    icon={Users}
    title="No users yet"
    description="Get started by inviting your first team member."
    action={{ label: "Invite User", onClick: () => {} }}
  />
)

export const NoProjects = () => (
  <EmptyState
    icon={FolderOpen}
    title="No projects"
    description="Create your first project to get started."
    action={{ label: "Create Project", onClick: () => {} }}
  />
)
```

---

## Patrones Responsive

### Container Queries (Tailwind v4.1)

```tsx
// Componente que responde al contenedor, no al viewport
<div className="@container">
  <div className="flex flex-col @md:flex-row gap-4">
    <div className="@md:w-1/3">Sidebar</div>
    <div className="@md:w-2/3">Content</div>
  </div>
</div>
```

### Mobile-First Grid

```tsx
// Grid responsive
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
  {items.map(item => (
    <Card key={item.id}>{item.content}</Card>
  ))}
</div>
```

---

## Resources

- [shadcn/ui Blocks](https://ui.shadcn.com/blocks)
- [Tailwind CSS v4 Container Queries](https://tailwindcss.com/docs/container-queries)
- [Next.js App Router Layouts](https://nextjs.org/docs/app/building-your-application/routing/layouts-and-templates)
