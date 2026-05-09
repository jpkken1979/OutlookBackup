---
name: shadcn-ui-components
description: "Experto completo en shadcn/ui - el estándar de facto para construir component libraries en React moderno"
type: feature

---
name: shadcn-ui-components
description: Experto en shadcn/ui - la forma moderna de construir component libraries. 70+ componentes accesibles basados en Radix UI, CVA para variantes type-safe, Tailwind CSS v4.1 para estilos, integración con React Hook Form, TanStack Table, Recharts. Usar PROACTIVAMENTE para cualquier UI en React/Next.js.
category: ui-components
displayName: shadcn/ui Component Expert
color: purple
version: 1.0
lastUpdate: 2026-02-02
---

# shadcn/ui Component Expert

Experto completo en shadcn/ui - el estándar de facto para construir component libraries en React moderno.

## Filosofía shadcn/ui

> "This is not a component library. It is how you build your component library."

### Principios Fundamentales

| Principio | Descripción |
|-----------|-------------|
| **Open Code** | Código abierto para modificación total |
| **Composition** | Interface común y componible para todos |
| **Distribution** | Schema flat-file + CLI para distribución |
| **Beautiful Defaults** | Estilos profesionales por defecto |
| **AI-Ready** | LLMs pueden leer y mejorar componentes |

## Instalación y Setup

### CLI Installation (Recomendado)

```bash
# Inicializar proyecto
npx shadcn@latest init

# Añadir componentes
npx shadcn@latest add button
npx shadcn@latest add card dialog form

# Ver componentes disponibles
npx shadcn@latest list

# Añadir todos los componentes
npx shadcn@latest add --all
```

### Frameworks Soportados

- Next.js (App Router)
- Vite
- React Router
- Remix
- Astro
- TanStack Start
- Laravel

### components.json Configuration

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "app/globals.css",
    "baseColor": "slate"
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
```

## Sistema de Theming (CSS Variables + OKLCH)

### globals.css con Tailwind v4.1

```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));

