"""Build the knowledge base (chunks.jsonl) from markdown / MDX / rst docs.

Examples
--------
Sample KB (bundled, fictional product, works offline):
    python -m scripts.ingest_kb --src data/sample_kb/docs --out data/sample_kb/chunks.jsonl

MLflow docs (clone first, then point at one or more docs folders):
    python -m scripts.ingest_kb --src ../mlflow/docs/docs/classic-ml ../mlflow/docs/docs/self-hosting \
        --root ../mlflow/docs/docs --out data/mlflow/chunks.jsonl

Chunking is by heading, so every chunk is a self-contained section with a
meaningful title. Headings inside fenced code blocks are ignored (a "# comment"
in a bash or python snippet is not a heading). Sections longer than MAX_CHARS
are split on paragraph boundaries; sections shorter than --min-chars, and chunks that are pure page decoration
(JSX components such as <TileCard>), are dropped.

chunk_id is derived from the file path relative to --root, so ids stay unique
across folders (many docs are called index.mdx) and stable between runs.
"""

import argparse
import json
import re
from pathlib import Path

MAX_CHARS = 1500
HEADING = re.compile(r"^(#{1,4})\s+(.*\S)\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
JSX_LINE = re.compile(r"^\s*</?[A-Z][A-Za-z0-9.]*(\s[^>]*)?/?>\s*$")  # <Tabs>, </TabItem>, <Foo bar="x" />
JSX_START = re.compile(r"\s*<[A-Z]|\s*<div")  # chunks that are page decoration (cards, banners)
SUFFIXES = {".md", ".mdx", ".rst", ".txt"}


def clean_mdx(text: str) -> tuple[str, str | None]:
    """Strip front matter, import/export lines and bare JSX tag lines.

    Returns (clean_text, title_from_front_matter_or_None). Content inside code
    fences is left untouched.
    """
    title = None
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            front = text[3:end]
            m = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$", front, re.MULTILINE)
            title = m.group(1) if m else None
            text = text[end + 4 :]
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence and (line.startswith(("import ", "export ")) or JSX_LINE.match(line)):
            continue
        out.append(line)
    return "\n".join(out), title


def split_sections(text: str, default_title: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = [(default_title, [])]
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
        m = None if in_fence else HEADING.match(line)
        if m:
            sections.append((m.group(2).strip(), []))
        else:
            sections[-1][1].append(line)
    return [(title, "\n".join(lines).strip()) for title, lines in sections if "\n".join(lines).strip()]


def split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    parts, current = [], ""
    for para in text.split("\n\n"):
        if current and len(current) + len(para) > MAX_CHARS:
            parts.append(current.strip())
            current = ""
        current += para + "\n\n"
    if current.strip():
        parts.append(current.strip())
    return parts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path, nargs="+", help="one or more folders")
    ap.add_argument("--root", type=Path, default=None,
                    help="paths in chunk ids/sources are relative to this (default: the single --src)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--kind", default="doc", choices=["doc", "issue", "release_note"])
    ap.add_argument("--min-chars", type=int, default=60)
    args = ap.parse_args()

    root = (args.root or (args.src[0] if len(args.src) == 1 else None))
    if root is None:
        ap.error("--root is required when --src has more than one folder")
    root = root.resolve()

    files = sorted(
        p for src in args.src for p in src.resolve().rglob("*") if p.is_file() and p.suffix in SUFFIXES
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    count = dropped = 0
    seen: set[str] = set()
    with open(args.out, "w", encoding="utf-8") as out:
        for path in files:
            rel = path.relative_to(root)
            stem = re.sub(r"[^a-z0-9]+", "-", rel.with_suffix("").as_posix().lower()).strip("-")
            text = path.read_text(encoding="utf-8", errors="ignore")
            text, fm_title = clean_mdx(text) if path.suffix == ".mdx" else (text, None)
            for s_idx, (title, body) in enumerate(split_sections(text, fm_title or path.stem)):
                for p_idx, piece in enumerate(split_long(body)):
                    if len(piece) < args.min_chars or JSX_START.match(piece):
                        dropped += 1
                        continue
                    chunk_id = f"{stem}-{s_idx}" + (f"-{p_idx}" if p_idx else "")
                    assert chunk_id not in seen, f"duplicate chunk_id {chunk_id}"
                    seen.add(chunk_id)
                    out.write(json.dumps({
                        "chunk_id": chunk_id,
                        "source": rel.as_posix(),
                        "title": title,
                        "text": piece,
                        "kind": args.kind,
                    }, ensure_ascii=False) + "\n")
                    count += 1
    print(f"Wrote {count} chunks from {len(files)} files to {args.out} ({dropped} tiny or decorative chunks dropped)")


if __name__ == "__main__":
    main()