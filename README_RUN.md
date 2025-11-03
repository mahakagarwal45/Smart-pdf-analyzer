Semantic PDF Highlighter - Run Instructions

Prereqs (local):
 - Python 3.10+
 - pip

Local run:
1. cd document_analyzer
2. pip install -r requirements.txt
3. cd backend
4. python app.py
5. Open http://127.0.0.1:8000 in browser

Docker run:
1. docker build -t semantic-pdf-highlighter .
2. docker run --rm -p 8000:8000 -v $(pwd)/backend/static/uploads:/app/backend/static/uploads semantic-pdf-highlighter
3. Open http://localhost:8000

Notes:
 - First build downloads the sentence-transformers model (done in Docker build).
 - Running locally the first time will download the model automatically.
 - Adjust chunk_size (words) and overlap in analyzer.semantic_rank_for_file call via app.py if needed.
 - The highlighting does best with exact text; chunking and fallback sentence splitting improves matching.
