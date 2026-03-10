FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir numpy==1.26.4

RUN pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir faiss-cpu==1.8.0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
