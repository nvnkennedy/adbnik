# Adbnik (PyQt5)

Desktop workspace for Android debugging: ADB, **SSH**, **serial**, file transfer, and USB **screen** forwarding.

| | |
|--|--|
| **PyPI package** | **`adbnik`** |
| **Run after install** | **`adbnik`** |
| **Python import** | `adbnik` |
| **Website** | [nvnkennedy.github.io/adbnik](https://nvnkennedy.github.io/adbnik/) |
| **PyPI** | [pypi.org/project/adbnik](https://pypi.org/project/adbnik/) |

## Install

```bash
pip install adbnik
adbnik
```

Same as: `python -m adbnik`

## Canonical repository

**[github.com/nvnkennedy/adbnik](https://github.com/nvnkennedy/adbnik)** — README, PyPI publish docs, and issues.

Rename the GitHub repo from `Device_Deck` (or earlier names) to **`adbnik`** in repository settings, then enable GitHub Pages from the `gh-pages` branch or `/docs` folder as you prefer.

## PyPI: retiring old package names

PyPI does not allow deleting projects entirely. For older names (**`devicedeck`**, **`adbsshdeck`**, or others you published):

1. Log in at [pypi.org](https://pypi.org) → your project → **Manage** → **Yank** releases (or mark the project deprecated in the description).
2. Publish **`adbnik`** as the current package (this repo uses `name = "adbnik"` in `pyproject.toml`).

## License

MIT — see [LICENSE](LICENSE).
