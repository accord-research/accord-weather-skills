"""Copy tools/accord_contract.py into every skill as ``scripts/accord_contract/__init__.py``.

``--check`` only compares. The copy is a package directory rather than a second
``.py`` file because the catalog runner (skills-runner) runs the one ``.py`` file
directly inside ``scripts/`` and refuses a directory that holds two.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "accord_contract.py"
COPY = Path("scripts") / "accord_contract" / "__init__.py"
LEGACY = Path("scripts") / "accord_contract.py"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    check = "--check" in args
    src = SRC.read_text()
    stale = []
    for skill in sorted(p for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file()):
        dst = skill / COPY
        legacy = skill / LEGACY
        if dst.is_file() and dst.read_text() == src and not legacy.exists():
            continue
        if check:
            stale.append(dst)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SRC, dst)
        if legacy.exists():
            legacy.unlink()
            print(f"removed {legacy.relative_to(ROOT)}")
        print(f"synced {dst.relative_to(ROOT)}")
    for dst in stale:
        print(f"out of sync: {dst.relative_to(ROOT)}", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
