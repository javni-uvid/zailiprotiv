"""The pages asked for, out of a built site, with what they load, to open from disk (the pregled workflow).

    python3 tools/pregled.py <built site> <out> [<page> …]

The pages may come instead in the environment, PREGLED_PAGES, separated by spaces or commas (the workflow's input,
never put into a shell line).
A page is a path inside the built site ("sednica/x.html", "cir/poslanik/y.html"); one that is not a file of the site
(an absolute path, "..", a name not built) is said and skipped, never read from elsewhere. Each page is copied with the
files of the site it names in src= and href= (styles, scripts, fonts, pictures), so it looks as it does on the site;
the pages it links to are not copied. Prints the site's size and what was copied.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

_REF = re.compile(r'(?:src|href)="([^"#?]+)')
_CSS_URL = re.compile(r'url\(["\']?([^"\')#?]+)')
_PAGE = re.compile(r"[A-Za-z0-9._/-]+\.html")


def inside(site: Path, rel: str) -> Path | None:
    """The file `rel` names inside the site, or None: no absolute path, no "..", only a file the build made."""
    if not _PAGE.fullmatch(rel) or rel.startswith("/") or ".." in rel.split("/"):
        return None
    path = (site / rel).resolve()
    try:
        path.relative_to(site.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def needs(site: Path, page: Path) -> set[Path]:
    """The site's own files a page loads (and those its stylesheets load), not the pages it links to."""
    found, todo = set(), [page]
    while todo:
        f = todo.pop()
        text = f.read_text(encoding="utf-8", errors="replace")
        refs = _CSS_URL.findall(text) if f.suffix == ".css" else _REF.findall(text)
        for ref in refs:
            if ref.startswith(("http:", "https:", "mailto:", "data:", "//")) or ref.endswith(".html") or ref.endswith("/"):
                continue
            target = (f.parent / ref).resolve()
            try:
                target.relative_to(site.resolve())
            except ValueError:
                continue
            if target.is_file() and target not in found:
                found.add(target)
                if target.suffix == ".css":
                    todo.append(target)
    return found


def main(argv: list[str]) -> int:
    import os
    site, out = Path(argv[0]), Path(argv[1])
    pages = argv[2:] or [p for p in re.split(r"[\s,]+", os.environ.get("PREGLED_PAGES", "")) if p][:40]
    size = sum(f.stat().st_size for f in site.rglob("*") if f.is_file())
    print(f"site: {size:,} bytes ({size / 1e6:.1f} MB), {sum(1 for f in site.rglob('*') if f.is_file()):,} files")
    # where the bytes are, by the first folder (and the Cyrillic edition's by its second), the largest first
    parts: dict[str, int] = {}
    for f in site.rglob("*"):
        if f.is_file():
            rel = f.relative_to(site).parts
            key = "/".join(rel[:2]) if rel[0] == "cir" and len(rel) > 2 else rel[0] if len(rel) > 1 else "(top)"
            if rel[0] in ("poslanik", "cir") and f.name.endswith("-glasovi.html"):
                key += " (-glasovi)"
            parts[key] = parts.get(key, 0) + f.stat().st_size
    for key, n in sorted(parts.items(), key=lambda kv: -kv[1])[:16]:
        print(f"  {n / 1e6:8.1f} MB  {key}")
    copied = 0
    for rel in pages:
        page = inside(site, rel)
        if page is None:
            print(f"not a page of the site: {rel!r}")
            continue
        for f in {page} | needs(site, page):
            to = out / f.relative_to(site.resolve())
            to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, to)
        copied += 1
        print(f"{rel}: {page.stat().st_size:,} bytes")
    return 0 if copied else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
