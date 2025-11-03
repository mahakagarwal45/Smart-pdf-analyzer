# backend/app.py
import os
import uuid
import fitz  # PyMuPDF
from datetime import datetime
import json
from flask import Flask, request, render_template, send_from_directory, jsonify, url_for
from werkzeug.utils import secure_filename
from analyzer import (
    semantic_rank_for_file,
    summarize_hits_for_uid,
    load_results,
    save_results,
    answer_question_for_uid,
    summarize_text_chunks
)
from highlighter import highlight_pdf_with_ranks
from utils import ensure_dir
import re
import textwrap

os.environ["HF_HOME"] = "B:/huggingface_cache"

BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
RESULTS_FOLDER = os.path.join(BASE_DIR, "static", "results")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf'}

app = Flask(
    __name__,
    template_folder=os.path.join("..", "frontend", "templates"),
    static_folder=os.path.join("..", "frontend", "static")
)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 400 * 1024 * 1024  # 400MB limit


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return render_template("index.html")


@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store"
    return response


# ✅ Clean text utility for appendix
def clean_text_for_pdf(text):
    replacements = {
        "•": "-", "–": "-", "—": "-", "−": "-",
        "’": "'", "‘": "'", "“": '"', "”": '"',
        "°": " degrees", "→": "->", "…": "...",
        "●": "-", "✓": "✔", "§": "Section"
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", " ", text)


# ✅ Single formatted appendix generator
def append_appendix_to_pdf(pdf_path, persona, summary, hits, uid):
    try:
        doc = fitz.open(pdf_path)
        page = doc.new_page()  # Add one appendix page at the end

        # === Title ===
        page.insert_textbox(
            fitz.Rect(40, 30, 550, 70),
            "APPENDIX",
            fontsize=20,
            fontname="Times-Bold",
            color=(0, 0, 0),
            align=1
        )

        # === Prepare formatted content ===
        appendix_text = f"""
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Persona / Research Goal:
{persona}


Summary of Findings:
{summary}


Top Relevant Sections:
"""
        appendix_text = clean_text_for_pdf(appendix_text)
        # === Write sections ===
        y = 100
        line_gap = 14
        wrap_width = 120
        def add_wrapped_text(text, bold=False, indent=0):
            """Helper to add wrapped text with optional indentation and bold font."""
            nonlocal y, page
            for line in textwrap.wrap(text, width=wrap_width - indent):
                if y > 770:
                    page = doc.new_page()
                    y = 80
                page.insert_text(
                    (60 + indent, y),
                    line,
                    fontsize=11 if bold else 10,
                    fontname="Times-Bold" if bold else "Times-Roman",
                    color=(0, 0, 0)
                )
                y += line_gap
        # --- Header sections ---
        add_wrapped_text(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", bold=True)
        y += 10
        add_wrapped_text("Persona / Research Goal:", bold=True)
        add_wrapped_text(persona)
        y += 15
        add_wrapped_text("Summary of Findings:", bold=True)
        add_wrapped_text(summary)
        y += 15
        add_wrapped_text("Top Relevant Sections:", bold=True)
        y += 5
        # --- Top Relevant Sections (Numbered + Indented) ---
        for i, h in enumerate(hits[:5], 1):
            snippet = clean_text_for_pdf(h["text"][:350].replace("\n", " "))
            header = f"{i}. (Pg {h['page']})"
            add_wrapped_text(header, bold=True, indent=5)
            add_wrapped_text(f"- {snippet}...", indent=15)
            y += 10
         # === Color Legend Block ===
        y += 20
        if y > 700:
            page = doc.new_page()
            y = 100
        page.insert_text((60, y), "Highlight Color Legend:", fontsize=12, fontname="Times-Bold")
        y += 20
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
        # show only top_k colors (based on hits length)
        top_k = min(len(hits), 5)
        for i in range(top_k):
            rgb = RANK_COLORS[i]
            label = RANK_LABELS[i]
            page.draw_rect(fitz.Rect(70, y, 90, y + 12), color=rgb, fill=rgb)
            page.insert_text((100, y + 1), f"{label}", fontsize=10, fontname="Times-Roman")
            y += 16
        # Footer line
        y += 25
        page.draw_line(fitz.Point(60, y), fitz.Point(550, y))
        page.insert_text((60, y + 10), "Generated by Smart PDF Analyzer", fontsize=8, color=(0.3, 0.3, 0.3))
        # === Save cleanly ===
        doc.save(pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        doc.close()
        print("[Analyzer] ✅ Appendix page added successfully with proper formatting.")

    except Exception as e:
        print(f"[WARN] Failed to append appendix page: {e}")

@app.route("/upload", methods=["POST"])
def upload():
    """Handles PDF upload, semantic analysis, highlighting, and appendix creation."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    persona = request.form.get('persona', '').strip()
    top_k = int(request.form.get('top_k', 3))

    top_k = min(top_k, 5)

    if not file or file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if not persona:
        return jsonify({"error": "Please provide a persona / job-to-be-done text"}), 400

    persona_words = persona.split()
    warning_message = None
    if len(persona_words) > 100:
        warning_message = f"Persona too long ({len(persona_words)} words). Using first 100."
        persona = " ".join(persona_words[:100])

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    filename = secure_filename(file.filename)
    uid = str(uuid.uuid4())[:8]
    saved_name = f"{uid}_{filename}"
    saved_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_name)
    file.save(saved_path)

    try:
        # Step 1: Semantic ranking
        hits = semantic_rank_for_file(
            saved_path, persona,
            top_k=top_k, chunk_size=60, overlap=20, score_threshold=0.25
        )

        # Step 2: Save results
        results = {"uid": uid, "hits": hits, "filename": filename}
        save_results(results, RESULTS_FOLDER)

        # Step 3: Summarize
        summary = summarize_hits_for_uid(uid, RESULTS_FOLDER)

        # Step 4: Highlight
        out_name = f"{uid}_highlighted_{filename}"
        out_path = os.path.join(app.config['UPLOAD_FOLDER'], out_name)
        highlight_pdf_with_ranks(saved_path, out_path, hits)

        # Step 5: Add clean single appendix
        append_appendix_to_pdf(out_path, persona, summary, hits, uid)

        # Step 6: Stats for chart
        color_stats = [
            sum(1 for h in hits if h["score"] >= 0.9),
            sum(1 for h in hits if 0.7 <= h["score"] < 0.9),
            sum(1 for h in hits if 0.5 <= h["score"] < 0.7),
            sum(1 for h in hits if 0.3 <= h["score"] < 0.5),
            sum(1 for h in hits if h["score"] < 0.3),
        ]

        download_url = url_for('download_file', filename=out_name)
        response_data = {
            "uid": uid,
            "summary": summary,
            "download_url": download_url,
            "color_stats": color_stats,
            "hits": hits,
        }
        if warning_message:
            response_data["warning"] = warning_message

        return jsonify(response_data)

    except Exception as e:
        print(f"[UPLOAD ERROR] {e}", flush=True)
        return jsonify({"error": f"Error during analysis or highlighting: {str(e)}"}), 500


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    uid = data.get("uid")
    question = data.get("question", "").strip()
    top_k = int(data.get("top_k", 5))

    if not uid or not question:
        return jsonify({"error": "uid and question are required"}), 400

    try:
        answer, score, sources = answer_question_for_uid(uid, RESULTS_FOLDER, question, top_k=top_k)
    except Exception as e:
        return jsonify({"error": f"Error during QA: {str(e)}"}), 500

    return jsonify({
        "answer": answer,
        "score": float(score),
        "sources": sources
    })


@app.route('/uploads/<path:filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
