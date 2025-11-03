import os
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

# def is_appendix_chunk(text: str) -> bool:
#     lower = text.lower()
#     appendix_keywords = ["appendix", "references", "bibliography", "index"]
#     return any(kw in lower for kw in appendix_keywords)

def is_appendix_chunk(pdf_path, persona, summary, hits, uid):
    """
    Appends an appendix page at the end of the PDF summarizing the analysis.
    """
    doc = fitz.open(pdf_path)
    page = doc.new_page()  # adds a blank page at end

    appendix_text = f"""
APPENDIX


🕒 Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

🎯 Persona / Research Goal:
{persona}

🧾 Summary of Findings:
{summary}

📑 Top Relevant Sections:
"""
    for i, h in enumerate(hits[:5], 1):
        snippet = h['text'][:200].replace('\n', ' ') + "..."
        appendix_text += f"\n{i}. (Pg {h['page']}) – {snippet}"

    page.insert_text((50, 50), appendix_text, fontsize=10)
    doc.save(pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    doc.close()
