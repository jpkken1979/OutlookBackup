#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "google-genai>=1.0.0",
#     "requests",
#     "pillow",
# ]
# ///
"""
Generate images using Google Gemini or HuggingFace (FLUX, SDXL) — free alternatives included.

Providers:
  Gemini (GEMINI_API_KEY required, billing required for image models):
    nanobanana     - gemini-2.5-flash-image (the original "Nano Banana" model)
    nanobanana-pro - gemini-3-pro-image-preview
    flash          - gemini-3.1-flash-image-preview
    exp            - gemini-2.0-flash-exp-image-generation

  HuggingFace (HF_TOKEN optional, truly free):
    flux-schnell   - FLUX.1-schnell (fast, Apache 2.0, recommended)
    sdxl           - Stable Diffusion XL Base 1.0

Usage:
    uv run image.py --prompt "A colorful abstract pattern" --output "./hero.png"
    uv run image.py --prompt "Minimalist icon" --output "./icon.png" --model flux-schnell
    uv run image.py --prompt "Hero image" --output "./hero.png" --model nanobanana --aspect landscape
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request

GEMINI_MODELS: dict[str, str] = {
    "nanobanana": "gemini-2.5-flash-image",
    "nanobanana-pro": "gemini-3-pro-image-preview",
    "flash": "gemini-3.1-flash-image-preview",
    "exp": "gemini-2.0-flash-exp-image-generation",
}

HF_MODELS: dict[str, str] = {
    "flux-schnell": "black-forest-labs/FLUX.1-schnell",
    "sdxl": "stabilityai/stable-diffusion-xl-base-1.0",
}

ALL_MODELS = {**GEMINI_MODELS, **HF_MODELS}

ASPECT_SIZES: dict[str, tuple[int, int]] = {
    "square": (1024, 1024),
    "landscape": (1280, 720),
    "portrait": (720, 1280),
}


def save_image(image_bytes: bytes, output_path: str) -> None:
    """Save image bytes to disk, creating parent dirs if needed."""
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(image_bytes)
    size_kb = len(image_bytes) // 1024
    print(f"Imagen guardada en: {output_path} ({size_kb} KB)")


def generate_with_gemini(
    prompt: str,
    output_path: str,
    model_id: str,
) -> None:
    """Generate image using Google Gemini API."""
    try:
        from google import genai  # type: ignore[import-untyped]
        from google.genai import types  # type: ignore[import-untyped]
    except ImportError:
        print("Error: google-genai no instalado. Usar: uv run image.py", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY no configurada.", file=sys.stderr)
        print("Obtener en: https://aistudio.google.com/apikey", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            print(
                "\nError: Cuota agotada (429). Los modelos de imagen Gemini requieren billing.",
                file=sys.stderr,
            )
            print("Activar en: https://console.cloud.google.com/billing", file=sys.stderr)
            print(
                "Alternativa gratuita: --model flux-schnell (no requiere API key)", file=sys.stderr
            )
        elif "404" in err or "NOT_FOUND" in err:
            print(f"\nError: Modelo '{model_id}' no encontrado.", file=sys.stderr)
        else:
            print(f"\nError Gemini: {e}", file=sys.stderr)
        sys.exit(1)

    image_bytes = None
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            image_bytes = base64.b64decode(part.inline_data.data)
            break

    if image_bytes is None:
        print("Error: la respuesta de Gemini no contiene imagen.", file=sys.stderr)
        sys.exit(1)

    save_image(image_bytes, output_path)


def generate_with_huggingface(
    prompt: str,
    output_path: str,
    model_id: str,
    width: int,
    height: int,
) -> None:
    """Generate image using HuggingFace Inference API (free, no billing required)."""
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")

    # HuggingFace migró a router.huggingface.co (requiere HF_TOKEN)
    if not hf_token:
        print("Error: HF_TOKEN requerido para HuggingFace.", file=sys.stderr)
        print("Token gratis en: https://huggingface.co/settings/tokens", file=sys.stderr)
        print("Luego: export HF_TOKEN=hf_...", file=sys.stderr)
        sys.exit(1)

    url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {hf_token}",
    }

    payload = json.dumps(
        {
            "inputs": prompt,
            "parameters": {
                "width": width,
                "height": height,
            },
        }
    ).encode("utf-8")

    # Reintentar hasta 3 veces si el modelo está cargando (503)
    for attempt in range(3):
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                image_bytes = resp.read()
                save_image(image_bytes, output_path)
                return
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 503:
                try:
                    data = json.loads(body)
                    wait = min(int(data.get("estimated_time", 20)), 30)
                except (json.JSONDecodeError, ValueError):
                    wait = 20
                print(f"Modelo cargando (intento {attempt + 1}/3), esperando {wait}s...")
                time.sleep(wait)
                continue
            elif e.code == 401:
                print("\nError: HF_TOKEN inválido o expirado.", file=sys.stderr)
                print(
                    "Obtener token gratis en: https://huggingface.co/settings/tokens",
                    file=sys.stderr,
                )
                sys.exit(1)
            elif e.code == 429:
                print(
                    "\nError: Rate limit alcanzado. Configura HF_TOKEN para más requests.",
                    file=sys.stderr,
                )
                print("Token gratis en: https://huggingface.co/settings/tokens", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"\nError HuggingFace {e.code}: {body[:300]}", file=sys.stderr)
                sys.exit(1)

    print(
        "Error: el modelo no respondió después de 3 intentos. Reintenta en unos minutos.",
        file=sys.stderr,
    )
    sys.exit(1)


def generate_image(
    prompt: str,
    output_path: str,
    aspect: str = "square",
    model: str = "flux-schnell",
    width: int | None = None,
    height: int | None = None,
) -> None:
    """Generate an image and save to output_path."""
    w, h = ASPECT_SIZES.get(aspect, ASPECT_SIZES["square"])
    if width:
        w = width
    if height:
        h = height

    if model in GEMINI_MODELS:
        model_id = GEMINI_MODELS[model]
        print(f"Proveedor: Gemini | Modelo: {model} ({model_id})")
        print(f"Tamaño: {w}x{h} | Generando...")
        generate_with_gemini(prompt, output_path, model_id)
    elif model in HF_MODELS:
        model_id = HF_MODELS[model]
        print(f"Proveedor: HuggingFace | Modelo: {model} ({model_id})")
        print(f"Tamaño: {w}x{h} | Generando...")
        generate_with_huggingface(prompt, output_path, model_id, w, h)
    else:
        print(f"Error: modelo '{model}' no reconocido.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Entry point para generación de imágenes."""
    parser = argparse.ArgumentParser(
        description="Genera imágenes con Gemini o HuggingFace FLUX/SDXL"
    )
    parser.add_argument("--prompt", required=True, help="Descripción de la imagen")
    parser.add_argument("--output", required=True, help="Ruta de salida (PNG/JPG)")
    parser.add_argument(
        "--aspect",
        choices=["square", "landscape", "portrait"],
        default="square",
        help="Ratio de aspecto: square (1024x1024), landscape (1280x720), portrait (720x1280)",
    )
    parser.add_argument(
        "--model",
        choices=list(ALL_MODELS.keys()),
        default="flux-schnell",
        help=(
            "Modelo (default: flux-schnell). "
            "Gratis: flux-schnell, sdxl. "
            "Requiere billing: nanobanana, nanobanana-pro, flash, exp"
        ),
    )
    parser.add_argument("--width", type=int, help="Ancho personalizado en píxeles")
    parser.add_argument("--height", type=int, help="Alto personalizado en píxeles")

    args = parser.parse_args()
    generate_image(
        prompt=args.prompt,
        output_path=args.output,
        aspect=args.aspect,
        model=args.model,
        width=args.width,
        height=args.height,
    )


if __name__ == "__main__":
    main()
