# gitops-platform-workload-api

The API listens on port 8080. `GET /` reports the workload identity and version. `GET /healthz` is the process probe. `GET /metrics` exposes Prometheus request counts and a request-duration histogram for an internal collector. Metrics omit probes and scrapes and use only known route names and status classes. The optional lab Ingress routes only the application path.

The image uses one Gunicorn worker per Pod so a scrape sees the same process-local counters on every request. Scrape each Pod independently, then aggregate rates across replicas. Counters reset on restart. Scale the number of Pods through reviewed Config, and review metric aggregation before increasing the number of workers within a Pod.

The application emits a bounded `workload_api_request` event with route name and status class. The approved collector only forwards that subset and omits headers, request data, raw paths, query parameters and exception diagnostics.

Run `python -B -m unittest discover -s tests -p test_red_metrics.py` from the Workload root. Install the existing runtime dependencies in an approved development environment to exercise the Flask test client as part of this suite.
