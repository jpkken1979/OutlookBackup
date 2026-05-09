---
name: tailwind-component-libraries
description: "**Versión:** 1.0"
type: feature
---

# TAILWIND COMPONENT LIBRARIES

> Guía completa de bibliotecas de componentes Tailwind CSS: HyperUI, Flowbite, Kutty, Tailblocks y más.

**Versión:** 1.0
**Fecha:** 2026-02-02
**Categoría:** Frontend / UI Components

---

## Descripción

Esta skill proporciona conocimiento exhaustivo sobre las principales bibliotecas de componentes gratuitas para Tailwind CSS. Incluye patrones de uso, ejemplos de código y guías de integración para acelerar el desarrollo de interfaces.

---

## Bibliotecas Cubiertas

| Biblioteca | Componentes | Enfoque | Interactividad |
|------------|-------------|---------|----------------|
| **HyperUI** | 475+ | Marketing, Application UI, Neobrutalism | HTML puro |
| **Flowbite** | 56+ tipos | Componentes interactivos | JavaScript/Alpine.js |
| **Kutty** | 20+ | Plugin Tailwind | Alpine.js integrado |
| **Tailblocks** | 60+ | Bloques de landing pages | HTML puro |

---

## 1. HyperUI

### Descripción
HyperUI es la biblioteca gratuita más grande de componentes Tailwind CSS con **475+ componentes** organizados en **65 colecciones**.

### Características
- **100% Gratuito** - Sin registro ni pago
- **Copy-Paste** - HTML puro, sin dependencias
- **3 Categorías principales**:
  - Marketing (landing pages, CTAs, testimonials)
  - Application UI (dashboards, forms, tables)
  - Neobrutalism (estilo bold y colorido)

### Colecciones Destacadas

#### Marketing Components
```html
<!-- Hero Section -->
<section class="bg-gray-900 text-white">
  <div class="mx-auto max-w-screen-xl px-4 py-32 lg:flex lg:h-screen lg:items-center">
    <div class="mx-auto max-w-3xl text-center">
      <h1 class="bg-gradient-to-r from-green-300 via-blue-500 to-purple-600 bg-clip-text text-3xl font-extrabold text-transparent sm:text-5xl">
        Understand User Flow.
        <span class="sm:block">Increase Conversion.</span>
      </h1>
      <p class="mx-auto mt-4 max-w-xl sm:text-xl/relaxed">
        Lorem ipsum dolor sit amet consectetur, adipisicing elit.
      </p>
      <div class="mt-8 flex flex-wrap justify-center gap-4">
        <a class="block w-full rounded border border-blue-600 bg-blue-600 px-12 py-3 text-sm font-medium text-white hover:bg-transparent hover:text-white focus:outline-none focus:ring active:text-opacity-75 sm:w-auto" href="#">
          Get Started
        </a>
        <a class="block w-full rounded border border-blue-600 px-12 py-3 text-sm font-medium text-white hover:bg-blue-600 focus:outline-none focus:ring active:bg-blue-500 sm:w-auto" href="#">
          Learn More
        </a>
      </div>
    </div>
  </div>
</section>

<!-- CTA Banner -->
<section class="bg-gray-50">
  <div class="p-8 md:p-12 lg:px-16 lg:py-24">
    <div class="mx-auto max-w-lg text-center">
      <h2 class="text-2xl font-bold text-gray-900 md:text-3xl">
        Lorem, ipsum dolor sit amet consectetur adipisicing elit
      </h2>
      <p class="hidden text-gray-500 sm:mt-4 sm:block">
        Lorem ipsum dolor sit amet, consectetur adipisicing elit.
      </p>
    </div>
    <div class="mx-auto mt-8 max-w-xl">
      <form action="#" class="sm:flex sm:gap-4">
        <div class="sm:flex-1">
          <input type="email" placeholder="Email address" class="w-full rounded-md border-gray-200 bg-white p-3 text-gray-700 shadow-sm transition focus:border-white focus:outline-none focus:ring focus:ring-yellow-400" />
        </div>
        <button type="submit" class="group mt-4 flex w-full items-center justify-center gap-2 rounded-md bg-rose-600 px-5 py-3 text-white transition focus:outline-none focus:ring focus:ring-yellow-400 sm:mt-0 sm:w-auto">
          <span class="text-sm font-medium">Sign Up</span>
          <svg class="size-5 rtl:rotate-180" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
          </svg>
        </button>
      </form>
    </div>
  </div>
</section>

<!-- Testimonial Card -->
<blockquote class="rounded-lg bg-gray-100 p-8">
  <div class="flex items-center gap-4">
    <img alt="" src="https://images.unsplash.com/photo-1595152772835-219674b2a8a6?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=1180&q=80" class="size-16 rounded-full object-cover" />
    <div>
      <div class="flex justify-center gap-0.5 text-green-500">
        <!-- 5 stars SVG -->
      </div>
      <p class="mt-1 text-lg font-medium text-gray-700">Paul Starr</p>
    </div>
  </div>
  <p class="mt-4 text-gray-500">
    Lorem ipsum dolor sit amet consectetur adipisicing elit.
  </p>
</blockquote>
```

