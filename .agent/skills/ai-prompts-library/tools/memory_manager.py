#!/usr/bin/env python3
"""
Memory Manager - Sistema de Memoria Persistente para Agentes
Basado en los sistemas de memoria de Claude y GPT

Uso:
    python memory_manager.py add "El usuario prefiere respuestas concisas"
    python memory_manager.py add --category preferences "Usa español como idioma principal"
    python memory_manager.py search "preferencias"
    python memory_manager.py list
    python memory_manager.py export memories.json
"""

import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field

# Directorio de almacenamiento de memoria
MEMORY_DIR = Path(__file__).parent.parent / "memory"
MEMORY_FILE = MEMORY_DIR / "agent_memory.json"


@dataclass
class MemoryEntry:
    """Una entrada de memoria."""

    id: str
    content: str
    category: str
    importance: str  # low, medium, high, critical
    created_at: str
    last_accessed: str
    access_count: int
    tags: list[str]
    context: str
    source: str


@dataclass
class MemoryStore:
    """Almacén completo de memorias."""

    version: str = "1.0"
    created_at: str = ""
    last_updated: str = ""
    entries: list[MemoryEntry] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.last_updated = datetime.now().isoformat()


# Categorías de memoria basadas en Claude/GPT
MEMORY_CATEGORIES = {
    "preferences": {
        "description": "Preferencias del usuario (estilo, formato, idioma)",
        "examples": ["Prefiere código comentado", "Usa TypeScript sobre JavaScript"],
        "retention": "permanent",
    },
    "context": {
        "description": "Contexto del proyecto o conversación",
        "examples": ["Trabajando en app Next.js", "Proyecto para cliente japonés"],
        "retention": "session",
    },
    "facts": {
        "description": "Hechos sobre el usuario o proyecto",
        "examples": ["Usuario es desarrollador senior", "Empresa: UNS Corp"],
        "retention": "permanent",
    },
    "instructions": {
        "description": "Instrucciones específicas del usuario",
        "examples": ["Siempre verificar tipos", "No usar console.log"],
        "retention": "permanent",
    },
    "learnings": {
        "description": "Aprendizajes de interacciones previas",
        "examples": ["Usuario corrigió: usar 'const' no 'let'"],
        "retention": "permanent",
    },
    "project": {
        "description": "Información específica del proyecto",
        "examples": ["Stack: React + Node", "Base de datos: PostgreSQL"],
        "retention": "project",
    },
    "temporary": {
        "description": "Información temporal de la sesión",
        "examples": ["Trabajando en archivo X", "Debuggeando error Y"],
        "retention": "session",
    },
}


def generate_memory_id(content: str) -> str:
    """Genera un ID único para una memoria."""
    hash_input = f"{content}{datetime.now().isoformat()}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:12]


