"""curl-based HTTP helper so the harness has no non-stdlib HTTP dependency,
mirroring the exact curl invocations already verified manually."""
import json
import subprocess


def curl_json(method, url, json_body=None, headers=None, timeout=10):
    cmd = ["curl", "-s", "-w", "\n%{http_code}", "--max-time", str(timeout), "-X", method, url]
    for h in headers or []:
        cmd += ["-H", h]
    if json_body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(json_body)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed: {' '.join(cmd)}\n{proc.stderr}")
    body, _, code = proc.stdout.rpartition("\n")
    parsed = None
    if body:
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = body
    return int(code), parsed
