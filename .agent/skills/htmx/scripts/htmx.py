#!/usr/bin/env python3
"""
HTMX Skill

Genera componentes HTMX y endpoints backend.
"""

import argparse
import json
import sys
from pathlib import Path


# HTMX Attributes reference
HTMX_ATTRIBUTES = {
    "hx-get": "Issues a GET request to the specified URL",
    "hx-post": "Issues a POST request to the specified URL",
    "hx-put": "Issues a PUT request to the specified URL",
    "hx-patch": "Issues a PATCH request to the specified URL",
    "hx-delete": "Issues a DELETE request to the specified URL",
    "hx-trigger": "Event that triggers the request (click, change, submit, etc.)",
    "hx-target": "CSS selector of element to swap content into",
    "hx-swap": "How to swap content (innerHTML, outerHTML, beforeend, etc.)",
    "hx-indicator": "Element to show during request (loading indicator)",
    "hx-confirm": "Shows a confirm dialog before issuing request",
    "hx-boost": "Progressively enhances links and forms",
    "hx-push-url": "Push URL into browser history",
    "hx-select": "Select content from response to swap",
    "hx-select-oob": "Select out-of-band content to swap",
    "hx-vals": "Add values to request (JSON)",
    "hx-headers": "Add headers to request (JSON)",
    "hx-include": "Include additional elements in request",
    "hx-params": "Filter parameters to include",
    "hx-disable": "Disable HTMX processing",
    "hx-disinherit": "Control attribute inheritance",
    "hx-sync": "Coordinate multiple requests",
}

# Component templates
COMPONENT_TEMPLATES = {
    "search": """<!-- Live Search Component -->
<div class="search-container">
  <input type="search"
         name="q"
         placeholder="Search..."
         hx-get="/api/search"
         hx-trigger="keyup changed delay:300ms"
         hx-target="#search-results"
         hx-indicator="#search-spinner">

  <span id="search-spinner" class="htmx-indicator">
    <svg class="spinner" viewBox="0 0 50 50">
      <circle cx="25" cy="25" r="20" fill="none" stroke-width="5"></circle>
    </svg>
  </span>

  <div id="search-results"></div>
</div>

<style>
.htmx-indicator {{ display: none; }}
.htmx-request .htmx-indicator {{ display: inline-block; }}
.spinner {{ animation: rotate 1s linear infinite; width: 20px; }}
@keyframes rotate {{ 100% {{ transform: rotate(360deg); }} }}
</style>
""",
    "infinite-scroll": """<!-- Infinite Scroll Component -->
<div id="items-container">
  <!-- Items will be loaded here -->
</div>

<div hx-get="/api/items?page=1"
     hx-trigger="revealed"
     hx-swap="afterend"
     hx-indicator="#load-more-spinner">
  <span id="load-more-spinner" class="htmx-indicator">Loading more...</span>
</div>

<!-- Each page response should include: -->
<!--
<div class="item">Item content...</div>
<div class="item">Item content...</div>
<div hx-get="/api/items?page={{next_page}}"
     hx-trigger="revealed"
     hx-swap="afterend">
</div>
-->
""",
    "modal": """<!-- Modal Component -->
<button hx-get="/api/modal/content"
        hx-target="#modal-container"
        hx-trigger="click">
  Open Modal
</button>

<div id="modal-container"></div>

<!-- Modal response template -->
<!--
<div id="modal" class="modal-backdrop" onclick="if(event.target===this) this.remove()">
  <div class="modal-content">
    <h2>Modal Title</h2>
    <p>Modal content here...</p>
    <button onclick="this.closest('.modal-backdrop').remove()">Close</button>
  </div>
</div>
-->

<style>
.modal-backdrop {{
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}}
.modal-content {{
  background: white;
  padding: 2rem;
  border-radius: 8px;
  max-width: 500px;
}}
</style>
""",
    "form": """<!-- HTMX Form Component -->
<form hx-post="/api/{name}"
      hx-target="#form-result"
      hx-swap="innerHTML"
      hx-indicator="#form-spinner">

  <div class="form-group">
    <label for="name">Name</label>
    <input type="text" id="name" name="name" required>
  </div>

  <div class="form-group">
    <label for="email">Email</label>
    <input type="email" id="email" name="email" required>
  </div>

  <button type="submit">
    <span class="btn-text">Submit</span>
    <span id="form-spinner" class="htmx-indicator">Sending...</span>
  </button>
</form>

<div id="form-result"></div>
""",
    "tabs": """<!-- HTMX Tabs Component -->
<div class="tabs">
  <nav class="tab-list" role="tablist">
    <button hx-get="/api/tabs/tab1"
            hx-target="#tab-content"
            class="tab active"
            aria-selected="true">
      Tab 1
    </button>
    <button hx-get="/api/tabs/tab2"
            hx-target="#tab-content"
            class="tab">
      Tab 2
    </button>
    <button hx-get="/api/tabs/tab3"
            hx-target="#tab-content"
            class="tab">
      Tab 3
    </button>
  </nav>

  <div id="tab-content" class="tab-panel">
    <!-- Initial content -->
  </div>
</div>

<script>
// Handle active tab styling
document.querySelector('.tab-list').addEventListener('click', (e) => {{
  if (e.target.matches('.tab')) {{
    document.querySelectorAll('.tab').forEach(t => {{
      t.classList.remove('active');
      t.setAttribute('aria-selected', 'false');
    }});
    e.target.classList.add('active');
    e.target.setAttribute('aria-selected', 'true');
  }}
}});
</script>
""",
    "delete-confirm": """<!-- Delete with Confirmation -->
<button hx-delete="/api/items/{id}"
        hx-confirm="Are you sure you want to delete this item?"
        hx-target="closest .item"
        hx-swap="outerHTML swap:1s">
  Delete
</button>

<style>
.item.htmx-swapping {{
  opacity: 0;
  transition: opacity 1s ease-out;
}}
</style>
""",
    "edit-inline": """<!-- Inline Edit Component -->
<div class="editable" id="item-{id}">
  <span class="view-mode">
    {value}
    <button hx-get="/api/items/{id}/edit"
            hx-target="#item-{id}"
            hx-swap="innerHTML">
      Edit
    </button>
  </span>
</div>

<!-- Edit mode response -->
<!--
<form hx-put="/api/items/{id}"
      hx-target="#item-{id}"
      hx-swap="innerHTML">
  <input type="text" name="value" value="{value}" autofocus>
  <button type="submit">Save</button>
  <button hx-get="/api/items/{id}"
          hx-target="#item-{id}"
          hx-swap="innerHTML">
    Cancel
  </button>
</form>
-->
""",
}

