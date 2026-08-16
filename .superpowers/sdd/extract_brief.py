"""Extract one Task N section from an implementation plan."""
from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: extract_brief.py PLAN_FILE N OUTFILE")
    plan = Path(sys.argv[1]).read_text(encoding="utf-8")
    n = int(sys.argv[2])
    out_path = Path(sys.argv[3])
    lines = plan.splitlines(keepends=True)
    out: list[str] = []
    intask = False
    infence = False
    fence = "```"
    for line in lines:
        if line.startswith(fence):
            infence = not infence
        if not infence and re.match(r"^#+[ \t]+Task[ \t]+\d+", line):
            intask = bool(re.match(rf"^#+[ \t]+Task[ \t]+{n}([^0-9]|$)", line))
        if intask:
            out.append(line)
    if not out:
        raise SystemExit(f"task {n} not found in {sys.argv[1]}")
    out_path.write_text("".join(out), encoding="utf-8")
    print(f"wrote {out_path}: {len(out)} lines")


if __name__ == "__main__":
    main()
