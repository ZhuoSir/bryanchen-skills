"""Probe a PDF: page count, encryption, text-layer coverage, outline.

Usage:
    python probe.py <file.pdf>

Prints a JSON report to stdout. Always run this FIRST before deciding
which extraction channel to use.
"""
import json
import sys

# A page is considered to have a usable text layer if it yields at least
# this many characters (filters out image-only pages with tiny headers).
MIN_TEXT_CHARS = 20


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python probe.py <file.pdf>", file=sys.stderr)
        sys.exit(2)

    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("PyMuPDF not installed. Run: pip install -r scripts/requirements.txt",
              file=sys.stderr)
        sys.exit(3)

    path = sys.argv[1]
    try:
        doc = fitz.open(path)
    except Exception as exc:  # corrupted / not a PDF
        print(json.dumps({"file": path, "error": f"cannot open: {exc}"},
                         ensure_ascii=False))
        sys.exit(1)

    info = {"file": path, "pages": doc.page_count, "encrypted": doc.needs_pass}
    if doc.needs_pass:
        # Do not attempt anything on an encrypted file.
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return

    pages = []
    for i in range(doc.page_count):
        n = len(doc[i].get_text("text").strip())
        pages.append({"page": i + 1, "chars": n, "has_text": n >= MIN_TEXT_CHARS})

    text_pages = sum(1 for p in pages if p["has_text"])
    info["text_pages"] = text_pages
    info["coverage"] = round(text_pages / doc.page_count, 3) if doc.page_count else 0.0
    info["no_text_pages"] = [p["page"] for p in pages if not p["has_text"]]
    info["outline"] = [
        {"level": lvl, "title": title, "page": page}
        for lvl, title, page in doc.get_toc()
    ]
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
