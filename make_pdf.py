"""Build a book PDF; see Developers.md for prerequisites and usage."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

if __package__:
    from .book_name import get_project_name
else:
    from book_name import get_project_name


class CanonicalURLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.url = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and "canonical" in attrs.get("rel", "").split():
            self.url = attrs.get("href")


def get_book_url(index_html):
    """Use the published URL, independent of the checkout's directory name."""
    parser = CanonicalURLParser()
    parser.feed(index_html)
    parsed = urlsplit(parser.url or "")
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("index.html needs an HTTP(S) canonical URL; use --book-url")
    return urljoin(parser.url, ".")


def prepare_html(source):
    # Annotation scripts can alter text after MathJax has typeset it.
    return source.replace(
        '<script src="https://hypothes.is/embed.js" async></script>', ""
    ).replace(
        '<script type="text/plain" data-run-after="mathjax" '
        'src="https://hypothes.is/embed.js"></script>',
        "",
    )


def build_pdf(root, output, book_url=None):
    root = Path(root).resolve()
    output = Path(output).resolve()
    book_url = book_url or get_book_url(
        (root / "index.html").read_text(encoding="utf-8")
    )
    parsed = urlsplit(book_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("--book-url must be an HTTP(S) URL")
    book_url = book_url.rstrip("/") + "/"
    for tool in ("node", "prince"):
        if not shutil.which(tool):
            raise RuntimeError(
                f"{tool} is required to build PDFs; see htmlbook/Developers.md"
            )

    chapters = json.loads((root / "chapters.json").read_text(encoding="utf-8"))
    chapter_files = [f"{c}.html" for c in ["index", *chapters["chapter_ids"]]]
    output.parent.mkdir(parents=True, exist_ok=True)
    # Keep the final PDF on the output filesystem so replacement is atomic.
    with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory(
        dir=output.parent
    ) as pdf_directory:
        directory = Path(directory)
        for asset in root.iterdir():
            if asset.name not in chapter_files:
                (directory / asset.name).symlink_to(asset)
        # Prepare every chapter first, so Prince can resolve cross-chapter links.
        for filename in chapter_files:
            (directory / filename).write_text(
                prepare_html((root / filename).read_text(encoding="utf-8")),
                encoding="utf-8",
            )
        for filename in chapter_files:
            path = directory / filename
            print(f"Rendering {filename}", flush=True)
            subprocess.run(
                [
                    "node",
                    str(root / "htmlbook/render_html.js"),
                    path.as_uri(),
                    str(path),
                    book_url,
                    *chapter_files,
                ],
                check=True,
            )
        temporary_pdf = Path(pdf_directory) / output.name
        subprocess.run(
            [
                "prince",
                "-s",
                str(root / "htmlbook/pdf.css"),
                *[str(directory / filename) for filename in chapter_files],
                "-o",
                str(temporary_pdf),
            ],
            check=True,
        )
        if not temporary_pdf.is_file() or temporary_pdf.stat().st_size == 0:
            raise RuntimeError("Prince did not produce a PDF")
        os.replace(temporary_pdf, output)
    return output


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o", "--output", type=Path, help="output PDF (default: <project-name>.pdf)"
    )
    parser.add_argument(
        "--book-url",
        help="published book directory URL (default: index.html canonical URL)",
    )
    args = parser.parse_args()
    output = args.output or Path(f"{get_project_name(root)}.pdf")
    try:
        result = build_pdf(root, output, args.book_url)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"PDF build failed: {error}\n")
    print(f"Wrote {result}")


if __name__ == "__main__":
    main()
