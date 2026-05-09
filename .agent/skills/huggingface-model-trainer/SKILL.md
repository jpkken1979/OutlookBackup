---
type: feature
name: huggingface-model-trainer
description: >
---
  Train and fine-tune LLMs on Hugging Face infrastructure using TRL (Transformer
  Reinforcement Learning). Supports SFT, DPO, GRPO methods with hardware selection,
  cost estimation, and GGUF conversion. Use when training or fine-tuning models.
source: Hugging Face
---

# HuggingFace Model Trainer

Fine-tune language models using TRL on Hugging Face Jobs infrastructure.

## Training Methods

### SFT (Supervised Fine-Tuning)
Standard supervised training on instruction-response pairs.

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["trl>=0.17", "transformers", "datasets", "accelerate", "torch", "peft"]
# ///
from trl import SFTConfig, SFTTrainer
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import load_dataset

model_id = "meta-llama/Llama-3.1-8B"
dataset = load_dataset("trl-lib/Capybara", split="train")
tokenizer = AutoTokenizer.from_pretrained(model_id)

training_args = SFTConfig(
    output_dir="output",
    num_train_epochs=1,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-5,
    logging_steps=10,
    push_to_hub=True,
    hub_model_id="my-username/my-sft-model",
)

trainer = SFTTrainer(
    model=model_id,
    args=training_args,
    train_dataset=dataset,
    processing_class=tokenizer,
)
trainer.train()
trainer.push_to_hub()
```

### DPO (Direct Preference Optimization)
Train from preference pairs (chosen/rejected).

```python
from trl import DPOConfig, DPOTrainer

training_args = DPOConfig(
    output_dir="output",
    num_train_epochs=1,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    learning_rate=5e-7,
    beta=0.1,  # DPO temperature
    logging_steps=10,
    push_to_hub=True,
)

trainer = DPOTrainer(
    model=model_id,
    args=training_args,
    train_dataset=dataset,  # Must have "chosen" and "rejected" columns
    processing_class=tokenizer,
)
trainer.train()
```

### GRPO (Group Relative Policy Optimization)
Reward-model-free RL with group-based scoring.

```python
from trl import GRPOConfig, GRPOTrainer

training_args = GRPOConfig(
    output_dir="output",
    num_train_epochs=1,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    learning_rate=1e-6,
    num_generations=4,
    logging_steps=10,
    push_to_hub=True,
)

def reward_fn(completions: list[str], **kwargs) -> list[float]:
    """Custom reward function for GRPO."""
    return [len(c.split()) / 100.0 for c in completions]

trainer = GRPOTrainer(
    model=model_id,
    args=training_args,
    train_dataset=dataset,
    reward_funcs=reward_fn,
    processing_class=tokenizer,
)
trainer.train()
```

## Hardware Selection

| Hardware | VRAM | Best For | Cost/hr |
|----------|------|----------|---------|
| `t4-small` | 1× T4 16GB | Small models, testing | ~$0.60 |
| `l4x1` | 1× L4 24GB | ≤7B SFT with QLoRA | ~$0.80 |
| `l4x4` | 4× L4 96GB | 7-13B SFT | ~$3.20 |
| `a10g-large` | 1× A10G 24GB | ≤13B inference/light train | ~$1.10 |
| `a100-large` | 1× A100 80GB | 7-13B full fine-tune | ~$4.00 |
| `8-a100-80` | 8× A100 640GB | 70B+ models | ~$32.00 |
| `h100x1` | 1× H100 80GB | Fast single-GPU training | ~$5.50 |
| `h100x8` | 8× H100 640GB | 70B+ with max speed | ~$44.00 |

## PEFT / LoRA Configuration

```python
from peft import LoraConfig

lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

trainer = SFTTrainer(
    model=model_id,
    args=training_args,
    train_dataset=dataset,
    peft_config=lora_config,
    processing_class=tokenizer,
)
```

## Launching on HF Jobs

```bash
# Via CLI
huggingface-cli jobs run \
  --hardware h100x1 \
  --script train.py \
  --secrets HF_TOKEN

# Monitor
huggingface-cli jobs logs <job-id> --follow
huggingface-cli jobs status <job-id>
```

## GGUF Conversion (for llama.cpp)

```bash
# After training, convert to GGUF
pip install llama-cpp-python
python -m llama_cpp.convert \
  --model output/final \
  --outtype q4_k_m \
  --outfile model.Q4_K_M.gguf
```

## Cost Estimation Formula

```
Total Cost ≈ (training_hours × hardware_cost_per_hour)
training_hours ≈ (dataset_tokens / (tokens_per_second × batch_size × num_gpus))
```

| Model Size | Method | Hardware | ~Time (10K samples) | ~Cost |
|-----------|--------|----------|---------------------|-------|
| 7B | SFT LoRA | L4×1 | 2-4h | $2-4 |
| 7B | SFT Full | A100×1 | 4-8h | $16-32 |
| 13B | DPO LoRA | A100×1 | 6-12h | $24-48 |
| 70B | SFT LoRA | H100×8 | 8-16h | $350-700 |

## Dataset Requirements

| Method | Required Columns |
|--------|-----------------|
| SFT | `messages` (list of role/content dicts) or `text` |
| DPO | `prompt`, `chosen`, `rejected` |
| GRPO | `prompt` (reward function provides scores) |

## Monitoring with Trackio

```python
# Add to training script
import trackio

trackio.init(project="my-training", run="sft-v1")

# TRL integrates automatically when trackio is initialized
trainer.train()

# Or log manually
trackio.log({"loss": 0.5, "learning_rate": 2e-5})
```
