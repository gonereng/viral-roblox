FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV MEDIA_ROOT=/app/media

EXPOSE 8000

CMD ["uvicorn", "roblox_viral.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
