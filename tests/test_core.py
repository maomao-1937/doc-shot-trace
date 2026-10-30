from pathlib import Path

import pytest
from PIL import Image

from doc_shot_trace.core import (LabelChange, markdown_image_refs, normalize,
                                 read_label_changes, resolve_image, scan)


def make_image(path: Path) -> None:
    Image.new("RGB", (32, 32), "white").save(path)


def test_changes_csv_and_normalization(tmp_path: Path) -> None:
    path = tmp_path / "changes.csv"
    path.write_text("old,new\nＳｅｔｔｉｎｇｓ,Preferences\n", encoding="utf-8")
    assert read_label_changes(path) == [LabelChange("Ｓｅｔｔｉｎｇｓ", "Preferences")]
    assert normalize("  Ｓｅｔｔｉｎｇｓ  ") == "settings"


@pytest.mark.parametrize("value", ["old\nA\n", "old,new\n,New\n", "old,new\nA,B\na,C\n"])
def test_invalid_changes_csv(tmp_path: Path, value: str) -> None:
    path = tmp_path / "changes.csv"
    path.write_text(value, encoding="utf-8")
    with pytest.raises(ValueError):
        read_label_changes(path)


def test_markdown_links_and_line_numbers(tmp_path: Path) -> None:
    page = tmp_path / "guide.md"
    page.write_text("Title\n![One](one.png) ![Two](<two image.png>)\n", encoding="utf-8")
    assert markdown_image_refs(page) == [(2, "one.png"), (2, "two image.png")]


def test_scan_candidates_and_cached_ocr(tmp_path: Path) -> None:
    make_image(tmp_path / "screen.png")
    (tmp_path / "a.md").write_text("![Screen](screen.png)\n![Again](screen.png)\n", encoding="utf-8")
    calls = []

    def fake_ocr(path: Path) -> str:
        calls.append(path)
        return "Settings\nAlerts"

    rows = scan(tmp_path, [LabelChange("Settings", "Preferences"), LabelChange("Billing", "Payments")],
                ocr=fake_ocr)
    assert len(calls) == 1
    assert [row.status for row in rows] == ["review_candidate", "not_visible"] * 2
    assert rows[0].line == 1


def test_scan_missing_and_outside_root(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("![Missing](missing.png)\n![Outside](../secret.png)\n", encoding="utf-8")
    rows = scan(tmp_path, [LabelChange("Old", "New")], ocr=lambda _: "")
    assert [row.status for row in rows] == ["image_missing", "outside_root"]


def test_remote_and_large_image(tmp_path: Path) -> None:
    page = tmp_path / "a.md"
    assert resolve_image(tmp_path, page, "https://example.org/a.png")[1] == "remote_skipped"
    make_image(tmp_path / "a.png")
    assert resolve_image(tmp_path, page, "a.png")[1] == "ready"
    assert resolve_image(tmp_path, page, "a.txt")[1] == "unsupported_image"


def test_image_budget_is_hard_limit(tmp_path: Path) -> None:
    make_image(tmp_path / "a.png")
    make_image(tmp_path / "b.png")
    (tmp_path / "a.md").write_text("![A](a.png) ![B](b.png)\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exceed"):
        scan(tmp_path, [LabelChange("Old", "New")], ocr=lambda _: "", max_images=1)


def test_ocr_exception_reported(tmp_path: Path) -> None:
    make_image(tmp_path / "a.png")
    (tmp_path / "a.md").write_text("![A](a.png)\n", encoding="utf-8")

    def fail(_: Path) -> str:
        raise RuntimeError("private details")

    row = scan(tmp_path, [LabelChange("Old", "New")], ocr=fail)[0]
    assert row.status == "ocr_error"
    assert "private details" not in repr(row)


def test_symlinked_document_outside_root_is_ignored(tmp_path: Path) -> None:
    root = tmp_path / "docs"
    root.mkdir()
    (tmp_path / "outside.md").write_text("![Secret](secret.png)\n", encoding="utf-8")
    (root / "linked.md").symlink_to(tmp_path / "outside.md")
    assert scan(root, [LabelChange("Old", "New")], ocr=lambda _: "") == []
