"""Generuje favicony, ikony PWA i logo aplikacji z plikow w branding/.

Uruchomienie (z katalogu glownego repo, Pillow w kontenerze):
    docker run --rm -v "$PWD:/repo" -w /repo python:3.12-slim \
        sh -c "pip install -q pillow && python scripts/generate_icons.py"

Zrodla:
- branding/calico_icon.png             - ikona na ciemnym tle (favicon, apple-touch-icon)
- branding/calico_icon_transparent.png - ikona z przezroczystym tlem (ikony PWA "any", logo w UI, "maskable")
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
BRANDING = ROOT / "branding"
OUT = ROOT / "frontend" / "icons"

# Granice zaokraglonego kwadratu w calico_icon.png (zmierzone; kwadrat ~1046 x 1029 px).
SQUARE_CENTER = (625, 601)
SQUARE_SIDE = 1050
# Kolor wnetrza kwadratu przy krawedzi - tlo ikon "maskable" (Android przycina je do dowolnego ksztaltu).
MASKABLE_BG = (4, 26, 72)
# Kolo z pierscieniem i litera "C" (srodek i promien z zapasem na poswiate).
RING_CENTER = (617, 604)
RING_RADIUS = 440


def square_crop(image: Image.Image) -> Image.Image:
    cx, cy = SQUARE_CENTER
    half = SQUARE_SIDE // 2
    return image.crop((cx - half, cy - half, cx + half, cy + half))


def pad_to_square(image: Image.Image, margin_ratio: float = 0.0) -> Image.Image:
    bbox = image.getbbox()
    content = image.crop(bbox)
    side = int(max(content.size) * (1 + 2 * margin_ratio))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(content, ((side - content.width) // 2, (side - content.height) // 2), content)
    return canvas


def save_png(image: Image.Image, size: int, name: str) -> None:
    image.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
    print(f"{name:32} {size}x{size}  {(OUT / name).stat().st_size // 1024} KB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    opaque = Image.open(BRANDING / "calico_icon.png").convert("RGBA")
    transparent = Image.open(BRANDING / "calico_icon_transparent.png").convert("RGBA")

    # Favicony: sam kwadrat (bez ciemnego marginesu), zeby w 16 px bylo widac pierscien i "C".
    favicon_source = square_crop(opaque)
    favicon_source.resize((256, 256), Image.LANCZOS).save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"{'favicon.ico':32} 16/32/48")
    save_png(favicon_source, 32, "favicon-32.png")
    save_png(favicon_source, 16, "favicon-16.png")

    # iOS sam zaokragla rogi - pelny kwadrat bez przezroczystosci.
    save_png(favicon_source.convert("RGB"), 180, "apple-touch-icon.png")

    # PWA "any": ksztalt ikony z przezroczystym tlem.
    any_source = pad_to_square(transparent, margin_ratio=0.02)
    save_png(any_source, 192, "icon-192.png")
    save_png(any_source, 512, "icon-512.png")

    # PWA "maskable": pelne tlo, a na nim samo kolo z pierscieniem i "C" (bez krawedzi kwadratu),
    # zmieszczone w strefie bezpiecznej (srodkowe 80%) - system moze przyciac ikone do kola, "squircle" itd.
    ring = opaque.crop((RING_CENTER[0] - RING_RADIUS, RING_CENTER[1] - RING_RADIUS, RING_CENTER[0] + RING_RADIUS, RING_CENTER[1] + RING_RADIUS))
    feather = Image.new("L", ring.size, 0)
    draw = ImageDraw.Draw(feather)
    steps = 40
    for step in range(steps):
        inset = step
        draw.ellipse((inset, inset, ring.width - inset, ring.height - inset), fill=int(255 * (step + 1) / steps))
    canvas_side = int(ring.width / 0.78)
    maskable = Image.new("RGBA", (canvas_side, canvas_side), MASKABLE_BG + (255,))
    offset = (canvas_side - ring.width) // 2
    maskable.paste(ring, (offset, offset), feather)
    save_png(maskable.convert("RGB"), 192, "icon-maskable-192.png")
    save_png(maskable.convert("RGB"), 512, "icon-maskable-512.png")

    # Logo w interfejsie (ekran blokady, pasek nawigacji).
    save_png(any_source, 64, "logo-64.png")
    save_png(any_source, 256, "logo-256.png")


if __name__ == "__main__":
    main()
