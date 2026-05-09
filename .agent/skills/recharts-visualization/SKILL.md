---
name: recharts-visualization
description: "Experto completo en visualización de datos con Recharts integrado en shadcn/ui"
type: feature
---

---
name: recharts-visualization
description: Experto en visualización de datos con Recharts y shadcn/ui Chart components. Bar charts, line charts, area charts, pie charts, radar charts, radial charts. Theming con CSS variables, tooltips personalizados, leyendas, responsive containers. Dashboards y analytics.
type: feature
category: data-visualization
displayName: Recharts & Data Visualization
color: emerald
version: 1.0
lastUpdate: 2026-02-02
---

# Recharts & Data Visualization

Experto completo en visualización de datos con Recharts integrado en shadcn/ui.

## Instalación

```bash
# Añadir chart component de shadcn/ui
npx shadcn add chart

# O instalar manualmente
npm install recharts
```

## Arquitectura de Charts

### Chart Container

```tsx
// components/ui/chart.tsx incluye:
// - ChartContainer: Wrapper con config y responsive
// - ChartTooltip: Tooltip personalizable
// - ChartTooltipContent: Contenido del tooltip
// - ChartLegend: Leyenda
// - ChartLegendContent: Contenido de leyenda
```

### Chart Config Pattern

```typescript
// Configuración centralizada de colores y labels
const chartConfig = {
  desktop: {
    label: "Desktop",
    color: "var(--color-primary)",
    // O color directo: color: "#2563eb"
  },
  mobile: {
    label: "Mobile",
    color: "var(--color-info)",
  },
  tablet: {
    label: "Tablet",
    color: "var(--color-warning)",
  },
} satisfies ChartConfig

// Esto genera automáticamente:
// --color-desktop: var(--color-primary)
// --color-mobile: var(--color-info)
// --color-tablet: var(--color-warning)
```

### CSS Variables para Theming

```css
/* globals.css */
@layer base {
  :root {
    --chart-1: oklch(0.646 0.222 41.116);
    --chart-2: oklch(0.6 0.118 184.704);
    --chart-3: oklch(0.398 0.07 227.392);
    --chart-4: oklch(0.828 0.189 84.429);
    --chart-5: oklch(0.769 0.188 70.08);
  }
  .dark {
    --chart-1: oklch(0.488 0.243 264.376);
    --chart-2: oklch(0.696 0.17 142.495);
    --chart-3: oklch(0.769 0.188 70.08);
    --chart-4: oklch(0.627 0.265 303.9);
    --chart-5: oklch(0.645 0.246 16.439);
  }
}
```

---

## Tipos de Gráficos

### 1. Bar Chart

```tsx
"use client"

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
  type ChartConfig,
} from "@/components/ui/chart"

const chartData = [
  { month: "January", desktop: 186, mobile: 80 },
  { month: "February", desktop: 305, mobile: 200 },
  { month: "March", desktop: 237, mobile: 120 },
  { month: "April", desktop: 73, mobile: 190 },
  { month: "May", desktop: 209, mobile: 130 },
  { month: "June", desktop: 214, mobile: 140 },
]

const chartConfig = {
  desktop: {
    label: "Desktop",
    color: "var(--chart-1)",
  },
  mobile: {
    label: "Mobile",
    color: "var(--chart-2)",
  },
} satisfies ChartConfig

export function BarChartDemo() {
  return (
    <ChartContainer config={chartConfig} className="min-h-[300px] w-full">
      <BarChart data={chartData} accessibilityLayer>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="month"
          tickLine={false}
          tickMargin={10}
          axisLine={false}
          tickFormatter={(value) => value.slice(0, 3)}
        />
        <YAxis tickLine={false} axisLine={false} tickMargin={10} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <ChartLegend content={<ChartLegendContent />} />
        <Bar dataKey="desktop" fill="var(--color-desktop)" radius={4} />
        <Bar dataKey="mobile" fill="var(--color-mobile)" radius={4} />
      </BarChart>
    </ChartContainer>
  )
}
```

### Bar Chart Horizontal