#### Application UI Components
```html
<!-- Stats Card -->
<article class="rounded-lg border border-gray-100 bg-white p-6">
  <div class="flex items-center justify-between">
    <div>
      <p class="text-sm text-gray-500">Profit</p>
      <p class="text-2xl font-medium text-gray-900">$240.94</p>
    </div>
    <span class="rounded-full bg-green-100 p-3 text-green-600">
      <svg xmlns="http://www.w3.org/2000/svg" class="size-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
      </svg>
    </span>
  </div>
  <div class="mt-4 flex gap-1 text-green-600">
    <svg xmlns="http://www.w3.org/2000/svg" class="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
    </svg>
    <p class="flex gap-2 text-xs">
      <span class="font-medium">67.81%</span>
      <span class="text-gray-500">Since last week</span>
    </p>
  </div>
</article>

<!-- Sidebar Navigation -->
<div class="flex h-screen flex-col justify-between border-e bg-white">
  <div class="px-4 py-6">
    <span class="grid h-10 w-32 place-content-center rounded-lg bg-gray-100 text-xs text-gray-600">
      Logo
    </span>
    <ul class="mt-6 space-y-1">
      <li>
        <a href="#" class="block rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700">
          General
        </a>
      </li>
      <li>
        <details class="group [&_summary::-webkit-details-marker]:hidden">
          <summary class="flex cursor-pointer items-center justify-between rounded-lg px-4 py-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700">
            <span class="text-sm font-medium">Teams</span>
            <span class="shrink-0 transition duration-300 group-open:-rotate-180">
              <svg xmlns="http://www.w3.org/2000/svg" class="size-5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
              </svg>
            </span>
          </summary>
          <ul class="mt-2 space-y-1 px-4">
            <li>
              <a href="#" class="block rounded-lg px-4 py-2 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700">
                Banned Users
              </a>
            </li>
          </ul>
        </details>
      </li>
    </ul>
  </div>
</div>

<!-- Data Table -->
<div class="overflow-x-auto">
  <table class="min-w-full divide-y-2 divide-gray-200 bg-white text-sm">
    <thead class="ltr:text-left rtl:text-right">
      <tr>
        <th class="whitespace-nowrap px-4 py-2 font-medium text-gray-900">Name</th>
        <th class="whitespace-nowrap px-4 py-2 font-medium text-gray-900">Date of Birth</th>
        <th class="whitespace-nowrap px-4 py-2 font-medium text-gray-900">Role</th>
        <th class="whitespace-nowrap px-4 py-2 font-medium text-gray-900">Salary</th>
        <th class="px-4 py-2"></th>
      </tr>
    </thead>
    <tbody class="divide-y divide-gray-200">
      <tr>
        <td class="whitespace-nowrap px-4 py-2 font-medium text-gray-900">John Doe</td>
        <td class="whitespace-nowrap px-4 py-2 text-gray-700">24/05/1995</td>
        <td class="whitespace-nowrap px-4 py-2 text-gray-700">Web Developer</td>
        <td class="whitespace-nowrap px-4 py-2 text-gray-700">$120,000</td>
        <td class="whitespace-nowrap px-4 py-2">
          <a href="#" class="inline-block rounded bg-indigo-600 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-700">
            View
          </a>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

#### Neobrutalism Style
```html
<!-- Neobrutalism Card -->
<article class="rounded-xl border-2 border-black bg-white">
  <div class="flex items-start gap-4 p-4 sm:p-6">
    <a href="#" class="block shrink-0">
      <img alt="" src="https://images.unsplash.com/photo-1614644147724-2d4785d69962?ixlib=rb-1.2.1&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=928&q=80" class="size-14 rounded-lg border-2 border-black object-cover shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]" />
    </a>
    <div>
      <h3 class="font-bold uppercase">
        <a href="#">Building a SaaS product as a software developer</a>
      </h3>
      <p class="mt-1 text-xs font-medium text-gray-600">By John Doe</p>
      <p class="mt-2 text-sm text-gray-700 line-clamp-2">
        Lorem ipsum dolor sit amet, consectetur adipisicing elit.
      </p>
      <div class="mt-4 flex flex-wrap gap-1">
        <span class="rounded-full border-2 border-black bg-purple-100 px-3 py-1.5 text-xs font-bold uppercase shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
          Snippet
        </span>
        <span class="rounded-full border-2 border-black bg-purple-100 px-3 py-1.5 text-xs font-bold uppercase shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
          React
        </span>
      </div>
    </div>
  </div>
</article>

<!-- Neobrutalism Button -->
<a class="inline-block rounded-full border-2 border-black bg-yellow-400 px-8 py-3 text-sm font-bold uppercase tracking-widest text-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-all hover:translate-x-[3px] hover:translate-y-[3px] hover:shadow-none" href="#">
  Get Started
