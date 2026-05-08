"""Genera el icono .ico de la app con branding UNS."""

import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    os.system(f'"{sys.executable}" -m pip install Pillow --quiet --break-system-packages')
    from PIL import Image, ImageDraw, ImageFont


def make_icon_at_size(size: int) -> Image.Image:
    UNS_NAVY = (0, 82, 204, 255)
    UNS_NAVY_DARK = (0, 61, 153, 255)
    WHITE = (255, 255, 255, 255)

    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = max(2, size // 6)
    draw.rounded_rectangle([(0, 0), (size - 1, size - 1)],
                            radius=radius, fill=UNS_NAVY)

    margin = max(2, size // 5)
    box_top = int(size * 0.32)
    draw.rounded_rectangle(
        [(margin, box_top), (size - margin, size - margin)],
        radius=max(1, radius // 2), fill=WHITE,
    )

    lid_height = max(2, size // 14)
    draw.rectangle(
        [(margin - 2, box_top - lid_height),
         (size - margin + 2, box_top + 2)],
        fill=UNS_NAVY_DARK,
    )

    if size >= 32:
        try:
            font_size = int(size * 0.35)
            font = None
            for font_name in [
                "arial.ttf", "Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "DejaVuSans-Bold.ttf",
            ]:
                try:
                    font = ImageFont.truetype(font_name, font_size)
                    break
                except OSError:
                    continue
            if font is None:
                font = ImageFont.load_default()

            text = "U"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = (size - tw) // 2 - bbox[0]
            ty = box_top + (size - margin - box_top - th) // 2 - bbox[1]
            draw.text((tx, ty), text, fill=UNS_NAVY, font=font)
        except Exception as e:
            print(f"WARN font {size}: {e}")

    return img


def make_icon():
    sizes = [256, 128, 64, 48, 32, 16]
    images = [make_icon_at_size(s) for s in sizes]

    out_dir = Path(__file__).resolve().parent.parent / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)

    ico_path = out_dir / "icon.ico"
    images[0].save(str(ico_path), format='ICO',
                    sizes=[(s, s) for s in sizes])

    png_path = out_dir / "icon.png"
    images[0].save(str(png_path), format='PNG')

    print(f"OK: {ico_path} ({ico_path.stat().st_size} bytes)")
    print(f"OK: {png_path}")


if __name__ == "__main__":
    make_icon()
