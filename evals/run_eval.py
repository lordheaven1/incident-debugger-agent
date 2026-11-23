import asyncio
import json
from pathlib import Path
import time

from app.agent.graph import run_triage_agent
from app.core.database import engine


async def evaluate() -> None:
    dataset_path = Path("evals/dataset.json")
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))

    total = len(cases)
    severity_hits = 0
    exception_hits = 0
    file_hits = 0
    latencies = []

    print(f"Running {total} evaluation cases...\n")

    for case in cases:
        start = time.perf_counter()
        report = await run_triage_agent(
            fingerprint=case["id"],
            service_name=case["service_name"],
            environment=case["environment"],
            raw_log=case["raw_log"],
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies.append(elapsed_ms)

        sev_ok = report["severity"] == case["expected_severity"]
        exc_ok = report["exception_type"] == case["expected_exception"]
        file_ok = report["affected_file"] == case["expected_file"]

        severity_hits += int(sev_ok)
        exception_hits += int(exc_ok)
        file_hits += int(file_ok)

        status = "PASS" if (sev_ok and exc_ok and file_ok) else "FAIL"
        print(
            f"[{status}] {case['id']} | "
            f"Severity: {report['severity']} | "
            f"Exception: {report['exception_type']} | "
            f"File: {report['affected_file']} | "
            f"{elapsed_ms:.1f} ms"
        )

    avg_latency = sum(latencies) / total if total else 0.0
    print("\n--- Evaluation Summary ---")
    print(f"Severity Accuracy  : {severity_hits}/{total} ({(severity_hits / total) * 100:.1f}%)")
    print(f"Exception Accuracy : {exception_hits}/{total} ({(exception_hits / total) * 100:.1f}%)")
    print(f"File Localization  : {file_hits}/{total} ({(file_hits / total) * 100:.1f}%)")
    print(f"Average Latency    : {avg_latency:.1f} ms")


async def main() -> None:
    try:
        await evaluate()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())