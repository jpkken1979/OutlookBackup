---
type: feature
name: huggingface-tool-builder
description: >
---
  Build reusable CLI scripts and tools for the Hugging Face API. Create composable
  shell/Python scripts for model management, dataset operations, and Hub interactions.
  Use when building HF API automation or CLI workflows.
source: Hugging Face
---

# HuggingFace Tool Builder

Create reusable, composable CLI tools for Hugging Face Hub operations.

## Design Principles

1. **Single responsibility** — one tool, one job
2. **Composable** — tools pipe into each other via stdin/stdout
3. **Auth via env** — use `HF_TOKEN` environment variable
4. **PEP 723** — inline script metadata for `uv run`

## PEP 723 Script Template

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["huggingface_hub>=0.25"]
# ///
"""Tool description — one sentence."""

import argparse
import sys
from huggingface_hub import HfApi

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_id", help="HF repo ID (user/model)")
    args = parser.parse_args()

    api = HfApi()
    # Tool logic here
    result = api.model_info(args.repo_id)
    print(result)

if __name__ == "__main__":
    main()
```

## Common Tool Patterns

### List Models by Author
```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["huggingface_hub>=0.25"]
# ///
"""List all models by a given author."""

import argparse
import json
from huggingface_hub import HfApi

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("author", help="HF username or organization")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    api = HfApi()
    models = api.list_models(author=args.author, limit=args.limit)

    for model in models:
        if args.as_json:
            print(json.dumps({"id": model.id, "downloads": model.downloads}))
        else:
            print(f"{model.id}\t{model.downloads:,} downloads")

if __name__ == "__main__":
    main()
```

### Download Model Files
```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["huggingface_hub>=0.25"]
# ///
"""Download specific files from a model repo."""

import argparse
from huggingface_hub import hf_hub_download

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_id")
    parser.add_argument("filename")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--local-dir", default=".")
    args = parser.parse_args()

    path = hf_hub_download(
        repo_id=args.repo_id,
        filename=args.filename,
        revision=args.revision,
        local_dir=args.local_dir,
    )
    print(path)

if __name__ == "__main__":
    main()
```

### Upload Files
```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["huggingface_hub>=0.25"]
# ///
"""Upload a file or folder to a HF repo."""

import argparse
from pathlib import Path
from huggingface_hub import HfApi

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_id")
    parser.add_argument("path", type=Path)
    parser.add_argument("--repo-type", default="model", choices=["model", "dataset", "space"])
    parser.add_argument("--path-in-repo", default=None)
    args = parser.parse_args()

    api = HfApi()

    if args.path.is_dir():
        api.upload_folder(
            repo_id=args.repo_id,
            folder_path=str(args.path),
            repo_type=args.repo_type,
        )
    else:
        api.upload_file(
            repo_id=args.repo_id,
            path_or_fileobj=str(args.path),
            path_in_repo=args.path_in_repo or args.path.name,
            repo_type=args.repo_type,
        )

    print(f"Uploaded to {args.repo_id}")

if __name__ == "__main__":
    main()
```

## Composable Pipeline Example

```bash
# List models → filter → download configs
uv run list_models.py my-org --json \
  | jq -r '.id' \
  | while read model; do
      uv run download_file.py "$model" config.json --local-dir ./configs/
    done
```

## HF CLI Reference

```bash
# Auth
huggingface-cli login
huggingface-cli whoami

# Repos
huggingface-cli repo create my-model
huggingface-cli repo info user/model
huggingface-cli repo list user

# Upload / Download
huggingface-cli upload user/model ./local_folder
huggingface-cli download user/model --local-dir ./output

# Cache
huggingface-cli cache scan
huggingface-cli cache delete --all

# Jobs (training)
huggingface-cli jobs run --hardware l4x1 --script train.py
huggingface-cli jobs logs <job-id> --follow
huggingface-cli jobs status <job-id>
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `HF_TOKEN` | Authentication token |
| `HF_HOME` | Cache directory (default: `~/.cache/huggingface`) |
| `HF_HUB_OFFLINE` | Set to `1` for offline mode |
| `HF_HUB_DISABLE_TELEMETRY` | Set to `1` to disable telemetry |
