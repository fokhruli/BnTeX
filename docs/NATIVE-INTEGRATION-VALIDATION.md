# Issue #7: executed native-document validation

Date: 24 September 2026. Parent commit: `efb9ed4189053ea919a18872bee261540aadebf8`.
This report separates actual local results from remote CI and manual review.

## Scope and local tests

The local development checkout was reconstructed from the original 41-test source
bundle and the 68-test native overlay, not the entire live repository. The exact
live profile JSON and frozen supplemental oracle were restored and hash-verified.
The final run, including 65 new integration tests, was:

```text
BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 \
BNTEX_NATIVE_PROFILE_JSON=build/live-profile.json PYTHONPATH=src python -m pytest -q
174 passed in 234.65s (0:03:54)
```

No skips. An earlier 173-test run passed before the final latexmk configuration
test was added; it is superseded by the run above. The live repository CI must
be read independently. No full-branch remote result is implied by 174 or by adding
counts to previous runs. On CI the existing fixtures compile the live profile,
without the local reconstructed-profile override.

Environment: Linux, Python 3.13.5, FontTools 4.63.0, HarfBuzz 10.2.0 (test side),
pypdf 5.9.0, pdfTeX 1.40.26 / TeX Live 2025/dev/Debian, LaTeX2e 2024-11-01
patch 2, expl3 2025-01-18, local static Noto Serif Bengali Regular.

## Checked behavior

- Actual article/report/book heading, TOC, title/author metadata and outline tests.
  Bengali heading weight is explicitly regular, not simulated bold.
- Original Unicode metadata/outline fidelity for decomposed/precomposed nukta,
  split-vowel encodings, ZWJ and ZWNJ; both hyperref package-load orders.
- Footnotes, table cells, captions/list of figures, amsmath text/subscripts,
  one TikZ node, one regular-font Beamer frame, and a BibTeX-generated protected
  title. These are individual constructions, not universal class/style support.
- Source declarations reject malformed keys, duplicate/unknown entries, empty
  text and user macros. The optional helper does not activate Bengali globally.
- Optional memoization preserves seven glyph fields, original text, point-size
  changes, color operators, extraction, eviction, disable/clear and trace bypass.
  First/new words still execute the native shaper; no persistent word file exists.
- Explicit manifest staging retains subdirectories and equal basenames in distinct
  directories; blocks traversal, symlinks, collisions, missing files, overwrites,
  invalid schemas and changed installation assets. Source edits are allowed and
  reported. Deterministic local ZIP creation excludes undeclared adjacent files.
- Trusted pdfLaTeX child runs use shell execution disabled, nonexistent executable
  PATH and recorder audits. A deliberate infinite loop is terminated and reaped
  with timeout status, not counted as a successful PDF.
- Native source/resource equality, unchanged scalar/GSUB/GPOS interpreter files,
  and unchanged frozen 261-form oracle. The inherited native tests still execute.

The local `bibtex` link was broken; the test explicitly falls back to the installed
`bibtex.original` executable. This is a bibliography tool invoked by the host test,
not an external Bengali shaping helper during TeX compilation.

## Multi-file demonstration

A fresh installation and separately staged project compiled through three passes:

| Pass | Status | Wall seconds | Actual pages | Warnings |
| --- | --- | ---: | ---: | --- |
| 1 | success | 14.875475 | 3 | expected unresolved cross-references/auxiliary rerun |
| 2 | success | 15.217330 | 3 | none |
| 3 | success | 14.908402 | 3 | none |

All installation hashes remained unchanged. The test suite separately appends
`পাঠপরিকল্পনাসমূহ` to the included results file after staging, recompiles without
preparation, verifies extraction and detects only the intended source modification.
The final 3-page PDF was rendered using Poppler and each page visually inspected.
The table values/bibliography are fictional formatting fixtures.

Actual PDF title: `বাংলায় গবেষণা-নথির উদাহরণ`.
Actual outline titles: `ভূমিকা ও পদ্ধতি`; `ফলাফল ও আলোচনা`.
PDF SHA-256: `acaf6fb048b17888def13e6499a4d6ed8ef83c4b8c92ad07f16942ddaeabd8ea`.
Poppler extraction and pypdf outline/metadata checks are not all-viewer
accessibility certification or new human approval of every glyph.

A separate fresh staged project also completed through local `latexmk -pdf`.
Its log recorded `pdflatex ... -no-shell-escape -halt-on-error` and finished
with all targets up to date. The document's shell-status assertion remained on.
This validates the supplied local `latexmkrc`, not Overleaf's browser runtime.

## Measured performance, including failures

Every requested page has 200 tokens. Repeated cases cycle 20 words; distinct cases
are synthetic four-syllable sequences, not dictionary-approved vocabulary.
Successful cases have two fresh-process passes. No cache persists between passes.

| Pages / workload | No memo, seconds | Optional memo, seconds |
| --- | --- | --- |
| 1 / repeated | 20.572 / 21.024 | 2.922 / 3.076 |
| 1 / distinct | 30.545 / 30.900 | 34.463 / 33.860 |
| 10 / repeated | timeout at 45 | 10.109 / 10.320 |
| 10 / distinct | timeout at 45 | timeout at 45 |
| 100 / repeated | timeout at 45 | timeout at 45; **77.849 / 79.756** with explicit 180-second budget |
| 100 / distinct | timeout at 45 | timeout at 45 |

The completed 100-page repeated case contains 20,000 tokens, 20 distinct words,
three Bengali font banks, four total embedded fonts, and a 207,685-byte PDF.
Peak RSS was 55,936 / 55,808 KiB; memo statistics were 19,980 hits, 20 misses,
20 entries and zero evictions. Actual page count and all distinct token extraction
were checked. The distinct-text bottleneck remains; increasing a timeout is not
an optimization or evidence of completion for the timed-out cases.

Compact measurements and field definitions are in `NATIVE-PERFORMANCE.json`.
The detailed local report is identified there by SHA-256. The measured installation
preceded only the optional module's load-time hook-presence guard; its measured
memo fingerprint is retained. Final-code correctness uses the fresh final suite.
These were shared-host timings with some other validation work overlapping, not
controlled hardware benchmarks or confidence intervals. Null values for timed-out
runs mean unavailable completed metrics, never zero memory or a completed page count.

## Installation identities and unresolved gates

Font SHA-256: `32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef`.
Typed profile SHA-256: `f6294540099a3b6f622f2cdd9e863050390f75fd0576495d5a2316903f8cfb42`.
Unchanged emitted tables: `7fd73a9d0d21b99c4d2580f209ec0c1cc8bf15d72c8eb444522b38898577cd4a`.
Final installation-manifest SHA-256: `9cd799040ca2f568654db3b89deaf4630caf5181c57f996b54364579bb41d30a`.

No font binaries or generated installation are committed or supplied as a download.
The user-side project packer can copy the user's separately installed font into
their own Overleaf project; it does not grant redistribution rights.

**Not performed:** actual Overleaf browser import/compile, independent second-user
reproduction, Windows/macOS, arbitrary publisher classes, new font styles,
all-viewer behavior, tagged PDF/PDF-UA, or public release. Automatic routing remains
deferred under #15. Issue #7 remains open for these acceptance gates and further
performance work. No merge, issue closure or publication is authorized by this PR.
