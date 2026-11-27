FROM python:3.12-alpine@sha256:c5ba3deef00c7758561a0f03c26f44f10589263d40e732b8748e0d1f38f6dd89

# Keep the Kerberos library on the verified Alpine security release.
RUN apk add --no-cache krb5-libs=1.22.3-r0
WORKDIR /app

COPY requirements-linux.lock .
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements-linux.lock

COPY workload_api/ ./workload_api/

USER 10001:10001
EXPOSE 8080

CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:8080", "workload_api.app:app"]
