---
type: feature
name: huggingface-evaluation
description: >
---
  Evaluate LLMs and manage model card evaluation tables. Supports lighteval,
  inspect-ai, vLLM backend, Artificial Analysis import, and Hugging Face Jobs
  for scalable evaluation. Use when evaluating model quality or benchmarks.
source: Hugging Face
---

# HuggingFace Model Evaluation

Evaluate language models and manage evaluation results in model cards.

## Evaluation Table Management

### Inspect Existing Tables
```bash
# View current eval tables in a model card
# Uses inspect-tables tool
hf eval inspect-tables <model-id>
```

### Extract from README
```bash
# Parse evaluation results from model card README
hf eval extract-readme <model-id>
```

### Import from Artificial Analysis
```python
import requests

# Fetch benchmark data from Artificial Analysis
url = "https://artificialanalysis.ai/api/v1/models"
response = requests.get(url)
benchmarks = response.json()

# Map to HF model cards
for model in benchmarks:
    print(f"{model['name']}: {model['scores']}")
```

## Running Evaluations

### With lighteval

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["lighteval[vllm]>=0.8", "transformers", "datasets"]
# ///
from lighteval.main import main as lighteval_main

# Evaluate with vLLM backend for speed
lighteval_main([
    "vllm",
    "--model", "meta-llama/Llama-3.1-8B-Instruct",
    "--tasks", "leaderboard|mmlu|5,leaderboard|arc:challenge|25",
    "--output-dir", "./eval-results",
    "--push-to-hub", "true",
    "--hub-results-org", "my-username",
])
```

### With inspect-ai

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["inspect-ai>=0.3", "transformers"]
# ///
from inspect_ai import Task, eval
from inspect_ai.dataset import hf_dataset
from inspect_ai.scorer import model_graded_fact
from inspect_ai.solver import generate, system_message

task = Task(
    dataset=hf_dataset("cais/mmlu", "all", split="test"),
    plan=[
        system_message("Answer the question accurately."),
        generate(),
    ],
    scorer=model_graded_fact(),
)

results = eval(task, model="hf/meta-llama/Llama-3.1-8B-Instruct")
```

### On HF Jobs (Scalable)

```bash
# Run evaluation on HF infrastructure
huggingface-cli jobs run \
  --hardware l4x1 \
  --script eval.py \
  --secrets HF_TOKEN
```

## Standard Benchmarks

| Benchmark | Tasks | Metric | Description |
|-----------|-------|--------|-------------|
| MMLU | 57 subjects | Accuracy | General knowledge |
| ARC-C | Challenge set | Accuracy | Science reasoning |
| HellaSwag | 10K | Accuracy | Commonsense NLI |
| TruthfulQA | 817 | MC accuracy | Truthfulness |
| WinoGrande | 1.2K | Accuracy | Coreference |
| GSM8K | 8.5K | Accuracy | Math word problems |
| HumanEval | 164 | pass@1 | Code generation |

## Evaluation Table Format (Model Card)

```yaml
# Add to model card metadata
model-index:
  - name: my-model
    results:
      - task:
          type: text-generation
          name: Text Generation
        dataset:
          type: cais/mmlu
          name: MMLU
          config: all
          split: test
        metrics:
          - type: accuracy
            value: 0.75
            name: accuracy
            verified: false
      - task:
          type: text-generation
        dataset:
          type: openai/gsm8k
          name: GSM8K
          split: test
        metrics:
          - type: accuracy
            value: 0.82
```

## Custom Evaluation

```python
from datasets import load_dataset
from transformers import pipeline

# Load model
pipe = pipeline("text-generation", model="my-model", device_map="auto")

# Load eval dataset
dataset = load_dataset("my-eval-dataset", split="test")

correct = 0
total = len(dataset)

for sample in dataset:
    output = pipe(sample["prompt"], max_new_tokens=256, temperature=0.0)
    predicted = output[0]["generated_text"]
    if sample["expected"] in predicted:
        correct += 1

accuracy = correct / total
print(f"Accuracy: {accuracy:.2%}")
```

## Cost Estimation for Evals

| Model Size | Hardware | Benchmark Suite | ~Time | ~Cost |
|-----------|----------|----------------|-------|-------|
| 7B | L4×1 | MMLU (57 subjects) | 1-2h | $1-2 |
| 13B | L4×1 | Full Open LLM Leaderboard | 4-8h | $4-8 |
| 70B | A100×1 | MMLU only | 4-6h | $16-24 |
| 70B | H100×1 | Full suite | 12-24h | $66-132 |
