# Changelog

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