</a>
```

### Categorías Completas HyperUI
- **Marketing**: Announcements, Banners, Blog Cards, CTAs, FAQs, Footers, Forms, Headers, Heroes, Logos, Pagination, Pricing, Stats, Steps, Testimonials
- **Application UI**: Alerts, Avatars, Badges, Breadcrumbs, Button Groups, Buttons, Cards, Checkboxes, Dividers, Dropdowns, Error Pages, Filters, Header, Inputs, Media, Modals, Progress, Quantity, Radio Groups, Selects, Side Menu, Stats, Steps, Tables, Tabs, Tags, Textarea, Timeline, Toggles, Vertical Menu
- **Neobrutalism**: All marketing components with bold borders and shadows

---

## 2. Flowbite

### Descripción
Flowbite es una biblioteca de **56+ tipos de componentes** interactivos con soporte para múltiples frameworks.

### Instalación

```bash
# NPM
npm install flowbite

# CDN (sin instalación)
# Añadir en <head>:
<link href="https://cdn.jsdelivr.net/npm/flowbite@2.5.2/dist/flowbite.min.css" rel="stylesheet" />
# Añadir antes de </body>:
<script src="https://cdn.jsdelivr.net/npm/flowbite@2.5.2/dist/flowbite.min.js"></script>
```

### Configuración Tailwind
```javascript
// tailwind.config.js
module.exports = {
  content: [
    "./node_modules/flowbite/**/*.js"
  ],
  plugins: [
    require('flowbite/plugin')
  ]
}
```

### Integraciones de Framework
```bash
# React
npm install flowbite-react

# Vue
npm install flowbite-vue

# Svelte
npm install flowbite-svelte

# Angular
npm install flowbite
```

### Componentes Destacados

#### Modal
```html
<!-- Modal toggle -->
<button data-modal-target="default-modal" data-modal-toggle="default-modal" class="block text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center" type="button">
  Toggle modal
</button>

<!-- Main modal -->
<div id="default-modal" tabindex="-1" aria-hidden="true" class="hidden overflow-y-auto overflow-x-hidden fixed top-0 right-0 left-0 z-50 justify-center items-center w-full md:inset-0 h-[calc(100%-1rem)] max-h-full">
  <div class="relative p-4 w-full max-w-2xl max-h-full">
    <!-- Modal content -->
    <div class="relative bg-white rounded-lg shadow dark:bg-gray-700">
      <!-- Modal header -->
      <div class="flex items-center justify-between p-4 md:p-5 border-b rounded-t dark:border-gray-600">
        <h3 class="text-xl font-semibold text-gray-900 dark:text-white">
          Terms of Service
        </h3>
        <button type="button" class="text-gray-400 bg-transparent hover:bg-gray-200 hover:text-gray-900 rounded-lg text-sm w-8 h-8 ms-auto inline-flex justify-center items-center dark:hover:bg-gray-600 dark:hover:text-white" data-modal-hide="default-modal">
          <svg class="w-3 h-3" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 14 14">
            <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m1 1 6 6m0 0 6 6M7 7l6-6M7 7l-6 6"/>
          </svg>
          <span class="sr-only">Close modal</span>
        </button>
      </div>
      <!-- Modal body -->
      <div class="p-4 md:p-5 space-y-4">
        <p class="text-base leading-relaxed text-gray-500 dark:text-gray-400">
          With less than a month to go before the European Union enacts new consumer privacy laws...
        </p>
      </div>
      <!-- Modal footer -->
      <div class="flex items-center p-4 md:p-5 border-t border-gray-200 rounded-b dark:border-gray-600">
        <button data-modal-hide="default-modal" type="button" class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center">
          I accept
        </button>
        <button data-modal-hide="default-modal" type="button" class="py-2.5 px-5 ms-3 text-sm font-medium text-gray-900 focus:outline-none bg-white rounded-lg border border-gray-200 hover:bg-gray-100 hover:text-blue-700 focus:z-10 focus:ring-4 focus:ring-gray-100">
          Decline
        </button>
      </div>
    </div>
  </div>
</div>
```

#### Dropdown
```html
<button id="dropdownDefaultButton" data-dropdown-toggle="dropdown" class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center inline-flex items-center" type="button">
  Dropdown button
  <svg class="w-2.5 h-2.5 ms-3" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 10 6">
    <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m1 1 4 4 4-4"/>
  </svg>
</button>

<!-- Dropdown menu -->
<div id="dropdown" class="z-10 hidden bg-white divide-y divide-gray-100 rounded-lg shadow w-44 dark:bg-gray-700">
  <ul class="py-2 text-sm text-gray-700 dark:text-gray-200" aria-labelledby="dropdownDefaultButton">
    <li>
      <a href="#" class="block px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 dark:hover:text-white">Dashboard</a>
    </li>
    <li>
      <a href="#" class="block px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 dark:hover:text-white">Settings</a>
    </li>
    <li>
      <a href="#" class="block px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 dark:hover:text-white">Earnings</a>
    </li>
    <li>
      <a href="#" class="block px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-600 dark:hover:text-white">Sign out</a>
    </li>
  </ul>
