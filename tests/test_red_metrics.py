import importlib.util
import unittest

from workload_api.metrics import RedMetrics


class RedMetricsTest(unittest.TestCase):
    def test_uses_bounded_labels_and_cumulative_buckets(self):
        metrics = RedMetrics()
        metrics.observe("index", 200, 0.01)
        metrics.observe("index", 503, 0.75)
        metrics.observe("request-path-with-secret", 404, 0.5)
        data = metrics.render()
        self.assertNotIn("request-path-with-secret", data)
        self.assertIn('workload_api_http_requests_total{route="index",status_class="2xx"} 1\n', data)
        self.assertIn('workload_api_http_requests_total{route="index",status_class="5xx"} 1\n', data)
        self.assertIn('workload_api_http_requests_total{route="unmatched",status_class="4xx"} 1\n', data)
        self.assertIn('workload_api_http_request_duration_seconds_bucket{route="index",le="0.05"} 1\n', data)
        self.assertIn('workload_api_http_request_duration_seconds_bucket{route="index",le="+Inf"} 2\n', data)
        self.assertIn('workload_api_http_request_duration_seconds_count{route="index"} 2\n', data)
        self.assertIn('workload_api_http_request_duration_seconds_sum{route="index"} 0.76\n', data)

    @unittest.skipUnless(importlib.util.find_spec("flask"), "Flask runtime dependency unavailable")
    def test_flask_smoke_preserves_contract_and_excludes_collection_from_red(self):
        from workload_api.app import app

        client = app.test_client()
        self.assertEqual(client.get("/").json, {"app": "workload-api", "version": "v2"})
        self.assertEqual(client.get("/healthz").json, {"status": "ok"})
        self.assertEqual(client.get("/unknown/customer-id?token=redacted").status_code, 404)
        response = client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "text/plain; version=0.0.4; charset=utf-8")
        data = response.get_data(as_text=True)
        for value in ("healthz", "metrics\"", "customer-id", "token=redacted"):
            self.assertNotIn(value, data)
        self.assertIn('route="index",status_class="2xx"', data)
        self.assertIn('route="unmatched",status_class="4xx"', data)

    @unittest.skipUnless(importlib.util.find_spec("flask"), "Flask runtime dependency unavailable")
    def test_request_log_uses_only_bounded_fields(self):
        from workload_api.app import app

        with self.assertLogs(app.logger, level="INFO") as captured:
            app.test_client().get(
                "/customer-proof-identifier?token=private-value",
                headers={"Authorization": "Bearer example-not-a-token"},
            )
        self.assertEqual(
            [record.getMessage() for record in captured.records],
            ["workload_api_request route=unmatched status_class=4xx"],
        )
