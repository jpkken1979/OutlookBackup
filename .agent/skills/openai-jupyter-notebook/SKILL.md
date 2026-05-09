---
name: openai-jupyter-notebook
description: "Crea Jupyter notebooks de calidad profesional. Dos modos: experiment (exploración) y tutorial (educativo). Incluye scaffold helper y quality checklist."
type: feature
---

# Jupyter Notebook Creator

Crea Jupyter notebooks profesionales con estructura consistente y buenas prácticas.

## Modos de Operación

### Experiment Mode
Para exploración y desarrollo iterativo:
- Hipótesis clara al inicio
- Celdas de datos, análisis, visualización
- Secciones de conclusiones parciales
- Métricas y resultados medibles

### Tutorial Mode
Para material educativo:
- Objetivos de aprendizaje definidos
- Explicaciones paso a paso
- Ejercicios interactivos
- Recursos adicionales y referencias

## Workflow

1. **Definir propósito** — ¿Experiment o tutorial?
2. **Scaffold** — Usar el helper para generar estructura base.
3. **Desarrollar contenido** — Llenar celdas con código y markdown.
4. **Ejecutar y validar** — Correr todo el notebook de principio a fin.
5. **Quality checklist** — Verificar contra la lista de calidad.

## Scaffold Helper

```bash
uv run --python 3.12 scripts/new_notebook.py \
  --mode experiment \
  --title "Fine-tuning LLM with LoRA" \
  --output notebooks/lora_experiment.ipynb
```

## Quality Checklist

- [ ] Título descriptivo en celda 1 (markdown H1)
- [ ] Descripción/resumen del notebook
- [ ] Imports agrupados en una sola celda al inicio
- [ ] Cada celda de código tiene un propósito claro
- [ ] Markdown entre secciones explicando el "por qué"
- [ ] Outputs limpios (sin warnings innecesarios)
- [ ] Visualizaciones con títulos y labels
- [ ] Notebook ejecutable de principio a fin (`Restart & Run All`)
- [ ] Conclusiones o resumen al final
- [ ] Requirements/dependencies documentados

## Estructura Recomendada

### Experiment
```
1. Title + Description
2. Setup (imports, config)
3. Data Loading
4. Exploration / EDA
5. Methodology
6. Experiments
7. Results & Metrics
8. Conclusions
```

### Tutorial
```
1. Title + Learning Objectives
2. Prerequisites
3. Setup (imports, installs)
4. Concept Introduction
5. Step-by-step Implementation
6. Exercises
7. Solutions
8. Summary + Next Steps
```

## Entorno de Ejecución

```bash
# Crear entorno
uv run --python 3.12 jupyter lab

# O con pip
pip install jupyterlab
jupyter lab
```

## Recursos

- [Jupyter Best Practices](https://jupyter.org/documentation)
- [NBFormat Spec](https://nbformat.readthedocs.io/)
