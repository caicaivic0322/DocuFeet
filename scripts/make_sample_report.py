from __future__ import annotations

import struct
import zlib
from pathlib import Path


def chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def make_png(path: Path, width: int = 900, height: int = 600) -> None:
    bg = (248, 250, 252)
    line = (210, 216, 224)
    textbar = (230, 234, 240)

    rows: list[bytes] = []
    for y in range(height):
        row = bytearray([0])  # filter type 0
        for x in range(width):
            r, g, b = bg
            # header blocks
            if y < 70:
                r, g, b = (255, 255, 255)
            elif 70 <= y < 120:
                r, g, b = textbar

            # table grid
            if y in (160, 200, 240, 280, 320, 360, 400, 440, 480, 520):
                r, g, b = line
            if x in (40, 240, 460, 680, 860):
                r, g, b = line

            # a couple highlighted cells
            if 240 < x < 460 and 238 < y < 260:
                r, g, b = (255, 237, 235)
            if 460 < x < 680 and 318 < y < 340:
                r, g, b = (255, 247, 230)

            row.extend([r, g, b])
        rows.append(bytes(row))

    raw = b"".join(rows)
    compressed = zlib.compress(raw, level=9)

    png = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "docs" / "sample-report.png"
    make_png(out)
    print(out)
