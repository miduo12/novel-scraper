from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def rounded_rectangle(draw: ImageDraw.ImageDraw, box, radius: int, fill) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "src" / "novel_scraper" / "resources"
    output_dir.mkdir(parents=True, exist_ok=True)

    size = 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    rounded_rectangle(draw, (8, 8, 248, 248), 54, "#2F6FED")
    rounded_rectangle(draw, (58, 43, 198, 204), 16, "#FFFFFF")
    rounded_rectangle(draw, (76, 64, 180, 76), 6, "#DDE7FB")
    rounded_rectangle(draw, (76, 92, 180, 104), 6, "#DDE7FB")
    rounded_rectangle(draw, (76, 120, 152, 132), 6, "#DDE7FB")

    draw.polygon(
        [(128, 146), (94, 112), (111, 112), (111, 94), (145, 94), (145, 112), (162, 112)],
        fill="#F4B740",
    )
    draw.rounded_rectangle((111, 142, 145, 154), 5, fill="#F4B740")
    rounded_rectangle(draw, (64, 183, 192, 220), 14, "#173E93")
    draw.text((90, 189), "TXT", fill="#FFFFFF")

    png_path = output_dir / "app.png"
    ico_path = output_dir / "app.ico"
    image.save(png_path)
    image.save(
        ico_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    print(f"generated {png_path}")
    print(f"generated {ico_path}")


if __name__ == "__main__":
    main()
