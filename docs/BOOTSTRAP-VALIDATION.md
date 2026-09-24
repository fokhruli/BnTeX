# Executed bootstrap validation — 0.1.0a2

These are local results, not a claim of completed GitHub Actions or Overleaf runs.
The cached renderer is unchanged; the Python helper adds diagnostics and auditing.

## Regression suite

```text
BNTEX_REQUIRE_INTEGRATION=1 PYTHONPATH=src python -m pytest -q
74 passed in 2.32s
```

The original 41-test baseline passed before modifications. The new revision adds
11 diagnostic cases and 22 structural-audit cases. No tests were skipped in this
run. Tests include real pdfLaTeX compilation with shell execution disabled,
Poppler extraction, deterministic builds, font integrity, missing words/styles,
source locations, malformed UTF-8, synthetic layout graphs and three local fonts.

## Geometry and demonstration

`tools/compare_reference.py` passed for 26 words at 12 pt. Maximum measured advance
difference was 0.00009000 pt, below the configured 0.02 pt tolerance. Both paths
use HarfBuzz; this is not an independent Bengali shaping-correctness proof.

The original two-page `examples/main.tex` was prepared with regular/bold fonts
and compiled twice with `pdflatex -no-shell-escape -halt-on-error`.
It contains 100 distinct words per style and six Bengali font banks. Both pages
were rendered with Poppler and visually inspected. The final log had no
Overfull/Underfull, missing-character or warning matches. `pdffonts` reports
embedded/subsetted TrueType Bengali faces. Compiled PDFs/fonts are not committed;
regenerate them from the example and locally installed fonts.

## Font closure audit

Regular font: NotoSerifBengali-Regular.ttf.
SHA-256: `32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef`.

GSUB: 59 total/reachable lookups, 34 direct roots, 25 nested-only dependencies.
GPOS: six total/reachable lookups, all direct roots. No lookup-cycle back edges
were found for this binary. Counts are version-specific. Structural auditing does
not implement GSUB/GPOS execution or produce an executable native font profile.

## Environment and package checks

Python 3.13.5; FontTools 4.63.0; HarfBuzz 10.2.0.
pdfTeX 3.141592653-2.6-1.40.26, TeX Live 2025/dev/Debian.
LuaHBTeX 1.18.0, TeX Live 2025/dev/Debian.

A 0.1.0a2 wheel was built without dependency downloads/build isolation, installed
to a separate target directory, and used from outside the source tree to run the
font audit. Both bntex.sty copies match. The filename audit passed. No font
binaries are included. Filename checks are not a comprehensive secret scanner.

## Not completed

TeX-native shaping, a runnable font-profile compiler, human-reviewed full corpus,
Overleaf browser validation, native Windows/macOS, book-length benchmarks,
generic publisher classes, automatic Unicode bookmarks and tagged-PDF/PDF-UA.
Remote CI status must be read from the actual PR checks. No CTAN/PyPI release,
merge into main, or repository visibility change is part of this bootstrap.
