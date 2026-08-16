from pathlib import Path
import subprocess
import sys
import uuid

base, head = sys.argv[1], sys.argv[2]
outdir = Path(".superpowers/sdd")
outdir.mkdir(parents=True, exist_ok=True)
out = outdir / f"review-{uuid.uuid4().hex[:12]}.diff"
parts = []
parts.append("=== COMMITS ===\n")
parts.append(
    subprocess.check_output(
        ["git", "log", "--oneline", f"{base}..{head}"], text=True, encoding="utf-8"
    )
)
parts.append("\n=== STAT ===\n")
parts.append(
    subprocess.check_output(
        ["git", "diff", "--stat", f"{base}..{head}"], text=True, encoding="utf-8"
    )
)
parts.append("\n=== DIFF ===\n")
parts.append(
    subprocess.check_output(
        ["git", "diff", "-U10", f"{base}..{head}"], text=True, encoding="utf-8"
    )
)
out.write_text("".join(parts), encoding="utf-8")
print(out.resolve())
