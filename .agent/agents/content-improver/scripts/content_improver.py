#!/usr/bin/env python3
"""
Content Improver - Mejora contenido técnico y documentación.

Especializado en:
- Mejorar claridad y estructura
- Corregir errores gramaticales
- Optimizar para SEO/legibilidad
- Adaptar tono y audiencia

Uso:
    python content_improver.py "Mejorar README de proyecto"
    python content_improver.py --analyze ./README.md
    python content_improver.py --improve ./docs/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ContentAnalysis:
    """Análisis de contenido."""

    file_path: str
    word_count: int
    sentence_count: int
    avg_sentence_length: float
    readability_score: float
    headings: list[str]
    issues: list[str]
    suggestions: list[str]


@dataclass
class ImprovementSuggestion:
    """Sugerencia de mejora."""

    type: str  # grammar, clarity, structure, seo
    original: str
    suggestion: str
    reason: str
    line_number: int | None = None


# Patrones de problemas comunes
COMMON_ISSUES = {
    "passive_voice": {
        "patterns": [
            r"\b(is|are|was|were|been|being)\s+\w+ed\b",
        ],
        "suggestion": "Considerar voz activa",
        "type": "clarity",
    },
    "weak_words": {
        "patterns": [
            r"\b(very|really|quite|basically|actually|just)\b",
        ],
        "suggestion": "Eliminar palabras débiles",
        "type": "clarity",
    },
    "long_sentences": {
        "patterns": [],  # Se detecta por longitud
        "suggestion": "Dividir oración larga",
        "type": "readability",
    },
    "missing_alt": {
        "patterns": [
            r"!\[]\(",
        ],
        "suggestion": "Añadir texto alt a imágenes",
        "type": "seo",
    },
    "no_headings": {
        "patterns": [],  # Se detecta por ausencia
        "suggestion": "Añadir encabezados para estructura",
        "type": "structure",
    },
}

# Templates de contenido
CONTENT_TEMPLATES = {
    "readme": """
# {project_name}

{description}

## Características

- Feature 1
- Feature 2
- Feature 3

## Instalación

```bash
npm install {package_name}
```

## Uso

```javascript
import {{ feature }} from '{package_name}';

// Ejemplo de uso
```

## API

### `function()`

Descripción de la función.

**Parámetros:**
- `param1` - Descripción

**Retorna:** Tipo - Descripción

## Contribuir

Las contribuciones son bienvenidas. Ver [CONTRIBUTING.md](CONTRIBUTING.md).

## Licencia

MIT
""",
    "api_docs": """
# API Reference

## Endpoints

### GET /resource

Obtiene recursos.

**Request:**
```http
GET /api/resource HTTP/1.1
Host: api.example.com
Authorization: Bearer {token}
```

**Response:**
```json
{{
  "data": [],
  "meta": {{
    "total": 0,
    "page": 1
  }}
}}
```

**Status Codes:**
- `200` - Éxito
- `401` - No autorizado
- `404` - No encontrado
""",
    "changelog": """
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- New feature

### Changed
- Updated feature

### Fixed
- Bug fix

## [1.0.0] - YYYY-MM-DD

