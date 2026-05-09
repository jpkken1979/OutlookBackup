---
name: fal-image-edit
description: "AI-powered image editing API providing style transfer, object removal, inpainting, and content-aware editing. Integrates with Fal AI serverless GPU endpoints for fast processing. Use when removing unwanted objects from images, applying artistic styles, inpainting missing regions, enhancing photos, editing product images, or building AI-powered image manipulation tools."
type: feature
source: "https://github.com/fal-ai-community/skills/blob/main/skills/claude.ai/fal-image-edit/SKILL.md"
risk: safe
user-invocable: true
---

# Fal AI Image Editing

Harness GPU-powered AI models for fast, high-quality image transformations without managing infrastructure.

## Core Capabilities

### 1. Object Removal (Inpainting)

Remove unwanted elements from images with content-aware fill:

```
Input: Photo with person in background
Mask: Paint area to remove
Output: Background filled naturally (no visible seams)
```

**Use cases**:
- Remove photobombers from vacation photos
- Clean up product photography (remove background clutter)
- Remove text or logos from images
- Erase temporary objects (poles, people, vehicles)

### 2. Style Transfer

Apply artistic styles, photographs, or visual themes to images:

```
Input: Your photo
Style source: Picasso painting, anime art, vintage photo
Output: Your photo in that style
```

**Use cases**:
- Convert photos to artwork
- Apply consistent brand styling across images
- Create variations of a design
- Convert photos to different eras/aesthetics

### 3. Image Inpainting

Fill in missing or masked regions with AI-generated content:

```
Input: Image with masked area
Prompt: Describe what should appear
Output: Masked region filled contextually
```

**Use cases**:
- Fix damaged photos
- Extend images beyond original boundaries
- Remove watermarks or text
- Replace backgrounds

## API Integration

### Setup

```python
import requests
from PIL import Image
import base64

# Get API key from https://www.fal.ai/dashboard
API_KEY = "your_fal_api_key"
```

### Basic Workflow: Remove Object

```python
def remove_object(image_path: str, mask_path: str) -> Image:
    """Remove unwanted object via inpainting."""

    # 1. Load and encode images
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode()
    with open(mask_path, 'rb') as f:
        mask_data = base64.b64encode(f.read()).decode()

    # 2. Call Fal API
    response = requests.post(
        "https://fal.run/fal-ai/inpainting",
        headers={"Authorization": f"Key {API_KEY}"},
        json={
            "image_url": f"data:image/png;base64,{image_data}",
            "mask_url": f"data:image/png;base64,{mask_data}",
            "prompt": "fill naturally, high quality"
        }
    )

    # 3. Get result
    result = response.json()
    return Image.open(requests.get(result['image_url'], stream=True).raw)
```

### Workflow: Apply Style Transfer

```python
def apply_style(image_path: str, style: str) -> Image:
    """Apply artistic style to image."""

    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode()

    response = requests.post(
        "https://fal.run/fal-ai/style-transfer",
        headers={"Authorization": f"Key {API_KEY}"},
        json={
            "image_url": f"data:image/png;base64,{image_data}",
            "style": style  # e.g., "oil painting", "anime", "vintage"
        }
    )

    result = response.json()
    return Image.open(requests.get(result['image_url'], stream=True).raw)
```

## Configuration Options

| Parameter | Type | Effect |
|-----------|------|--------|
| `image_url` / `image_file` | URL or bytes | Source image (JPEG, PNG, WebP) |
| `mask_url` / `mask_file` | URL or bytes | White = fill, black = keep (for inpainting) |
| `prompt` | string | Description of desired fill (inpainting) |
| `strength` | float (0-1) | Style transfer intensity (default 0.7) |
| `guidance_scale` | int (1-20) | Follow prompt more strictly (default 7.5) |

## Performance Characteristics

| Operation | GPU Time | Total | Cost |
|-----------|----------|-------|------|
| Object removal | 2-5s | 3-6s | ~$0.01 |
| Style transfer | 3-8s | 4-9s | ~$0.02 |
| Inpainting (complex) | 5-15s | 6-16s | ~$0.03 |

**Bottleneck**: Network latency (upload + download), not model inference.

## Best Practices

### Quality Tips

1. **Mask precision**: Clean edges on mask = better inpainting
2. **Prompt clarity**: "Remove person" works; "remove person better" doesn't help
3. **Image resolution**: 512x512 → 1024x1024 (larger = slower + expensive)
4. **Content context**: Model fills based on surrounding pixels; provide enough context

### Cost Optimization

```python
# Resize before upload (reduces cost)
def optimize_for_api(image_path: str, max_dim: int = 768) -> str:
    img = Image.open(image_path)
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
        img.save("optimized.png")
        return "optimized.png"
    return image_path
```

### Error Handling

```python
def call_api_with_retry(url: str, payload: dict, retries: int = 3):
    for attempt in range(retries):
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

## Use Cases & Examples

| Use Case | Technique | Prompt/Config |
|----------|-----------|---------------|
| Remove person | Inpainting | Mask person, prompt: "fill background" |
| Artistic version | Style transfer | Style: "watercolor painting" |
| Background replacement | Inpainting | Mask background, describe new style |
| Product cleanup | Inpainting | Mask shadows/reflections, "studio lighting" |
| Photo restoration | Inpainting | Mask damaged area, "high quality detail" |

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Poor quality fill | Weak context in image | Provide more surrounding context, tighter mask |
| Style not applied | Mismatched style name | Check available styles in API docs |
| Timeout | Large image or slow network | Reduce resolution or increase timeout |
| API errors | Invalid API key or quota exceeded | Check dashboard, verify credits |

See [Fal AI documentation](https://www.fal.ai/docs) for advanced features and community models.
