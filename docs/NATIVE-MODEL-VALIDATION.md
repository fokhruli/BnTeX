# Issue #5 — executed validation snapshot

Date: 24 September 2026. This records executed local work before opening the PR.
Remote CI results must be read from the actual PR jobs/comments, not inferred
from this document. No TeX-native shaping or public release is claimed.

## Identities and unchanged inputs

Parent: `ba9390d5830c187d1de94279930af9d308212463` (`feat/pdftex-utf8`).
Pinned font SHA-256:
`32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef`.
Compiled ABI-1 profile SHA-256:
`f6294540099a3b6f622f2cdd9e863050390f75fd0576495d5a2316903f8cfb42`.
Profile size: 121,814 bytes; 640 glyph metrics, 173 cmap entries, 54 GSUB and six
GPOS lookups for bng2/default. Compilation takes no document/corpus input.

Original frozen supplementary reference Git blob:
`513f018036962986ac9a3663ba2496c1e1a5cbea` (2,953 bytes).
Original user inventory Git blob:
`26061b4760c267bd89fe663dcee79486057d926b` (5,157 bytes).
Both were fetched and hash-verified, not regenerated from model output.
The issue #4 decoder pair was recovered unchanged from the supplied standalone
ZIP and checked against the live Git blob hashes before the handoff test.

## Local suite

```
BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 PYTHONPATH=src \
  python -m pytest -q -k 'not original_corpus'

150 passed, 1 deselected in 17.67s
```

**Scope:** 109 new tests plus the original 41-test source-bundle baseline. The
local reconstruction does not contain every later inherited test/file from the
267-test live branch. The one deselected new test compares the inherited original
138-case corpus, which was not restored locally; it is mandatory in full-branch
CI. No missing original corpus was replaced by a miniature stand-in. Full remote
CI must run all 110 new tests alongside the actual inherited suite.

Environment: Python 3.13.5, FontTools 4.63.0, HarfBuzz 10.2.0, local pdfLaTeX and
the exact installed static Noto Serif Bengali Regular font. Generic environments
with a different HarfBuzz explicitly skip live generated-reference comparisons;
`BNTEX_REQUIRE_ORACLE=1` turns that condition into failure. Frozen glyph-row tests
do not execute HarfBuzz.

## Differential coverage actually executed

- All **261 frozen supplementary samples**: exact equality of GID, UTF-8 byte
  cluster, x/y advances, x/y offsets and flags. Original text/bytes preserved.
- All **96 mapped Bengali-block scalars** in the pinned font, including explicit
  isolated-sign diagnostic mode, compared against HarfBuzz 10.2.0.
- **1,606 conjunct/vowel probes**: each of the user's 146 conjunct bases with no
  sign or each of ten vowel signs; all seven fields match.
- **12,000 seeded generated word-like consonant chains**: all seven fields match.
  These are generated stress inputs, not 12,000 verified Bengali dictionary words.
- Targeted real words, reph, split-matra/nukta equivalent encodings, repeated marks,
  join controls, ligature-component identity and diagnostic regressions.

Generated malformed probes initially found joiner/attachment/cluster-flag bugs.
Those were corrected with targeted tests. A remaining behavior family involving
**ZWJ inside broken/standalone dotted-circle clusters** is explicitly rejected,
not silently approximated or counted as supported. See NATIVE-MODEL.md. Matching
ordinary inventory and generated cases is finite regression evidence, not a proof
of all possible Unicode sequences or all Bengali typographic traditions.

## Independence and interface tests

A fresh subprocess used `python -S`, an otherwise empty PATH, a temporary working
directory, and an import blocker for HarfBuzz, uharfbuzz, ctypes and FontTools.
It loaded only the compiled profile and independently shaped `আত্মবিশ্বাস`.
No font file, word dictionary, network service or subprocess shaper was needed.
Python itself is still required by this development model.

The actual issue #4 decoder was run under an absolute pdfLaTeX executable with
`-no-shell-escape -halt-on-error` and an otherwise empty PATH. Its scalars, byte
offsets, byte lengths and original hex for `ক্ষ` were read by the test harness and
passed into `shape_decoded`; output equals direct Unicode shaping. TeX did not
invoke Python. This is an interface test, not the later all-TeX shaping gate.

## Compiler, corruption and robustness checks

Typed profile roundtrip and repeated compilation are byte-identical. Tests reject
wrong raw fonts, changed compiled rules even with unchanged claimed font hash,
unknown/wrong JSON types, boolean-as-integer fields, invalid glyph references,
missing/cyclic/deep lookups, bad filtering sets, device/variation constructs and
unsupported required subtable/anchor formats. Synthetic lookups exercise ordered
ligature priority, length-changing nested contexts, class-zero pair positioning
and pen-relative mark attachments.

Source/scalar mismatch, invalid bytes/scalars, unsupported scripts, input/glyph/
operation/trace bounds, output overwrite and symbolic-link protection, damaged
reference rows and wrong reference provenance/configuration are tested. These
limits are engineering guards, not an arbitrary-font or arbitrary-code sandbox.

## Remaining acceptance work

No existing corpus, renderer or oracle is changed; no fonts are committed. The
maintainer's earlier document-level acceptance remains scoped to that PDF. This
milestone does not manufacture new human reviews or auto-close the full issue.
The traceable Python model and typed profile are ready for review, with the
explicit input boundary above. The expl3 port, font-profile installation into
TeX, native `\\bn`, cache-free pdfLaTeX, Overleaf browser validation, other fonts,
and publication remain separate work, primarily issue #6 onward.
