# DocShotTrace

When a UI label changes, DocShotTrace helps a documentation writer find **existing Markdown screenshots that still visibly contain the old label**. It scans locally referenced images with a real on-device OCR model and produces a review queue with the Markdown file and line number. It is a *candidate finder*, not a screenshot-staleness classifier.

## Who this is for

Technical writers maintaining screenshot-heavy Markdown or MDX docs for web or native software. The repeated job is to find which screenshots need inspection after a known UI-label rename. The alternative is opening each docs page and image manually, or investing in a screenshot recapture pipeline. The product hypothesis is that an explicit old-label lookup is a useful middle step for teams without UI automation.

## Install and try

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). The first installation/model initialization may download dependencies and RapidOCR models. OCR itself runs locally; this tool does not send screenshots to a paid API.

```sh
uv sync --python 3.11 --extra test
uv run python examples/make_demo.py --out-dir demo.local
uv run doc-shot-trace demo.local demo.local/changes.csv --out review.local.md --json-out review.local.json
uv run pytest -q
```

The demo is a **fictional** screen with a visible “Settings” label and a `Settings → Preferences` CSV change. The report should contain one `review_candidate` pointing to `guide.md:5`. Open the report and the source screenshot to decide whether a real image should be recaptured. For your own docs, write a UTF-8 CSV with `old,new` headers and run `uv run doc-shot-trace /path/to/docs changes.csv`. The tool scans `.md` and `.mdx` recursively, follows local Markdown image references, and reads PNG/JPEG/WebP/BMP files. Use `--max-images` to bound the run; the default is 100 unique images.

Output statuses are `review_candidate` (OCR sees the old label), `not_visible` (OCR did not see it), and explicit unreadable/skipped states such as `image_missing`, `outside_root`, and `ocr_error`. An OCR match is **not** proof an image is outdated: a comparison guide could legitimately show the old interface. No match does **not** prove the image is current: OCR can miss small or stylized text. The tool does not capture the current UI, compare layouts, inspect videos/GIFs, parse every possible Markdown image syntax, edit docs, or certify accessibility.

The JSON report includes OCR text snippets that may contain private UI information. Keep private documentation and reports local; never commit them to a public repo. Inputs are read-only. Individual images are bounded to 20 MB and 12 million pixels; symlinked image paths outside the docs root are not opened.

## Product judgment and evidence

[Technical writers in July 2026](https://www.reddit.com/r/technicalwriting/comments/1urqhka/keeping_screenshotheavy_docs_current_especially/) describe screenshots becoming stale after native-app updates; [different writers in October 2026](https://www.reddit.com/r/technicalwriting/comments/1xcn4l0/lets_talk_screenshots/) discuss label changes and the cost of locating affected images; a [repository maintainer in July 2026](https://github.com/vdhamer/Photo-Club-Hub/issues/774) describes a UI migration affecting many doc images. This is repeated problem evidence across Reddit and GitHub, **not** evidence anyone wants this exact CLI or that it will attract users.

Competitors and counterevidence are substantial: [Sentry's screenshot pipeline](https://github.com/getsentry/sentry-docs/issues/18242) already identifies stale screenshots within its workflow, [DOSUD](https://people.cs.vt.edu/~nm8247/publications/DOSUD2025.pdf) studies automatic detection, and [Tango](https://www.tango.ai/product/it-documentation) automates capture and guide creation. The unvalidated difference here is a local, transparent impact query against *existing* Markdown images given a known old/new label, including screenshots of apps you cannot automate. See [RESEARCH.md](RESEARCH.md) for the source audit and limits.

MIT licensed original code. RapidOCR, ONNX Runtime and their models have separate upstream licenses; model weights are not included in this repository.
