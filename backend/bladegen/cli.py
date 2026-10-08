"""BladeGen command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bladegen.pipeline import build


def main() -> int:
    parser = argparse.ArgumentParser(prog="bladegen")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="Build one blade from BladeSpec JSON")
    build_parser.add_argument("spec", type=Path)
    build_parser.add_argument("--output", type=Path, default=Path("output"))
    build_parser.add_argument(
        "--reference-step",
        type=Path,
        help="Optional regression reference; not part of BladeSpec or production generation.",
    )
    args = parser.parse_args()

    result = build(args.spec, args.output, args.reference_step)
    summary = {
        "status": result["status"],
        "solid": result["solidification"]["solid_after_reimport"],
        "x57_regression": result.get("x57_regression"),
        "outputs": result["outputs"],
    }
    print(json.dumps(summary, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
