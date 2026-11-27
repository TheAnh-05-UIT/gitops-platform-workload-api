import io
import json
import unittest
from unittest.mock import patch

from workload_api.demo_jobs import aggregate, run_batch, run_worker


class DemoJobsTests(unittest.TestCase):
    def test_batch_reports_availability_and_fails_on_any_failed_probe(self):
        stream = io.StringIO()
        self.assertEqual(run_batch(3, probe=lambda: (False, 8), stream=stream), 1)
        self.assertEqual(json.loads(stream.getvalue()), {"event": "batch", "attempts": 3, "successes": 0, "max_ms": 8})

    def test_worker_until_asked_to_stop_and_redacted_events(self):
        stream = io.StringIO()
        stop = __import__("threading").Event()
        with patch.object(stop, "wait", side_effect=lambda interval: (stop.set(), True)[1]) as wait:
            run_worker(10, stop, probe=lambda: (True, 4), stream=stream)
        self.assertEqual(json.loads(stream.getvalue()), {"event": "probe", "attempts": 1, "successes": 1, "max_ms": 4})
        wait.assert_called_once_with(10)

    def test_aggregate_handles_mixed_results(self):
        self.assertEqual(aggregate("batch", [(True, 5), (False, 20), (True, 7)]),
                         {"event": "batch", "attempts": 3, "successes": 2, "max_ms": 20})