# Backend templates
BACKEND_TEMPLATES = {
    "fastapi": '''from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/api/{name}", response_class=HTMLResponse)
async def get_{name}(request: Request, q: str = ""):
    """
    HTMX endpoint for {name}
    Returns HTML fragment
    """
    # Implementar: lógica del endpoint
    items = []  # Your data here

    return templates.TemplateResponse(
        "{name}_partial.html",
        {{"request": request, "items": items}}
    )

@app.post("/api/{name}", response_class=HTMLResponse)
async def create_{name}(
    request: Request,
    name: str = Form(...),
    email: str = Form(...)
):
    """
    HTMX form submission endpoint
    """
    # Implementar: guardar datos

    return HTMLResponse(
        '<div class="success">Created successfully!</div>'
    )
''',
    "flask": '''from flask import Flask, request, render_template

app = Flask(__name__)

@app.route('/api/{name}', methods=['GET'])
def get_{name}():
    """
    HTMX endpoint for {name}
    Returns HTML fragment
    """
    q = request.args.get('q', '')

    # Implementar: lógica del endpoint
    items = []  # Your data here

    return render_template('{name}_partial.html', items=items)

@app.route('/api/{name}', methods=['POST'])
def create_{name}():
    """
    HTMX form submission endpoint
    """
    name = request.form.get('name')
    email = request.form.get('email')

    # Implementar: guardar datos

    return '<div class="success">Created successfully!</div>'
''',
    "express": """import express from 'express';

const app = express();
app.use(express.urlencoded({{ extended: true }}));

app.get('/api/{name}', (req, res) => {{
  /**
   * HTMX endpoint for {name}
   * Returns HTML fragment
   */
  const {{ q }} = req.query;

  // Implementar: lógica del endpoint
  const items = [];

  res.send(`
    <ul>
      ${{items.map(item => `<li>${{item.name}}</li>`).join('')}}
    </ul>
  `);
}});

app.post('/api/{name}', (req, res) => {{
  /**
   * HTMX form submission endpoint
   */
  const {{ name, email }} = req.body;

  // Implementar: guardar datos

  res.send('<div class="success">Created successfully!</div>');
}});
""",
}


def generate_component(name: str, component_type: str = "form") -> str:
    """Genera componente HTMX."""
    template = COMPONENT_TEMPLATES.get(component_type, COMPONENT_TEMPLATES["form"])
    return template.format(name=name, id="{id}", value="{value}")


def generate_endpoint(name: str, framework: str = "fastapi") -> str:
    """Genera endpoint backend."""
    template = BACKEND_TEMPLATES.get(framework, BACKEND_TEMPLATES["fastapi"])
    return template.format(name=name)


def main():
    parser = argparse.ArgumentParser(description="HTMX Skill - Genera componentes HTMX")

    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # component
    comp_parser = subparsers.add_parser("component", help="Genera componente")
    comp_parser.add_argument("--name", "-n", required=True, help="Nombre del componente")
    comp_parser.add_argument(
        "--type",
        "-t",
        choices=list(COMPONENT_TEMPLATES.keys()),
        default="form",
        help="Tipo de componente",
    )

    # endpoint
    ep_parser = subparsers.add_parser("endpoint", help="Genera endpoint")
    ep_parser.add_argument("--name", "-n", required=True, help="Nombre del endpoint")
    ep_parser.add_argument(
        "--framework", "-f", choices=["fastapi", "flask", "express"], default="fastapi"
    )

    # pattern
    pattern_parser = subparsers.add_parser("pattern", help="Muestra patrón")
    pattern_parser.add_argument(
        "--name", "-n", required=True, choices=list(COMPONENT_TEMPLATES.keys())
    )

    # attributes
    subparsers.add_parser("attributes", help="Lista atributos HTMX")

    # Común
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--output", "-o", help="Archivo de salida")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    output = None

    if args.command == "component":
        output = generate_component(args.name, args.type)

    elif args.command == "endpoint":
        output = generate_endpoint(args.name, args.framework)

    elif args.command == "pattern":
        output = COMPONENT_TEMPLATES.get(args.name, "Pattern not found")

    elif args.command == "attributes":
        if args.json:
            output = json.dumps(HTMX_ATTRIBUTES, indent=2)
        else:
            print(f"\n{'=' * 60}")
            print(" HTMX ATTRIBUTES")
            print(f"{'=' * 60}\n")
            for attr, desc in HTMX_ATTRIBUTES.items():
                print(f"  {attr:<20} {desc}")

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
