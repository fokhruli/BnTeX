# Native dispatch optimization

The performance implementation supplied after issue #7 is now integrated as a
separate change on the consolidated main branch. The runtime and test files are
byte-identical to the tested source overlay; historical local-only instructions
are not used to overwrite live integration interfaces.

## Mechanism

The font exporter derives first-input-glyph candidate indexes for each supported
GSUB/GPOS lookup and each ordered ligature subtable. Empty-action contextual rules
and zero-valued class-zero positioning rules remain in the dispatch coverage.
A first-two-glyph index is used only for unfiltered ligature lookups with manual
join-control handling; otherwise the original matching semantics are retained.
The index is compiled from font rules, never document text or vocabulary.

Legacy tables without the dispatch marker use the original scan. Removing only
the additional index declarations reproduces the original table hash exactly:
`7fd73a9d0d21b99c4d2580f209ec0c1cc8bf15d72c8eb444522b38898577cd4a`.
The typed profile and font fingerprints have not changed.

Coordinate scaling uses e-TeX's combined dimension multiplication/division with
integer font-unit inputs. Negative offsets, half-way rounding, fractional sizes
and wide intermediate products are tested. Optional process-local memoization
and the native/cached authoring interfaces remain unchanged.

## Installation and testing

Re-export a fresh complete installation after updating the package; do not patch
individual files inside an old generated installation. Asset checks deliberately
reject mixed versions. After installation, new words still need only pdfLaTeX.

```
BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 \
  python -m pytest -q
python tools/native_performance.py \
  --installation optimized=build/native-installation \
  --out build/performance-check --pages 1 10 100 \
  --modes repeated distinct --memo off --passes 2 --timeout 90
```

The command accepts only trusted local installations, uses fresh directories,
disables shell execution, audits runtime inputs, verifies unchanged assets and
records actual page counts, extraction and font counts. Source generation uses
96 tokens per requested page by default: Bengali stems plus digits, not book
prose. Distinct/repeated and memo on/off are separate workloads. The original
`native_benchmark.py` uses a different 200-token workload; do not compare these
numbers as though the sources were identical.

## Evidence at PR creation

The 41 added tests passed locally with mandatory integration and pinned-reference
prerequisites (41 passed in 10.37 seconds). That is not the full repository suite.
The remote full-branch workflows must be read separately. Longer 100-page tests
are being executed with an explicitly larger measurement budget; completing with
that budget must not be presented as satisfying the previous 90-second target.
Final observed results belong in the PR discussion and consolidation report.

Tests check ordered coverage, zero-action blocking, exact indexed/unindexed stage
traces, unchanged legacy table data, dimension rounding, memo/new-word behavior,
heading metadata and benchmark timeout/integrity safeguards. Frozen glyph
references are unchanged. This is neither automatic Bengali input (#15) nor an
Overleaf browser acceptance, all-font support or a public release.
