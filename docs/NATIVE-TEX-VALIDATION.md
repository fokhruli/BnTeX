# Issue #6: executed native-pdfTeX validation

Date: 24 September 2026. This report records local executions, not inferred CI.
Parent repository revision: `1098050b2f9cab54e750efd18de34ad44f171f81`
(`feat/fixed-font-model`). The existing cached renderer, decoder and frozen
reference files are unchanged.

## Identities and implementation

- Font SHA-256: `32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef`.
- Live typed-profile SHA-256: `f6294540099a3b6f622f2cdd9e863050390f75fd0576495d5a2316903f8cfb42`.
- Emitted table SHA-256: `7fd73a9d0d21b99c4d2580f209ec0c1cc8bf15d72c8eb444522b38898577cd4a`.
- 640 glyph metrics, three 256-slot font banks, 59 GSUB and six GPOS lookups.
- New opt-in `bntex-native.sty` / `\bnNative`; the cached `\bn` contract is unchanged.
- TeX-readable tables contain font rules and a finite syllable-grammar DFA, not
  words or document-specific glyph runs. Export takes no text/corpus argument.

The independently executed expl3 runtime performs normalization of a separate
working sequence, syllable analysis, font-dependent classification, initial and
final reordering, masked/nested GSUB, component ownership, GPOS positioning,
cluster flags and original-order ActualText. It adapts the existing model and
published HarfBuzz algorithms; this is not an algorithmic novelty claim.

## Final local suite

```text
BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 \
BNTEX_NATIVE_PROFILE_JSON=build/live-profile.json PYTHONPATH=src python -m pytest -q
243 passed in 159.62s (0:02:39)
```

No skips. This reconstructed local checkout contains the 41-test original bundle,
134 issue-5 overlay tests and 68 new native-TeX tests. It is **not the full live
repository checkout**. In particular, do not add this number to the old remote
counts or describe it as a full-branch CI result. The live-profile data were
reconstructed and their exact live fingerprint verified. New repository tests
compile the live profile directly when the local override is absent.

Environment: Python 3.13.5, FontTools 4.63.0, HarfBuzz 10.2.0, pdfTeX 1.40.26
(TeX Live 2025/dev/Debian), Linux x86-64. Python/HarfBuzz run on the test side,
not as programs called by TeX.

| Check | Executed result |
| --- | --- |
| Frozen supplied inventory | All 261 original strings match all seven frozen glyph fields exactly |
| Conjunct/vowel interactions | 146 bases times 11 contexts: 1,606 exact matches |
| Generated extended sequences | 192 runs match the pinned reference |
| Join controls and difficult regressions | 116 runs match |
| Byte/encoding preservation | Literal and hex APIs retain original logical Unicode; nukta and split-sign encodings remain distinct |
| Geometry | Ten words at three sizes match reference advances/ink bounds within the test's one-scaled-point rounding tolerance |
| Errors and bounds | Unsupported input, malformed UTF-8, oversized syllables/spans, token non-expansion, style rejection and asset tampering tested |
| Export | Reproducible tables, exact font/profile pins, closed grammar, no-overwrite/symlink guards and identical wheel resources tested |
| Ordinary engine isolation | Absolute pdfLaTeX executable, empty PATH, shell disabled; recorder verifies no Python/JSON/corpus/cache reads |

Generated runs are behavior probes, not independently approved dictionary words.
Some sets overlap and must not be summed as unique vocabulary coverage. The frozen
supplement was recovered from the live repository without rebaselining; its Git
blob SHA-1 remains `513f018036962986ac9a3663ba2496c1e1a5cbea`.

## Strong unseen-word gate: no Python in the runtime filesystem

`tools/native_chroot_gate.py` was actually run with the needed Linux capability.
A disposable root contained only pdfTeX, its measured shared-library/LaTeX
requirements and the vocabulary-independent font installation. It contained no
Python interpreter, HarfBuzz library, corpus, JSON profile or word cache. Shell
execution was disabled; PATH pointed to a nonexistent directory.

Only after assembling that root, the tool introduced six new compound/inflected
word samples and three encoding/join-control diagnostic runs. The document was
compiled inside the root. After the engine exited, the host compared every glyph
field against HarfBuzz, checked logical Unicode extraction and verified that all
installation assets were unchanged. Result: **passed**, 4.253429 seconds of engine
wall time for this one-page diagnostic document. This timing is not a general
throughput benchmark and includes diagnostics and repeated shape/render calls.

The proof output records `root_contains_python=false`,
`root_contains_harfbuzz=false`, `root_contains_word_cache=false`, and
`shell_escape=false`, plus the actual runtime-file inventory and hashes. The
privileged chroot tool is for this trusted capability test, not a hostile-TeX
security sandbox. The temporary root and its font copies were removed afterward.

## Rendering and development findings

The final unseen-word proof and mixed English/Bengali/math example were rendered
with Poppler and visually inspected for layout. The mixed example compiled twice
without overfull/underfull/missing-character/font warnings. Embedded Bengali
fonts are native subsetted TrueType, not bitmap words or page-fragment caches.
Poppler extraction preserves the expected original text.

A separate native-versus-cached comparison for ten words at 12 pt found a maximum
width/height/depth difference of five scaled points (about 0.0000763 pt). Both use
the same pinned font and explicit glyph geometry; the small difference comes
from dimensional rounding. This is backend agreement, not all-viewer approval.

Development exposed and fixed eager-versus-delayed scratch-register arguments,
protected membership tests used in expandable predicates, and ordinary-space
classification. Ordinary SPACE is now Other, not a standalone placeholder;
SPACE plus an orphan matra is rejected instead of silently mis-reordered.
These fixes have regression tests and are included in the final table hash above.

## Remaining boundaries

Only the pinned regular upright font/configuration is claimed. Bold/italic,
Latin letters inside `\bnNative`, automatic global script switching, arbitrary
fonts and general malformed input are outside scope. Limits are explicit: 4096
UTF-8 bytes per call/span, 64 normalized elements per syllable, 8192 allocated
nodes, 32 contextual levels, two million charged lookup operations and 200,000
trace cells. These bounds do not establish a production security certification.

Ordinary spaces permit paragraph wrapping between word boxes; intraword breaks,
hyphenation and complete line-break semantics are not implemented. Moving
arguments, bookmarks, tagged PDF, other viewers/platforms, real Overleaf browser
execution and long-document performance require separate validation. Visual
inspection here is not a new human typography approval attributed to the user.

Remote workflow results, if executed, belong in the PR discussion with their real
run IDs and counts. No merge, release, visibility change or font redistribution
is implied by this report.