</div>
```

#### Tabs
```html
<div class="mb-4 border-b border-gray-200 dark:border-gray-700">
  <ul class="flex flex-wrap -mb-px text-sm font-medium text-center" id="default-tab" data-tabs-toggle="#default-tab-content" role="tablist">
    <li class="me-2" role="presentation">
      <button class="inline-block p-4 border-b-2 rounded-t-lg" id="profile-tab" data-tabs-target="#profile" type="button" role="tab" aria-controls="profile" aria-selected="false">Profile</button>
    </li>
    <li class="me-2" role="presentation">
      <button class="inline-block p-4 border-b-2 rounded-t-lg hover:text-gray-600 hover:border-gray-300 dark:hover:text-gray-300" id="dashboard-tab" data-tabs-target="#dashboard" type="button" role="tab" aria-controls="dashboard" aria-selected="false">Dashboard</button>
    </li>
    <li class="me-2" role="presentation">
      <button class="inline-block p-4 border-b-2 rounded-t-lg hover:text-gray-600 hover:border-gray-300 dark:hover:text-gray-300" id="settings-tab" data-tabs-target="#settings" type="button" role="tab" aria-controls="settings" aria-selected="false">Settings</button>
    </li>
  </ul>
</div>
<div id="default-tab-content">
  <div class="hidden p-4 rounded-lg bg-gray-50 dark:bg-gray-800" id="profile" role="tabpanel" aria-labelledby="profile-tab">
    <p class="text-sm text-gray-500 dark:text-gray-400">Profile content...</p>
  </div>
  <div class="hidden p-4 rounded-lg bg-gray-50 dark:bg-gray-800" id="dashboard" role="tabpanel" aria-labelledby="dashboard-tab">
    <p class="text-sm text-gray-500 dark:text-gray-400">Dashboard content...</p>
  </div>
  <div class="hidden p-4 rounded-lg bg-gray-50 dark:bg-gray-800" id="settings" role="tabpanel" aria-labelledby="settings-tab">
    <p class="text-sm text-gray-500 dark:text-gray-400">Settings content...</p>
  </div>
</div>
```

#### Datepicker
```html
<div class="relative max-w-sm">
  <div class="absolute inset-y-0 start-0 flex items-center ps-3 pointer-events-none">
    <svg class="w-4 h-4 text-gray-500 dark:text-gray-400" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 20 20">
      <path d="M20 4a2 2 0 0 0-2-2h-2V1a1 1 0 0 0-2 0v1h-3V1a1 1 0 0 0-2 0v1H6V1a1 1 0 0 0-2 0v1H2a2 2 0 0 0-2 2v2h20V4ZM0 18a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8H0v10Zm5-8h10a1 1 0 0 1 0 2H5a1 1 0 0 1 0-2Z"/>
    </svg>
  </div>
  <input datepicker datepicker-autohide type="text" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full ps-10 p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" placeholder="Select date">
</div>
```

#### Charts (ApexCharts Integration)
```html
<div id="area-chart"></div>

<script>
const options = {
  chart: {
    height: "100%",
    maxWidth: "100%",
    type: "area",
    fontFamily: "Inter, sans-serif",
    toolbar: { show: false },
  },
  series: [
    {
      name: "New users",
      data: [6500, 6418, 6456, 6526, 6356, 6456],
      color: "#1A56DB",
    },
  ],
  xaxis: {
    categories: ['01 Feb', '02 Feb', '03 Feb', '04 Feb', '05 Feb', '06 Feb'],
  },
};

const chart = new ApexCharts(document.getElementById("area-chart"), options);
chart.render();
</script>
```

### Categorías Completas Flowbite
- **Forms**: Input, Checkbox, Radio, Toggle, Range, File Input, Search, Select, Textarea, Floating Label
- **Components**: Accordion, Alert, Avatar, Badge, Banner, Bottom Navigation, Breadcrumb, Button, Button Group, Card, Carousel, Chat Bubble, Clipboard, Device Mockups, Drawer, Dropdown, Footer, Gallery, Indicators, Jumbotron, KBD, List Group, Mega Menu, Modal, Navbar, Pagination, Popover, Progress, Rating, Sidebar, Skeleton, Speed Dial, Spinner, Stepper, Table, Tabs, Timeline, Toast, Tooltip, Typography, Video
- **Forms Pro**: Datepicker, Timepicker, Input Field, WYSIWYG Editor

---

## 3. Kutty

### Descripción
Kutty es un **plugin de Tailwind CSS** que proporciona componentes accesibles con Alpine.js integrado.

### Instalación

```bash
npm install kutty
```

### Configuración
```javascript
// tailwind.config.js
module.exports = {
  plugins: [
    require('kutty')
  ]
}
```

### Inclusión de Scripts
```html
<!-- Alpine.js viene incluido en Kutty -->
<script src="https://cdn.jsdelivr.net/npm/kutty@latest/dist/kutty.min.js"></script>
```

### Componentes Destacados

#### Accordion
```html
<div x-data="{ selected: null }">
  <div class="border-b border-gray-200">
    <button @click="selected !== 1 ? selected = 1 : selected = null" class="flex items-center justify-between w-full px-4 py-4 text-left">
      <span class="font-medium text-gray-900">What is Kutty?</span>
      <svg class="w-4 h-4 transition-transform" :class="{ 'rotate-180': selected === 1 }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>
    <div x-show="selected === 1" x-collapse class="px-4 pb-4">
      <p class="text-gray-600">Kutty is a Tailwind plugin for building web applications.</p>
    </div>
  </div>
  <div class="border-b border-gray-200">
    <button @click="selected !== 2 ? selected = 2 : selected = null" class="flex items-center justify-between w-full px-4 py-4 text-left">
      <span class="font-medium text-gray-900">How do I install Kutty?</span>
      <svg class="w-4 h-4 transition-transform" :class="{ 'rotate-180': selected === 2 }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>
    <div x-show="selected === 2" x-collapse class="px-4 pb-4">
      <p class="text-gray-600">Install via npm: npm install kutty</p>
    </div>
  </div>
