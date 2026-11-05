#!/usr/bin/env python3
"""Read-only, bounded NFCore HTTP load benchmark for 50/100 concurrent clients.

NEVER transmits fiscal documents or requires secrets. This only measures readiness.
The actual issuance contract is /v1/issuances; /v2/documents/issue is not
registered in the current Bridge API and must not be mistaken for a working API.

To execute on the authorized homologation host:
 python scripts/bench/nfcore_readiness_load.py --base-url https://api.nfcore.com.br \\
   --acknowledge-shared-environment

Results are JSON on stdout; HTTP 500 or non-200 is counted as failure.
This does NOT certify end-to-end document issuance or PostgreSQL integrity.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import statistics
import time
from collections import Counter
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def _percentile(samples: list[float], percentile: float) -> float:
    if not samples:
        return math.nan
    sorted_values = sorted(samples)
    index = (len(sorted_values) - 1) * percentile / 100
    low = int(index)
    high = min(len(sorted_values) - 1, low + 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (index - low)


def _get_health(url: str) -> tuple[int, float]:
    start = time.perf_counter()
    try:
        request = Request(url, method="GET", headers={"Accept": "application/json"})
        with urlopen(request, timeout=15) as response:
            response.read(4096)
            status = response.status
    except HTTPError as exc:
        status = exc.code
    except (URLError, TimeoutError, OSError):
        status = 0
    return status, round((time.perf_counter() - start) * 1000, 3)


def run_phase(url: str, concurrency: int, total_requests: int) -> dict[str, object]:
    if total_requests < concurrency:
        raise ValueError("total_requests must be at least concurrency")
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(_get_health, [url] * total_requests))
    duration = time.perf_counter() - started
    latencies = [ms for _, ms in results]
    codes = Counter(str(code) for code, _ in results)
    return {
        "concurrency": concurrency,
        "requests": len(results),
        "http_status_counts": dict(sorted(codes.items())),
        "ok_200": codes.get("200", 0),
        "failures": len(results) - codes.get("200", 0),
        "duration_seconds": round(duration, 3),
        "throughput_requests_per_second": round(len(results) / duration, 2),
        "latency_mean_ms": round(statistics.mean(latencies), 3),
        "latency_p50_ms": round(_percentile(latencies, 50), 3),
        "latency_p95_ms": round(_percentile(latencies, 95), 3),
        "latency_p99_ms": round(_percentile(latencies, 99), 3),
        "latency_max_ms": round(max(latencies), 3),
        "target_mean_below_350_ms": statistics.mean(latencies) < 350,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--acknowledge-shared-environment", action="store_true",
        help="Operator attests that the shared environment is authorized for this load.",
    )
    parser.add_argument("--requests-per-phase", type=int, default=100)
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "api.nfcore.com.br", "staging-api.nfcore.com.br",
    } or parsed.path not in {"", "/"}:
        parser.error("Only the approved NFCore HTTPS API hostname is supported")
    if not args.acknowledge_shared_environment:
        parser.error("Explicit shared-environment approval is required")
    if not 100 <= args.requests_per_phase <= 500:
        parser.error("Bounded load must use 100..500 requests per phase")
    url = args.base_url.rstrip("/") + "/health/ready"
    phases = [run_phase(url, parallelism, args.requests_per_phase) for parallelism in (50, 100)]
    print(json.dumps({
        "scenario": "non-mutating readiness GET",
        "url": url,
        "issue_endpoint": "/v1/issuances (NOT exercised)",
        "requested_v2_issue_endpoint": "not exposed in current canonical API",
        "postgresql_integrity": "not measured",
        "plan_limits": "not measured",
        "phases": phases,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
