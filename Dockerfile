FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    WORDLIST_PATH=/data/words.tsv \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

# Kör som vanlig användare. /data håller ordlistan (och ev. nedladdad SALDO).
RUN useradd --create-home --uid 1000 korsord \
    && mkdir -p /data \
    && chown korsord:korsord /data
USER korsord
VOLUME ["/data"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/status', timeout=4)"

CMD ["python", "-m", "crossword.server"]