</div>
```

#### Alert
```html
<div x-data="{ show: true }" x-show="show" class="flex items-center p-4 mb-4 text-blue-800 rounded-lg bg-blue-50" role="alert">
  <svg class="flex-shrink-0 w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
    <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
  </svg>
  <span class="sr-only">Info</span>
  <div class="ml-3 text-sm font-medium">
    A simple info alert with an icon.
  </div>
  <button @click="show = false" type="button" class="ml-auto -mx-1.5 -my-1.5 bg-blue-50 text-blue-500 rounded-lg focus:ring-2 focus:ring-blue-400 p-1.5 hover:bg-blue-200 inline-flex items-center justify-center h-8 w-8">
    <span class="sr-only">Close</span>
    <svg class="w-3 h-3" fill="none" viewBox="0 0 14 14">
      <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m1 1 6 6m0 0 6 6M7 7l6-6M7 7l-6 6"/>
    </svg>
  </button>
</div>
```

#### Modal
```html
<div x-data="{ open: false }">
  <button @click="open = true" class="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700">
    Open Modal
  </button>

  <div x-show="open" x-transition class="fixed inset-0 z-50 overflow-y-auto" style="display: none;">
    <div class="flex items-center justify-center min-h-screen px-4">
      <div @click="open = false" class="fixed inset-0 bg-black opacity-30"></div>

      <div class="relative bg-white rounded-lg max-w-md w-full p-6">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-medium text-gray-900">Modal Title</h3>
          <button @click="open = false" class="text-gray-400 hover:text-gray-500">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <p class="text-gray-600">Modal content goes here...</p>
        <div class="mt-6 flex justify-end gap-3">
          <button @click="open = false" class="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200">
            Cancel
          </button>
          <button class="px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700">
            Confirm
          </button>
        </div>
      </div>
    </div>
  </div>
</div>
```

#### Dropdown
```html
<div x-data="{ open: false }" class="relative inline-block text-left">
  <button @click="open = !open" class="inline-flex items-center justify-center w-full px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
    Options
    <svg class="w-5 h-5 ml-2 -mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
    </svg>
  </button>

  <div x-show="open" @click.away="open = false" x-transition class="absolute right-0 z-10 mt-2 w-56 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none" style="display: none;">
    <div class="py-1">
      <a href="#" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">Account settings</a>
      <a href="#" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">Support</a>
      <a href="#" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">License</a>
      <a href="#" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">Sign out</a>
    </div>
  </div>
</div>
```

### Características Kutty
- **Accesibilidad**: ARIA labels y roles integrados
- **Alpine.js**: Interactividad sin escribir JS
- **Plugin Tailwind**: Se integra como plugin nativo
- **Responsivo**: Mobile-first por defecto

---

## 4. Tailblocks

### Descripción
Tailblocks ofrece **60+ bloques** responsive listos para landing pages con soporte para dark mode y paleta de colores personalizable.

### Uso
1. Visitar [tailblocks.cc](https://tailblocks.cc)
2. Seleccionar un bloque
3. Elegir color de la paleta
4. Toggle dark/light mode
5. Click "View Code"
6. Copiar/pegar en tu proyecto

### Categorías de Bloques

#### Hero Sections
```html
<section class="text-gray-600 body-font">
  <div class="container mx-auto flex px-5 py-24 md:flex-row flex-col items-center">
    <div class="lg:flex-grow md:w-1/2 lg:pr-24 md:pr-16 flex flex-col md:items-start md:text-left mb-16 md:mb-0 items-center text-center">
      <h1 class="title-font sm:text-4xl text-3xl mb-4 font-medium text-gray-900">
        Before they sold out
        <br class="hidden lg:inline-block">readymade gluten
      </h1>
      <p class="mb-8 leading-relaxed">
        Copper mug try-hard pitchfork pour-over freegan heirloom neutra air plant cold-pressed tacos poke beard tote bag.
      </p>
      <div class="flex justify-center">
        <button class="inline-flex text-white bg-indigo-500 border-0 py-2 px-6 focus:outline-none hover:bg-indigo-600 rounded text-lg">Button</button>
        <button class="ml-4 inline-flex text-gray-700 bg-gray-100 border-0 py-2 px-6 focus:outline-none hover:bg-gray-200 rounded text-lg">Button</button>
      </div>
    </div>
    <div class="lg:max-w-lg lg:w-full md:w-1/2 w-5/6">
      <img class="object-cover object-center rounded" alt="hero" src="https://dummyimage.com/720x600">
    </div>
  </div>
