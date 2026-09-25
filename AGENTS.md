# BnTeX contributor and coding-agent contract

Current main contains both a native fixed-profile shaper and a legacy cached
backend. Read README.md, docs/NATIVE-TEX.md, docs/NATIVE-INTEGRATION.md,
docs/NATIVE-DISPATCH-PERFORMANCE.md and docs/RELEASE-READINESS.md first.
Historical architecture/roadmap snapshots are not a current feature inventory.

## Invariants

- `bntex-native.sty` / `\bnNative` shapes new words in unmodified pdfTeX.
  Its exporter consumes a pinned font/profile only, never document vocabulary.
- `bntex.sty` / `\bn` retains the cached HarfBuzz preparation contract.
- Preserve original Unicode/byte mappings and logical-order ActualText/PDF strings.
  Do not normalize source keys, remove join controls or infer breakpoints from
  glyph clusters. Keep glyph output native, not images, paths or PDF fragments.
- Keep authoritative `tex/latex/bntex/*.sty` and `*.def` identical to the matching
  `src/bntex/data/` resources. Never rebaseline frozen glyph fixtures to fix tests.
- One exact regular-upright profile is supported. Automatic wrapper-free routing
  is deferred under #15 until the pending backlog is completed; do not activate it.
- Optimize measured work without weakening ordering, filtering, contextual
  blocking, bounds, failure policies or the unseen-word/no-helper gate.

## Validation and Git workflow

Use topic branches from current main and reviewable PRs. Preserve ancestry when
consolidating stacked work; never force-reset main or silently overwrite user
changes. Merge only when authorized and after checking current head and CI.

Run `BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 python -m pytest -q`
in the pinned environment. Record actual full-suite results, skipped tests,
font/profile identity and the exact source revision. Locally reconstructed
subsets are not full-repository evidence. Benchmark repeated/distinct vocabulary
separately; record timeouts, source bytes, page counts, extraction and resources.

## Distribution and acceptance

Keep all font files, generated installations, credentials and build clutter out
of Git and shared source artifacts. Preserve LICENSE and THIRD-PARTY-NOTICES.md.
Do not change visibility, publish releases or upload to CTAN/PyPI without separate
explicit authorization. Do not enable shell escape or network during compilation.

A mechanical packaging pass is not legal review, typography approval, Overleaf
browser validation or independent second-user reproduction. Leave unperformed
gates pending. The release preflight must fail closed with `--require-ready`.
No automation, fabricated reviewer identity or future background work is implied
by a checklist. Release preparation is allowed; public publication is not.
