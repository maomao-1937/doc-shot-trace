"""Command-line interface for DocShotTrace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import read_label_changes, scan


def render_markdown(findings: list[dict[str, object]]) -> str:
    candidates = [finding for finding in findings if finding["status"] == "review_candidate"]
    problems = [finding for finding in findings if finding["status"] not in {"review_candidate", "not_visible"}]
    lines = ["# DocShotTrace review queue", "", f"Potentially affected references: {len(candidates)}", "",
             "A match is OCR evidence of an old label, **not** proof that a screenshot is outdated.", ""]
    for title, group in (("Review candidates", candidates), ("Unreadable or skipped", problems)):
        lines.extend([f"## {title}", ""])
        if not group:
            lines.append("None.")
        for row in group:
            location = f"{row['document']}:{row['line']}"
            lines.append(f"- `{location}` → `{row['image']}` | {row['status']} | "
                         f"`{row['old_label']}` → `{row['new_label']}`")
        lines.append("")
    lines.extend(["## Limits", "", "Review the current UI and source image manually. OCR misses, historic screenshots, "
                  "and custom Markdown syntax can change the result.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Find Markdown screenshots that visibly contain renamed UI labels")
    parser.add_argument("docs_root", type=Path)
    parser.add_argument("changes_csv", type=Path, help="CSV with old,new columns")
    parser.add_argument("--out", type=Path, default=Path("review.local.md"))
    parser.add_argument("--json-out", type=Path, default=Path("review.local.json"))
    parser.add_argument("--max-images", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        changes = read_label_changes(args.changes_csv)
        findings = [finding.to_dict() for finding in scan(args.docs_root, changes, max_images=args.max_images)]
        args.out.write_text(render_markdown(findings), encoding="utf-8")
        args.json_out.write_text(json.dumps(findings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{sum(row['status'] == 'review_candidate' for row in findings)} review candidates; "
              f"{sum(row['status'] not in {'review_candidate', 'not_visible'} for row in findings)} unreadable/skipped")
        print(f"Reports: {args.out}, {args.json_out}")
        return 0
    except (OSError, ValueError) as error:
        print(f"DocShotTrace: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
