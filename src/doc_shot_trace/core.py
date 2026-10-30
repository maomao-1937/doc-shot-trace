"""Conservative, source-linked screenshot OCR review."""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlsplit

from PIL import Image, UnidentifiedImageError


IMAGE_RE = re.compile(r"!\[[^\]]*\]\((<[^>]+>|[^)]+)\)")
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000


@dataclass(frozen=True)
class LabelChange:
    old: str
    new: str


@dataclass(frozen=True)
class Finding:
    document: str
    line: int
    image: str
    old_label: str
    new_label: str
    status: str
    ocr_excerpt: str
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def read_label_changes(path: Path) -> list[LabelChange]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"old", "new"}.issubset(reader.fieldnames):
            raise ValueError("CSV needs old,new columns")
        changes: list[LabelChange] = []
        seen: set[str] = set()
        for line, row in enumerate(reader, start=2):
            old = (row.get("old") or "").strip()
            new = (row.get("new") or "").strip()
            if not old or not new:
                raise ValueError(f"CSV line {line}: both old and new are required")
            key = normalize(old)
            if key in seen:
                raise ValueError(f"CSV line {line}: duplicate old label")
            seen.add(key)
            changes.append(LabelChange(old, new))
        if not changes:
            raise ValueError("CSV has no label changes")
        return changes


def markdown_image_refs(document: Path) -> list[tuple[int, str]]:
    refs: list[tuple[int, str]] = []
    for line_number, line in enumerate(document.read_text(encoding="utf-8").splitlines(), start=1):
        for match in IMAGE_RE.finditer(line):
            destination = match.group(1).strip()
            if destination.startswith("<") and destination.endswith(">"):
                destination = destination[1:-1]
            else:
                destination = destination.split(maxsplit=1)[0]
            refs.append((line_number, destination))
    return refs


def resolve_image(root: Path, document: Path, destination: str) -> tuple[Path | None, str]:
    parsed = urlsplit(destination)
    if parsed.scheme or parsed.netloc or destination.startswith("//"):
        return None, "remote_skipped"
    if not parsed.path or parsed.path.startswith("/"):
        return None, "outside_root"
    image = (document.parent / unquote(parsed.path)).resolve()
    try:
        image.relative_to(root)
    except ValueError:
        return None, "outside_root"
    if image.suffix.lower() not in IMAGE_TYPES:
        return None, "unsupported_image"
    if not image.is_file():
        return None, "image_missing"
    if image.stat().st_size > MAX_IMAGE_BYTES:
        return None, "image_too_large"
    try:
        with Image.open(image) as opened:
            if opened.width * opened.height > MAX_IMAGE_PIXELS:
                return None, "image_too_large"
            opened.verify()
    except (OSError, UnidentifiedImageError, ValueError):
        return None, "unreadable_image"
    return image, "ready"


def rapidocr_text(path: Path) -> str:
    from rapidocr import RapidOCR

    # Avoid constructing the model separately for every image.
    if not hasattr(rapidocr_text, "_engine"):
        rapidocr_text._engine = RapidOCR()  # type: ignore[attr-defined]
    result = rapidocr_text._engine(str(path))  # type: ignore[attr-defined]
    return "\n".join(str(text) for text in (getattr(result, "txts", None) or []) if str(text).strip())


def scan(root: Path, changes: list[LabelChange], *, ocr: Callable[[Path], str] = rapidocr_text,
         max_images: int = 100) -> list[Finding]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError("Documentation root must be a directory")
    if max_images < 1:
        raise ValueError("max_images must be positive")
    documents = []
    for document in sorted([*root.rglob("*.md"), *root.rglob("*.mdx")]):
        try:
            document.resolve().relative_to(root)
        except ValueError:
            continue  # Do not read symlinked Markdown outside the supplied root.
        documents.append(document)
    refs = [(document, line, dest) for document in documents
            for line, dest in markdown_image_refs(document)]
    local_paths = set()
    for document, _, dest in refs:
        image, status = resolve_image(root, document, dest)
        if status == "ready":
            local_paths.add(image)
    if len(local_paths) > max_images:
        raise ValueError(f"{len(local_paths)} images exceed --max-images {max_images}")

    cache: dict[Path, tuple[str, str]] = {}
    findings: list[Finding] = []
    for document, line, dest in refs:
        image, status = resolve_image(root, document, dest)
        visible = ""
        detail = ""
        if status == "ready" and image is not None:
            if image not in cache:
                try:
                    cache[image] = (ocr(image), "ready")
                except Exception as error:  # OCR backends can raise several exception types.
                    cache[image] = ("", "ocr_error")
                    detail = type(error).__name__
            visible, status = cache[image]
        image_name = str(image.relative_to(root)) if image else dest
        for change in changes:
            outcome = status
            if status == "ready":
                outcome = "review_candidate" if normalize(change.old) in normalize(visible) else "not_visible"
            findings.append(Finding(str(document.relative_to(root)), line, image_name,
                                    change.old, change.new, outcome, visible[:500], detail))
    return findings
