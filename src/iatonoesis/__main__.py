"""Research programme command-line interface."""

import argparse
import json
from pathlib import Path

from .programme import ready, validate


def main():
    parser = argparse.ArgumentParser(prog="iatonoesis")
    parser.add_argument("command", choices=("validate", "ready"))
    parser.add_argument("--programme", type=Path, default=Path("contracts/programme.v1.json"))
    args = parser.parse_args()
    try:
        data = json.loads(args.programme.read_text(encoding="utf-8"))
        if args.command == "validate":
            validate(data)
            print("Programme valid")
        else:
            for task in ready(data):
                print(f"{task['id']} {task['title']}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Programme rejected: {exc}\n")


if __name__ == "__main__":
    main()
