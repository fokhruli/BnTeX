# Milestone #3: Bengali corpus, pinned oracle, and review workflow

The mechanical implementation is available on `feat/corpus-oracle`, stacked on
bootstrap PR #9. Human typography review is **not performed**. Issue #3 stays
open until the required review is actually recorded; a green test is not approval.

## What is included

`corpus/bengali-v1.json` contains **138 cases in 18 categories**: 128 renderable
samples/probes and 10 expected rejections. Its source is original machine-assisted
curation, not an independently reviewed orthography standard or exhaustive list.
There are 192 additional deterministic generated behavior probes in the tests;
these are neither gold-standard words nor part of the 138-case frozen fixture.

Categories cover independent vowels; representative consonants; dependent,
pre-base, and split vowels; conjuncts; reph; ra-/ya-phala; nukta; candrabindu,
anusvara and visarga; digits; punctuation; ZWJ/ZWNJ; normalization equivalents;
combined word behavior; malformed sequences; and input errors.

Malformed but well-encoded sequences are deliberately distinguished from invalid
UTF-8. Their observed HarfBuzz rendering is stored as a **behavior probe**, not
accepted Bengali spelling. The missing-emoji case is valid Unicode but unsupported
by the pinned font. Empty and NUL-containing runs are adapter-contract errors.
The seven byte-only invalid-UTF-8 cases cover stray/bad continuation bytes,
truncation, overlong encodings, a surrogate, and a value above U+10FFFF.

## Files and commands

The command-line interface is `python -m bntex.corpus`; the existing preparer and
renderer are unchanged. Run from the repository after the README setup:

```bash
CORPUS=corpus/bengali-v1.json
ORACLE=corpus/oracles/noto-serif-bengali-regular-hb10.2.0.json
REVIEWS=corpus/reviews/noto-serif-bengali-regular.pending.json
FONT=/usr/share/fonts/truetype/noto/NotoSerifBengali-Regular.ttf

python -m bntex.corpus validate --corpus "$CORPUS"
python -m bntex.corpus check --corpus "$CORPUS" --oracle "$ORACLE" --font "$FONT"
python -m bntex.corpus review-status --corpus "$CORPUS" --oracle "$ORACLE" --reviews "$REVIEWS"
```

The maintained original text is in the corpus, not reconstructed from GIDs. Each
case stores original UTF-8 hex and, when decodable, the exact Unicode string.
Validation rejects inconsistent copies. Five canonical-equivalence groups retain
both original encodings (nukta letters and two-part vowels); no source is replaced
with NFC. The Python Unicode data version is recorded separately from the Unicode
17 reference used for reading. Cluster values remain **UTF-8 byte offsets**.

## Frozen reference contract

The checked-in oracle pins:

- Static Noto Serif Bengali Regular SHA-256:
  `32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef`.
- HarfBuzz **10.2.0**, FontTools **4.63.0**, Python `unicodedata` **15.1.0**,
  and the SHA-256 of the exact C-API adapter source.
- LTR, script `Beng`, language `bn`, cluster level 0 (monotone graphemes), buffer
  flags 0, default OpenType features, face index 0, OT font functions, and em scale.
- Corpus file digest/version and original byte digest for every case.

The row format is explicitly declared:

```text
[gid, cluster, x_advance, y_advance, x_offset, y_offset, flags]
```

Positions are signed integer font units, not points or pixels. Checks compare
all seven fields exactly; there is no numeric tolerance, font fallback, silent
version drift, or automatic regeneration. Cluster/flag metadata is not a language
line-breaking policy. With buffer flags 0, do not infer that absence of an
unsafe-to-concat flag proves arbitrary concatenation is safe.

`record` creates a candidate fixture, not approval:

```bash
python -m bntex.corpus record --corpus "$CORPUS" --font "$FONT" --out /tmp/candidate.json
```

It refuses unexpected outcomes. Existing files are not overwritten without an
explicit `--force`; that option still cannot replace the command's inputs.
`check` never writes the reference. A changed corpus, font, adapter, or toolchain
requires a deliberate reference-update PR and re-review, not an automatic fix.
Hashes detect changes; neither the oracle nor a review JSON is a signed attestation.

## A review sheet bound to the checked reference

Use the guarded build, which checks the exact font and toolchain **before**
emitting assets:

