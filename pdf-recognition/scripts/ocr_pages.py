"""Local offline OCR via RapidOCR (channel C, the fallback).

RapidOCR runs ONNX Runtime inference in-process on CPU. It is a pip
library, NOT a server: no ports, no daemon, no deployment. Model weights
(~15MB) are downloaded once on first use, then it works fully offline.

Usage:
    python ocr_pages.py <file.pdf> --pages 3,5,7-9 --dpi 200
    python ocr_pages.py --images rendered/page-3.png rendered/page-5.png

Output: reconstructed plain text per page on stdout. Lines whose mean
recognition confidence is below LOW_CONFIDENCE are marked [低置信度];
downstream readers must treat them as uncertain.
"""
import argparse
import gc
import sys

LOW_CONFIDENCE = 0.6
# Two boxes belong to the same visual line if their vertical centers are
# within this fraction of the average box height.
LINE_Y_TOLERANCE = 0.6


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


def reconstruct_lines(ocr_result):
    """Turn scattered OCR boxes into reading-order lines.

    ocr_result: list of [box, text, score] where box is 4 corner points.
    Strategy: sort by vertical center, cluster boxes whose centers are
    close vertically, then sort each cluster left-to-right.
    """
    if not ocr_result:
        return ""

    items = []
    for box, text, score in ocr_result:
        # rapidocr_onnxruntime 1.2.x returns score as a str like '0.6657';
        # coerce to float so confidence math works across versions.
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 1.0
        ys = [pt[1] for pt in box]
        xs = [pt[0] for pt in box]
        items.append({
            "yc": sum(ys) / len(ys),
            "x0": min(xs),
            "h": max(ys) - min(ys),
            "text": text,
            "score": score,
        })
    items.sort(key=lambda it: it["yc"])

    lines, current = [], []
    for it in items:
        if current:
            avg_h = sum(c["h"] for c in current) / len(current)
            ref_yc = sum(c["yc"] for c in current) / len(current)
            if abs(it["yc"] - ref_yc) > avg_h * LINE_Y_TOLERANCE:
                lines.append(current)
                current = []
        current.append(it)
    if current:
        lines.append(current)

    out = []
    for line in lines:
        line.sort(key=lambda it: it["x0"])
        text = " ".join(it["text"] for it in line)
        conf = sum(it["score"] for it in line) / len(line)
        out.append(f"[低置信度] {text}" if conf < LOW_CONFIDENCE else text)
    return "\n".join(out)


def ocr_image(engine, image):
    """Run OCR on a file path or numpy array; return reconstructed text."""
    result, _ = engine(image)
    return reconstruct_lines(result)


def make_engine():
    """Create the RapidOCR engine with constrained resources.

    Single-threaded ONNX sessions use noticeably less memory and CPU —
    important on small servers where the OOM killer watches RSS.
    Falls back to defaults on older rapidocr versions without these args.
    """
    from rapidocr_onnxruntime import RapidOCR
    try:
        return RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
    except TypeError:
        return RapidOCR()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?", help="PDF file (omit when using --images)")
    ap.add_argument("--pages", help="1-based page spec, e.g. 3,5,7-9 (default: all)")
    ap.add_argument("--dpi", type=int, default=200, help="render DPI for PDF input")
    ap.add_argument("--images", nargs="+", help="OCR these image files instead of a PDF")
    args = ap.parse_args()

    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        print("RapidOCR not installed. Run: pip install -r scripts/requirements.txt",
              file=sys.stderr)
        sys.exit(3)

    engine = make_engine()  # first call downloads ~15MB weights, then offline

    if args.images:
        for img in args.images:
            print(f"===== {img} =====")
            print(ocr_image(engine, img))
            print()
        return

    if not args.pdf:
        print("provide a PDF file or --images", file=sys.stderr)
        sys.exit(2)

    try:
        import fitz
        import numpy as np
    except ImportError as exc:
        print(f"missing dependency: {exc}. Run: pip install -r scripts/requirements.txt",
              file=sys.stderr)
        sys.exit(3)

    doc = fitz.open(args.pdf)
    if doc.needs_pass:
        print("PDF is encrypted; password required.", file=sys.stderr)
        sys.exit(1)

    pages = parse_pages(args.pages, doc.page_count) if args.pages else range(1, doc.page_count + 1)
    zoom = args.dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for pno in pages:
        pix = doc[pno - 1].get_pixmap(matrix=matrix, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)
        print(f"===== Page {pno} =====")
        print(ocr_image(engine, img))
        print()
        # Free the page bitmap immediately — at 200 DPI one A4 page is
        # ~12MB, and letting them pile up gets small servers OOM-killed.
        del img, pix
        gc.collect()

    doc.close()


if __name__ == "__main__":
    main()
