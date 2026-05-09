---
type: feature
name: huggingface-datasets
description: >
---
  Create, curate, and query Hugging Face datasets using DuckDB SQL via hf://
  protocol. Supports multiple formats (chat, QA, classification, tabular) with
  templates and dataset lifecycle management. Use when working with HF datasets.
source: Hugging Face
---

# HuggingFace Datasets

Create, query, and manage datasets on the Hugging Face Hub.

## SQL Querying with DuckDB

Query any HF dataset directly using SQL via the `hf://` protocol:

```sql
-- Install and load HF extension
INSTALL httpfs;
LOAD httpfs;

-- Query a dataset directly from HF Hub
SELECT *
FROM 'hf://datasets/squad/plain_text/train.parquet'
LIMIT 10;

-- Aggregate queries
SELECT
  COUNT(*) as total,
  AVG(LENGTH(context)) as avg_context_len
FROM 'hf://datasets/squad/plain_text/train.parquet';

-- Filter and transform
SELECT question, context, answers
FROM 'hf://datasets/squad/plain_text/train.parquet'
WHERE LENGTH(question) > 50
ORDER BY LENGTH(context) DESC
LIMIT 100;
```

```python
# Python DuckDB usage
import duckdb

conn = duckdb.connect()
conn.execute("INSTALL httpfs; LOAD httpfs;")

df = conn.sql("""
    SELECT *
    FROM 'hf://datasets/tatsu-lab/alpaca/data/train-00000-of-00001.parquet'
    WHERE LENGTH(output) > 100
    LIMIT 1000
""").df()
```

## Dataset Creation

### Chat / Instruction Format
```python
from datasets import Dataset

data = {
    "messages": [
        [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language..."},
        ],
        [
            {"role": "user", "content": "Explain recursion"},
            {"role": "assistant", "content": "Recursion is when a function calls itself..."},
        ],
    ]
}

dataset = Dataset.from_dict(data)
dataset.push_to_hub("my-username/my-chat-dataset")
```

### Classification Format
```python
data = {
    "text": ["Great product!", "Terrible experience", "It was okay"],
    "label": [2, 0, 1],  # positive, negative, neutral
}

dataset = Dataset.from_dict(data)
dataset.push_to_hub("my-username/my-classification-dataset")
```

### Question-Answering Format
```python
data = {
    "question": ["What is the capital of France?"],
    "context": ["France is a country in Europe. Its capital is Paris."],
    "answers": [{"text": ["Paris"], "answer_start": [50]}],
}

dataset = Dataset.from_dict(data)
dataset.push_to_hub("my-username/my-qa-dataset")
```

### Preference / DPO Format
```python
data = {
    "prompt": ["Explain quantum computing"],
    "chosen": ["Quantum computing uses quantum bits (qubits)..."],
    "rejected": ["Quantum computing is about fast computers..."],
}

dataset = Dataset.from_dict(data)
dataset.push_to_hub("my-username/my-preference-dataset")
```

### Tabular / CSV Import
```python
from datasets import load_dataset

# From CSV
dataset = load_dataset("csv", data_files="data.csv")
dataset.push_to_hub("my-username/my-tabular-dataset")

# From JSON
dataset = load_dataset("json", data_files="data.jsonl")
dataset.push_to_hub("my-username/my-json-dataset")

# From Pandas DataFrame
import pandas as pd
df = pd.read_csv("data.csv")
dataset = Dataset.from_pandas(df)
dataset.push_to_hub("my-username/my-pandas-dataset")
```

## Dataset Lifecycle

### Validation
```python
from datasets import load_dataset

dataset = load_dataset("my-username/my-dataset")

# Check structure
print(dataset)
print(dataset["train"].features)
print(dataset["train"][0])

# Validate chat format
for i, example in enumerate(dataset["train"]):
    messages = example["messages"]
    assert isinstance(messages, list), f"Row {i}: messages must be a list"
    for msg in messages:
        assert "role" in msg and "content" in msg, f"Row {i}: invalid message"
        assert msg["role"] in ("system", "user", "assistant"), f"Row {i}: invalid role"
```

### Preprocessing
```python
def clean_dataset(example):
    """Clean and normalize a dataset example."""
    messages = example["messages"]
    cleaned = []
    for msg in messages:
        content = msg["content"].strip()
        if content:  # Remove empty messages
            cleaned.append({"role": msg["role"], "content": content})
    return {"messages": cleaned}

dataset = dataset.map(clean_dataset)
dataset = dataset.filter(lambda x: len(x["messages"]) >= 2)
```

### Splitting
```python
# Create train/test split
dataset = dataset["train"].train_test_split(test_size=0.1, seed=42)
dataset.push_to_hub("my-username/my-dataset")
```

## Dataset Card Template

```yaml
---
license: mit
task_categories:
  - text-generation
language:
  - en
size_categories:
  - 1K<n<10K
tags:
  - chat
  - instruction-tuning
---

# My Dataset

## Description
Brief description of the dataset.

## Format
Chat format with `messages` column containing role/content pairs.

## Usage
```python
from datasets import load_dataset
dataset = load_dataset("my-username/my-dataset")
```

## Statistics
- Total examples: X
- Average conversation length: Y turns
- Languages: English
```

## CLI Operations

```bash
# Upload dataset
huggingface-cli upload my-username/my-dataset ./data

# Download dataset
huggingface-cli download my-username/my-dataset

# Dataset info
huggingface-cli repo info my-username/my-dataset --repo-type dataset
```
