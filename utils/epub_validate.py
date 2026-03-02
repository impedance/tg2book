from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree


class EpubValidationError(ValueError):
    pass


_CONTAINER_NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}


def _fail(message: str) -> EpubValidationError:
    return EpubValidationError(message)


def validate_epub_zip(zf: zipfile.ZipFile) -> None:
    names = zf.namelist()
    if not names:
        raise _fail("Empty ZIP archive.")

    if len(names) != len(set(names)):
        raise _fail("ZIP contains duplicate filenames.")

    for name in names:
        if name.startswith("/") or name.startswith("\\") or ".." in Path(name).parts:
            raise _fail(f"Suspicious ZIP path: {name!r}")

    if names[0] != "mimetype":
        raise _fail("EPUB requires 'mimetype' to be the first ZIP entry.")

    mimetype_info = zf.getinfo("mimetype")
    if mimetype_info.compress_type != zipfile.ZIP_STORED:
        raise _fail("EPUB requires 'mimetype' to be stored (uncompressed).")

    mimetype = zf.read("mimetype")
    if mimetype != b"application/epub+zip":
        raise _fail("Invalid mimetype payload (expected 'application/epub+zip').")

    required = (
        "META-INF/container.xml",
        "OEBPS/content.opf",
        "OEBPS/content.xhtml",
    )
    missing = [p for p in required if p not in names]
    if missing:
        raise _fail(f"Missing required EPUB files: {', '.join(missing)}")

    container_xml = zf.read("META-INF/container.xml")
    try:
        root = ElementTree.fromstring(container_xml)
    except ElementTree.ParseError as e:
        raise _fail(f"Invalid container.xml XML: {e}") from e

    rootfile = root.find(".//c:rootfile", namespaces=_CONTAINER_NS)
    if rootfile is None:
        raise _fail("container.xml missing <rootfile> entry.")

    full_path = rootfile.attrib.get("full-path")
    if not full_path:
        raise _fail("container.xml <rootfile> missing 'full-path' attribute.")

    if full_path not in names:
        raise _fail(f"container.xml points to missing package document: {full_path!r}")


def validate_epub_bytes(data: bytes) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        validate_epub_zip(zf)


def validate_epub_path(path: str | Path) -> None:
    with zipfile.ZipFile(path) as zf:
        validate_epub_zip(zf)


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate basic EPUB ZIP invariants.")
    parser.add_argument("path", help="Path to .epub file")
    args = parser.parse_args(argv)

    try:
        validate_epub_path(args.path)
    except EpubValidationError as e:
        print(f"EPUB validation failed: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
