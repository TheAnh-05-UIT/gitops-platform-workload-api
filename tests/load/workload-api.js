import http from "k6/http";
import { check, sleep } from "k6";

const origin = __ENV.WORKLOAD_LOOPBACK || "http://127.0.0.1:18080";
if (!/^http:\/\/127\.0\.0\.1:[0-9]{1,5}$/.test(origin)) {
  throw new Error("WORKLOAD_LOOPBACK must be an approved local HTTP port-forward");
}

export const options = {
  vus: 3,
  duration: "30s",
  discardResponseBodies: false,
  thresholds: {
    checks: [{ threshold: "rate>=0.99", abortOnFail: true, delayAbortEval: "5s" }],
    http_req_duration: ["p(95)<250"],
  },
};

export default function () {
  const response = http.get(`${origin}/`, { timeout: "2s", redirects: 0 });
  if (response.status === 200) {
    let valid = false;
    try {
      const body = response.json();
      valid = body.app === "workload-api" && Boolean(body.version);
    } catch {
      // Record invalid response bodies as failed checks.
    }
    check(response, { "HTTP 200 with workload identity": () => valid });
  } else {
    check(response, { "HTTP 200 with workload identity": () => false });
  }
  sleep(1);
}
