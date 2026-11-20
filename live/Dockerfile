# Built from the repository's root (see docker-compose.yml), so the site's fonts are copied, not kept twice.
# The images are named by their content (20 Nov 2026): a tag can be moved to another image, a digest can't. Dependabot
# moves them once a month (.github/dependabot.yml).
FROM denoland/deno:bin-2.9.8@sha256:b507583d3c68ba69f3ed2ce5969ae5b8b70f43421c781279c7aea06435263543 AS deno
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr tesseract-ocr-srp fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
# yt-dlp needs a JavaScript runtime for YouTube; Deno is the one it uses without settings.
COPY --from=deno /deno /usr/local/bin/deno
WORKDIR /srv
COPY live/requirements.txt live/constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt
COPY live/uzivo ./uzivo
COPY src/zailiprotiv/static/fonts ./uzivo/static/fonts
# The script and styles shared with the site's mikrofon page (page._shared)
COPY src/zailiprotiv/templates/mikrofon.js src/zailiprotiv/templates/mikrofon.css ./uzivo/static/
# The site's Cyrillic converter (names.cyrillic), so both editions write Cyrillic alike.
COPY src/zailiprotiv/cyrillic.py ./uzivo/cirilica.py
# The site's analytics token and counter (config.ANALYTICS_TOKEN, VOTES_API): visits and presses counted as on the site
COPY data/settings.json ./uzivo/static/settings.json
# Whisper's model is fetched once and kept with the data (prepis.py)
ENV HF_HOME=/data/hf
# What was built (mikrofon.ps1 passes them): the commit, its branch, and whether the tree had changes not committed.
# `uzivo` puts live only an image of a clean origin/main; the page and /stanje.json show the commit (config.VERSION).
ARG VERZIJA=""
ARG GRANA=""
ARG CISTO=""
LABEL zailiprotiv.verzija=$VERZIJA zailiprotiv.grana=$GRANA zailiprotiv.cisto=$CISTO
ENV VERZIJA=$VERZIJA
# `docker ps` says whether it answers (mikrofon.ps1 waits for the page itself)
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/stanje.json', timeout=4)"
# Not as root (20 Nov 2026): the service reads video from outside with ffmpeg, yt-dlp and tesseract, and holds keys.
# The entry starts as root only to hand /data (volumes written by root until now) to the user, then becomes it.
RUN useradd --create-home --uid 1000 uzivo
COPY --chmod=755 live/ulaz.sh /usr/local/bin/ulaz
ENTRYPOINT ["ulaz"]
EXPOSE 8000
CMD ["uvicorn", "uzivo.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
