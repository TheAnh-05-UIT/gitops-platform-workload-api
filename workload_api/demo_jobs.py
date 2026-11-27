"""Private HTTP probe worker and finite availability batch for the lab demo."""
import argparse
import json
import signal
import sys
from threading import Event
import time
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

TARGET = "http://workload-api.workloads.svc.cluster.local/healthz"


class DenyRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_readiness():
    start = time.monotonic()
    try:
        with build_opener(ProxyHandler({}), DenyRedirect()).open(TARGET, timeout=3) as response:
            ready = response.status == 200
    except (OSError, URLError):
        ready = False
    return ready, round((time.monotonic() - start) * 1000)


def aggregate(event, samples):
    return {"event": event, "attempts": len(samples), "successes": sum(ready for ready, _ in samples),
            "max_ms": max(elapsed for _, elapsed in samples)}


def run_worker(interval, stop, *, probe=request_readiness, stream=sys.stdout):
    while not stop.is_set():
        print(json.dumps(aggregate("probe", [probe()])), file=stream, flush=True)
        stop.wait(interval)


def run_batch(count, *, probe=request_readiness, stream=sys.stdout):
    result = aggregate("batch", [probe() for _ in range(count)])
    print(json.dumps(result), file=stream, flush=True)
    return int(result["successes"] != count)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    jobs = parser.add_subparsers(dest="job", required=True)
    worker = jobs.add_parser("worker")
    worker.add_argument("--interval", type=int, choices=range(10, 301), default=30, metavar="SECONDS")
    batch = jobs.add_parser("batch")
    batch.add_argument("--samples", type=int, choices=range(1, 11), default=3, metavar="COUNT")
    args = parser.parse_args()
    if args.job == "batch":
        return run_batch(args.samples)
    stop = Event()

    def request_stop(*_):
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    run_worker(args.interval, stop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
