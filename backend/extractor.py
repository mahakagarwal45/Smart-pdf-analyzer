import fitz  # PyMuPDF
import re
import os
import base64

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads")
IMAGE_DIR = os.path.join(UPLOAD_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

def _save_image_bytes(img_dict, out_path):
    """
    img_dict is what doc.extract_image(xref) returns.
    Save bytes to out_path.
    """
    bytes_ = img_dict["image"]
    with open(out_path, "wb") as f:
        f.write(bytes_)

def extract_text_chunks(pdf_path, chunk_size=60, overlap=20):
    """
    Extract word windows as before, PLUS image blocks with caption detection.
    Returns list of chunks.
    """
    doc = fitz.open(pdf_path)
    chunks = []

    for pindex in range(len(doc)):
        page = doc[pindex]
        # Extract structured 'blocks' so we can find image blocks and text blocks with positions
        page_dict = page.get_text("dict")  # dict contains "blocks" with type: 0=text, 1=image, 2=...
        blocks = page_dict.get("blocks", [])

        # First: extract normal text chunks by using full-page combined text (like before)
        # We'll still produce text chunks via words window so semantic chunking remains stable.
        page_text = page.get_text().strip()
        if page_text:
            text = re.sub(r'\s+', ' ', page_text)
            words = text.split(" ")
            if len(words) <= chunk_size:
                chunks.append({"page": pindex + 1, "text": " ".join(words), "type": "text"})
            else:
                start = 0
                while start < len(words):
                    end = start + chunk_size
                    chunk_words = words[start:end]
                    chunk_text = " ".join(chunk_words)
                    chunks.append({"page": pindex + 1, "text": chunk_text, "type": "text"})
                    if end >= len(words):
                        break
                    start = end - overlap

        # Second: handle image blocks and try to find captions near the image bbox
        # blocks is ordered in reading order; image blocks have "type": 1
        for b in blocks:
            if b.get("type") == 1:
                # Image block
                bbox = b.get("bbox")  # [x0, y0, x1, y1]
                # get xref of image if available
                image_info = b.get("image")
                # PyMuPDF sometimes stores "image" with "xref"
                # extract by using the xref in the "image" dictionary or fallback to page.get_images
                img_path = None
                try:
                    # doc.extract_image needs xref; some block 'image' dict includes 'xref'
                    if isinstance(b.get("image"), dict) and "xref" in b.get("image"):
                        xref = b["image"]["xref"]
                        img_dict = doc.extract_image(xref)
                        img_ext = img_dict.get("ext", "png")
                        img_name = f"page{pindex+1}_img_{xref}.{img_ext}"
                        img_path = os.path.join(IMAGE_DIR, img_name)
                        _save_image_bytes(img_dict, img_path)
                    else:
                        # Fallback: scan page.get_images and save first matching xref (best-effort)
                        imgs = page.get_images(full=True)
                        if imgs:
                            # Use first image from page (best-effort fallback)
                            xref = imgs[0][0]
                            img_dict = doc.extract_image(xref)
                            img_ext = img_dict.get("ext", "png")
                            img_name = f"page{pindex+1}_img_{xref}.{img_ext}"
                            img_path = os.path.join(IMAGE_DIR, img_name)
                            if not os.path.exists(img_path):
                                _save_image_bytes(img_dict, img_path)
                except Exception:
                    img_path = None

                # Find caption: look for a text block whose bbox is just below the image bbox (y0 slightly greater than image y1)
                caption_text = ""
                try:
                    img_y1 = bbox[3]
                    # look for small vertical distance
                    for tb in blocks:
                        if tb.get("type") == 0:  # text block
                            tb_bbox = tb.get("bbox", [0,0,0,0])
                            tb_y0 = tb_bbox[1]
                            # check if tb is positioned below image and horizontally overlapping
                            if 0 <= (tb_y0 - img_y1) <= 30:  # tolerance px (tweakable)
                                # candidate caption
                                raw = tb.get("text", "").strip()
                                raw = re.sub(r'\s+', ' ', raw)
                                if len(raw) > 0 and len(raw) < 400:  # reasonable caption length
                                    caption_text = raw
                                    break
                except Exception:
                    caption_text = ""

                # Add an image chunk entry
                chunk = {
                    "page": pindex + 1,
                    "text": caption_text,      # may be empty
                    "type": "image",
                    "image_path": img_path,    # may be None
                    "bbox": bbox
                }
                chunks.append(chunk)

    doc.close()
    return chunks