```tsx
export function HorizontalBarChart() {
  return (
    <ChartContainer config={chartConfig} className="min-h-[300px] w-full">
      <BarChart data={chartData} layout="vertical" accessibilityLayer>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tickLine={false} axisLine={false} />
        <YAxis
          dataKey="month"
          type="category"
          tickLine={false}
          axisLine={false}
          tickFormatter={(value) => value.slice(0, 3)}
        />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Bar dataKey="desktop" fill="var(--color-desktop)" radius={4} />
      </BarChart>
    </ChartContainer>
  )
}
```

### Stacked Bar Chart

```tsx
export function StackedBarChart() {
  return (
    <ChartContainer config={chartConfig} className="min-h-[300px] w-full">
      <BarChart data={chartData} accessibilityLayer>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="month" tickLine={false} axisLine={false} />
        <YAxis tickLine={false} axisLine={false} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <ChartLegend content={<ChartLegendContent />} />
        <Bar
          dataKey="desktop"
          stackId="a"
          fill="var(--color-desktop)"
          radius={[0, 0, 4, 4]}
        />
        <Bar
          dataKey="mobile"
          stackId="a"
          fill="var(--color-mobile)"
          radius={[4, 4, 0, 0]}
        />
      </BarChart>
    </ChartContainer>
  )
}
```

### 2. Line Chart

```tsx
import { Line, LineChart, CartesianGrid, XAxis, YAxis } from "recharts"

export function LineChartDemo() {
  return (
    <ChartContainer config={chartConfig} className="min-h-[300px] w-full">
      <LineChart data={chartData} accessibilityLayer>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="month"
          tickLine={false}
          axisLine={false}
          tickFormatter={(value) => value.slice(0, 3)}
        />
        <YAxis tickLine={false} axisLine={false} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <ChartLegend content={<ChartLegendContent />} />
        <Line
          type="monotone"
          dataKey="desktop"
          stroke="var(--color-desktop)"
          strokeWidth={2}
          dot={{ fill: "var(--color-desktop)" }}
          activeDot={{ r: 6 }}
        />
        <Line
          type="monotone"
          dataKey="mobile"
          stroke="var(--color-mobile)"
          strokeWidth={2}
          dot={{ fill: "var(--color-mobile)" }}
        />
      </LineChart>
    </ChartContainer>
  )
}
```

### Line Chart con Dots Custom

```tsx
export function LineChartWithDots() {
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
          dot={({ cx, cy, payload }) => {
            // Custom dot rendering
            return (
              <circle
                key={payload.month}
                cx={cx}
                cy={cy}
                r={4}
                fill="var(--color-desktop)"
                stroke="white"
                strokeWidth={2}
              />
            )
          }}
        />
      </LineChart>
    </ChartContainer>
  )
}
```

### 3. Area Chart

```tsx
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts"

export function AreaChartDemo() {
  return (
    <ChartContainer config={chartConfig} className="min-h-[300px] w-full">
      <AreaChart data={chartData} accessibilityLayer>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="month" tickLine={false} axisLine={false} />
        <YAxis tickLine={false} axisLine={false} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Area
          type="monotone"
          dataKey="desktop"
          stroke="var(--color-desktop)"
          fill="var(--color-desktop)"
          fillOpacity={0.4}
          stackId="1"
        />
        <Area
          type="monotone"
          dataKey="mobile"
          stroke="var(--color-mobile)"
          fill="var(--color-mobile)"
          fillOpacity={0.4}
          stackId="1"
        />
      </AreaChart>
    </ChartContainer>
  )
}
```

### Area Chart con Gradiente

```tsx
export function AreaChartGradient() {
  return (
    <ChartContainer config={chartConfig} className="min-h-[300px] w-full">
      <AreaChart data={chartData}>
        <defs>
          <linearGradient id="colorDesktop" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--color-desktop)" stopOpacity={0.8} />
            <stop offset="95%" stopColor="var(--color-desktop)" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="colorMobile" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--color-mobile)" stopOpacity={0.8} />
            <stop offset="95%" stopColor="var(--color-mobile)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="month" />
        <YAxis />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Area
          type="monotone"
          dataKey="desktop"
          stroke="var(--color-desktop)"
          fill="url(#colorDesktop)"
        />
        <Area
          type="monotone"
          dataKey="mobile"
          stroke="var(--color-mobile)"
          fill="url(#colorMobile)"
        />
      </AreaChart>
    </ChartContainer>
  )
}
```

