#!/usr/bin/env python3
"""
Image Processing Patterns Demo

Este script demuestra patrones de procesamiento de imágenes incluyendo:
- Validación de imágenes
- Metadatos
- Pipeline de procesamiento
- Simulación de operaciones (resize, crop, compress)

Uso:
    python image_demo.py --demo validate
    python image_demo.py --demo pipeline
    python image_demo.py --image path/to/image.jpg
"""

import argparse
import logging
from dataclasses import dataclass, field
from enum import Enum

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class ImageFormat(Enum):
    """Formatos de imagen soportados."""

    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"
    GIF = "gif"
    AVIF = "avif"
    UNKNOWN = "unknown"


@dataclass
class ImageMetadata:
    """Metadatos de imagen."""

    width: int
    height: int
    format: ImageFormat
    file_size: int
    color_space: str = "RGB"
    has_alpha: bool = False
    bit_depth: int = 8


@dataclass
class ValidationResult:
    """Resultado de validación."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: ImageMetadata | None = None


@dataclass
class ProcessedImage:
    """Imagen procesada."""

    original_size: int
    processed_size: int
    format: ImageFormat
    width: int
    height: int
    operations: list[str] = field(default_factory=list)

    @property
    def compression_ratio(self) -> float:
        if self.original_size == 0:
            return 0
        return 1 - (self.processed_size / self.original_size)


class ImageValidator:
    """Validador de imágenes."""

    # Configuración de validación
    MIN_WIDTH = 100
    MIN_HEIGHT = 100
    MAX_WIDTH = 10000
    MAX_HEIGHT = 10000
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_FORMATS = [ImageFormat.JPEG, ImageFormat.PNG, ImageFormat.WEBP, ImageFormat.GIF]
    MIN_ASPECT_RATIO = 0.1
    MAX_ASPECT_RATIO = 10.0

    def validate(self, metadata: ImageMetadata, file_size: int) -> ValidationResult:
        """Validar imagen según reglas."""
        errors = []
        warnings = []

        # Validar formato
        if metadata.format not in self.ALLOWED_FORMATS:
            errors.append(f"Formato no permitido: {metadata.format.value}")

        # Validar dimensiones mínimas
        if metadata.width < self.MIN_WIDTH or metadata.height < self.MIN_HEIGHT:
            errors.append(
                f"Imagen muy pequeña: {metadata.width}x{metadata.height} (mín: {self.MIN_WIDTH}x{self.MIN_HEIGHT})"
            )

        # Validar dimensiones máximas
        if metadata.width > self.MAX_WIDTH or metadata.height > self.MAX_HEIGHT:
            errors.append(
                f"Imagen muy grande: {metadata.width}x{metadata.height} (máx: {self.MAX_WIDTH}x{self.MAX_HEIGHT})"
            )

        # Validar tamaño de archivo
        if file_size > self.MAX_FILE_SIZE:
            errors.append(
                f"Archivo muy grande: {file_size / 1024 / 1024:.1f}MB (máx: {self.MAX_FILE_SIZE / 1024 / 1024:.0f}MB)"
            )

        # Validar aspect ratio
        aspect_ratio = metadata.width / metadata.height
        if aspect_ratio < self.MIN_ASPECT_RATIO or aspect_ratio > self.MAX_ASPECT_RATIO:
            errors.append(
                f"Aspect ratio inválido: {aspect_ratio:.2f} (permitido: {self.MIN_ASPECT_RATIO}-{self.MAX_ASPECT_RATIO})"
            )

        # Warnings
        if file_size > 5 * 1024 * 1024:
            warnings.append("Archivo grande, considere comprimir")

        if metadata.format == ImageFormat.GIF:
            warnings.append("GIF no recomendado para fotos, use JPEG/WebP")

        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings, metadata=metadata
        )


class ImageProcessor:
    """
    Procesador de imágenes (simulado).

    En producción, usar:
    - Python: Pillow, opencv-python
    - Node.js: sharp, jimp
    - Cloud: Cloudinary, imgix
    """

    def __init__(self) -> None:
        self.operations_log: list[str] = []
        logger.info("ImageProcessor inicializado")

    def resize(
        self,
        metadata: ImageMetadata,
        max_width: int,
        max_height: int | None = None,
        fit: str = "inside",
    ) -> ImageMetadata:
        """
        Simular resize de imagen.

        Args:
            metadata: Metadatos originales
            max_width: Ancho máximo
            max_height: Alto máximo (opcional)
            fit: Modo de ajuste (inside, cover, fill)
        """
        original_w, original_h = metadata.width, metadata.height

        if max_height is None:
            max_height = max_width

        # Calcular nuevas dimensiones
        if fit == "inside":
            # Mantener aspect ratio, caber dentro de límites
            ratio = min(max_width / original_w, max_height / original_h)
            if ratio < 1:  # Solo reducir, no ampliar
                new_w = int(original_w * ratio)
                new_h = int(original_h * ratio)
            else:
                new_w, new_h = original_w, original_h
        elif fit == "cover":
            # Cubrir área, puede recortar
            ratio = max(max_width / original_w, max_height / original_h)
            new_w = int(original_w * ratio)
            new_h = int(original_h * ratio)
        else:  # fill
            new_w, new_h = max_width, max_height

        # Simular nuevo tamaño de archivo (proporcional a píxeles)
        pixel_ratio = (new_w * new_h) / (original_w * original_h)
        new_size = int(metadata.file_size * pixel_ratio * 0.9)  # 10% compresión adicional

        operation = f"resize({original_w}x{original_h} -> {new_w}x{new_h}, fit={fit})"
        self.operations_log.append(operation)
        logger.info(operation)

        return ImageMetadata(
            width=new_w,
            height=new_h,
            format=metadata.format,
            file_size=new_size,
            color_space=metadata.color_space,
            has_alpha=metadata.has_alpha,
            bit_depth=metadata.bit_depth,
        )

    def crop(
        self, metadata: ImageMetadata, width: int, height: int, position: str = "center"
    ) -> ImageMetadata:
        """Simular crop de imagen."""
        # Asegurar que no excede dimensiones originales
        new_w = min(width, metadata.width)
        new_h = min(height, metadata.height)

        pixel_ratio = (new_w * new_h) / (metadata.width * metadata.height)
        new_size = int(metadata.file_size * pixel_ratio)

        operation = f"crop({metadata.width}x{metadata.height} -> {new_w}x{new_h}, pos={position})"
        self.operations_log.append(operation)
        logger.info(operation)

        return ImageMetadata(
            width=new_w,
            height=new_h,
            format=metadata.format,
            file_size=new_size,
            color_space=metadata.color_space,
            has_alpha=metadata.has_alpha,
            bit_depth=metadata.bit_depth,
        )

    def compress(self, metadata: ImageMetadata, quality: int = 80) -> ImageMetadata:
        """Simular compresión de imagen."""
        # Simular reducción basada en calidad
        compression_factor = quality / 100
        new_size = int(metadata.file_size * compression_factor)

        operation = f"compress(quality={quality}%, {metadata.file_size / 1024:.0f}KB -> {new_size / 1024:.0f}KB)"
        self.operations_log.append(operation)
        logger.info(operation)

        return ImageMetadata(
            width=metadata.width,
            height=metadata.height,
            format=metadata.format,
            file_size=new_size,
            color_space=metadata.color_space,
            has_alpha=metadata.has_alpha,
            bit_depth=metadata.bit_depth,
        )

    def convert(self, metadata: ImageMetadata, target_format: ImageFormat) -> ImageMetadata:
        """Simular conversión de formato."""
        # Factores de tamaño aproximados por formato
        format_factors = {
            ImageFormat.JPEG: 1.0,
            ImageFormat.PNG: 1.5,
            ImageFormat.WEBP: 0.7,
            ImageFormat.AVIF: 0.5,
            ImageFormat.GIF: 1.2,
        }

        current_factor = format_factors.get(metadata.format, 1.0)
        target_factor = format_factors.get(target_format, 1.0)

        new_size = int(metadata.file_size * (target_factor / current_factor))

        operation = f"convert({metadata.format.value} -> {target_format.value})"
        self.operations_log.append(operation)
        logger.info(operation)

        return ImageMetadata(
            width=metadata.width,
            height=metadata.height,
            format=target_format,
            file_size=new_size,
            color_space=metadata.color_space,
            has_alpha=metadata.has_alpha if target_format != ImageFormat.JPEG else False,
            bit_depth=metadata.bit_depth,
        )

    def generate_thumbnail(self, metadata: ImageMetadata, size: int = 150) -> ImageMetadata:
        """Generar thumbnail."""
        # Crop cuadrado + resize
        min_dim = min(metadata.width, metadata.height)
        cropped = self.crop(metadata, min_dim, min_dim, "entropy")
        return self.resize(cropped, size, size, "cover")

    def process_pipeline(
        self, metadata: ImageMetadata, generate_sizes: bool = True
    ) -> dict[str, ImageMetadata]:
        """
        Pipeline completo de procesamiento.

        Genera múltiples versiones de la imagen.
        """
        self.operations_log = []
        results = {}

        logger.info("Iniciando pipeline de procesamiento...")

        # Original optimizado
        results["original"] = self.compress(metadata, quality=90)

        if generate_sizes:
            # Thumbnail 150x150
            results["thumbnail"] = self.generate_thumbnail(metadata, 150)

            # Medium 800px
            results["medium"] = self.resize(metadata, 800)
            results["medium"] = self.compress(results["medium"], quality=85)

            # Large 1920px
            results["large"] = self.resize(metadata, 1920)
            results["large"] = self.compress(results["large"], quality=90)

            # WebP version
            results["webp"] = self.convert(results["large"], ImageFormat.WEBP)

        return results


def detect_format(data: bytes) -> ImageFormat:
    """Detectar formato de imagen por magic bytes."""
    if data[:3] == b"\xff\xd8\xff":
        return ImageFormat.JPEG
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        return ImageFormat.PNG
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ImageFormat.WEBP
    elif data[:6] in (b"GIF87a", b"GIF89a"):
        return ImageFormat.GIF
    elif data[4:12] == b"ftypavif":
        return ImageFormat.AVIF
    return ImageFormat.UNKNOWN


def demo_validation() -> None:
    """Demostrar validación de imágenes."""
    logger.info("=== Demo: Validación de Imágenes ===")

    validator = ImageValidator()

    # Casos de prueba
    test_cases = [
        ("Imagen válida", ImageMetadata(1920, 1080, ImageFormat.JPEG, 2_000_000)),
        ("Muy pequeña", ImageMetadata(50, 50, ImageFormat.JPEG, 5_000)),
        ("Muy grande", ImageMetadata(15000, 10000, ImageFormat.PNG, 50_000_000)),
        ("Formato inválido", ImageMetadata(800, 600, ImageFormat.UNKNOWN, 500_000)),
        ("Aspect ratio extremo", ImageMetadata(100, 2000, ImageFormat.JPEG, 300_000)),
        ("GIF grande", ImageMetadata(1200, 800, ImageFormat.GIF, 8_000_000)),
    ]

    print("\nResultados de validación:")
    print("-" * 60)

    for name, metadata in test_cases:
        result = validator.validate(metadata, metadata.file_size)
        status = "✓ VÁLIDA" if result.valid else "✗ INVÁLIDA"

        print(f"\n{name}: {status}")
        print(f"  Dimensiones: {metadata.width}x{metadata.height}")
        print(f"  Formato: {metadata.format.value}")
        print(f"  Tamaño: {metadata.file_size / 1024:.0f}KB")

        if result.errors:
            for error in result.errors:
                print(f"  ❌ {error}")

        if result.warnings:
            for warning in result.warnings:
                print(f"  ⚠️  {warning}")


def demo_pipeline() -> None:
    """Demostrar pipeline de procesamiento."""
    logger.info("=== Demo: Pipeline de Procesamiento ===")

    processor = ImageProcessor()

    # Imagen de entrada simulada
    original = ImageMetadata(
        width=4000,
        height=3000,
        format=ImageFormat.JPEG,
        file_size=5_500_000,  # 5.5MB
        color_space="sRGB",
        has_alpha=False,
        bit_depth=8,
    )

    print("\nImagen original:")
    print(f"  Dimensiones: {original.width}x{original.height}")
    print(f"  Formato: {original.format.value}")
    print(f"  Tamaño: {original.file_size / 1024 / 1024:.2f}MB")

    # Procesar
    results = processor.process_pipeline(original)

    print("\n" + "-" * 60)
    print("Versiones generadas:")
    print("-" * 60)

    total_original = original.file_size
    total_processed = 0

    for name, meta in results.items():
        compression = (1 - meta.file_size / original.file_size) * 100
        total_processed += meta.file_size

        print(f"\n  {name}:")
        print(f"    Dimensiones: {meta.width}x{meta.height}")
        print(f"    Formato: {meta.format.value}")
        print(f"    Tamaño: {meta.file_size / 1024:.0f}KB ({compression:.0f}% reducción)")

    print("\n" + "-" * 60)
    print(f"Operaciones realizadas: {len(processor.operations_log)}")
    for op in processor.operations_log:
        print(f"  • {op}")

    print("\nResumen:")
    print(f"  Original: {total_original / 1024 / 1024:.2f}MB")
    print(f"  Todas las versiones: {total_processed / 1024 / 1024:.2f}MB")


def main() -> None:
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Image Processing Patterns Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python image_demo.py --demo validate
    python image_demo.py --demo pipeline
    python image_demo.py --demo all
        """,
    )

    parser.add_argument(
        "--demo",
        choices=["validate", "pipeline", "all"],
        default="all",
        help="Tipo de demo a ejecutar",
    )

    parser.add_argument("--image", type=str, help="Ruta a imagen para procesar (opcional)")

    args = parser.parse_args()

    print("=" * 60)
    print("       IMAGE PROCESSING PATTERNS DEMO")
    print("=" * 60)

    if args.demo in ("validate", "all"):
        demo_validation()
        print()

    if args.demo in ("pipeline", "all"):
        demo_pipeline()

    print("\n" + "=" * 60)
    print("Demo completada. Ver SKILL.md para patrones de producción")
    print("con Sharp, Pillow y Cloudinary.")
    print("=" * 60)


if __name__ == "__main__":
    main()