@theme {
  /* ========== COLORS - OKLCH ========== */
  --color-background: oklch(1 0 0);
  --color-foreground: oklch(0.145 0.02 250);

  --color-primary: oklch(0.205 0.02 250);
  --color-primary-foreground: oklch(0.985 0 0);

  --color-secondary: oklch(0.97 0.01 250);
  --color-secondary-foreground: oklch(0.205 0.02 250);

  --color-muted: oklch(0.97 0.01 250);
  --color-muted-foreground: oklch(0.556 0.02 250);

  --color-accent: oklch(0.97 0.01 250);
  --color-accent-foreground: oklch(0.205 0.02 250);

  --color-destructive: oklch(0.577 0.245 27);
  --color-destructive-foreground: oklch(0.985 0 0);

  --color-success: oklch(0.696 0.17 142);
  --color-warning: oklch(0.769 0.188 70);
  --color-info: oklch(0.623 0.214 255);

  --color-border: oklch(0.922 0.01 250);
  --color-ring: oklch(0.708 0.165 254);

  --color-card: oklch(1 0 0);
  --color-card-foreground: oklch(0.145 0.02 250);

  /* ========== TYPOGRAPHY ========== */
  --font-sans: 'Inter', ui-sans-serif, system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, monospace;

  /* ========== SPACING (8pt Grid) ========== */
  --spacing-0: 0;
  --spacing-1: 0.25rem;
  --spacing-2: 0.5rem;
  --spacing-3: 0.75rem;
  --spacing-4: 1rem;
  --spacing-6: 1.5rem;
  --spacing-8: 2rem;
  --spacing-12: 3rem;
  --spacing-16: 4rem;

  /* ========== BORDER RADIUS ========== */
  --radius: 0.5rem;
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);
  --radius-full: 9999px;

  /* ========== SHADOWS ========== */
  --shadow-sm: 0 1px 2px 0 oklch(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px oklch(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px oklch(0 0 0 / 0.1);
}

/* Dark Mode */
.dark {
  --color-background: oklch(0.145 0.02 250);
  --color-foreground: oklch(0.985 0 0);
  --color-primary: oklch(0.985 0 0);
  --color-primary-foreground: oklch(0.205 0.02 250);
  --color-muted: oklch(0.269 0.02 250);
  --color-muted-foreground: oklch(0.708 0.02 250);
  --color-border: oklch(0.269 0.02 250);
  --color-card: oklch(0.145 0.02 250);
  --color-card-foreground: oklch(0.985 0 0);
}
```

## Catálogo Completo de Componentes (70+)

### Layout & Structure

| Componente | Uso | Instalación |
|------------|-----|-------------|
| **Card** | Contenedor con header/content/footer | `npx shadcn add card` |
| **Separator** | Línea divisora | `npx shadcn add separator` |
| **Scroll Area** | Área con scroll custom | `npx shadcn add scroll-area` |
| **Resizable** | Paneles redimensionables | `npx shadcn add resizable` |
| **Aspect Ratio** | Mantener proporciones | `npx shadcn add aspect-ratio` |

### Navigation

| Componente | Uso | Instalación |
|------------|-----|-------------|
| **Breadcrumb** | Navegación jerárquica | `npx shadcn add breadcrumb` |
| **Menubar** | Barra de menú tipo desktop | `npx shadcn add menubar` |
| **Navigation Menu** | Menú de navegación | `npx shadcn add navigation-menu` |
| **Pagination** | Paginación de listas | `npx shadcn add pagination` |
| **Tabs** | Pestañas | `npx shadcn add tabs` |
| **Sidebar** | Navegación lateral | `npx shadcn add sidebar` |

### Forms & Input

| Componente | Uso | Instalación |
|------------|-----|-------------|
| **Button** | Botones con variantes | `npx shadcn add button` |
| **Input** | Campo de texto | `npx shadcn add input` |
| **Textarea** | Campo multilínea | `npx shadcn add textarea` |
| **Checkbox** | Casillas de verificación | `npx shadcn add checkbox` |
| **Radio Group** | Opciones exclusivas | `npx shadcn add radio-group` |
| **Select** | Dropdown nativo mejorado | `npx shadcn add select` |
| **Combobox** | Select con búsqueda | `npx shadcn add combobox` |
| **Toggle** | Botón toggle | `npx shadcn add toggle` |
| **Switch** | Interruptor on/off | `npx shadcn add switch` |
| **Slider** | Control deslizante | `npx shadcn add slider` |
| **Input OTP** | Código de verificación | `npx shadcn add input-otp` |
| **Form** | Integración React Hook Form | `npx shadcn add form` |
| **Label** | Etiquetas de formulario | `npx shadcn add label` |
| **Calendar** | Selector de fecha | `npx shadcn add calendar` |
| **Date Picker** | Input con calendario | `npx shadcn add date-picker` |

### Dialogs & Overlays

| Componente | Uso | Instalación |
|------------|-----|-------------|
| **Dialog** | Modal centrado | `npx shadcn add dialog` |
| **Alert Dialog** | Confirmación crítica | `npx shadcn add alert-dialog` |
| **Sheet** | Panel lateral deslizante | `npx shadcn add sheet` |
| **Drawer** | Panel desde bottom | `npx shadcn add drawer` |
| **Dropdown Menu** | Menú contextual | `npx shadcn add dropdown-menu` |
| **Context Menu** | Click derecho | `npx shadcn add context-menu` |
| **Popover** | Popup pequeño | `npx shadcn add popover` |
| **Hover Card** | Preview al hover | `npx shadcn add hover-card` |
| **Tooltip** | Texto de ayuda | `npx shadcn add tooltip` |
| **Command** | Paleta de comandos (⌘K) | `npx shadcn add command` |

### Feedback & Status

| Componente | Uso | Instalación |
|------------|-----|-------------|
| **Alert** | Mensajes informativos | `npx shadcn add alert` |
| **Badge** | Etiquetas/chips | `npx shadcn add badge` |
| **Progress** | Barra de progreso | `npx shadcn add progress` |
| **Skeleton** | Placeholder de carga | `npx shadcn add skeleton` |
| **Toast** | Notificaciones | `npx shadcn add toast` |
| **Sonner** | Toasts mejorados | `npx shadcn add sonner` |

### Data Display

| Componente | Uso | Instalación |
|------------|-----|-------------|
| **Table** | Tabla básica | `npx shadcn add table` |
| **Data Table** | Tabla con TanStack | `npx shadcn add table` + TanStack |
| **Avatar** | Imagen de usuario | `npx shadcn add avatar` |
| **Carousel** | Galería deslizante | `npx shadcn add carousel` |
| **Collapsible** | Contenido expandible | `npx shadcn add collapsible` |
| **Accordion** | Secciones colapsables | `npx shadcn add accordion` |
| **Chart** | Gráficos con Recharts | `npx shadcn add chart` |

---

## Patrones de Componentes Esenciales

### 1. Button con CVA (Class Variance Authority)

```typescript
// components/ui/button.tsx
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "@radix-ui/react-slot"
import { forwardRef } from "react"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline: "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
```

#### Uso del Button

```tsx
import { Button } from "@/components/ui/button"
import { Mail, Loader2 } from "lucide-react"

// Variantes
<Button>Default</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="destructive">Destructive</Button>
<Button variant="outline">Outline</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="link">Link</Button>

// Tamaños
<Button size="sm">Small</Button>
<Button size="lg">Large</Button>
<Button size="icon"><Mail /></Button>

// Con icono
<Button>
  <Mail data-icon="inline-start" />
  Login with Email
</Button>

// Loading state
<Button disabled>
  <Loader2 className="animate-spin" data-icon="inline-start" />
  Please wait
</Button>

// Como link (asChild)
<Button asChild>
  <a href="/login">Login</a>
</Button>
```

### 2. Card Component

```tsx
// components/ui/card.tsx
import { cn } from "@/lib/utils"
import { forwardRef } from "react"

const Card = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-xl border bg-card text-card-foreground shadow",
        className
      )}
      {...props}
    />
  )
)