def load_memory_store() -> MemoryStore:
    """Carga el almacén de memoria desde disco."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, encoding="utf-8") as f:
                data = json.load(f)
                entries = [MemoryEntry(**e) for e in data.get("entries", [])]
                return MemoryStore(
                    version=data.get("version", "1.0"),
                    created_at=data.get("created_at", ""),
                    last_updated=data.get("last_updated", ""),
                    entries=entries,
                )
        except Exception as e:
            print(f"⚠️ Error cargando memoria: {e}")

    return MemoryStore()


def save_memory_store(store: MemoryStore) -> None:
    """Guarda el almacén de memoria a disco."""
    store.last_updated = datetime.now().isoformat()

    data = {
        "version": store.version,
        "created_at": store.created_at,
        "last_updated": store.last_updated,
        "entries": [asdict(e) for e in store.entries],
    }

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_memory(
    content: str,
    category: str = "context",
    importance: str = "medium",
    tags: list[str] = None,
    context: str = "",
    source: str = "user",
) -> MemoryEntry:
    """Añade una nueva memoria."""
    store = load_memory_store()

    # Verificar si ya existe una memoria similar
    for entry in store.entries:
        if entry.content.lower() == content.lower():
            print(f"⚠️ Memoria similar ya existe: {entry.id}")
            return entry

    entry = MemoryEntry(
        id=generate_memory_id(content),
        content=content,
        category=category,
        importance=importance,
        created_at=datetime.now().isoformat(),
        last_accessed=datetime.now().isoformat(),
        access_count=0,
        tags=tags or [],
        context=context,
        source=source,
    )

    store.entries.append(entry)
    save_memory_store(store)

    return entry


def search_memories(
    query: str, category: str | None = None, importance: str | None = None, limit: int = 10
) -> list[MemoryEntry]:
    """Busca memorias por query."""
    store = load_memory_store()
    results = []
    query_lower = query.lower()

    for entry in store.entries:
        # Filtrar por categoría
        if category and entry.category != category:
            continue

        # Filtrar por importancia
        if importance and entry.importance != importance:
            continue

        # Buscar en contenido y tags
        if query_lower in entry.content.lower() or any(
            query_lower in tag.lower() for tag in entry.tags
        ):
            results.append(entry)
            # Actualizar acceso
            entry.last_accessed = datetime.now().isoformat()
            entry.access_count += 1

    save_memory_store(store)

    # Ordenar por importancia y accesos
    importance_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    results.sort(key=lambda x: (importance_order.get(x.importance, 2), -x.access_count))

    return results[:limit]


def get_memories_for_context(max_tokens: int = 2000) -> str:
    """Obtiene memorias relevantes para inyectar en contexto."""
    store = load_memory_store()

    # Priorizar por importancia y recencia
    importance_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_entries = sorted(
        store.entries,
        key=lambda x: (importance_order.get(x.importance, 2), x.last_accessed),
        reverse=True,
    )

    context_parts = []
    current_length = 0

    for entry in sorted_entries:
        entry_text = f"[{entry.category}] {entry.content}"
        entry_length = len(entry_text)

        if current_length + entry_length > max_tokens:
            break

        context_parts.append(entry_text)
        current_length += entry_length

    if not context_parts:
        return ""

    return """
## Agent Memory Context

The following information has been remembered from previous interactions:

