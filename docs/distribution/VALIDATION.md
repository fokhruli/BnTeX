# Installable-distribution continuation: executed validation

This record continues PR #27 from exact upstream head
`293cd5c3e737aa999ae77707bc6d54d7e1d5f281`, tree
`9529ea1955dc5036836d4d21bc2ed8ecb65ebbba`. The recovered full source and file
modes reproduced that Git tree before changes. PR #26 is already in main;
this continuation does not claim another authoring implementation or merge.

## Implemented in this continuation

The parent verifier accepted a tree with its default profile deleted when the
corresponding manifest entry was also deleted. A reproduced negative test exposed
that problem. Completeness now comes from a closed required-file schema rather
than trusting the inventory alone. It covers runtime/profile/font resources,
complete notices, manual and reproducible sources. Unknown members, broken
symlinks, inconsistent runtime/source modules and differing default loaders fail.
Rehashing an incomplete OFL file does not make it valid. These checks are not
signatures and do not authenticate coordinated malicious replacements.

The shipped TDS source now contains REPRODUCING.md and a maintainer-only rebuild
command. Tested from that source directory, without the checkout on PYTHONPATH,
it re-compiles the manual, runs the actual font-profile compiler, and produces
identical manifests and archives. The documented -B flag avoids adding Python
bytecode to the immutable source tree. New tests exercise the actual two-pass
maintainer builder rather than treating a one-pass manual as its output.

No production TeX runtime, security setting, font profile or frozen glyph
expectation changed in this continuation. The installed-distribution workflow
now includes the completeness tests. The manual is two pages, rendered and
inspected together with the native example.

## Executed local tests

Environment: Python 3.13.5, FontTools 4.63.0, HarfBuzz 10.2.0, pdfTeX
1.40.26 / Kpathsea 6.4.0-dev (TeX Live 2025/dev/Debian), exact supported fonts.
Both BNTEX_REQUIRE_INTEGRATION and BNTEX_REQUIRE_ORACLE were mandatory for full
runs. The actual font compiler ran, with no profile override.

| Run | Result |
| --- | --- |
| Unchanged, separately frozen full PR #27 head | 855 passed in 227.41 s; no skips |
| New completeness/rebuild tests | 30 passed in 6.49 s |
| Installed-distribution plus completeness selection | 68 passed in 18.16 s |
| Final complete candidate repository | 885 passed in 232.32 s; no skips |

These are local results, not remote CI totals or document-throughput numbers.
The earlier head's remote workflows reported action_required; a successful
workflow file or local run does not replace execution on the final remote head.
Record final remote results separately from their actual completed logs.

## Installed author-only proof

A complete 72-file TDS candidate (including its manifest) was placed in the
standard HOME/texmf location. An unrelated directory initially contained only
main.tex. The user document was preserved except for replacing its two-line
package/profile preamble with usepackage[synthetic-italic]{bntex}.
No explicit TEXMFHOME, TEXINPUTS, author-side font path or manual profile load
was supplied. Absolute pdfLaTeX ran with shell execution disabled and an empty
executable PATH. Initial compile: 0.518 s; a newly added sentence: 0.629 s.
These are individual local small-document samples, not performance guarantees.

Original Unicode extraction passed, all 72 installation files remained unchanged,
and no missing-character/font/layout warning occurred. Recorder inputs contained
no Python, JSON profile or prepared-word cache. The produced one-page PDF is
SHA-256 cd4f1d5c5d27fbcf15505bb6ced3dbe2fb7b1c4899fb4f1d334149a3eecbb3bd.

A separate temporary installed-filesystem test contained only pdfTeX, its observed
LaTeX dependencies, installed runtime assets and shared libraries. Python,
HarfBuzz, build sources and word caches were physically absent. New text was
introduced after building the root. Standard HOME/texmf loading, automatic
Regular/Bold/declared-slant output and extraction passed; runtime assets stayed
unchanged. Elapsed 0.691 s, no layout/font warnings. Its PDF SHA-256 is
67a9cd6a60ef43cd5c59e1f9551a6f67fc4cce703aaf80d79e25833c0702c1be.
This capability test checks independence and extraction; glyph-reference tests
are separate. It is not a hostile-TeX security sandbox or a browser test.

## Remaining boundaries

The symbolic-root resolver still cannot compile under the restrictive input
policy of the tested local older engine. It fails explicitly, without changing
policy or skipping integrity checks. Engine/Kpathsea behavior varies; upstream
2026 changes are documented in README.md. Actual target-platform validation is
still required. No Overleaf browser session, independent user or new-style human
approval has been invented, and the long-document target is not remeasured.

The complete local TDS and browsing candidate archives include the supported
fonts. They are not committed, attached or uploaded. Shared source archives
remain font-free and are not the complete CTAN submission. Naming/distribution
review, publication authorization and CTAN/TeX Live/Overleaf inclusion remain
separate. No release gate is marked passed and no public publication occurs.
