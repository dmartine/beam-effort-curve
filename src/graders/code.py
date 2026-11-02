"""Code grader: run the model's last ```python block against the task's tests.

Model output is untrusted. Every run gets a fresh temp dir, a stripped
environment, and a timeout. Set CODE_SANDBOX=docker to also cut network
access (recommended for the full run).
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT_S = 20
RUNNER = """

if __name__ == "__main__":
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
    print("ALL_PASSED")
"""


def extract_code(text):
    if not text:
        return None
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    return blocks[-1] if blocks else None


def grade(task, row):
    code = extract_code(row.get("content"))
    if code is None:
        return {"correct": False, "format_ok": False, "detail": "no code block"}
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "run.py"
        script.write_text(code + "\n\n" + task["tests"] + RUNNER)
        if os.getenv("CODE_SANDBOX") == "docker":
            cmd = ["docker", "run", "--rm", "--network", "none", "--memory", "512m",
                   "-v", f"{tmp}:/w:ro", "python:3.11-slim", "python", "-I", "/w/run.py"]
        else:
            cmd = [sys.executable, "-I", str(script)]
        try:
            p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=TIMEOUT_S,
                               env={"PATH": os.environ.get("PATH", "")})
        except subprocess.TimeoutExpired:
            return {"correct": False, "format_ok": True, "detail": "timeout"}
    passed = p.returncode == 0 and "ALL_PASSED" in p.stdout
    return {"correct": passed, "format_ok": True, "detail": None if passed else p.stderr[-500:]}
