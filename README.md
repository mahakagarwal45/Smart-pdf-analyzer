# Document Intelligence System

This project is an AI-powered PDF Understanding and Highlighting Tool. It allows users to upload any PDF, define a persona (what they are searching for), and the system will semantically analyze the document, highlight only the most relevant sections inside the PDF, and also generate an appendix page summarizing the findings.

# What this system does


- Upload a PDF through browser
- Enter a persona (example: *"I am looking for technological advancements in renewable energy"*)
- System reads the PDF, splits text into chunks, creates embeddings, and finds meaningfully relevant content using cosine similarity
- Highlights relevant sections in the original PDF (color-coded by importance)
- Appends a summary (appendix) at the end of the PDF with:
  - Page numbers
  - Relevance scores
  - Color legend
- Final highlighted PDF becomes available to download

# How to run the project (Step-by-Step)

# Step 1 - Clone the repository
git clone https://github.com/LavanyaPathak17/Document-Intelligence-System.git

# Step 2 - Go into the project root folder
cd pdf-analyzer

# Step 3 - Create a Virtual Environment
 FOR WINDOWS
python -m venv venv
venv\Scripts\activate

FOR MAC/LINUX
python3 -m venv venv
source venv/bin/activate

# Step 4 - Install all dependencies
pip install -r requirements.txt

# Step 5 - Run the Flask server
cd backend
python app.py

# Step 6 - Open the application on browser
you will be able to see the Browser Url, Run the app, upload your PDF, provide your persona, and instantly get a highlighted, appendix-enhanced research-ready PDF.
