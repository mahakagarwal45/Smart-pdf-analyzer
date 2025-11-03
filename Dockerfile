FROM python:3.10-slim

WORKDIR /app

# copy everything
COPY . .

# install pytorch cpu
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu

# install requirements from root
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["gunicorn", "backend.app:app", "--bind", "0.0.0.0:8000"]