""" + "\n".join(f"- {part}" for part in context_parts)


def delete_memory(memory_id: str) -> bool:
    """Elimina una memoria por ID."""
    store = load_memory_store()

    for i, entry in enumerate(store.entries):
        if entry.id == memory_id:
            del store.entries[i]
            save_memory_store(store)
            return True

    return False


def clear_category(category: str) -> int:
    """Limpia todas las memorias de una categoría."""
    store = load_memory_store()
    initial_count = len(store.entries)

    store.entries = [e for e in store.entries if e.category != category]

    save_memory_store(store)
    return initial_count - len(store.entries)


def list_memories(category: str | None = None) -> None:
    """Lista todas las memorias."""
    store = load_memory_store()

    print("\n" + "=" * 70)
    print("🧠 MEMORIA DEL AGENTE")
    print("=" * 70)
    print(f"Total de memorias: {len(store.entries)}")
    print(f"Última actualización: {store.last_updated}")
    print()

    # Agrupar por categoría
    by_category = {}
    for entry in store.entries:
        if category and entry.category != category:
            continue
        if entry.category not in by_category:
            by_category[entry.category] = []
        by_category[entry.category].append(entry)

    for cat, entries in by_category.items():
        cat_info = MEMORY_CATEGORIES.get(cat, {"description": "Categoría personalizada"})
        print(f"\n📁 {cat.upper()} ({len(entries)})")
        print(f"   {cat_info['description']}")
        print("-" * 50)

        for entry in entries:
            importance_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
            emoji = importance_emoji.get(entry.importance, "⚪")
            print(f"   {emoji} [{entry.id}] {entry.content[:60]}...")
            if entry.tags:
                print(f"      Tags: {', '.join(entry.tags)}")

    print()


def export_memories(output_path: str) -> None:
    """Exporta todas las memorias a un archivo."""
    store = load_memory_store()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": store.version,
                "created_at": store.created_at,
                "last_updated": store.last_updated,
                "total_entries": len(store.entries),
                "entries": [asdict(e) for e in store.entries],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"✅ Memorias exportadas a: {output_path}")
    print(f"   Total: {len(store.entries)} entradas")


def import_memories(input_path: str) -> int:
    """Importa memorias desde un archivo."""
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for entry_data in data.get("entries", []):
        try:
            add_memory(
                content=entry_data["content"],
                category=entry_data.get("category", "context"),
                importance=entry_data.get("importance", "medium"),
                tags=entry_data.get("tags", []),
                context=entry_data.get("context", ""),
                source="import",
            )
            count += 1
        except Exception as e:
            print(f"⚠️ Error importando entrada: {e}")

    return count


def show_categories() -> None:
    """Muestra las categorías disponibles."""
    print("\n" + "=" * 60)
    print("📂 CATEGORÍAS DE MEMORIA")
    print("=" * 60 + "\n")

    for key, info in MEMORY_CATEGORIES.items():
        print(f"  [{key}]")
        print(f"    {info['description']}")
        print(f"    Retención: {info['retention']}")
        print(f"    Ejemplos: {', '.join(info['examples'][:2])}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Memory Manager - Sistema de memoria persistente para agentes IA"
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # Comando: add
    add_parser = subparsers.add_parser("add", help="Añadir nueva memoria")
    add_parser.add_argument("content", help="Contenido de la memoria")
    add_parser.add_argument(
        "--category",
        "-c",
        default="context",
        choices=list(MEMORY_CATEGORIES.keys()),
        help="Categoría de la memoria",
    )
    add_parser.add_argument(
        "--importance",
        "-i",
        default="medium",
        choices=["low", "medium", "high", "critical"],
        help="Nivel de importancia",
    )
    add_parser.add_argument("--tags", "-t", nargs="+", help="Tags para la memoria")

    # Comando: search
    search_parser = subparsers.add_parser("search", help="Buscar memorias")
    search_parser.add_argument("query", help="Término de búsqueda")
    search_parser.add_argument("--category", "-c", help="Filtrar por categoría")
    search_parser.add_argument("--limit", "-l", type=int, default=10, help="Límite de resultados")

    # Comando: list
    list_parser = subparsers.add_parser("list", help="Listar memorias")
    list_parser.add_argument("--category", "-c", help="Filtrar por categoría")

    # Comando: delete
    delete_parser = subparsers.add_parser("delete", help="Eliminar memoria")
    delete_parser.add_argument("id", help="ID de la memoria a eliminar")

    # Comando: clear
    clear_parser = subparsers.add_parser("clear", help="Limpiar categoría")
    clear_parser.add_argument("category", help="Categoría a limpiar")

    # Comando: export
    export_parser = subparsers.add_parser("export", help="Exportar memorias")
    export_parser.add_argument("output", help="Archivo de salida")

    # Comando: import
    import_parser = subparsers.add_parser("import", help="Importar memorias")
    import_parser.add_argument("input", help="Archivo de entrada")

    # Comando: context
    subparsers.add_parser("context", help="Obtener contexto para inyección")

    # Comando: categories
    subparsers.add_parser("categories", help="Mostrar categorías disponibles")

    args = parser.parse_args()

    if args.command == "add":
        entry = add_memory(
            content=args.content, category=args.category, importance=args.importance, tags=args.tags
        )
        print(f"✅ Memoria añadida: {entry.id}")
        print(f"   Categoría: {entry.category}")
        print(f"   Importancia: {entry.importance}")

    elif args.command == "search":
        results = search_memories(args.query, category=args.category, limit=args.limit)
        if results:
            print(f"\n🔍 Resultados para '{args.query}':")
            for r in results:
                print(f"  [{r.id}] ({r.category}) {r.content}")
        else:
            print("No se encontraron memorias.")

    elif args.command == "list":
        list_memories(category=args.category)

    elif args.command == "delete":
        if delete_memory(args.id):
            print(f"✅ Memoria {args.id} eliminada")
        else:
            print(f"❌ Memoria {args.id} no encontrada")

    elif args.command == "clear":
        count = clear_category(args.category)
        print(f"✅ {count} memorias eliminadas de '{args.category}'")

    elif args.command == "export":
        export_memories(args.output)

    elif args.command == "import":
        count = import_memories(args.input)
        print(f"✅ {count} memorias importadas")

    elif args.command == "context":
        context = get_memories_for_context()
        if context:
            print(context)
        else:
            print("No hay memorias para inyectar en contexto.")

    elif args.command == "categories":
        show_categories()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
