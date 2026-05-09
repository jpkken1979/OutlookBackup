---
type: feature
name: huggingface-trackio
description: >
---
  Track ML experiments with Trackio — log metrics during training, retrieve
  results via CLI, and sync to Hugging Face Spaces for visualization.
  Use when monitoring training runs or managing experiment histories.
source: Hugging Face
---

# HuggingFace Trackio

Lightweight experiment tracking for ML training runs.

## Quick Start

```python
import trackio

# Initialize a project and run
trackio.init(project="my-project", run="sft-experiment-v1")

# Log metrics during training
for step in range(1000):
    loss = train_step()
    trackio.log({
        "loss": loss,
        "learning_rate": scheduler.get_last_lr()[0],
        "step": step,
    })

# Finish the run
trackio.finish()
```

## Integration with TRL

Trackio integrates automatically with TRL trainers:

```python
from trl import SFTConfig, SFTTrainer
import trackio

# Initialize tracking before training
trackio.init(project="fine-tuning", run="llama-sft-v2")

training_args = SFTConfig(
    output_dir="output",
    logging_steps=10,
    report_to=["trackio"],  # Enable trackio reporting
)

trainer = SFTTrainer(
    model=model_id,
    args=training_args,
    train_dataset=dataset,
    processing_class=tokenizer,
)

trainer.train()
trackio.finish()
```

## Python API

### Logging

```python
import trackio

trackio.init(project="my-project", run="run-001")

# Log scalar metrics
trackio.log({"loss": 0.5, "accuracy": 0.85})

# Log with step
trackio.log({"loss": 0.3}, step=100)

# Log hyperparameters
trackio.config({
    "model": "llama-3.1-8b",
    "learning_rate": 2e-5,
    "batch_size": 4,
    "method": "sft",
    "lora_rank": 16,
})

# Log a summary metric
trackio.summary({"final_loss": 0.1, "total_steps": 5000})

trackio.finish()
```

### Retrieving Results

```python
import trackio

# Get all runs for a project
runs = trackio.get_runs("my-project")
for run in runs:
    print(f"{run.name}: loss={run.summary.get('final_loss')}")

# Get specific run history
history = trackio.get_history("my-project", "run-001")
for entry in history:
    print(f"Step {entry['step']}: loss={entry['loss']}")
```

## CLI Usage

```bash
# List projects
trackio list

# List runs in a project
trackio list my-project

# Show run details
trackio show my-project/run-001

# Export run data
trackio export my-project/run-001 --format csv > metrics.csv
trackio export my-project/run-001 --format json > metrics.json

# Compare runs
trackio compare my-project/run-001 my-project/run-002
```

## Syncing to HF Spaces

```python
import trackio

# Sync project dashboard to a HF Space
trackio.sync_to_hub(
    project="my-project",
    space_id="my-username/my-training-dashboard",
)
```

```bash
# Via CLI
trackio sync my-project --space my-username/my-training-dashboard
```

## Context Manager Pattern

```python
import trackio

with trackio.Run(project="my-project", run="experiment-3") as run:
    run.config({"model": "llama-8b", "lr": 2e-5})

    for step in range(1000):
        loss = train_step()
        run.log({"loss": loss, "step": step})

    run.summary({"final_loss": loss})
# Automatically calls finish()
```

## Best Practices

1. **Always call `trackio.finish()`** — or use context manager
2. **Log config first** — hyperparameters at start of run
3. **Use consistent metric names** — enables cross-run comparison
4. **Log at regular intervals** — match `logging_steps` in training config
5. **Add summary metrics** — final values for quick comparison
6. **Name runs descriptively** — `sft-llama8b-lr2e5-lora16` not `run-001`
