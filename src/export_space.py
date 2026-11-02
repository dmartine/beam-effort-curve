"""Copy analysis outputs and the chart module into space/ so the Space runs standalone.

    python -m src.analyze && python -m src.router && python -m src.export_space
    python -m src.export_space --write-policy   # after the full run: ship the learned policy in the wrapper
"""

import argparse
import json
import shutil
from pathlib import Path

from .client import EFFORTS
from .run import RESULTS_DIR

SPACE = Path(__file__).resolve().parents[1] / "space"
FILES = ["summary.csv", "summary_by_tier.csv", "overthinking.csv", "router_eval.csv", "router_sweep.csv", "router_policy.json"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-policy", action="store_true",
                        help="overwrite beam_autoeffort/policy.json with results/router_policy.json")
    args = parser.parse_args()

    data = SPACE / "data"
    data.mkdir(exist_ok=True)
    for name in FILES:
        src = RESULTS_DIR / name
        if src.exists():
            shutil.copy(src, data / name)
            print(f"copied {name}")
        else:
            print(f"missing {name} (run analyze/router first)")
    shutil.copy(Path(__file__).resolve().parents[1] / "FINDINGS.md", data / "findings.md")
    charts_src = (Path(__file__).parent / "charts.py").read_text()
    standalone = charts_src.replace("from .client import EFFORTS", f"EFFORTS = {EFFORTS!r}")
    (SPACE / "charts.py").write_text(standalone)
    (SPACE / "requirements.txt").write_text("gradio[oauth]\nplotly\npandas\nopenai\n")

    # ship the learned policy in the drop-in wrapper, then copy the wrapper into the Space
    policy_src = RESULTS_DIR / "router_policy.json"
    package = Path(__file__).resolve().parents[1] / "beam_autoeffort"
    if args.write_policy and policy_src.exists():
        learned = json.loads(policy_src.read_text())
        (package / "policy.json").write_text(json.dumps(
            {"provisional": False, "tolerance": learned["tolerance"], "policy": learned["policy"]}, indent=2) + "\n")
        print(f"policy written to {package / 'policy.json'}: {learned['policy']}")
    shutil.copytree(package, SPACE / "beam_autoeffort", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    print(f"space ready in {SPACE}")


if __name__ == "__main__":
    main()
