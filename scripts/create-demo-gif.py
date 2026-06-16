#!/usr/bin/env python3
"""Create the 60-second Workflow Skill Router demo GIF.

This script intentionally uses only the Python standard library so the demo
asset can be regenerated without ffmpeg, ImageMagick, Pillow, or Node packages.
"""

from __future__ import annotations

import argparse
from pathlib import Path


WIDTH = 720
HEIGHT = 405
FRAME_COUNT = 18
DELAY_CS = 333
LZW_MIN_CODE_SIZE = 4

PALETTE = [
    (8, 17, 31),  # 0 background
    (15, 23, 42),  # 1 panel
    (30, 41, 59),  # 2 border
    (248, 250, 252),  # 3 white
    (148, 163, 184),  # 4 muted
    (47, 111, 237),  # 5 blue
    (24, 160, 88),  # 6 green
    (246, 166, 9),  # 7 amber
    (239, 68, 68),  # 8 red
    (226, 232, 240),  # 9 light
    (12, 74, 110),  # 10 blue dark
    (20, 83, 45),  # 11 green dark
    (120, 53, 15),  # 12 amber dark
    (69, 10, 10),  # 13 red dark
    (99, 102, 241),  # 14 indigo
    (14, 116, 144),  # 15 cyan
]


FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["10010", "10010", "10010", "11111", "00010", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    ":": ["00000", "00100", "00100", "00000", "00100", "00100", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
    ">": ["10000", "01000", "00100", "00010", "00100", "01000", "10000"],
    "<": ["00001", "00010", "00100", "01000", "00100", "00010", "00001"],
    "(": ["00010", "00100", "01000", "01000", "01000", "00100", "00010"],
    ")": ["01000", "00100", "00010", "00010", "00010", "00100", "01000"],
    "_": ["00000", "00000", "00000", "00000", "00000", "00000", "11111"],
    "|": ["00100", "00100", "00100", "00100", "00100", "00100", "00100"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


class Canvas:
    def __init__(self) -> None:
        self.pixels = bytearray([0]) * (WIDTH * HEIGHT)

    def rect(self, x: int, y: int, w: int, h: int, color: int) -> None:
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(WIDTH, x + w)
        y1 = min(HEIGHT, y + h)
        for yy in range(y0, y1):
            start = yy * WIDTH + x0
            self.pixels[start : start + (x1 - x0)] = bytes([color]) * (x1 - x0)

    def border(self, x: int, y: int, w: int, h: int, color: int) -> None:
        self.rect(x, y, w, 2, color)
        self.rect(x, y + h - 2, w, 2, color)
        self.rect(x, y, 2, h, color)
        self.rect(x + w - 2, y, 2, h, color)

    def text(self, x: int, y: int, message: str, color: int = 3, scale: int = 2) -> None:
        cx = x
        for char in message.upper():
            glyph = FONT.get(char, FONT[" "])
            for row, bits in enumerate(glyph):
                for col, bit in enumerate(bits):
                    if bit == "1":
                        self.rect(cx + col * scale, y + row * scale, scale, scale, color)
            cx += 6 * scale

    def label(self, x: int, y: int, message: str, color: int, fill: int, scale: int = 2) -> None:
        width = len(message) * 6 * scale + 16
        self.rect(x, y, width, 24, fill)
        self.border(x, y, width, 24, color)
        self.text(x + 8, y + 6, message, color, scale=scale)


def progress(canvas: Canvas, frame: int) -> None:
    canvas.rect(44, 370, 632, 8, 2)
    canvas.rect(44, 370, int(632 * (frame + 1) / FRAME_COUNT), 8, 6)
    second = 60 if frame + 1 == FRAME_COUNT else min(60, (frame + 1) * DELAY_CS // 100)
    canvas.text(44, 386, f"{second:02d}/60 SEC DEMO", 4, scale=1)


def draw_header(canvas: Canvas, frame: int, title: str, subtitle: str) -> None:
    canvas.text(44, 28, "WORKFLOW SKILL ROUTER", 3, scale=2)
    canvas.text(44, 54, title, 6, scale=2)
    canvas.text(44, 78, subtitle, 4, scale=1)
    canvas.text(584, 28, f"V1.2.0", 14, scale=1)
    progress(canvas, frame)


def draw_phase(frame: int) -> bytes:
    canvas = Canvas()
    canvas.rect(0, 0, WIDTH, HEIGHT, 0)

    phase = min(5, frame * 6 // FRAME_COUNT)
    if phase == 0:
        draw_header(canvas, frame, "1. FUZZY REQUEST", "THE AGENT STARTS WITH TOO MANY PLAUSIBLE SKILLS.")
        canvas.rect(44, 112, 632, 210, 1)
        canvas.border(44, 112, 632, 210, 2)
        canvas.text(68, 136, "USER:", 7, scale=2)
        canvas.text(68, 170, "DEBUG A VUE-ONLY RENDERING BUG", 3, scale=2)
        canvas.text(68, 202, "AND ADD A PLAYWRIGHT REGRESSION CHECK.", 3, scale=2)
        canvas.text(68, 258, "OVER-ROUTE: FRONTEND UI BROWSER QA DOCS DEPLOY", 8, scale=1)
    elif phase == 1:
        draw_header(canvas, frame, "2. READ THE ROUTER", "ROUTES GROUP WORK BY TASK NATURE, STAGE, AND DOMAIN.")
        canvas.rect(44, 112, 288, 214, 1)
        canvas.rect(388, 112, 288, 214, 1)
        canvas.border(44, 112, 288, 214, 2)
        canvas.border(388, 112, 288, 214, 2)
        canvas.text(68, 136, "SKILL TREE", 7, scale=2)
        canvas.text(68, 178, "FRONTEND", 3, scale=2)
        canvas.text(92, 210, "> VUE / UI", 4, scale=2)
        canvas.text(92, 242, "> BROWSER REGRESSION", 4, scale=2)
        canvas.text(412, 136, "ROUTING RULES", 7, scale=2)
        canvas.text(412, 178, "ONE PRIMARY", 3, scale=2)
        canvas.text(412, 210, "MAX 3 SUPPORTING", 3, scale=2)
        canvas.text(412, 242, "NO RELATED-ONLY PICKS", 3, scale=2)
    elif phase == 2:
        draw_header(canvas, frame, "3. SELECT A SMALL ROUTE", "ONE OWNER, A FEW HELPERS, AND AN EXPLAINABLE REASON.")
        canvas.rect(44, 112, 632, 214, 1)
        canvas.border(44, 112, 632, 214, 6)
        canvas.text(68, 136, "ROUTE:", 7, scale=2)
        canvas.text(68, 170, "FRONTEND / VUE / UI > BROWSER REGRESSION", 3, scale=2)
        canvas.label(68, 224, "PRIMARY: VUE-EXPERT", 6, 11, scale=1)
        canvas.label(286, 224, "SUPPORT: SYSTEMATIC-DEBUGGING", 5, 10, scale=1)
        canvas.label(68, 264, "SUPPORT: PLAYWRIGHT", 14, 10, scale=1)
        canvas.text(68, 304, "3 SKILLS SELECTED. 0 EXTRA DISTRACTIONS.", 6, scale=1)
    elif phase == 3:
        draw_header(canvas, frame, "4. EXECUTE WITH A PLAN", "THE ROUTE TURNS INTO A REVIEWABLE WORKING SET.")
        canvas.rect(44, 112, 632, 214, 1)
        canvas.border(44, 112, 632, 214, 2)
        rows = [
            ("1", "REPRODUCE THE RENDERING BUG", 6),
            ("2", "ISOLATE COMPONENT STATE OR LIFECYCLE CAUSE", 6),
            ("3", "PATCH THE VUE COMPONENT", 6),
            ("4", "ADD A PLAYWRIGHT REGRESSION CHECK", 6),
        ]
        for idx, (num, text, color) in enumerate(rows):
            y = 140 + idx * 42
            canvas.rect(68, y - 8, 28, 28, color)
            canvas.text(78, y, num, 0, scale=1)
            canvas.text(112, y, text, 3, scale=2)
    elif phase == 4:
        draw_header(canvas, frame, "5. VALIDATE BEFORE SHARING", "THE STARTER, EXAMPLES, AND RELEASE ASSETS STAY CHECKABLE.")
        canvas.rect(44, 112, 632, 214, 1)
        canvas.border(44, 112, 632, 214, 2)
        canvas.text(68, 142, "PYTHON SCRIPTS/VALIDATE-ROUTER.PY", 4, scale=2)
        canvas.text(68, 178, "STARTER/WORKFLOW-SKILL-ROUTER", 4, scale=2)
        canvas.text(68, 232, "OK: WORKFLOW-SKILL-ROUTER PASSED VALIDATION", 6, scale=2)
        canvas.text(68, 278, "SMOKE TEST: ZIP ASSETS EXTRACT AND VALIDATE", 6, scale=1)
    else:
        draw_header(canvas, frame, "6. INSTALL, ADAPT, SHARE", "START BLANK, BORROW THE TEMPLATE, KEEP ROUTES SMALL.")
        canvas.rect(44, 112, 632, 214, 1)
        canvas.border(44, 112, 632, 214, 5)
        canvas.text(68, 140, "DOWNLOAD BLANK ROUTER", 3, scale=3)
        canvas.text(68, 192, "FILL WITH YOUR REAL SKILLS", 6, scale=2)
        canvas.text(68, 230, "VALIDATE BEFORE YOU SHARE", 6, scale=2)
        canvas.text(68, 286, "GITHUB.COM/ERIC861129/WORKFLOW-SKILL-ROUTER", 4, scale=1)

    return bytes(canvas.pixels)


def lzw_encode(indices: bytes, min_code_size: int = LZW_MIN_CODE_SIZE) -> bytes:
    return lzw_encode_clear_chunks(indices, min_code_size)


def lzw_encode_clear_chunks(indices: bytes, min_code_size: int = LZW_MIN_CODE_SIZE) -> bytes:
    """Encode valid GIF LZW by resetting before code-size growth.

    The generated demo has flat colors and is intentionally small enough that a
    conservative clear-chunk stream is acceptable. This avoids relying on local
    image libraries while keeping the asset deterministic and portable.
    """

    clear_code = 1 << min_code_size
    end_code = clear_code + 1
    code_size = min_code_size + 1
    codes: list[tuple[int, int]] = []

    chunk_size = 12
    for offset in range(0, len(indices), chunk_size):
        codes.append((clear_code, code_size))
        for value in indices[offset : offset + chunk_size]:
            codes.append((value, code_size))
    codes.append((end_code, code_size))

    out = bytearray()
    bit_buffer = 0
    bit_count = 0
    for code, size in codes:
        bit_buffer |= code << bit_count
        bit_count += size
        while bit_count >= 8:
            out.append(bit_buffer & 0xFF)
            bit_buffer >>= 8
            bit_count -= 8
    if bit_count:
        out.append(bit_buffer & 0xFF)
    return bytes(out)


def lzw_encode_dictionary(indices: bytes, min_code_size: int = LZW_MIN_CODE_SIZE) -> bytes:
    clear_code = 1 << min_code_size
    end_code = clear_code + 1
    next_code = end_code + 1
    code_size = min_code_size + 1
    dictionary = {(i,): i for i in range(clear_code)}
    codes: list[tuple[int, int]] = [(clear_code, code_size)]

    w = (indices[0],)
    for value in indices[1:]:
        wk = w + (value,)
        if wk in dictionary:
            w = wk
            continue

        codes.append((dictionary[w], code_size))
        if next_code < 4096:
            dictionary[wk] = next_code
            next_code += 1
            if next_code == (1 << code_size) and code_size < 12:
                code_size += 1
        else:
            codes.append((clear_code, code_size))
            dictionary = {(i,): i for i in range(clear_code)}
            next_code = end_code + 1
            code_size = min_code_size + 1
        w = (value,)

    codes.append((dictionary[w], code_size))
    codes.append((end_code, code_size))

    out = bytearray()
    bit_buffer = 0
    bit_count = 0
    for code, size in codes:
        bit_buffer |= code << bit_count
        bit_count += size
        while bit_count >= 8:
            out.append(bit_buffer & 0xFF)
            bit_buffer >>= 8
            bit_count -= 8
    if bit_count:
        out.append(bit_buffer & 0xFF)
    return bytes(out)


def write_sub_blocks(handle, data: bytes) -> None:
    for offset in range(0, len(data), 255):
        block = data[offset : offset + 255]
        handle.write(bytes([len(block)]))
        handle.write(block)
    handle.write(b"\x00")


def write_gif(path: Path) -> None:
    palette = PALETTE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(b"GIF89a")
        handle.write(WIDTH.to_bytes(2, "little"))
        handle.write(HEIGHT.to_bytes(2, "little"))
        handle.write(b"\xF3\x00\x00")
        for red, green, blue in palette:
            handle.write(bytes([red, green, blue]))
        handle.write(b"\x21\xFF\x0BNETSCAPE2.0\x03\x01\x00\x00\x00")

        for frame in range(FRAME_COUNT):
            pixels = draw_phase(frame)
            encoded = lzw_encode(pixels)
            handle.write(b"\x21\xF9\x04\x04")
            handle.write(DELAY_CS.to_bytes(2, "little"))
            handle.write(b"\x00\x00")
            handle.write(b"\x2C\x00\x00\x00\x00")
            handle.write(WIDTH.to_bytes(2, "little"))
            handle.write(HEIGHT.to_bytes(2, "little"))
            handle.write(b"\x00")
            handle.write(bytes([LZW_MIN_CODE_SIZE]))
            write_sub_blocks(handle, encoded)
        handle.write(b"\x3B")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="docs/assets/workflow-skill-router-60s-demo.gif",
        help="Output GIF path.",
    )
    parser.add_argument(
        "--site-copy",
        default="site/public/assets/workflow-skill-router-60s-demo.gif",
        help="Optional site/public copy path. Pass an empty string to skip.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.out)
    write_gif(output)
    if args.site_copy:
        write_gif(Path(args.site_copy))
    print(f"Wrote {output}")
    if args.site_copy:
        print(f"Wrote {args.site_copy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
