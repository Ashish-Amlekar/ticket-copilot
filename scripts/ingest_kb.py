"""Build the knowledge base (data/.../chunks.jsonl) from markdown / rst docs.

Examples
--------
Sample KB (bundled, fictional product, works offline):
    python -m scripts.ingest_kb --src data/sample_kb/docs --out data/sample_kb/chunks.jsonl

Real project docs (clone first, then point at the docs folder):
    git clone --depth 1 https://github.com/apache/airflow /tmp/airflow
    python -m scripts.ingest_kb --src /tmp/airflow/airflow-core/docs \
        --out data/airflow/chunks.jsonl --kind doc

Past tickets: export closed GitHub issues as .md files (one per issue, title as
"# heading", resolution in the body) and ingest them with --kind issue.

Chunking is by heading, so every chunk is a self-contained section with a
meaningful title; sections over MAX_CHARS are split on paragraph boundaries.
"""

import argparse
import json
import re
from pathlib import Path

MAX_CHARS = 1500
HEADING = re.compile(r"^(#{1,4})\s+(.*)$", re.MULTILINE)


def split_sections(text: str, default_title: str) -> list[tuple[str, str]]:
    matches = list(HEADING.finditer(text))
    if not matches:
        return [(default_title, text.strip())]
    sections = []
    if matches[0].start() > 0 and text[: matches[0].start()].strip():
        sections.append((default_title, text[: matches[0].start()].strip()))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end() : end].strip()
        if body:
            sections.append((m.group(2).strip(), body))
    return sections


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
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--kind", default="doc", choices=["doc", "issue", "release_note"])
    args = ap.parse_args()

    files = sorted(p for p in args.src.rglob("*") if p.suffix in {".md", ".rst", ".txt"})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(args.out, "w", encoding="utf-8") as out:
        for path in files:
            rel = path.relative_to(args.src).as_posix()
            stem = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
            text = path.read_text(encoding="utf-8", errors="ignore")
            for s_idx, (title, body) in enumerate(split_sections(text, path.stem)):
                for p_idx, piece in enumerate(split_long(body)):
                    chunk = {
                        "chunk_id": f"{stem}-{s_idx}" + (f"-{p_idx}" if p_idx else ""),
                        "source": rel,
                        "title": title,
                        "text": piece,
                        "kind": args.kind,
                    }
                    out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    count += 1
    print(f"Wrote {count} chunks from {len(files)} files to {args.out}")


if __name__ == "__main__":
    main()