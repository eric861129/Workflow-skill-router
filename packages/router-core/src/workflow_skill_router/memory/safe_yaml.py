from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from typing import Any

from .models import MemoryPolicyError


_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_INTEGER_PATTERN = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_DECIMAL_PATTERN = re.compile(r"^-?(?:0|[1-9][0-9]*)\.[0-9]+$")
_PLAIN_STRING_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./:-]*$")
_DATE_LIKE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}(?:$|[Tt ])")
_FORBIDDEN_PLAIN_TOKENS = frozenset("&*!|>{}[]`#")


@dataclass(frozen=True, slots=True)
class _Line:
    number: int
    indent: int
    content: str


def _error(code: str, line: int | None = None) -> MemoryPolicyError:
    suffix = "" if line is None else f":line-{line}"
    return MemoryPolicyError(code + suffix)


def _has_unquoted_hash(value: str) -> bool:
    quoted = False
    escaped = False
    for character in value:
        if escaped:
            escaped = False
            continue
        if quoted and character == "\\":
            escaped = True
            continue
        if character == '"':
            quoted = not quoted
            continue
        if character == "#" and not quoted:
            return True
    return False


def _prepare(text: str) -> tuple[_Line, ...]:
    if not isinstance(text, str):
        raise MemoryPolicyError("yaml-text-invalid")
    if text.startswith("\ufeff") or "\x00" in text:
        raise MemoryPolicyError("yaml-encoding-marker-forbidden")
    prepared: list[_Line] = []
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for number, raw in enumerate(normalized.split("\n"), 1):
        if "\t" in raw:
            raise _error("yaml-tab-forbidden", number)
        if not raw.strip() or raw.lstrip(" ").startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2:
            raise _error("yaml-indent-invalid", number)
        content = raw[indent:].rstrip()
        if content in {"---", "..."} or content.startswith("--- "):
            raise _error("yaml-multiple-documents-forbidden", number)
        if _has_unquoted_hash(content):
            raise _error("yaml-inline-comment-forbidden", number)
        prepared.append(_Line(number, indent, content))
    if not prepared:
        raise MemoryPolicyError("yaml-root-empty")
    if prepared[0].indent != 0:
        raise _error("yaml-root-indent-invalid", prepared[0].number)
    return tuple(prepared)


def _find_separator(content: str, line: int) -> int:
    quoted = False
    escaped = False
    for index, character in enumerate(content):
        if escaped:
            escaped = False
            continue
        if quoted and character == "\\":
            escaped = True
            continue
        if character == '"':
            quoted = not quoted
            continue
        if character == ":" and not quoted:
            return index
    raise _error("yaml-mapping-separator-missing", line)


def _parse_key(value: str, line: int) -> str:
    candidate = value.strip()
    if not candidate:
        raise _error("yaml-key-empty", line)
    if candidate.startswith('"'):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as error:
            raise _error("yaml-key-invalid", line) from error
        if (
            not isinstance(parsed, str)
            or not parsed
            or not _KEY_PATTERN.fullmatch(parsed)
        ):
            raise _error("yaml-key-invalid", line)
        return parsed
    if candidate.startswith("'") or not _KEY_PATTERN.fullmatch(candidate):
        raise _error("yaml-key-invalid", line)
    if candidate == "<<":
        raise _error("yaml-merge-key-forbidden", line)
    return candidate


def _parse_scalar(value: str, line: int) -> object:
    candidate = value.strip()
    if not candidate:
        raise _error("yaml-scalar-empty", line)
    if candidate.startswith('"'):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as error:
            raise _error("yaml-string-invalid", line) from error
        if not isinstance(parsed, str):
            raise _error("yaml-string-invalid", line)
        return parsed
    if candidate.startswith("'"):
        raise _error("yaml-single-quote-forbidden", line)
    if any(token in candidate for token in _FORBIDDEN_PLAIN_TOKENS):
        raise _error("yaml-control-token-forbidden", line)
    if candidate == "null":
        return None
    if candidate == "true":
        return True
    if candidate == "false":
        return False
    if candidate in {
        "~", ".nan", ".NaN", ".NAN", ".inf", ".Inf", ".INF",
        "-.inf", "+.inf",
    }:
        raise _error("yaml-non-json-scalar", line)
    if _DATE_LIKE_PATTERN.match(candidate):
        raise _error("yaml-implicit-date-forbidden", line)
    if _INTEGER_PATTERN.fullmatch(candidate):
        return int(candidate)
    if _DECIMAL_PATTERN.fullmatch(candidate):
        number = float(candidate)
        if not math.isfinite(number):
            raise _error("yaml-non-json-scalar", line)
        return number
    if not _PLAIN_STRING_PATTERN.fullmatch(candidate):
        raise _error("yaml-plain-string-invalid", line)
    return candidate


def _split_mapping(content: str, line: int) -> tuple[str, str]:
    separator = _find_separator(content, line)
    key = _parse_key(content[:separator], line)
    value = content[separator + 1:].strip()
    return key, value


def _is_sequence(content: str) -> bool:
    return content == "-" or content.startswith("- ")


def _parse_mapping(
    lines: tuple[_Line, ...],
    index: int,
    indent: int,
) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise _error("yaml-indent-invalid", line.number)
        if _is_sequence(line.content):
            raise _error("mixed-container", line.number)
        key, raw_value = _split_mapping(line.content, line.number)
        if key in result:
            raise _error("duplicate-key", line.number)
        index += 1
        if raw_value:
            result[key] = _parse_scalar(raw_value, line.number)
            if index < len(lines) and lines[index].indent > indent:
                raise _error("yaml-scalar-cannot-have-children", lines[index].number)
            continue
        if index >= len(lines) or lines[index].indent <= indent:
            raise _error("yaml-nested-value-missing", line.number)
        if lines[index].indent != indent + 2:
            raise _error("yaml-indent-invalid", lines[index].number)
        result[key], index = _parse_block(lines, index, indent + 2)
    return result, index


def _parse_sequence(
    lines: tuple[_Line, ...],
    index: int,
    indent: int,
) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise _error("yaml-indent-invalid", line.number)
        if not _is_sequence(line.content):
            raise _error("mixed-container", line.number)
        raw_value = line.content[1:].strip()
        index += 1
        if not raw_value:
            if index >= len(lines) or lines[index].indent != indent + 2:
                raise _error("yaml-sequence-value-missing", line.number)
            parsed, index = _parse_block(lines, index, indent + 2)
            result.append(parsed)
            continue
        if ":" in raw_value:
            raise _error("yaml-sequence-mapping-unsupported", line.number)
        result.append(_parse_scalar(raw_value, line.number))
        if index < len(lines) and lines[index].indent > indent:
            raise _error("yaml-scalar-cannot-have-children", lines[index].number)
    return result, index


def _parse_block(
    lines: tuple[_Line, ...],
    index: int,
    indent: int,
) -> tuple[Any, int]:
    line = lines[index]
    if line.indent != indent:
        raise _error("yaml-indent-invalid", line.number)
    if _is_sequence(line.content):
        return _parse_sequence(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def parse_safe_yaml(text: str) -> dict[str, Any]:
    """Parse a deterministic JSON-compatible subset of YAML 1.2."""

    lines = _prepare(text)
    result, index = _parse_block(lines, 0, 0)
    if index != len(lines):
        raise _error("yaml-trailing-content", lines[index].number)
    if not isinstance(result, dict):
        raise MemoryPolicyError("yaml-root-must-be-object")
    return result
