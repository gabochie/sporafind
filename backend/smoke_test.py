"""
Production smoke test — runs against deployed endpoints and reports results.
Usage:
    python smoke_test.py                    # checks + reports to admin API
    python smoke_test.py --dry-run          # checks only, no reporting
    python smoke_test.py --api-base https://api.sporafind.com --web-base https://www.sporafind.com
"""

import argparse
import asyncio
import os
import time
import sys

import httpx

API_BASE = os.environ.get("SMOKE_API_BASE", "https://api.sporafind.com")
WEB_BASE = os.environ.get("SMOKE_WEB_BASE", "https://www.sporafind.com")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
TEST_EMAIL = os.environ.get("SMOKE_TEST_EMAIL", "testws@sporafind.com")
TEST_PASSWORD = os.environ.get("SMOKE_TEST_PASSWORD", "test123")


async def check(method: str, url: str, label: str, **kwargs) -> dict:
    start = time.monotonic()
    result = {
        "endpoint": label,
        "passed": False,
        "status_code": None,
        "duration_ms": None,
        "error": None,
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.request(method, url, **kwargs)
            duration = int((time.monotonic() - start) * 1000)
            result["status_code"] = resp.status_code
            result["duration_ms"] = duration
            result["passed"] = resp.status_code < 500
    except Exception as e:
        duration = int((time.monotonic() - start) * 1000)
        result["duration_ms"] = duration
        result["error"] = str(e)[:250]
    return result


async def run_smoke_tests(dry_run: bool = False) -> list[dict]:
    checks = [
        check("GET", f"{API_BASE}/", "api_root"),
        check("GET", f"{API_BASE}/health", "api_health"),
        check("GET", f"{API_BASE}/stats", "api_stats", headers={"X-Api-Key": "public"}),
        check("GET", f"{WEB_BASE}/", "web_home"),
        check("GET", f"{WEB_BASE}/api/pricing", "web_pricing"),
    ]

    # Auth check: login as test subscriber
    checks.append(
        check(
            "POST",
            f"{WEB_BASE}/api/workspace/login",
            "workspace_login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
    )

    results = await asyncio.gather(*checks)

    if dry_run:
        return results

    # Report results to admin API
    admin_results = []
    for r in results:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{API_BASE}/admin/smoke-test",
                    json={
                        "endpoint": r["endpoint"],
                        "passed": r["passed"],
                        "status_code": r["status_code"],
                        "duration_ms": r["duration_ms"],
                        "error": r["error"],
                    },
                    headers={"X-Admin-Key": ADMIN_KEY},
                )
                admin_results.append(resp.status_code)
        except Exception:
            admin_results.append(0)

    return results


def main():
    parser = argparse.ArgumentParser(description="Sporafind production smoke test")
    parser.add_argument("--dry-run", action="store_true", help="Check only, don't report")
    args = parser.parse_args()

    results = asyncio.run(run_smoke_tests(dry_run=args.dry_run))

    all_passed = all(r["passed"] for r in results)
    print(f"\n{'='*50}")
    print(f"Smoke test {'PASSED' if all_passed else 'FAILED'}")
    print(f"{'='*50}")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        ms = f"{r['duration_ms']}ms" if r["duration_ms"] else "N/A"
        code = r["status_code"] or "ERR"
        print(f"  [{status}] {r['endpoint']:30s} {code}  {ms}")
        if r["error"]:
            print(f"         error: {r['error']}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