```bash
python -m bntex.corpus review-build --corpus "$CORPUS" --oracle "$ORACLE" \
  --font "$FONT" --out build/corpus-review
(cd build/corpus-review && pdflatex -no-shell-escape -halt-on-error review.tex)
(cd build/corpus-review && pdflatex -no-shell-escape -halt-on-error review.tex)
```

The resulting PDF shows each stable case ID, category, reference rendering, and
original Unicode scalar sequence (raw hex for rejection cases). It explicitly
states that human review has not occurred. The generated project contains a
local font copy; **do not commit or redistribute its font assets**. The normal
prepared-build integrity guard applies. Subsequent edits invalidate the evidential
value of the review sheet unless it is rebuilt and rechecked.

`review-tex` exports only editable source. It is not by itself evidence that the
reference font/toolchain was used to render that source. Use `review-build` for
the actual review workflow. A zero-width or otherwise unsupported rendering probe
must fail visibly rather than be replaced by a screenshot or an approximate glyph.

## Record human judgments separately

The tracked `.pending.json` ledger has **128 explicit unreviewed entries** with
null reviewer/date fields. Nothing here attributes a review to the maintainer.
Rejection cases are engineering checks, not typography approvals.

An actual reviewer should inspect the guarded PDF, compare each case with the
original scalar sequence, and record `accepted`, `rejected`, or `needs-discussion`.
A completed entry requires a human reviewer name, `reviewer_kind: "human"`, a
real ISO date, and explanatory notes. Alternative forms belong in
`unresolved_variants`; an accepted entry cannot retain unresolved variants.
Do not batch-approve cases merely because the oracle matches itself.

The ledger binds the corpus, **entire oracle file**, and font hashes. Changing
any of those makes old reviews stale. The validator checks completeness, types,
case order, provenance and attribution fields; a maintainer still must verify
that a claimed reviewer actually performed the work. JSON cannot authenticate a
person or prove linguistic correctness.

```bash
python -m bntex.corpus review-status --corpus "$CORPUS" --oracle "$ORACLE" \
  --reviews "$REVIEWS" --require-approved
```

Exit codes: 0 for success, 1 for an unmet human-approval gate, 2 for invalid input
or an oracle error. On the initial ledger, this release gate intentionally returns
**1**, reports 128 unreviewed cases, and does not change any records.

## Tests and CI

```bash
BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 \
  python -m pytest -q tests/test_corpus.py
```

The tests check deterministic recording, provenance, byte/source invariants,
malformed JSON, integer glyph rows, all seven field-level fault injections,
structural corruption, stale/fabricated review fields, safe writes, no rebaseline,
generated probes, bounded input, full pdfLaTeX review-sheet compilation, and
original Unicode extraction (including joiners and both nukta encodings).

The normal bootstrap CI exercises its installed toolchain; it may explicitly
skip **only the exact pinned-reference test** when that toolchain differs. Such a
skip is not a passing oracle gate. The new `pinned-corpus-oracle` workflow builds
HarfBuzz 10.2.0 from commit
`7b27c8edd46c674e01dd226fa9e1aa7549f5c436`, pins Python/FontTools, and makes the
exact oracle test mandatory. It never updates fixtures or publishes font files.
The font SHA must match even if a distribution's installed font package changes.
A CI definition is not evidence that a run passed; inspect the actual PR checks.

## Next implementation boundary

This milestone supplies a regression oracle and a review process, **not an
independent shaper**. HarfBuzz is used to generate the reference. The future
Python model (#5) must produce its own glyph runs without calling HarfBuzz for its
answer, and compare them against this fixture. The corpus is a regression sample,
not evidence of generic OpenType/font support. The pdfTeX decoder in #4 can be
implemented while typography review proceeds. The unseen-word/no-cache gate in
#6 remains unmet.

## Primary reading sources

The examples are original test data. The following sources inform the categories
and semantics; they do not certify this corpus or its typography:

1. [Unicode 17, Chapter 12, Bengali](https://www.unicode.org/versions/Unicode17.0.0/core-spec/chapter-12/).
2. [Microsoft Bengali shaping model](https://learn.microsoft.com/en-us/typography/script-development/bengali).
3. [HarfBuzz buffer/cluster/glyph-flag API](https://harfbuzz.github.io/harfbuzz-hb-buffer.html).
4. [HarfBuzz 10.2.0 build options](https://github.com/harfbuzz/harfbuzz/blob/7b27c8edd46c674e01dd226fa9e1aa7549f5c436/meson_options.txt).
