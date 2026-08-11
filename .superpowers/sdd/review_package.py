from pathlib import Path
import subprocess
import sys

base, head = sys.argv[1], sys.argv[2]
out = Path(sys.argv[3]) if len(sys.argv) > 3 else None

def sh(*args):
    return subprocess.check_output(list(args), text=True)

base7 = sh("git", "rev-parse", "--short", base).strip()
head7 = sh("git", "rev-parse", "--short", head).strip()
if out is None:
    out = Path(f".superpowers/sdd/review-{base7}..{head7}.diff")

parts = [
    f"# Review package: {base}..{head}\n",
    "\n## Commits\n",
    sh("git", "log", "--oneline", f"{base}..{head}"),
    "\n## Files changed\n",
    sh("git", "diff", "--stat", f"{base}..{head}"),
    "\n## Diff\n",
    sh("git", "diff", "-U10", f"{base}..{head}"),
]
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("".join(parts), encoding="utf-8")
count = sh("git", "rev-list", "--count", f"{base}..{head}").strip()
print(f"wrote {out}: {count} commit(s), {out.stat().st_size} bytes")
