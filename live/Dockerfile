# Built from the repository's root (see docker-compose.yml), so the site's fonts are copied, not kept twice.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr tesseract-ocr-srp \
    && rm -rf /var/lib/apt/lists/*
# yt-dlp needs a JavaScript runtime for YouTube; Deno is the one it uses without settings.
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno
WORKDIR /srv
COPY live/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY live/uzivo ./uzivo
COPY src/zailiprotiv/static/fonts ./uzivo/static/fonts
EXPOSE 8000
CMD ["uvicorn", "uzivo.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
