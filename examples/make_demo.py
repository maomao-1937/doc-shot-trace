"""Generate a fictional screenshot and Markdown page for a repeatable demo."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=Path("demo.local"))
    args = parser.parse_args()
    root = args.out_dir
    root.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (900, 400), "#f6f4ef")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((80, 80, 820, 320), radius=12, fill="white", outline="#b9b6ad", width=2)
    draw.text((130, 120), "Settings", fill="#111111", font=ImageFont.load_default(size=56))
    draw.text((130, 205), "Open Settings to change alerts", fill="#222222",
              font=ImageFont.load_default(size=34))
    image.save(root / "settings.png")
    (root / "guide.md").write_text("# Alert preferences\n\nOpen the settings screen.\n\n"
                                    "![Fictional settings screen](settings.png)\n", encoding="utf-8")
    (root / "changes.csv").write_text("old,new\nSettings,Preferences\n", encoding="utf-8")
    print(root.resolve())


if __name__ == "__main__":
    main()
