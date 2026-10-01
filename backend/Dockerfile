# Budowany z katalogu glownego repo (context: .), bo obraz zawiera tez frontend.
# Obraz wieloarchitekturowy (amd64, arm64) budowany przez .github/workflows/release.yml.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Kod nalezy do roota (proces aplikacji nie moze go zmienic); zapisywalny jest tylko /data.
# UID 1000 stały - istniejace wolumeny z danymi naleza do tego uzytkownika.
COPY backend/app ./app
COPY frontend ./frontend
RUN adduser --disabled-password --gecos "" --uid 1000 appuser && mkdir -p /data && chown appuser:appuser /data
USER appuser

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
