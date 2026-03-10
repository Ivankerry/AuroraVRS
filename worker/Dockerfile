FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir numpy==1.26.4

RUN pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "two_tower_trainer.py"]
