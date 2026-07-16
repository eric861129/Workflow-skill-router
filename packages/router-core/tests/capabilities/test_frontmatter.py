from io import BytesIO
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from workflow_skill_router.capabilities.frontmatter import (
    FrontmatterError,
    parse_frontmatter,
    read_frontmatter_stream,
)


class GuardedReader(BytesIO):
    def readline(self, size=-1):
        if self.tell() >= self.getvalue().index(b"# instruction"):
            raise AssertionError("discovery 讀取了 instruction body")
        return super().readline(size)


class FrontmatterTests(unittest.TestCase):
    def test_reader_stops_at_closing_delimiter(self) -> None:
        stream = GuardedReader(
            b"---\nname: demo\ndescription: metadata only\n---\n# instruction\nnever read"
        )
        self.assertEqual(
            "demo",
            parse_frontmatter(read_frontmatter_stream(stream))["name"],
        )

    def test_invalid_utf8_in_instruction_body_does_not_break_discovery(self) -> None:
        stream = BytesIO(b"---\nname: demo\ndescription: ok\n---\n\xff\xfe")
        self.assertEqual(
            "demo",
            parse_frontmatter(read_frontmatter_stream(stream))["name"],
        )

    def test_duplicate_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(FrontmatterError, "重複 key"):
            parse_frontmatter(b"name: one\nname: two\n")

    def test_ambiguous_one_space_indentation_is_rejected(self) -> None:
        with self.assertRaisesRegex(FrontmatterError, "縮排"):
            parse_frontmatter(b"name: demo\nmetadata:\n domains: workflow\n")

    def test_invalid_utf8_in_frontmatter_is_rejected(self) -> None:
        with self.assertRaisesRegex(FrontmatterError, "UTF-8"):
            parse_frontmatter(b"name: \xff\n")

    def test_reader_rejects_header_over_limit_without_reading_body(self) -> None:
        stream = BytesIO(b"---\nname: " + b"a" * 64 + b"\n---\nbody")
        with self.assertRaisesRegex(FrontmatterError, "超過 32 bytes"):
            read_frontmatter_stream(stream, max_bytes=32)


if __name__ == "__main__":
    unittest.main()