</section>
```

#### Features Section
```html
<section class="text-gray-600 body-font">
  <div class="container px-5 py-24 mx-auto">
    <div class="text-center mb-20">
      <h1 class="sm:text-3xl text-2xl font-medium title-font text-gray-900 mb-4">Raw Denim Heirloom Man Braid</h1>
      <p class="text-base leading-relaxed xl:w-2/4 lg:w-3/4 mx-auto text-gray-500s">Blue bottle crucifix vinyl post-ironic four dollar toast vegan taxidermy.</p>
    </div>
    <div class="flex flex-wrap sm:-m-4 -mx-4 -mb-10 -mt-4 md:space-y-0 space-y-6">
      <div class="p-4 md:w-1/3 flex flex-col text-center items-center">
        <div class="w-20 h-20 inline-flex items-center justify-center rounded-full bg-indigo-100 text-indigo-500 mb-5 flex-shrink-0">
          <svg fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" class="w-10 h-10" viewBox="0 0 24 24">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>
          </svg>
        </div>
        <div class="flex-grow">
          <h2 class="text-gray-900 text-lg title-font font-medium mb-3">Shooting Stars</h2>
          <p class="leading-relaxed text-base">Blue bottle crucifix vinyl post-ironic four dollar toast vegan taxidermy.</p>
          <a class="mt-3 text-indigo-500 inline-flex items-center">Learn More
            <svg fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" class="w-4 h-4 ml-2" viewBox="0 0 24 24">
              <path d="M5 12h14M12 5l7 7-7 7"></path>
            </svg>
          </a>
        </div>
      </div>
      <!-- Repeat for more features -->
    </div>
  </div>
</section>
```

#### Pricing Section
```html
<section class="text-gray-600 body-font overflow-hidden">
  <div class="container px-5 py-24 mx-auto">
    <div class="flex flex-col text-center w-full mb-20">
      <h1 class="sm:text-4xl text-3xl font-medium title-font mb-2 text-gray-900">Pricing</h1>
      <p class="lg:w-2/3 mx-auto leading-relaxed text-base text-gray-500">Whatever cardigan tote bag tumblr hexagon brooklyn asymmetrical.</p>
    </div>
    <div class="flex flex-wrap -m-4">
      <div class="p-4 xl:w-1/4 md:w-1/2 w-full">
        <div class="h-full p-6 rounded-lg border-2 border-gray-300 flex flex-col relative overflow-hidden">
          <h2 class="text-sm tracking-widest title-font mb-1 font-medium">START</h2>
          <h1 class="text-5xl text-gray-900 pb-4 mb-4 border-b border-gray-200 leading-none">Free</h1>
          <p class="flex items-center text-gray-600 mb-2">
            <span class="w-4 h-4 mr-2 inline-flex items-center justify-center bg-gray-400 text-white rounded-full flex-shrink-0">
              <svg fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" class="w-3 h-3" viewBox="0 0 24 24">
                <path d="M20 6L9 17l-5-5"></path>
              </svg>
            </span>Vexillologist pitchfork
          </p>
          <p class="flex items-center text-gray-600 mb-2">
            <span class="w-4 h-4 mr-2 inline-flex items-center justify-center bg-gray-400 text-white rounded-full flex-shrink-0">
              <svg fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" class="w-3 h-3" viewBox="0 0 24 24">
                <path d="M20 6L9 17l-5-5"></path>
              </svg>
            </span>Tumeric plaid portland
          </p>
          <button class="flex items-center mt-auto text-white bg-gray-400 border-0 py-2 px-4 w-full focus:outline-none hover:bg-gray-500 rounded">Button
            <svg fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" class="w-4 h-4 ml-auto" viewBox="0 0 24 24">
              <path d="M5 12h14M12 5l7 7-7 7"></path>
            </svg>
          </button>
        </div>
      </div>
      <!-- PRO plan highlighted -->
      <div class="p-4 xl:w-1/4 md:w-1/2 w-full">
        <div class="h-full p-6 rounded-lg border-2 border-indigo-500 flex flex-col relative overflow-hidden">
          <span class="bg-indigo-500 text-white px-3 py-1 tracking-widest text-xs absolute right-0 top-0 rounded-bl">POPULAR</span>
          <h2 class="text-sm tracking-widest title-font mb-1 font-medium">PRO</h2>
          <h1 class="text-5xl text-gray-900 leading-none flex items-center pb-4 mb-4 border-b border-gray-200">
            <span>$38</span>
            <span class="text-lg ml-1 font-normal text-gray-500">/mo</span>
          </h1>
          <!-- Features list -->
          <button class="flex items-center mt-auto text-white bg-indigo-500 border-0 py-2 px-4 w-full focus:outline-none hover:bg-indigo-600 rounded">Button</button>
        </div>
      </div>
    </div>
  </div>
