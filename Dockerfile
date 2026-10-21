FROM python:3.12-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home appuser \
    && mkdir -p /app/.patchpilot && chown -R appuser:appuser /app
ENV PATCHPILOT_ROOT=/app PATCHPILOT_STATE=/app/.patchpilot PYTHONDONTWRITEBYTECODE=1
USER appuser
EXPOSE 8000
CMD ["uvicorn", "patchpilot.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
