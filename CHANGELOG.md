# Authoring update (unreleased)

- Add opt-in `bntex-auto`: literal Bengali in ordinary mixed text, commands,
  headings and PDF strings without per-passage wrappers.
- Add the exact Noto Serif Bengali Bold profile and NFSS weight selection.
  Shared substitutions are structurally checked; bold metrics/positioning are
  independent. Reuse keys include the full face identity.
- Add explicit synthetic-italic consent and standard decoration regressions.
  No genuine italic face, generic font support or Overleaf certification claimed.
- Record prior regular-specimen acceptance narrowly; new styles need review.
- The maintainer has activated #15/#25; the earlier deferral is superseded.

# Changelog

## Unreleased — consolidated native development checkpoint

- Consolidate existing corpus, inventory, decoder, independent shaping model,
  native expl3 engine and document integration into main, preserving history.
- Add conservative indexed font-rule dispatch and integer dimension scaling;
  preserve original references, profile identity and fallback scan semantics.
- Retain optional bounded process-local memoization and declared-text PDF strings.
- Add a current README/contributor contract, preserve the original roadmap, and
  distinguish cached/native editing and deferred automatic routing.
- Add a PDF manual source, complete source-distribution manifest, mechanical
  preflight tests and a private release dry run. Pending acceptance blocks ready
  status. No font files, public release, CTAN/PyPI upload or version promotion.

## 0.1.0a2 — private bootstrap review

- Import the native-glyph cached pdfLaTeX backend and development documentation.
- Add source filename, line, Unicode-scalar column, excerpt and caret diagnostics.
- Reject invalid source UTF-8 and unprepared explicit styles with source locations.
- Add deterministic GSUB/GPOS dependency-closure audit, including extensions,
  filtering/GDEF requirements, original wire formats and cycle reporting.
- Add synthetic and real-font regression tests; native shaping remains unimplemented.

## 0.1.0a1 — initial local prototype

HarfBuzz preparation, static TrueType glyph banks, pdfLaTeX rendering, Unicode
ActualText, integrity safeguards, documentation and local integration tests.