### 4. Pie Chart

```tsx
import { Pie, PieChart, Cell } from "recharts"

const pieData = [
  { name: "Chrome", value: 400, fill: "var(--chart-1)" },
  { name: "Safari", value: 300, fill: "var(--chart-2)" },
  { name: "Firefox", value: 200, fill: "var(--chart-3)" },
  { name: "Edge", value: 100, fill: "var(--chart-4)" },
]

const pieConfig = {
  chrome: { label: "Chrome", color: "var(--chart-1)" },
  safari: { label: "Safari", color: "var(--chart-2)" },
  firefox: { label: "Firefox", color: "var(--chart-3)" },
  edge: { label: "Edge", color: "var(--chart-4)" },
} satisfies ChartConfig

export function PieChartDemo() {
  return (
    <ChartContainer config={pieConfig} className="min-h-[300px] w-full">
      <PieChart>
        <ChartTooltip content={<ChartTooltipContent />} />
        <Pie
          data={pieData}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          outerRadius={100}
          label={({ name, percent }) =>
            `${name} ${(percent * 100).toFixed(0)}%`
          }
        />
      </PieChart>
    </ChartContainer>
  )
}
```

### Donut Chart

```tsx
export function DonutChart() {
  const total = pieData.reduce((sum, item) => sum + item.value, 0)

  return (
    <ChartContainer config={pieConfig} className="min-h-[300px] w-full">
      <PieChart>
        <ChartTooltip content={<ChartTooltipContent />} />
        <Pie
          data={pieData}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={100}
          paddingAngle={2}
        />
        {/* Center text */}
        <text
          x="50%"
          y="50%"
          textAnchor="middle"
          dominantBaseline="middle"
          className="fill-foreground text-3xl font-bold"
        >
          {total}
        </text>
      </PieChart>
    </ChartContainer>
  )
}
```

### 5. Radar Chart

```tsx
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts"

const radarData = [
  { subject: "Math", A: 120, B: 110 },
  { subject: "Chinese", A: 98, B: 130 },
  { subject: "English", A: 86, B: 130 },
  { subject: "Geography", A: 99, B: 100 },
  { subject: "Physics", A: 85, B: 90 },
  { subject: "History", A: 65, B: 85 },
]

const radarConfig = {
  A: { label: "Student A", color: "var(--chart-1)" },
  B: { label: "Student B", color: "var(--chart-2)" },
} satisfies ChartConfig

export function RadarChartDemo() {
  return (
    <ChartContainer config={radarConfig} className="min-h-[300px] w-full">
      <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="80%">
        <PolarGrid />
        <PolarAngleAxis dataKey="subject" />
        <PolarRadiusAxis angle={30} domain={[0, 150]} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <ChartLegend content={<ChartLegendContent />} />
        <Radar
          name="Student A"
          dataKey="A"
          stroke="var(--color-A)"
          fill="var(--color-A)"
          fillOpacity={0.6}
        />
        <Radar
          name="Student B"
          dataKey="B"
          stroke="var(--color-B)"
          fill="var(--color-B)"
          fillOpacity={0.6}
        />
      </RadarChart>
    </ChartContainer>
  )
}
```

### 6. Radial Bar Chart

```tsx
import { RadialBar, RadialBarChart, PolarAngleAxis } from "recharts"

const radialData = [
  { name: "18-24", value: 31.47, fill: "var(--chart-1)" },
  { name: "25-29", value: 26.69, fill: "var(--chart-2)" },
  { name: "30-34", value: 15.69, fill: "var(--chart-3)" },
  { name: "35-39", value: 8.22, fill: "var(--chart-4)" },
]

export function RadialBarChartDemo() {
  return (
    <ChartContainer config={{}} className="min-h-[300px] w-full">
      <RadialBarChart
        data={radialData}
        cx="50%"
        cy="50%"
        innerRadius="10%"
        outerRadius="80%"
        startAngle={180}
        endAngle={0}
      >
        <PolarAngleAxis
          type="number"
          domain={[0, 100]}
          angleAxisId={0}
          tick={false}
        />
        <RadialBar
          background
          dataKey="value"
          cornerRadius={10}
          label={{ position: "insideStart", fill: "#fff" }}
        />
        <ChartTooltip content={<ChartTooltipContent />} />
        <ChartLegend content={<ChartLegendContent />} />
      </RadialBarChart>
    </ChartContainer>
  )
}
```

