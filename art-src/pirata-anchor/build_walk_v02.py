from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "pirata-walk-8dir-v02-source.png"
PALETTE_SOURCE = ROOT / "pirata-walk-8dir-v01.png"
ATLAS_OUTPUT = ROOT / "pirata-walk-8dir-v02.png"
GIF_OUTPUT = ROOT / "pirata-walk-8dir-v02.gif"
JSON_OUTPUT = ROOT / "pirata-walk-8dir-v02.json"

CELL = 64
DIRECTIONS = ("s", "se", "e", "ne", "n", "nw", "w", "sw")
FRAMES = 4
DURATION_MS = 140


def palette_from(image: Image.Image) -> list[tuple[int, int, int, int]]:
    colours: list[tuple[int, int, int, int]] = []
    for colour in image.convert("RGBA").get_flattened_data():
        if colour[3] == 0 or colour in colours:
            continue
        colours.append(colour)
    return colours


def nearest_colour(
    colour: tuple[int, int, int, int],
    palette: list[tuple[int, int, int, int]],
) -> tuple[int, int, int, int]:
    if colour[3] < 128:
        return (0, 0, 0, 0)
    red, green, blue, _ = colour
    return min(
        palette,
        key=lambda candidate: (
            (red - candidate[0]) ** 2
            + (green - candidate[1]) ** 2
            + (blue - candidate[2]) ** 2
        ),
    )


def quantize_source(source: Image.Image, palette: list[tuple[int, int, int, int]]) -> Image.Image:
    source = source.convert("RGBA")
    output = Image.new("RGBA", source.size, (0, 0, 0, 0))
    cache: dict[tuple[int, int, int, int], tuple[int, int, int, int]] = {}
    pixels = []
    for colour in source.get_flattened_data():
        mapped = cache.get(colour)
        if mapped is None:
            mapped = nearest_colour(colour, palette)
            cache[colour] = mapped
        pixels.append(mapped)
    output.putdata(pixels)
    return output


def add_ground_clearance(atlas: Image.Image) -> Image.Image:
    output = Image.new("RGBA", atlas.size, (0, 0, 0, 0))
    for direction_index in range(len(DIRECTIONS)):
        for frame_index in range(FRAMES):
            left = frame_index * CELL
            top = direction_index * CELL
            cell = atlas.crop((left, top, left + CELL, top + CELL))
            output.alpha_composite(cell, (left, top - 1))
    return output


def gif_frames(atlas: Image.Image) -> list[Image.Image]:
    frames: list[Image.Image] = []
    for frame_index in range(FRAMES):
        strip = Image.new("RGBA", (CELL * len(DIRECTIONS), CELL), (0, 0, 0, 0))
        for direction_index in range(len(DIRECTIONS)):
            left = frame_index * CELL
            top = direction_index * CELL
            cell = atlas.crop((left, top, left + CELL, top + CELL))
            strip.alpha_composite(cell, (direction_index * CELL, 0))
        frames.append(strip)
    return frames


def metadata() -> dict[str, object]:
    frames = []
    for direction_index, direction in enumerate(DIRECTIONS):
        for frame_index in range(FRAMES):
            frames.append(
                {
                    "name": f"walk_{direction}_{frame_index}",
                    "direction": direction,
                    "index": frame_index,
                    "duration_ms": DURATION_MS,
                    "frame": {
                        "x": frame_index * CELL,
                        "y": direction_index * CELL,
                        "w": CELL,
                        "h": CELL,
                    },
                    "pivot": {"x": 32, "y": 62},
                }
            )
    return {
        "image": ATLAS_OUTPUT.name,
        "animation": "walk",
        "directions": list(DIRECTIONS),
        "frames_per_direction": FRAMES,
        "duration_ms": DURATION_MS,
        "loop": True,
        "frames": frames,
    }


def main() -> None:
    source = Image.open(SOURCE)
    if source.size != (CELL * FRAMES, CELL * len(DIRECTIONS)):
        raise ValueError(f"fonte deve medir 256x512; recebeu {source.size}")

    palette = palette_from(Image.open(PALETTE_SOURCE))
    atlas = add_ground_clearance(quantize_source(source, palette))
    atlas.save(ATLAS_OUTPUT, optimize=True)

    frames = gif_frames(atlas)
    frames[0].save(
        GIF_OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=[DURATION_MS] * FRAMES,
        loop=0,
        disposal=2,
        transparency=0,
        optimize=False,
    )

    JSON_OUTPUT.write_text(
        json.dumps(metadata(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
