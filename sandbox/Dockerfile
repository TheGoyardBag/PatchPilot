FROM python:3.12-slim
WORKDIR /workspace
COPY src/patchpilot/engine/harness.py /runner/harness.py
ENV PYTHONDONTWRITEBYTECODE=1
USER 65532:65532
ENTRYPOINT ["python", "-I", "-S", "-B", "/runner/harness.py"]
