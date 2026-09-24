# Validation strategy

## Required local suite

```bash
BNTEX_REQUIRE_INTEGRATION=1 PYTHONPATH=src python -m pytest -q
```

The gate makes missing fonts/HarfBuzz/TeX prerequisites failures rather than skips.
Override local font paths with BNTEX_REGULAR_FONT, BNTEX_BOLD_FONT and
BNTEX_SANS_FONT. A passing unit-only run is not rendering validation.

The suite covers literal scanning/rejection and source diagnostics, original
Unicode, byte clusters, three font faces, native pdfLaTeX, Poppler extraction,
determinism, asset integrity, output safety and structural font lookup auditing.
Synthetic graphs test nested references/extensions/filtering/cycles separately
from installed-font integration. These checks are not exhaustive typography review.

```bash
PYTHONPATH=src python tools/compare_reference.py --font /path/to/static-font.ttf
PYTHONPATH=src python -m bntex profile --font /path/to/static-font.ttf
python tools/audit_release.py
```

The width comparison uses pdfLaTeX and LuaLaTeX-HarfBuzz with the same font at
12 pt. Both paths use HarfBuzz: this validates rendering geometry/configuration,
not an independent shaping algorithm. See BOOTSTRAP-VALIDATION.md for actual local
results. Remote CI results must be read from the PR checks, not inferred from the
workflow definition. Record failing/skipped tests and untested platforms.

## Next acceptance tests

Curate native-speaker-reviewed real words, uncommon conjuncts, malformed inputs,
join controls, normalized equivalents, marks, digits and punctuation. Pin the exact
font/tool/configuration versions and compare glyph IDs plus integer font-unit
advances/offsets, preserving original logical text.

Test extraction/search/selection across viewers. Treat bookmarks, metadata,
reading order, tagging and PDF/UA separately. Test different widths and long words
before adding legal line breaks; no arbitrary break inside connected clusters.

Build per-context tests for headings/TOC/captions/footnotes/tables/bibliographies,
math text, TikZ/Beamer and publisher classes. Profile 1/10/100 pages, repeated versus
unique vocabulary, font counts, memory, PDF size and cold/warm build time.

Run an actual no-shell Overleaf import and cross-platform/distribution tests.
Inject missing/changed assets, malformed fonts, stale profiles, invalid source
and long combining sequences. A filename audit is not a full secret scanner.

Use exact source/hash invariants, exact pinned glyph sequences, integer-unit
position checks, scaled-point rounding tolerance, and visual/native-speaker review.
A screenshot similarity score alone cannot validate logical Unicode or typography.