### Added
- Initial release
""",
}


class ContentImprover:
    """
    Mejora contenido técnico y documentación.

    Capacidades:
    - Analizar legibilidad
    - Detectar problemas comunes
    - Sugerir mejoras
    - Generar templates
    """

    def __init__(self):
        self.issues = COMMON_ISSUES
        self.templates = CONTENT_TEMPLATES

    def analyze_content(self, text: str, file_path: str = "") -> ContentAnalysis:
        """Analiza contenido de texto."""
        # Contar palabras y oraciones
        words = re.findall(r"\b\w+\b", text)
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        word_count = len(words)
        sentence_count = len(sentences)
        avg_sentence_length = word_count / max(sentence_count, 1)

        # Calcular legibilidad (Flesch-Kincaid simplificado)
        syllables = sum(self._count_syllables(w) for w in words)
        if word_count > 0 and sentence_count > 0:
            readability = (
                206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllables / word_count)
            )
        else:
            readability = 0

        # Detectar encabezados
        headings = re.findall(r"^#{1,6}\s+(.+)$", text, re.MULTILINE)

        # Detectar issues
        issues = []
        suggestions = []

        # Oraciones largas
        for _i, sentence in enumerate(sentences):
            words_in_sentence = len(sentence.split())
            if words_in_sentence > 30:
                issues.append(f"Oración muy larga ({words_in_sentence} palabras)")
                suggestions.append("Dividir oraciones de más de 25-30 palabras")

        # Patrones problemáticos
        for issue_name, issue_info in self.issues.items():
            for pattern in issue_info.get("patterns", []):
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    issues.append(f"{issue_name}: {len(matches)} ocurrencias")
                    suggestions.append(issue_info["suggestion"])

        # Sin encabezados
        if not headings and word_count > 200:
            issues.append("Sin encabezados en documento largo")
            suggestions.append("Añadir encabezados para mejorar estructura")

        # Legibilidad baja
        if readability < 30 and word_count > 100:
            issues.append(f"Legibilidad baja ({readability:.0f})")
            suggestions.append("Simplificar vocabulario y estructura")

        return ContentAnalysis(
            file_path=file_path,
            word_count=word_count,
            sentence_count=sentence_count,
            avg_sentence_length=round(avg_sentence_length, 1),
            readability_score=round(readability, 1),
            headings=headings,
            issues=list(set(issues)),
            suggestions=list(set(suggestions)),
        )

    def _count_syllables(self, word: str) -> int:
        """Cuenta sílabas de una palabra (aproximado)."""
        word = word.lower()
        vowels = "aeiou"
        count = 0
        prev_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel

        # Ajustes
        if word.endswith("e"):
            count -= 1
        if count == 0:
            count = 1

        return count

    def analyze_file(self, file_path: Path) -> ContentAnalysis:
        """Analiza un archivo."""
        if not file_path.exists():
            return ContentAnalysis(
                file_path=str(file_path),
                word_count=0,
                sentence_count=0,
                avg_sentence_length=0,
                readability_score=0,
                headings=[],
                issues=["Archivo no encontrado"],
                suggestions=[],
            )

        text = file_path.read_text(errors="ignore")
        return self.analyze_content(text, str(file_path))

    def improve_text(self, text: str) -> list[ImprovementSuggestion]:
        """Genera sugerencias de mejora para texto."""
        suggestions = []

        lines = text.split("\n")

        for i, line in enumerate(lines, 1):
            # Detectar voz pasiva
            passive_matches = re.findall(r"\b(is|are|was|were)\s+(\w+ed)\b", line, re.IGNORECASE)
            for match in passive_matches:
                suggestions.append(
                    ImprovementSuggestion(
                        type="clarity",
                        original=f"{match[0]} {match[1]}",
                        suggestion="Considerar voz activa",
                        reason="La voz activa es más directa y clara",
                        line_number=i,
                    )
                )

            # Detectar palabras débiles
            weak_words = re.findall(
                r"\b(very|really|quite|basically|actually|just)\b", line, re.IGNORECASE
            )
            for word in weak_words:
                suggestions.append(
                    ImprovementSuggestion(
                        type="clarity",
                        original=word,
                        suggestion="Eliminar o reemplazar",
                        reason="Palabras débiles diluyen el mensaje",
                        line_number=i,
                    )
                )

            # Detectar oraciones largas
            sentences = re.split(r"[.!?]", line)
            for sentence in sentences:
                words = sentence.split()
                if len(words) > 30:
                    suggestions.append(
                        ImprovementSuggestion(
                            type="readability",
                            original=sentence[:50] + "...",
                            suggestion="Dividir en oraciones más cortas",
                            reason="Oraciones largas dificultan la comprensión",
                            line_number=i,
                        )
                    )

        return suggestions

    def get_template(self, template_name: str, **kwargs) -> str:
        """Obtiene template con variables reemplazadas."""
        template = self.templates.get(template_name, "")
        return template.format(**kwargs) if kwargs else template

    def print_analysis(self, analysis: ContentAnalysis) -> None:
        """Imprime análisis de forma legible."""
        print(f"\n{'=' * 60}")
        print("ANÁLISIS DE CONTENIDO")
        print(f"{'=' * 60}")

        if analysis.file_path:
            print(f"\n📄 Archivo: {analysis.file_path}")

        print("\n📊 Estadísticas:")
        print(f"   Palabras: {analysis.word_count}")
        print(f"   Oraciones: {analysis.sentence_count}")
        print(f"   Longitud promedio: {analysis.avg_sentence_length} palabras/oración")
        print(f"   Legibilidad: {analysis.readability_score}/100")

        # Interpretar legibilidad
        if analysis.readability_score >= 70:
            readability_desc = "Fácil de leer"
        elif analysis.readability_score >= 50:
            readability_desc = "Moderadamente fácil"
        elif analysis.readability_score >= 30:
            readability_desc = "Difícil"
        else:
            readability_desc = "Muy difícil"
        print(f"   Nivel: {readability_desc}")

        if analysis.headings:
            print(f"\n📑 Encabezados ({len(analysis.headings)}):")
            for h in analysis.headings[:5]:
                print(f"   - {h}")
            if len(analysis.headings) > 5:
                print(f"   ... y {len(analysis.headings) - 5} más")

        if analysis.issues:
            print("\n⚠️ Problemas detectados:")
            for issue in analysis.issues:
                print(f"   - {issue}")

        if analysis.suggestions:
            print("\n💡 Sugerencias:")
            for sug in analysis.suggestions:
                print(f"   - {sug}")

        print(f"\n{'=' * 60}\n")

    def list_templates(self) -> None:
        """Lista templates disponibles."""
        print(f"\n{'=' * 60}")
        print("TEMPLATES DE CONTENIDO")
        print(f"{'=' * 60}\n")

        for key in self.templates:
            print(f"📝 {key}")

        print("\nUsa --template <nombre> para ver el template")
        print(f"\n{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(description="Content Improver - Mejora contenido técnico")
    parser.add_argument("task", nargs="?", help="Descripción de la tarea")
    parser.add_argument("--analyze", "-a", type=Path, help="Analizar archivo")
    parser.add_argument("--improve", "-i", type=Path, help="Sugerir mejoras para archivo")
    parser.add_argument("--template", "-t", help="Obtener template")
    parser.add_argument("--list-templates", "-l", action="store_true", help="Listar templates")
    parser.add_argument("--json", "-j", action="store_true", help="Output en JSON")

    args = parser.parse_args()
    improver = ContentImprover()

    if args.list_templates:
        improver.list_templates()
        return 0

    if args.template:
        template = improver.get_template(args.template)
        print(template)
        return 0

    if args.analyze:
        analysis = improver.analyze_file(args.analyze)
        if args.json:
            print(
                json.dumps(
                    {
                        "file_path": analysis.file_path,
                        "word_count": analysis.word_count,
                        "readability_score": analysis.readability_score,
                        "issues": analysis.issues,
                        "suggestions": analysis.suggestions,
                    },
                    indent=2,
                )
            )
        else:
            improver.print_analysis(analysis)
        return 0

    if args.improve:
        if args.improve.exists():
            text = args.improve.read_text(errors="ignore")
            suggestions = improver.improve_text(text)

            print(f"\n{'=' * 60}")
            print(f"SUGERENCIAS DE MEJORA: {args.improve}")
            print(f"{'=' * 60}\n")

            for sug in suggestions[:20]:
                print(f"Línea {sug.line_number}: [{sug.type}]")
                print(f"  Original: {sug.original}")
                print(f"  Sugerencia: {sug.suggestion}")
                print(f"  Razón: {sug.reason}")
                print()

            if len(suggestions) > 20:
                print(f"... y {len(suggestions) - 20} sugerencias más")

            print(f"{'=' * 60}\n")
        return 0

    if args.task:
        print(f"Tarea: {args.task}")
        improver.list_templates()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
