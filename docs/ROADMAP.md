# Current roadmap and acceptance status

> **Installed-distribution candidate:** the public `\usepackage{bntex}` now selects automatic input and the prebuilt default profile. The project-local compiler/staging commands below are maintainer/developer workflows, not ordinary author setup. The legacy cached entry is `bntex-cached` or `bntex[cached]`. See [distribution/README.md](distribution/README.md) for the current installation boundary and remaining restricted-read/Overleaf acceptance.

The original bootstrap roadmap is preserved byte-for-byte as
`ROADMAP-ORIGINAL.md`. It documents the original plan, not current feature status.
Current engineering work uses main as the integration base and topic PRs for
changes. This is an alpha; publishing a release requires the maintainer's explicit
decision.

## Implemented baseline and current authoring work

Consolidation PR #16 preserved the corpus, expanded inventory, decoder,
independent Python model, native expl3 shaper and document integration ancestry.
Performance PR #17 adds indexed rule dispatch and integer coordinate scaling.
The complete pinned performance suite passed 551 tests without skips before
merge. These are distinct from earlier reconstructed local subsets.

The original native baseline supports one regular-upright profile without
per-document preparation. Current authoring extends that baseline with automatic
`bntex-auto` input and an audited regular/bold family; see AUTOMATIC-AUTHORING.md.
The cached `bntex.sty` interface still needs new-word preparation. Explicit native
text declarations remain available for legacy moving/PDF arguments. Optional
bounded reuse is process-local and face-aware, never a required word dictionary.

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

## Active authoring milestone: #15 and #25

The maintainer explicitly superseded the earlier deferral. `bntex-auto` routes
connected Unicode Bengali without per-passage wrappers. The authoring exporter
installs the two audited regular/bold faces; standard NFSS weight switches select
real bold. Synthetic slanted emphasis is an explicit option, not a true italic
face. Standard effects and ordinary LaTeX contexts have separate regression
coverage. See AUTOMATIC-AUTHORING.md for the exact implemented support matrix.
Historical statements that routing is deferred are preserved in dated reports,
not instructions overriding the current request. Performance and external user
acceptance remain open; do not require another micro-optimization before useful
authoring tests. No public release is authorized by this priority change.

## Subsequent scope, not current claims

Additional sans/true-italic/other font profiles, stronger line-break policy, supported
publisher classes, additional platforms/viewers and tagged-PDF accessibility each
need separate specifications and tests. Passing a fixed font or Poppler does not
establish any of these. Existing human-review records must retain real attribution.
