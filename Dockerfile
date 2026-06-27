# Build context is the repo root:  docker build .
FROM python:3.12-slim

WORKDIR /app

# Single package: the editor brain and the platform host that wraps it.
COPY . .
RUN pip install --no-cache-dir .

# The site lives on a persistent volume mounted here; seeded at runtime on first boot.
# Do NOT COPY content into this path — it's the mount point.
ENV SITE_DIR=/site
ENV PORT=8080
RUN mkdir -p /site

EXPOSE 8080
# `python -m rectify.platform` starts the platform host.
ENTRYPOINT ["python", "-m", "rectify.platform"]
