---
type: feature
name: huggingface-paper-publisher
description: "Publica papers de investigación en HuggingFace Hub. Indexa desde arXiv, vincula modelos/datasets, reclama autoría, gestiona visibilidad. Incluye paper_manager.py CLI."
---

# HuggingFace Paper Publisher

Publica y gestiona papers de investigación en el HuggingFace Hub.

## Funcionalidades

- **Indexar papers** desde arXiv al Hub
- **Vincular** papers con modelos y datasets
- **Reclamar autoría** de papers publicados
- **Gestionar visibilidad** (público/privado)
- **Crear artículos** de investigación con templates

## Script CLI: paper_manager.py

```bash
# Indexar paper desde arXiv
python scripts/paper_manager.py index --arxiv-id 2301.12345

# Vincular paper con modelo
python scripts/paper_manager.py link \
  --paper-id 2301.12345 \
  --model username/my-model

# Vincular paper con dataset
python scripts/paper_manager.py link \
  --paper-id 2301.12345 \
  --dataset username/my-dataset

# Reclamar autoría
python scripts/paper_manager.py claim --paper-id 2301.12345

# Toggle visibilidad
python scripts/paper_manager.py toggle-visibility \
  --paper-id 2301.12345 \
  --visibility public

# Crear artículo de investigación
python scripts/paper_manager.py create \
  --template standard \
  --title "My Research Paper" \
  --output paper.md

# Convertir a formato HF
python scripts/paper_manager.py convert \
  --input paper.tex \
  --output paper.md

# Verificar paper
python scripts/paper_manager.py check --paper-id 2301.12345

# Buscar papers
python scripts/paper_manager.py search --query "transformers attention"
```

## Templates Disponibles

### Standard
Template general para papers de investigación:
```markdown
---
title: "[Título]"
authors: ["Author 1", "Author 2"]
date: "2026-03-01"
tags: ["nlp", "transformers"]
---

# Abstract
[Resumen del paper]

# 1. Introduction
[Introducción y motivación]

# 2. Related Work
[Trabajo previo relevante]

# 3. Methodology
[Descripción del método]

# 4. Experiments
[Setup experimental y resultados]

# 5. Conclusion
[Conclusiones y trabajo futuro]

# References
[Lista de referencias]
```

### Modern
Template con badges y visual elements:
```markdown
---
title: "[Título]"
thumbnail: "https://..."
badge: "🏆 Best Paper"
---
```

### arXiv Format
Compatible con formato arXiv estándar.

### ML Report
Reporte de machine learning con métricas y benchmarks.

## YAML Frontmatter para Model Cards

```yaml
---
library_name: transformers
tags:
  - text-generation
  - llm
datasets:
  - username/my-dataset
metrics:
  - accuracy
  - f1
model-index:
  - name: my-model
    results:
      - task:
          type: text-generation
        dataset:
          name: my-dataset
          type: username/my-dataset
        metrics:
          - name: Accuracy
            type: accuracy
            value: 0.95
paper: https://arxiv.org/abs/2301.12345
---
```

## YAML Frontmatter para Dataset Cards

```yaml
---
license: apache-2.0
task_categories:
  - text-classification
language:
  - en
size_categories:
  - 10K<n<100K
configs:
  - config_name: default
    data_files:
      - split: train
        path: data/train.parquet
      - split: test
        path: data/test.parquet
paper: https://arxiv.org/abs/2301.12345
---
```

## API de HuggingFace Hub

```python
from huggingface_hub import HfApi

api = HfApi()

# Buscar papers
papers = api.list_papers(query="attention mechanism")

# Obtener paper info
paper = api.paper_info("2301.12345")

# Vincular modelo con paper
api.create_model_card(
    repo_id="username/my-model",
    card_data={"paper": "https://arxiv.org/abs/2301.12345"}
)
```

## Recursos

- [HuggingFace Papers](https://huggingface.co/papers)
- [Hub Documentation](https://huggingface.co/docs/hub/)
- [huggingface_hub Python](https://huggingface.co/docs/huggingface_hub/)
