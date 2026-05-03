"""stdin: full git commit message, stdout: same message without Cursor co-author trailer."""
import sys

def main() -> None:
    data = sys.stdin.read()
    out: list[str] = []
    for line in data.splitlines(keepends=True):
        s = line.strip()
        if s.startswith("Co-authored-by:") and "cursoragent@cursor.com" in s:
            continue
        out.append(line)
    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main()
