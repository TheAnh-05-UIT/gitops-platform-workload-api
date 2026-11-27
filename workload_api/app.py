import logging
from time import perf_counter

from flask import Flask, Response, g, request

from workload_api.metrics import RedMetrics

app = Flask(__name__)
app.logger.setLevel(logging.INFO)
VERSION = "v2"
metrics = RedMetrics()


@app.before_request
def start_request_timer():
    g.request_started = perf_counter()


@app.after_request
def observe_request(response):
    if request.endpoint not in {"health", "metrics_endpoint"}:
        started = g.get("request_started")
        if started is not None:
            route, status_class = metrics.observe(
                request.endpoint, response.status_code, perf_counter() - started
            )
            app.logger.info("workload_api_request route=%s status_class=%s", route, status_class)
    return response


@app.get("/")
def index():
    return {"app": "workload-api", "version": VERSION}


@app.get("/healthz")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics_endpoint():
    return Response(metrics.render(), content_type="text/plain; version=0.0.4; charset=utf-8")
