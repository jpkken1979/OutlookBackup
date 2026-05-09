---
name: ollama-local-llm
description: "Ejecutar y gestionar LLMs localmente con Ollama: descargar modelos, API REST, integración Python/JS, RAG local, benchmarking. Sin API keys ni nube. Privacidad total."
version: "1.0.0"
risk: safe
tags: [ollama, local-llm, ia-local, llama, mistral, gemma, phi, qwen, rag, embeddings]
type: feature
---

# Ollama — LLMs Locales sin API Keys

> Ejecuta Llama 3, Mistral, Gemma, Phi, Qwen y más directamente en tu máquina.
> Sin costos. Sin datos en la nube. Control total.

---

## ¿Cuándo usar esta skill?

- Privacidad total — datos que no salen de la máquina
- Inferencia offline/sin latencia de red
- Prototipado sin costos de API
- RAG local sobre documentos privados
- Fallback cuando no hay API keys disponibles

---

## Instalación

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows — descargar de: https://ollama.com/download

# Verificar
ollama --version
```

---

## Modelos recomendados

| Modelo | Tamaño | RAM mín | Mejor para |
|---|---|---|---|
| `llama3.2:3b` | 2 GB | 8 GB | Chat rápido, prototipado |
| `llama3.1:8b` | 4.7 GB | 8 GB | Balance calidad/velocidad ✅ |
| `llama3.1:70b` | 40 GB | 64 GB | Calidad top, razonamiento |
| `mistral:7b` | 4 GB | 8 GB | Código, instrucciones |
| `codellama:7b` | 3.8 GB | 8 GB | Generación de código |
| `gemma2:9b` | 5.5 GB | 8 GB | Multilingüe |
| `phi3:mini` | 2.3 GB | 4 GB | Laptops con poca RAM |
| `qwen2.5:7b` | 4.4 GB | 8 GB | Chino + Inglés, código |
| `nomic-embed-text` | 274 MB | 4 GB | Embeddings RAG local |
| `mxbai-embed-large` | 670 MB | 4 GB | Embeddings alta calidad |

---

## Comandos esenciales

```bash
ollama pull llama3.1:8b       # Descargar modelo
ollama run llama3.1:8b        # Chat interactivo
ollama list                   # Modelos instalados
ollama rm llama3.1:8b         # Borrar modelo
ollama show llama3.1:8b       # Info del modelo
ollama ps                     # Instancias en ejecución
```

---

## API REST (compatible OpenAI)

Puerto: `http://localhost:11434`

### Chat (Python)

```python
import requests

def chat(prompt: str, model: str = "llama3.1:8b") -> str:
    """Chat simple con Ollama."""
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        },
    )
    return response.json()["message"]["content"]
```

### Drop-in replacement para OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",  # cualquier string
)

response = client.chat.completions.create(
    model="llama3.1:8b",
    messages=[{"role": "user", "content": "Hola"}],
)
print(response.choices[0].message.content)
```

### TypeScript (SDK Ollama)

```typescript
import Ollama from 'ollama';

const ollama = new Ollama({ host: 'http://localhost:11434' });

const stream = await ollama.chat({
  model: 'llama3.1:8b',
  messages: [{ role: 'user', content: 'Escribe un haiku sobre código' }],
  stream: true,
});

for await (const chunk of stream) {
  process.stdout.write(chunk.message.content);
}
```

---

## Embeddings

```python
import requests

def get_embedding(text: str, model: str = "nomic-embed-text") -> list[float]:
    response = requests.post(
        "http://localhost:11434/api/embed",
        json={"model": model, "input": text},
    )
    return response.json()["embeddings"][0]
```

---

## RAG Local — stack 100% privado

Stack: Ollama + ChromaDB + nomic-embed-text

```python
import chromadb
import requests

client = chromadb.Client()
collection = client.create_collection("docs")

def embed(text: str) -> list[float]:
    r = requests.post("http://localhost:11434/api/embed",
                      json={"model": "nomic-embed-text", "input": text})
    return r.json()["embeddings"][0]

def add_doc(doc_id: str, text: str) -> None:
    collection.add(documents=[text], embeddings=[embed(text)], ids=[doc_id])

def query_rag(question: str, top_k: int = 3) -> str:
    results = collection.query(query_embeddings=[embed(question)], n_results=top_k)
    context = "\n---\n".join(results["documents"][0])
    prompt = f"Contexto:\n{context}\n\nPregunta: {question}\nRespuesta:"
    r = requests.post("http://localhost:11434/api/chat",
                      json={"model": "llama3.1:8b",
                            "messages": [{"role": "user", "content": prompt}],
                            "stream": False})
    return r.json()["message"]["content"]
```

---

## Modelfiles — personalizar modelos

```dockerfile
FROM llama3.1:8b

SYSTEM """
Eres un asistente técnico del ecosistema Antigravity.
Responde siempre en español. Incluye código cuando sea relevante.
"""

PARAMETER temperature 0.7
PARAMETER num_ctx 4096
```

```bash
ollama create antigravity-assistant -f Modelfile
ollama run antigravity-assistant
```

---

## Integración con Antigravity — patrón de cascada

```python
import os
import requests

def get_llm_response(prompt: str) -> str:
    """Cascada: Anthropic → OpenAI → Ollama local (siempre disponible)."""
    if os.getenv("ANTHROPIC_API_KEY"):
        return anthropic_call(prompt)
    if os.getenv("OPENAI_API_KEY"):
        return openai_call(prompt)
    # Fallback final sin dependencias externas
    r = requests.post(
        "http://localhost:11434/api/chat",
        json={"model": "llama3.1:8b",
              "messages": [{"role": "user", "content": prompt}],
              "stream": False},
    )
    return r.json()["message"]["content"]
```

---

## Variables de entorno Ollama

```bash
OLLAMA_MODELS=/data/ollama/models    # Directorio de modelos
OLLAMA_HOST=0.0.0.0:11434            # Acceso red local
OLLAMA_NUM_GPU=99                    # Capas en GPU (max)
```

---

## Checklist de setup

```
[ ] Ollama instalado (ollama --version)
[ ] Modelo base descargado (ollama pull llama3.1:8b)
[ ] Embeddings descargados (ollama pull nomic-embed-text)
[ ] API accesible (curl http://localhost:11434/api/tags)
[ ] (Opcional) Modelfile con system prompt personalizado
[ ] (Opcional) ChromaDB instalado (pip install chromadb)
```

---

## Recursos

- Docs: https://ollama.com/docs
- Modelos: https://ollama.com/library
- GitHub: https://github.com/ollama/ollama

---

*Skill: ollama-local-llm — Ecosistema Antigravity — v1.0.0*