</section>
```

#### Contact Form
```html
<section class="text-gray-600 body-font relative">
  <div class="container px-5 py-24 mx-auto">
    <div class="flex flex-col text-center w-full mb-12">
      <h1 class="sm:text-3xl text-2xl font-medium title-font mb-4 text-gray-900">Contact Us</h1>
      <p class="lg:w-2/3 mx-auto leading-relaxed text-base">Whatever cardigan tote bag tumblr hexagon brooklyn asymmetrical gentrify.</p>
    </div>
    <div class="lg:w-1/2 md:w-2/3 mx-auto">
      <div class="flex flex-wrap -m-2">
        <div class="p-2 w-1/2">
          <div class="relative">
            <label for="name" class="leading-7 text-sm text-gray-600">Name</label>
            <input type="text" id="name" name="name" class="w-full bg-gray-100 bg-opacity-50 rounded border border-gray-300 focus:border-indigo-500 focus:bg-white focus:ring-2 focus:ring-indigo-200 text-base outline-none text-gray-700 py-1 px-3 leading-8 transition-colors duration-200 ease-in-out">
          </div>
        </div>
        <div class="p-2 w-1/2">
          <div class="relative">
            <label for="email" class="leading-7 text-sm text-gray-600">Email</label>
            <input type="email" id="email" name="email" class="w-full bg-gray-100 bg-opacity-50 rounded border border-gray-300 focus:border-indigo-500 focus:bg-white focus:ring-2 focus:ring-indigo-200 text-base outline-none text-gray-700 py-1 px-3 leading-8 transition-colors duration-200 ease-in-out">
          </div>
        </div>
        <div class="p-2 w-full">
          <div class="relative">
            <label for="message" class="leading-7 text-sm text-gray-600">Message</label>
            <textarea id="message" name="message" class="w-full bg-gray-100 bg-opacity-50 rounded border border-gray-300 focus:border-indigo-500 focus:bg-white focus:ring-2 focus:ring-indigo-200 h-32 text-base outline-none text-gray-700 py-1 px-3 resize-none leading-6 transition-colors duration-200 ease-in-out"></textarea>
          </div>
        </div>
        <div class="p-2 w-full">
          <button class="flex mx-auto text-white bg-indigo-500 border-0 py-2 px-8 focus:outline-none hover:bg-indigo-600 rounded text-lg">Button</button>
        </div>
      </div>
    </div>
  </div>
</section>
```

#### Footer
```html
<footer class="text-gray-600 body-font">
  <div class="container px-5 py-24 mx-auto flex md:items-center lg:items-start md:flex-row md:flex-nowrap flex-wrap flex-col">
    <div class="w-64 flex-shrink-0 md:mx-0 mx-auto text-center md:text-left">
      <a class="flex title-font font-medium items-center md:justify-start justify-center text-gray-900">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" class="w-10 h-10 text-white p-2 bg-indigo-500 rounded-full" viewBox="0 0 24 24">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path>
        </svg>
        <span class="ml-3 text-xl">Tailblocks</span>
      </a>
      <p class="mt-2 text-sm text-gray-500">Air plant banjo lyft occupy retro adaptogen indego</p>
    </div>
    <div class="flex-grow flex flex-wrap md:pl-20 -mb-10 md:mt-0 mt-10 md:text-left text-center">
      <div class="lg:w-1/4 md:w-1/2 w-full px-4">
        <h2 class="title-font font-medium text-gray-900 tracking-widest text-sm mb-3">CATEGORIES</h2>
        <nav class="list-none mb-10">
          <li><a class="text-gray-600 hover:text-gray-800">First Link</a></li>
          <li><a class="text-gray-600 hover:text-gray-800">Second Link</a></li>
          <li><a class="text-gray-600 hover:text-gray-800">Third Link</a></li>
          <li><a class="text-gray-600 hover:text-gray-800">Fourth Link</a></li>
        </nav>
      </div>
      <!-- More columns -->
    </div>
  </div>
  <div class="bg-gray-100">
    <div class="container mx-auto py-4 px-5 flex flex-wrap flex-col sm:flex-row">
      <p class="text-gray-500 text-sm text-center sm:text-left">© 2024 Tailblocks —
        <a href="https://twitter.com/knaborbin" rel="noopener noreferrer" class="text-gray-600 ml-1" target="_blank">@knaborbin</a>
      </p>
    </div>
  </div>
