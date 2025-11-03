from sentence_transformers import SentenceTransformer, util
from transformers import pipeline
import numpy as np
import re
import os
import json
import time
from extractor import extract_text_chunks
from utils import is_appendix_chunk, ensure_dir
import torch

# Global cache for models
_ST_MODEL = None
_SUM_PIPE = None
_QA_PIPE = None


def log(msg):
    print(f"[Analyzer] {msg}", flush=True)


# ========== Sentence Transformer (for semantic ranking) ==========
def get_st_model():
    global _ST_MODEL
    if _ST_MODEL is None:
        log("Loading lightweight embedding model (all-MiniLM-L6-v2)...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _ST_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    return _ST_MODEL


# ========== Summarization Pipeline ==========
def get_summarizer():
    """
    Loads summarizer model with fallback and truncation.
    Uses DistilBART first, falls back to T5-small for speed.
    """
    global _SUM_PIPE
    if _SUM_PIPE is None:
        try:
            log("Loading summarization model (DistilBART)...")
            _SUM_PIPE = pipeline("summarization", model="t5-small",
                                 device=0 if torch.cuda.is_available() else -1,
                                 truncation=True)
        except Exception as e:
            log(f"⚠️ DistilBART unavailable ({e}). Using T5-small instead.")
            try:
                _SUM_PIPE = pipeline("summarization", model="t5-small",
                                     device=0 if torch.cuda.is_available() else -1,
                                     truncation=True)
            except Exception as e2:
                log(f"❌ All summarization models failed: {e2}")
                _SUM_PIPE = None
    return _SUM_PIPE


# ========== QA Pipeline ==========
def get_qa_pipeline():
    global _QA_PIPE
    if _QA_PIPE is None:
        log("Loading QA model (distilbert)...")
        _QA_PIPE = pipeline("question-answering", model="sshleifer/tiny-distilbert-base-cased-distilled-squad",
                            device=0 if torch.cuda.is_available() else -1)
    return _QA_PIPE


# ========== File Handling ==========
def results_path_for_uid(uid, results_folder):
    return os.path.join(results_folder, f"{uid}_results.json")


def save_results(results_dict, results_folder):
    ensure_dir(results_folder)
    with open(results_path_for_uid(results_dict["uid"], results_folder), "w", encoding="utf-8") as f:
        json.dump(results_dict, f, ensure_ascii=False, indent=2)


def load_results(uid, results_folder):
    path = results_path_for_uid(uid, results_folder)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ========== Semantic Ranking ==========
def semantic_rank_for_file(pdf_path, persona_text, top_k=20, chunk_size=120, overlap=40, score_threshold=0.15):
    start = time.time()
    log("Extracting text chunks...")
    chunks = extract_text_chunks(pdf_path, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return []

    texts = [c["text"] for c in chunks if c["text"].strip()]
    model = get_st_model()

    log("Encoding chunks (may take ~5-10s first time)...")
    with torch.no_grad():
        embeddings = model.encode(texts, convert_to_tensor=True, batch_size=8, show_progress_bar=False)
        q_emb = model.encode(persona_text, convert_to_tensor=True)

    scores = util.cos_sim(q_emb, embeddings)[0].cpu().numpy()

    keywords = re.findall(r"\b[a-zA-Z]{3,}\b", persona_text.lower())
    hits = []
    for idx, (chunk, s) in enumerate(zip(chunks, scores)):
        t = chunk["text"].lower()
        boost = 0.3 * sum(1 for kw in keywords if kw in t)
        if chunk.get("is_heading"): 
            boost += 0.5
        combined = float(s) + boost
        if combined >= score_threshold:
            hits.append({
                "page": chunk.get("page"),
                "text": chunk["text"],
                "score": round(combined, 3)
            })

    hits.sort(key=lambda x: x["score"], reverse=True)
    unique, seen = [], set()
    for h in hits:
        key = h["text"][:100].lower()
        if key not in seen:
            seen.add(key)
            unique.append(h)
        if len(unique) >= top_k:
            break

    log(f"✅ Ranking complete in {round(time.time()-start,2)}s. Found {len(unique)} relevant chunks.")
    return unique


# ========== Summarization ==========
def summarize_text_chunks(chunks):
    if not chunks:
        return "No relevant sections found."
    joined = " ".join([c["text"] for c in chunks])[:2000]
    summarizer = get_summarizer()
    if summarizer:
        try:
            res = summarizer(joined, max_length=80, min_length=25, do_sample=False)
            return res[0]["summary_text"].strip()
        except Exception:
            pass
    # fallback: fast top sentences
    sentences = re.split(r'(?<=[.!?]) +', joined)
    return " ".join(sentences[:3]).strip()


def summarize_hits_for_uid(uid, results_folder):
    """
    Load top retrieved chunks and generate a summary.
    """
    r = load_results(uid, results_folder)
    hits = r.get("hits", [])
    if not hits:
        return ""
    return summarize_text_chunks(hits[:6])

# ========== Question Answering ==========
def answer_question_for_uid(uid, results_folder, question, top_k=5):
    r = load_results(uid, results_folder)
    hits = r.get("hits", [])
    
    if not hits:
        return "No context available.", 0.0, []

    context = " ".join([h["text"] for h in hits[:top_k]])
    qa = get_qa_pipeline()
    try:
        res = qa(question=question, context=context)
        answer = res.get("answer", "").strip()
        score = float(res.get("score", 0.0))
    except Exception:
        answer, score = "Unable to answer. Please try again later.", 0.0

    sources = []
    for i, h in enumerate(hits[:top_k], start=1):
        snippet = (h["text"][:200] + "...") if len(h["text"]) > 200 else h["text"]
        sources.append({
            "rank": i,
            "page": h.get("page"),
            "score": h.get("score"),
            "snippet": snippet
        })

    return answer, score, sources
