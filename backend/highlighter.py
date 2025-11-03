# backend/highlighter.py
import fitz
import re
import shutil
import textwrap

# Define colors for highlight ranks
RANK_COLORS = [
    (1, 0.2, 0.2),    # Red - Most Relevant
    (1, 0.5, 0.0),    # Orange - Highly Relevant
    (1, 0.85, 0.2),   # Yellow - Moderately Relevant
    (0.6, 0.9, 0.6),  # Green - Somewhat Relevant
    (0.6, 0.8, 0.95)  # Blue - Less Relevant
]

RANK_LABELS = [
    "Most Relevant",
    "Highly Relevant",
    "Moderately Relevant",
    "Somewhat Relevant",
    "Less Relevant"
]


def _rgb(c):
    """Convert tuple to valid RGB float tuple."""
    return (float(c[0]), float(c[1]), float(c[2]))


def highlight_pdf_with_ranks(input_pdf_path, output_pdf_path, hits, appendix_text=None):
    """
    Highlights text in the PDF based on relevance rank and adds a clean legend appendix page.
    """
    if not hits:
        shutil.copy(input_pdf_path, output_pdf_path)
        return

    doc = fitz.open(input_pdf_path)
    used_ranks = {}

    for rank_idx, hit in enumerate(hits):
        page_no = hit.get("page", 1) - 1
        if page_no < 0 or page_no >= len(doc):
            continue

        page = doc[page_no]
        color = _rgb(RANK_COLORS[min(rank_idx, len(RANK_COLORS) - 1)])
        used_ranks[min(rank_idx, len(RANK_COLORS) - 1)] = used_ranks.get(rank_idx, 0) + 1

        text = hit.get("text", "").strip()
        if not text:
            continue

        # Find text in page with fallback methods
        rects = page.search_for(text, hit_max=50)
        if not rects and len(text.split()) > 5:
            partial = " ".join(text.split()[:6])
            rects = page.search_for(partial, hit_max=50)
        if not rects:
            first = re.escape(text.split()[0]) if text.split() else ""
            if first:
                rects = page.search_for(first, hit_max=20)

        # Apply highlights
        for r in rects:
            annot = page.add_highlight_annot(r)
            annot.set_colors(stroke=color)
            annot.update()
    doc.save(output_pdf_path, garbage=4, deflate=True)
    doc.close()
    print("[Highlighter] ✅ Highlights + Single Appendix Page added successfully.")
