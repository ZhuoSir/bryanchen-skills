"""Extract the embedded text layer of a PDF (channel A).

Usage:
    python extract_text.py <file.pdf>                  # whole document
    python extract_text.py <file.pdf> --pages 3,5,7-9  # selected pages
    python extract_text.py <file.pdf> -o out.md        # write to file

Output goes to stdout unless -o is given. Page ranges are 1-based,
inclusive, comma-separated, with hyphen ranges allowed.
"""
import argparse
import sys


def parse_pages(spec, total):
    """Parse '3,5,7-9' into a sorted list of valid 1-based page numbers."""
    pages = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            pages.update(range(int(a), int(b) + 1))
        else:
            pages.add(int(part))
    return sorted(p for p in pages if 1 <= p <= total)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--pages", help="1-based page spec, e.g. 3,5,7-9")
    ap.add_argument("-o", "--out", help="output file (default: stdout)")
    args = ap.parse_args()

    try:
        import fitz
    except ImportError:
        print("PyMuPDF not installed. Run: pip install -r scripts/requirements.txt",
              file=sys.stderr)
        sys.exit(3)

    doc = fitz.open(args.pdf)
    if doc.needs_pass:
        print("PDF is encrypted; password required.", file=sys.stderr)
        sys.exit(1)

    pages = parse_pages(args.pages, doc.page_count) if args.pages else range(1, doc.page_count + 1)

    chunks = []
    for pno in pages:
        text = doc[pno - 1].get_text("text").strip()
        chunks.append(f"===== Page {pno} =====\n{text}")
    result = "\n\n".join(chunks)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"wrote {args.out} ({len(result)} chars)")
    else:
        print(result)


if __name__ == "__main__":
    main()