---

## Tooltips Personalizados

### Tooltip Básico

```tsx
<ChartTooltip content={<ChartTooltipContent />} />
```

### Tooltip con Indicator

```tsx
<ChartTooltip
  content={
    <ChartTooltipContent
      indicator="line"  // "line" | "dot" | "dashed"
      labelKey="month"
      nameKey="name"
    />
  }
/>
```

### Tooltip Custom

```tsx
const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg border bg-background p-2 shadow-sm">
        <div className="font-medium">{label}</div>
        {payload.map((entry: any, index: number) => (
          <div key={index} className="flex items-center gap-2">
            <div
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-muted-foreground">{entry.name}:</span>
            <span className="font-medium">{entry.value}</span>
          </div>
        ))}
      </div>
    )
  }
  return null
}

// Uso
<ChartTooltip content={<CustomTooltip />} />
```

---

## Dashboard Completo con Charts

```tsx
// app/(dashboard)/analytics/page.tsx
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { BarChartDemo } from "@/components/charts/bar-chart"
import { LineChartDemo } from "@/components/charts/line-chart"
import { AreaChartDemo } from "@/components/charts/area-chart"
import { PieChartDemo } from "@/components/charts/pie-chart"

export default function AnalyticsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Analytics</h1>
        <p className="text-muted-foreground">
          Track your performance and metrics.
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Revenue</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">$45,231.89</div>
            <p className="text-xs text-muted-foreground">
              +20.1% from last month
            </p>
          </CardContent>
        </Card>
        {/* Más cards... */}
      </div>

      {/* Charts grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <Card className="col-span-4">
          <CardHeader>
            <CardTitle>Overview</CardTitle>
          </CardHeader>
          <CardContent className="pl-2">
            <BarChartDemo />
          </CardContent>
        </Card>
        <Card className="col-span-3">
          <CardHeader>
            <CardTitle>Traffic Sources</CardTitle>
          </CardHeader>
          <CardContent>
            <PieChartDemo />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Visitors Trend</CardTitle>
            <CardDescription>Daily visitors over the last month</CardDescription>
          </CardHeader>
          <CardContent>
            <LineChartDemo />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Revenue Breakdown</CardTitle>
            <CardDescription>Revenue by category</CardDescription>
          </CardHeader>
          <CardContent>
            <AreaChartDemo />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
```

---

## Responsive Charts

```tsx
// El ChartContainer ya es responsive por defecto
// Pero puedes controlarlo con classes

<ChartContainer
  config={chartConfig}
  className="min-h-[200px] sm:min-h-[300px] lg:min-h-[400px] w-full"
>
  {/* Chart content */}
</ChartContainer>
```

---

## Formatters Útiles

```typescript
// Formatear números
const formatNumber = (value: number) => {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    compactDisplay: "short",
  }).format(value)
}

// Formatear moneda
const formatCurrency = (value: number) => {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value)
}

// Formatear porcentaje
const formatPercent = (value: number) => {
  return new Intl.NumberFormat("en-US", {
    style: "percent",
    minimumFractionDigits: 1,
  }).format(value / 100)
}

// Uso en YAxis
<YAxis
  tickFormatter={formatNumber}
  tickLine={false}
  axisLine={false}
/>
```

---

## Animaciones

```tsx
// Deshabilitar animaciones (para SSR o preferencia de usuario)
<BarChart data={chartData}>
  <Bar
    dataKey="value"
    fill="var(--color-primary)"
    isAnimationActive={false}
  />
</BarChart>

// Configurar duración de animación
<Bar
  animationDuration={500}
  animationEasing="ease-in-out"
/>
```

---

## Resources

- [Recharts Documentation](https://recharts.org/en-US/)
- [shadcn/ui Charts](https://ui.shadcn.com/docs/components/chart)
- [Charts Examples](https://ui.shadcn.com/charts)
