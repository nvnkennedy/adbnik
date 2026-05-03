# Managing old versions on PyPI (after **1.0.0**)

PyPI does **not** support deleting **every** release: a project must keep at least one **non-yanked** distribution so installs remain possible.

## Recommended approach

1. Publish **`adbnik==1.0.0`** (wheel + sdist) from this repository.
2. For each older release you no longer want advertised as “latest” (**2.x–5.x**):
   - Open [pypi.org/manage/project/adbnik/releases/](https://pypi.org/manage/project/adbnik/releases/)
   - Choose the version → **Yank** (optionally with a reason).

**Yanking** hides the release from the default “latest” resolution while **pins** like `pip install adbnik==5.1.2` can still work for reproducibility.

## Deleting a file entirely

PyPI allows **removing individual files** in limited cases; policies change—check [PyPI help](https://pypi.org/help/). Prefer **yank** unless you have a strong compliance reason.

## API / automation

You can yank via the [PyPI API](https://docs.pypi.org/api/) using an API token with appropriate scope. Rotate tokens after use.
