"""BladeGen command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bladegen.pipeline import build
from bladegen.propeller_pipeline import build_propeller
from bladegen.runtime.manager import RuntimeReadinessError, require_runtime_ready


def main() -> int:
    parser = argparse.ArgumentParser(prog="bladegen")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="Build one blade from BladeSpec JSON")
    build_parser.add_argument("spec", type=Path)
    build_parser.add_argument("--output", type=Path, default=Path("output"))
    build_parser.add_argument(
        "--progress-file",
        type=Path,
        help="Optional atomic progress JSON path for an external job supervisor.",
    )
    build_parser.add_argument(
        "--reference-step",
        type=Path,
        help="Optional regression reference; not part of BladeSpec or production generation.",
    )
    propeller_parser = subparsers.add_parser(
        "build-propeller", help="Build a full propeller from PropellerSpec JSON"
    )
    propeller_parser.add_argument("spec", type=Path)
    propeller_parser.add_argument("--output", type=Path, default=Path("output"))
    propeller_parser.add_argument(
        "--progress-file",
        type=Path,
        help="Optional atomic progress JSON path for an external job supervisor.",
    )
    runtime_parser = subparsers.add_parser(
        "runtime-info", help="Inspect the selected fixed-plane generation runtime"
    )
    runtime_parser.add_argument("--json", action="store_true", dest="as_json")
    subparsers.add_parser("doctor", help="Check fixed-plane generation readiness")
    args = parser.parse_args()

    if args.command in {"runtime-info", "doctor"}:
        try:
            identity = require_runtime_ready()
        except RuntimeReadinessError as exc:
            payload = {"ready": False, "error": str(exc)}
            if args.command == "runtime-info" and args.as_json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"Generation runtime: NOT READY\n{exc}")
            return 2
        payload = {"ready": True, **identity.private_dict()}
        if args.command == "runtime-info" and args.as_json:
            print(json.dumps(payload, indent=2))
        else:
            print(
                "Generation runtime: READY\n"
                f"Build: {identity.build_id}\n"
                f"Contract: {identity.construction_contract}\n"
                f"Root: {identity.root}"
            )
        return 0

    if args.command == "build-propeller":
        result = build_propeller(args.spec, args.output, args.progress_file)
        summary = {
            "status": result["status"],
            "build_type": "propeller",
            "solid": result["assembly_validation"]["final_after_reimport"],
            "assembly": result["assembly_validation"],
            "outputs": result["outputs"],
            "engine": result.get("engine"),
        }
    else:
        result = build(args.spec, args.output, args.reference_step, args.progress_file)
        summary = {
            "status": result["status"],
            "build_type": "blade",
            "solid": result["solidification"]["solid_after_reimport"],
            "x57_regression": result.get("x57_regression"),
            "outputs": result["outputs"],
            "engine": result["engine"],
        }
    print(json.dumps(summary, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