const CardHeader = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("flex flex-col space-y-1.5 p-6", className)}
      {...props}
    />
  )
)

const CardTitle = forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3
      ref={ref}
      className={cn("font-semibold leading-none tracking-tight", className)}
      {...props}
    />
  )
)

const CardDescription = forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p
      ref={ref}
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  )
)

const CardContent = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
  )
)

const CardFooter = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("flex items-center p-6 pt-0", className)}
      {...props}
    />
  )
)

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
```

#### Uso del Card

```tsx
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

// Card de Login
export function LoginCard() {
  return (
    <Card className="w-[350px]">
      <CardHeader>
        <CardTitle>Login</CardTitle>
        <CardDescription>
          Enter your email below to login to your account
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" placeholder="m@example.com" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" />
          </div>
        </form>
      </CardContent>
      <CardFooter className="flex-col gap-2">
        <Button className="w-full">Sign in</Button>
        <Button variant="outline" className="w-full">
          Sign in with Google
        </Button>
      </CardFooter>
    </Card>
  )
}
```

### 3. Dialog Component

```tsx
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export function EditProfileDialog() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline">Edit Profile</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Edit profile</DialogTitle>
          <DialogDescription>
            Make changes to your profile here. Click save when you're done.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="name" className="text-right">Name</Label>
            <Input id="name" defaultValue="Pedro Duarte" className="col-span-3" />
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="username" className="text-right">Username</Label>
            <Input id="username" defaultValue="@peduarte" className="col-span-3" />
          </div>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Cancel</Button>
          </DialogClose>
          <Button type="submit">Save changes</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

### 4. Form con React Hook Form + Zod

