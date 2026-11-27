FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b

WORKDIR /app

COPY requirements-linux.lock .
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements-linux.lock

COPY workload_api/ ./workload_api/

USER 10001:10001
EXPOSE 8080

CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:8080", "workload_api.app:app"]