</footer>
```

### Categorías Completas Tailblocks
- **Blog** - Layouts de posts y artículos
- **Contact** - Formularios de contacto
- **Content** - Secciones de contenido
- **CTA** - Call-to-action banners
- **Ecommerce** - Product cards, carts
- **Feature** - Feature showcases
- **Footer** - Footer layouts
- **Gallery** - Image galleries
- **Header** - Navigation headers
- **Hero** - Hero sections
- **Pricing** - Pricing tables
- **Statistic** - Stats displays
- **Step** - Step indicators
- **Team** - Team member cards
- **Testimonial** - Testimonial blocks

---

## 5. Comparativa y Selección

### Cuándo Usar Cada Biblioteca

| Caso de Uso | Biblioteca Recomendada |
|-------------|------------------------|
| Landing page rápida | **Tailblocks** - Bloques listos para copiar |
| App con interactividad | **Flowbite** - JS incluido, modals, dropdowns |
| Máxima variedad | **HyperUI** - 475+ componentes |
| Plugin nativo Tailwind | **Kutty** - Se integra en config |
| Estilo Neobrutalism | **HyperUI** - Colección dedicada |
| Dashboard admin | **Flowbite** - Charts, tables, forms |
| Prototipado rápido | **Tailblocks** - Visual builder |
| React/Vue/Svelte | **Flowbite** - Integraciones oficiales |

### Matriz de Características

| Característica | HyperUI | Flowbite | Kutty | Tailblocks |
|----------------|---------|----------|-------|------------|
| Componentes | 475+ | 56+ tipos | 20+ | 60+ |
| Interactividad | ❌ HTML | ✅ JS | ✅ Alpine | ❌ HTML |
| Dark Mode | ✅ | ✅ | ✅ | ✅ |
| Accesibilidad | ✅ | ✅ | ✅ | ⚠️ Básica |
| React Support | ❌ | ✅ | ❌ | ❌ |
| Plugin Tailwind | ❌ | ✅ | ✅ | ❌ |
| Charts | ❌ | ✅ | ❌ | ❌ |
| Gratuito | ✅ | ✅ | ✅ | ✅ |
| Open Source | ✅ | ✅ | ✅ | ✅ |

---

## 6. Patrones de Integración

### Combinando Bibliotecas

```html
<!-- Base: Tailblocks para estructura -->
<!-- Interactividad: Flowbite para modals/dropdowns -->
<!-- Detalles: HyperUI para componentes específicos -->

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Flowbite para interactividad -->
  <link href="https://cdn.jsdelivr.net/npm/flowbite@2.5.2/dist/flowbite.min.css" rel="stylesheet" />
</head>
<body class="bg-gray-50">
  <!-- Header de Tailblocks -->
  <header class="text-gray-600 body-font">
    <!-- ... -->
  </header>

  <!-- Hero de HyperUI -->
  <section class="bg-gray-900 text-white">
    <!-- ... -->
  </section>

  <!-- Features de Tailblocks -->
  <section class="text-gray-600 body-font">
    <!-- ... -->
  </section>

  <!-- Modal de Flowbite -->
  <div id="modal" class="hidden">
    <!-- ... -->
  </div>

  <!-- Footer de Tailblocks -->
  <footer class="text-gray-600 body-font">
    <!-- ... -->
  </footer>

  <script src="https://cdn.jsdelivr.net/npm/flowbite@2.5.2/dist/flowbite.min.js"></script>
</body>
</html>
```

### Con React + shadcn/ui

```tsx
// Combinar shadcn/ui (componentes base) con estilos de HyperUI

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

// Estilo Neobrutalism de HyperUI aplicado a shadcn
export function NeobrutalistCard() {
  return (
    <Card className="rounded-xl border-2 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
      <CardHeader>
        <CardTitle className="font-bold uppercase">Card Title</CardTitle>
      </CardHeader>
      <CardContent>
        <p>Card content with neobrutalism style</p>
        <Button className="mt-4 rounded-full border-2 border-black bg-yellow-400 text-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[3px] hover:translate-y-[3px] hover:shadow-none">
          Action
        </Button>
      </CardContent>
    </Card>
  )
}
```

---

## 7. Recursos

### Enlaces Oficiales
- **HyperUI**: https://www.hyperui.dev/
- **Flowbite**: https://flowbite.com/
- **Kutty**: https://kutty.netlify.app/
- **Tailblocks**: https://tailblocks.cc/

### GitHub
- HyperUI: https://github.com/markmead/hyperui
- Flowbite: https://github.com/themesberg/flowbite
- Kutty: https://github.com/praveenjuge/kutty
- Tailblocks: https://github.com/mertJF/tailblocks

### Alternativas Adicionales
- **DaisyUI** - 61+ componentes con clases semánticas
- **Tailwind UI** - Componentes premium oficiales
- **Headless UI** - Primitivos accesibles sin estilos
- **Radix UI** - Primitivos para React

---

## Skills Relacionadas

- `tailwind-patterns` - Patrones Tailwind CSS v4.1
- `tailwind-design-system` - Design systems con CVA
- `shadcn-ui-components` - 70+ componentes shadcn/ui
- `ui-blocks-layouts` - Layouts pre-construidos

---

*Skill creada: 2026-02-02*
*Bibliotecas cubiertas: HyperUI, Flowbite, Kutty, Tailblocks*
