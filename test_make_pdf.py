import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from htmlbook import make_pdf
from htmlbook.book_name import get_project_name


class MakePdfTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="book with spaces ")
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        (self.project / "pyproject.toml").write_text(
            '[tool.poetry]\nname = "example-book"\n', encoding="utf-8"
        )
        self.root = self.project / "book"
        self.root.mkdir()
        (self.root / "index.html").write_text(
            '<link rel="canonical" href="https://example.org/notes/index.html">',
            encoding="utf-8",
        )
        (self.root / "intro.html").write_text("<p>Chapter</p>", encoding="utf-8")
        (self.root / "notebooks.js").write_text("// asset", encoding="utf-8")
        (self.root / "chapters.json").write_text(
            json.dumps({"chapter_ids": ["intro"]}), encoding="utf-8"
        )
        self.output = self.project / "output directory" / "result.pdf"
        self.output.parent.mkdir()
        self.output.write_bytes(b"existing PDF")

    def test_project_name_uses_explicit_location(self):
        self.assertEqual(get_project_name(self.root), "example-book")

    def test_book_url_uses_canonical_directory(self):
        source = (self.root / "index.html").read_text(encoding="utf-8")
        self.assertEqual(make_pdf.get_book_url(source), "https://example.org/notes/")
        for source in (
            "<html></html>",
            '<link rel="canonical" href="file:///tmp/book">',
        ):
            with self.subTest(source=source), self.assertRaisesRegex(
                ValueError, "canonical"
            ):
                make_pdf.get_book_url(source)

    @patch.object(make_pdf.shutil, "which", return_value="tool")
    def test_renderer_failure_preserves_previous_pdf(self, _which):
        failure = subprocess.CalledProcessError(1, "node")
        with patch.object(make_pdf.subprocess, "run", side_effect=failure) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                make_pdf.build_pdf(self.root, self.output)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(self.output.read_bytes(), b"existing PDF")
        self.assertEqual(list(self.output.parent.iterdir()), [self.output])

    @patch.object(make_pdf.shutil, "which", return_value="tool")
    def test_prince_failure_preserves_previous_pdf(self, _which):
        calls = [None, None, subprocess.CalledProcessError(1, "prince")]
        with patch.object(make_pdf.subprocess, "run", side_effect=calls):
            with self.assertRaises(subprocess.CalledProcessError):
                make_pdf.build_pdf(self.root, self.output)
        self.assertEqual(self.output.read_bytes(), b"existing PDF")

    @patch.object(make_pdf.shutil, "which", return_value="tool")
    def test_success_prepares_all_chapters_and_assets_before_rendering(self, _which):
        def run(args, *, check):
            self.assertTrue(check)
            if args[0] == "node":
                chapter = Path(args[3])
                self.assertTrue((chapter.parent / "intro.html").is_file())
                self.assertTrue((chapter.parent / "notebooks.js").is_file())
                self.assertEqual(
                    args[4:], ["https://example.org/notes/", "index.html", "intro.html"]
                )
                self.assertEqual(chapter.as_uri(), args[2])
            else:
                self.assertEqual(args[0], "prince")
                Path(args[-1]).write_bytes(b"new PDF")

        with patch.object(make_pdf.subprocess, "run", side_effect=run):
            self.assertEqual(
                make_pdf.build_pdf(self.root, self.output), self.output.resolve()
            )
        self.assertEqual(self.output.read_bytes(), b"new PDF")
        self.assertEqual(list(self.output.parent.iterdir()), [self.output])

    def test_missing_prince_has_actionable_error(self):
        with patch.object(make_pdf.shutil, "which", side_effect=["node", None]):
            with self.assertRaisesRegex(RuntimeError, "prince is required"):
                make_pdf.build_pdf(self.root, self.output)


if __name__ == "__main__":
    unittest.main()
