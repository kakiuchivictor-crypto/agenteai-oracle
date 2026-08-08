# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# tesseract-ocr/poppler-utils sao necessarios apenas se OCR_ENABLED=true no
# .env (secao 5.1 do prompt mestre). Mantidos por padrao para que o OCR
# funcione out-of-the-box; remova-os do apt-get para reduzir o tamanho da
# imagem caso OCR nunca seja usado no seu ambiente.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/uploads data/processed data/vector_store data/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Aplica migrations, garante o usuario "sistema" (atribuicao de acoes sem
# login) e sobe a API. O frontend Streamlit roda em um comando separado (ver
# docker-compose.yml) reaproveitando esta mesma imagem.
CMD ["sh", "-c", "alembic upgrade head && python scripts/seed_system_user.py && uvicorn app.api.main:app --host 0.0.0.0 --port 8000"]