```tsx
"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import * as z from "zod"
import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"

// Schema de validación
const formSchema = z.object({
  username: z.string().min(2, {
    message: "Username must be at least 2 characters.",
  }),
  email: z.string().email({
    message: "Please enter a valid email address.",
  }),
})

export function ProfileForm() {
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      username: "",
      email: "",
    },
  })

  function onSubmit(values: z.infer<typeof formSchema>) {
    console.log(values)
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
        <FormField
          control={form.control}
          name="username"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Username</FormLabel>
              <FormControl>
                <Input placeholder="shadcn" {...field} />
              </FormControl>
              <FormDescription>
                This is your public display name.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input placeholder="email@example.com" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit">Submit</Button>
      </form>
    </Form>
  )
}
```

### 5. Data Table con TanStack Table

```tsx
// types/payment.ts
export type Payment = {
  id: string
  amount: number
  status: "pending" | "processing" | "success" | "failed"
  email: string
}

// columns.tsx
"use client"

import { ColumnDef } from "@tanstack/react-table"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import { ArrowUpDown, MoreHorizontal } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

export const columns: ColumnDef<Payment>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <Checkbox
        checked={table.getIsAllPageRowsSelected()}
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Select all"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Select row"
      />
    ),
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const status = row.getValue("status") as string
      return (
        <Badge variant={status === "success" ? "default" : "secondary"}>
          {status}
        </Badge>
      )
    },
  },
  {
    accessorKey: "email",
    header: ({ column }) => (
      <Button
        variant="ghost"
        onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
      >
        Email
        <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
  },
  {
    accessorKey: "amount",
    header: () => <div className="text-right">Amount</div>,
    cell: ({ row }) => {
      const amount = parseFloat(row.getValue("amount"))
      const formatted = new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
      }).format(amount)
      return <div className="text-right font-medium">{formatted}</div>
    },
  },
  {
    id: "actions",
    cell: ({ row }) => {
      const payment = row.original
      return (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="h-8 w-8 p-0">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            <DropdownMenuItem
              onClick={() => navigator.clipboard.writeText(payment.id)}
            >
              Copy payment ID
            </DropdownMenuItem>
            <DropdownMenuItem>View details</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )
    },
  },
]

// data-table.tsx
"use client"

import {
  ColumnDef,
  ColumnFiltersState,
  SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { useState } from "react"

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
}

export function DataTable<TData, TValue>({
  columns,
  data,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [rowSelection, setRowSelection] = useState({})

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onRowSelectionChange: setRowSelection,
    state: { sorting, columnFilters, rowSelection },
  })

  return (
    <div>
      <div className="flex items-center py-4">
        <Input
          placeholder="Filter emails..."
          value={(table.getColumn("email")?.getFilterValue() as string) ?? ""}
          onChange={(event) =>
            table.getColumn("email")?.setFilterValue(event.target.value)
          }
          className="max-w-sm"
        />
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-end space-x-2 py-4">
        <div className="flex-1 text-sm text-muted-foreground">
          {table.getFilteredSelectedRowModel().rows.length} of{" "}
          {table.getFilteredRowModel().rows.length} row(s) selected.
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => table.previousPage()}
          disabled={!table.getCanPreviousPage()}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => table.nextPage()}
          disabled={!table.getCanNextPage()}
        >
          Next
        </Button>
      </div>
    </div>
  )
}
```

### 6. Charts con Recharts

