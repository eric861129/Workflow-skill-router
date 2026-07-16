from __future__ import annotations

import re
from typing import BinaryIO


_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class FrontmatterError(ValueError):
    """表示 SKILL metadata 不可信或格式無效。"""


def read_frontmatter_stream(stream: BinaryIO, max_bytes: int = 65536) -> bytes:
    """只讀取 frontmatter，遇到結束 delimiter 立即停止。"""

    if max_bytes <= 0:
        raise ValueError("max_bytes 必須大於 0")
    first = stream.readline(max_bytes + 1)
    if len(first) > max_bytes:
        raise FrontmatterError(f"frontmatter 超過 {max_bytes} bytes")
    if first.rstrip(b"\r\n") != b"---":
        raise FrontmatterError("SKILL.md 缺少 frontmatter 起始符號")
    consumed = len(first)
    lines: list[bytes] = []
    while consumed <= max_bytes:
        remaining = max_bytes - consumed
        line = stream.readline(remaining + 1)
        if not line:
            raise FrontmatterError("SKILL.md 缺少 frontmatter 結束符號")
        consumed += len(line)
        if consumed > max_bytes:
            raise FrontmatterError(f"frontmatter 超過 {max_bytes} bytes")
        if line.rstrip(b"\r\n") == b"---":
            return b"".join(lines)
        lines.append(line)
    raise FrontmatterError(f"frontmatter 超過 {max_bytes} bytes")


def _unquote(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        return stripped[1:-1]
    return stripped


def parse_frontmatter(data: bytes) -> dict[str, object]:
    """解析不執行 tag、anchor 或自訂型別的安全 YAML 子集合。"""

    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise FrontmatterError("frontmatter 必須是有效 UTF-8") from error

    result: dict[str, object] = {}
    metadata: dict[str, str] = {}
    in_metadata = False
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw == "metadata:":
            if "metadata" in result:
                raise FrontmatterError("重複 key: metadata")
            result["metadata"] = metadata
            in_metadata = True
            continue

        has_leading_whitespace = raw[0].isspace()
        indented = raw.startswith(("  ", "\t"))
        if has_leading_whitespace and not indented:
            raise FrontmatterError(f"第 {number} 行使用模糊縮排")
        if indented and not in_metadata:
            raise FrontmatterError(f"第 {number} 行出現未支援的巢狀欄位")
        if ":" not in raw:
            raise FrontmatterError(f"第 {number} 行不是 key: value")
        key, value = raw.split(":", 1)
        key = key.strip()
        if not key or not _KEY_PATTERN.fullmatch(key):
            raise FrontmatterError(f"第 {number} 行的 key 無效")
        target: dict[str, object] | dict[str, str]
        target = metadata if indented and in_metadata else result
        if key in target:
            raise FrontmatterError(f"重複 key: {key}")
        target[key] = _unquote(value)

    if not isinstance(result.get("name"), str) or not result["name"]:
        raise FrontmatterError("frontmatter 缺少 name")
    return result
