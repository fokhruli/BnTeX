# Current roadmap and acceptance status

The original bootstrap roadmap is preserved byte-for-byte as
`ROADMAP-ORIGINAL.md`. It documents the original plan, not current feature status.
Current engineering work uses main as the integration base and topic PRs for
changes. This is a private alpha; no public release has been authorized.

## Implemented on main

Consolidation PR #16 preserved the corpus, expanded inventory, decoder,
independent Python model, native expl3 shaper and document integration ancestry.
Performance PR #17 adds indexed rule dispatch and integer coordinate scaling.
The complete pinned performance suite passed 551 tests without skips before
merge. These are distinct from earlier reconstructed local subsets.

One fixed regular-upright Bengali profile supports new text without document
preparation. The cached `bntex.sty` interface remains available and still needs
new-word preparation. Explicit native text declarations support moving/PDF
arguments. Optional bounded reuse is process-local, never a word dictionary
required by the algorithm.

## Issue #7 remains an acceptance milestone

Engineering checks include exact frozen glyph runs, unseen-word/no-helper
execution, mixed document contexts, source manifests and performance tooling.
Required remaining decisions/evidence are actual Overleaf browser import and
new-word editing, independent second-user reproduction, scoped native visual
review and a practical long-document performance budget. Extended-budget 100-page
measurements do not mean the previous 90-second interactive target passed.
Do not label local LatexMk, CI, or an agent's second directory a browser/person.

## Issue #8: prepare, do not publish

The manual, complete source manifest, resource equality checks, private review
archive builder and dry-run workflow establish mechanical release infrastructure.
The readiness JSON is deliberately blocked for missing real-use, naming,
font/profile distribution and publication decisions. CTAN packaging still needs
final naming/layout review and removal of private-development references before
any public submission. No package, tag or public release is created by preflight.

## Deferred issue #15

Wrapper-free automatic Bengali input is a recorded product requirement, not the
current coding task. Revisit it after the pending backlog with the maintainer.
Keep explicit `\bnNative` available and retain no-helper, original-Unicode and
Latin-compatibility regressions when an automatic dispatcher is eventually added.

## Subsequent scope, not current claims

Reviewed bold/sans/other font profiles, stronger line-break policy, supported
publisher classes, additional platforms/viewers and tagged-PDF accessibility each
need separate specifications and tests. Passing a fixed font or Poppler does not
establish any of these. Existing human-review records must retain real attribution.
