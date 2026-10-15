FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app \
    && mkdir -p /data/uploads \
    && chown -R app:app /app /data

COPY --chown=app:app backend/ ./backend/

ENV DATABASE_URL=sqlite:////data/rutasegura.db \
    UPLOADS_DIR=/data/uploads

USER app
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
