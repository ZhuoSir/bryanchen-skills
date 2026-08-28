"""Render PDF pages to PNG images (NOT OCR — just rasterization).

Used as the input step for both channel B (model reads the image) and
channel C (local OCR). Rendering is done in-process by PyMuPDF.

Usage:
    python render_pages.py <file.pdf> --pages 3,5,7-9
    python render_pages.py <file.pdf> --dpi 200 --outdir rendered/

Prints the list of generated PNG paths (one per line) to stdout.
"""
import argparse
import os
import sys


def parse_pages(spec, total):
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
    ap.add_argument("--pages", help="1-based page spec, e.g. 3,5,7-9 (default: all)")
    ap.add_argument("--dpi", type=int, default=150,
                    help="150 is enough for model reading; use 200+ for OCR")
    ap.add_argument("--outdir", default="rendered")
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
    os.makedirs(args.outdir, exist_ok=True)

    zoom = args.dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    for pno in pages:
        pix = doc[pno - 1].get_pixmap(matrix=matrix, alpha=False)
        out = os.path.join(args.outdir, f"page-{pno}.png")
        pix.save(out)
        print(out)


if __name__ == "__main__":
    main()