```tsx
"use client"

import {
  Bar,
  BarChart,
  Line,
  LineChart,
  Area,
  AreaChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
} from "@/components/ui/chart"

const chartData = [
  { month: "Jan", desktop: 186, mobile: 80 },
  { month: "Feb", desktop: 305, mobile: 200 },
  { month: "Mar", desktop: 237, mobile: 120 },
  { month: "Apr", desktop: 73, mobile: 190 },
  { month: "May", desktop: 209, mobile: 130 },
  { month: "Jun", desktop: 214, mobile: 140 },
]

const chartConfig = {
  desktop: {
    label: "Desktop",
    color: "var(--color-primary)",
  },
  mobile: {
    label: "Mobile",
    color: "var(--color-info)",
  },
}

// Bar Chart
export function BarChartDemo() {
  return (
    <ChartContainer config={chartConfig} className="min-h-[300px] w-full">
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="month" />
        <YAxis />
        <ChartTooltip content={<ChartTooltipContent />} />
        <ChartLegend content={<ChartLegendContent />} />
        <Bar dataKey="desktop" fill="var(--color-desktop)" radius={4} />
        <Bar dataKey="mobile" fill="var(--color-mobile)" radius={4} />
      </BarChart>
    </ChartContainer>
  )
}

// Line Chart
export function LineChartDemo() {
  return (
    <ChartContainer config={chartConfig} className="min-h-[300px] w-full">
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="month" />
        <YAxis />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Line
          type="monotone"
          dataKey="desktop"
          stroke="var(--color-desktop)"
          strokeWidth={2}
        />
        <Line
          type="monotone"
          dataKey="mobile"
          stroke="var(--color-mobile)"
          strokeWidth={2}
        />
      </LineChart>
    </ChartContainer>
  )
}

// Area Chart
export function AreaChartDemo() {
  return (
    <ChartContainer config={chartConfig} className="min-h-[300px] w-full">
      <AreaChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="month" />
        <YAxis />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Area
          type="monotone"
          dataKey="desktop"
          fill="var(--color-desktop)"
          fillOpacity={0.4}
          stroke="var(--color-desktop)"
        />
        <Area
          type="monotone"
          dataKey="mobile"
          fill="var(--color-mobile)"
          fillOpacity={0.4}
          stroke="var(--color-mobile)"
        />
      </AreaChart>
    </ChartContainer>
  )
}
```

---

## Bloques Pre-construidos

### Dashboard Blocks

```bash
npx shadcn add dashboard-01  # Dashboard con sidebar, charts, data table
npx shadcn add sidebar-07    # Sidebar que colapsa a iconos
npx shadcn add sidebar-03    # Sidebar con submenús
```

### Authentication Blocks

```bash
npx shadcn add login-03      # Login con fondo muted
npx shadcn add login-04      # Login con imagen lateral
```

---

## CLI Commands Reference

| Comando | Descripción |
|---------|-------------|
| `npx shadcn init` | Inicializar proyecto |
| `npx shadcn add [component]` | Añadir componente |
| `npx shadcn add --all` | Añadir todos los componentes |
| `npx shadcn diff [component]` | Ver cambios en componente |
| `npx shadcn list` | Listar componentes instalados |

---

## Dependencias Clave

| Paquete | Propósito |
|---------|-----------|
| `@radix-ui/*` | Primitivas accesibles |
| `class-variance-authority` | Variantes de componentes |
| `clsx` | Concatenación de clases |
| `tailwind-merge` | Merge de clases Tailwind |
| `lucide-react` | Iconos |
| `@tanstack/react-table` | Data tables |
| `recharts` | Gráficos |
| `react-hook-form` | Formularios |
| `zod` | Validación |

---

## Utilidades

### cn() - Class Name Utility

```typescript
// lib/utils.ts
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

### Uso de cn()

```tsx
// Combinar clases condicionalmente
<button
  className={cn(
    "px-4 py-2 rounded",
    isActive && "bg-primary text-primary-foreground",
    disabled && "opacity-50 cursor-not-allowed"
  )}
>
  Click me
</button>
```

---

## Accesibilidad

Todos los componentes están construidos sobre **Radix UI Primitives**, garantizando:

- ✅ Navegación por teclado
- ✅ Roles ARIA correctos
- ✅ Focus management
- ✅ Screen reader support
- ✅ Reduced motion respect

---

## Resources

- [shadcn/ui Documentation](https://ui.shadcn.com/docs)
- [Component Gallery](https://ui.shadcn.com/docs/components)
- [Blocks Library](https://ui.shadcn.com/blocks)
- [Charts Library](https://ui.shadcn.com/charts)
- [Radix UI Primitives](https://www.radix-ui.com/primitives)
- [CVA Documentation](https://cva.style/docs)
