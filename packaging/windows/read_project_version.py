"""Print project version from pyproject.toml (works on Python 3.9; tomllib is 3.11+)."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    try:
        import tomllib  # Python 3.11+

        ver = tomllib.loads(text)["project"]["version"]
    except ModuleNotFoundError:
        m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
        if not m:
            sys.exit("Could not parse version from pyproject.toml")
        ver = m.group(1)
    print(ver)


if __name__ == "__main__":
    main()
