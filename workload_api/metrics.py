"""Bounded Prometheus RED metrics for a single workload API process."""

from collections import Counter
from threading import Lock


BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)
REQUESTS = "workload_api_http_requests_total"
DURATION = "workload_api_http_request_duration_seconds"


class RedMetrics:
    def __init__(self):
        self._requests = Counter()
        self._buckets = Counter()
        self._sums = Counter()
        self._counts = Counter()
        self._lock = Lock()

    def observe(self, route, status_code, seconds):
        route = "index" if route == "index" else "unmatched"
        status = status_code // 100
        status_class = f"{status}xx" if 1 <= status <= 5 else "other"

        with self._lock:
            self._requests[route, status_class] += 1
            self._counts[route] += 1
            self._sums[route] += seconds
            for boundary in BUCKETS:
                if seconds <= boundary:
                    self._buckets[route, boundary] += 1
        return route, status_class

    def render(self):
        lines = [
            f"# HELP {REQUESTS} Completed application HTTP requests.",
            f"# TYPE {REQUESTS} counter",
        ]
        with self._lock:
            for (route, status_class), count in sorted(self._requests.items()):
                lines.append(f'{REQUESTS}{{route="{route}",status_class="{status_class}"}} {count}')

            lines.extend((
                f"# HELP {DURATION} Application HTTP request duration in seconds.",
                f"# TYPE {DURATION} histogram",
            ))
            for route, count in sorted(self._counts.items()):
                for boundary in BUCKETS:
                    bucket_count = self._buckets[route, boundary]
                    lines.append(f'{DURATION}_bucket{{route="{route}",le="{boundary}"}} {bucket_count}')
                lines.extend((
                    f'{DURATION}_bucket{{route="{route}",le="+Inf"}} {count}',
                    f'{DURATION}_sum{{route="{route}"}} {self._sums[route]:.12g}',
                    f'{DURATION}_count{{route="{route}"}} {count}',
                ))

        return "\n".join(lines) + "\n"
