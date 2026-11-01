FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir '.[mp,wbm]'
COPY web/backend ./web/backend
RUN python -m pip install --no-cache-dir ./web/backend
WORKDIR /app/web/backend
CMD ["uvicorn", "ssscreen_web.main:app", "--host", "0.0.0.0", "--port", "8000"]
