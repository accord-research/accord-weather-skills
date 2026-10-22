"""Copy tools/accord_contract.py beside every skill script. ``--check`` only compares."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "accord_contract.py"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    check = "--check" in args
    src = SRC.read_text()
    stale = []
    for skill in sorted(p for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file()):
        dst = skill / "scripts" / "accord_contract.py"
        if dst.is_file() and dst.read_text() == src:
            continue
        if check:
            stale.append(dst)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SRC, dst)
        print(f"synced {dst.relative_to(ROOT)}")
    for dst in stale:
        print(f"out of sync: {dst.relative_to(ROOT)}", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
