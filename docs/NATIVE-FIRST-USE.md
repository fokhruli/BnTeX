# Native first-use throughput

Incremental optimization against main `b04d7881fb88301cabaa6dedbdaa4fdc4824cad4`.
This change targets first-time shaping, not cache hits. It does not close issue
#7, implement automatic input (#15), add fonts, or authorize a public release.

## Mechanisms and correctness conditions

1. Compile reverse first-input coverage from the exact font profile. On each
   glyph-ID assignment, mark the lookups that may start at that glyph. Markers
   accumulate monotonically within one run; a removed glyph can cause a harmless
   extra scan, never an incorrectly skipped lookup. New glyphs from substitutions
   and clones pass through the same setter. Zero-action contextual blockers and
   class-zero positioning coverage remain included. Root passes with no possible
   starting glyph skip the scan but retain its charged no-op work and terminal
   state. Actual matching, filtering, masks and lookup ordering are unchanged.
2. Use copied epoch stamps rather than clearing every lookup for every word.
   State is bounded by 640 glyph names and 128 names for each layout-table kind,
   not vocabulary size. Each shape call advances the epoch, including repeated
   text. A tested wrap clears all marker names before reuse. No glyph runs are
   stored by this mechanism, and no data are written across compilations.
3. Specialize integer-array setters once, retaining the existing authoritative
   arrays. Only glyph-ID assignments invoke the activation hook. A separate
   control-sequence state-mirror experiment was slower and is not included.
4. Guarded initial reordering handles one unligated, zero-mask base or a base
   with one attached sign and equal input clusters. Complex syllables retain the
   full original algorithm, including stable bucket sorting. Final reordering
   skips only an unligated singleton already at base position. The original
   functions remain executable dense controls; tests compare complete traces.
5. After literal token validation, construct original byte hex once with
   pdfTeX's escape primitive. Keep the strict UTF-8 state machine, byte/scalar
   mappings, malformed-input policy and non-expansion of macros unchanged. The
   exact-hex API remains an independent control in decoder tests.

Legacy emitted tables without the activity marker keep dense root scans. Current
installations still require matching files and hashes; this is not permission to
mix files from old and new exports. Removing only the new activity declarations
recovers the pre-change indexed table SHA-256 exactly:
`1f6c6135dec97b3260deee6826508b9688d20c16257437f3e6582af7221df78d`.
Removing all dispatch indexes also preserves the original unindexed identity.
The font/profile, frozen glyph fixtures, renderer geometry, authoring interfaces,
optional memo package and publication-readiness gates are unchanged.

New table SHA-256:
`e0599bf2311d96947cac928f76ebbf4c2596de2250ee934c0d8a34ab74bd5cae`.
Table size increases from 873,538 to 918,705 bytes for font-derived activation
rules, not pre-shaped words.

## Actual local correctness evidence

Thirty new tests cover reverse coverage, unchanged rule bytes, complete dense
versus optimized traces, exercised shortcuts, complex-cluster fallback, per-call
state resets, new/removed glyphs, epoch wrap, no-op accounting and operation-limit
errors, literal versus exact-hex decoding, and matching source/resource copies.

The reconstructed local checkout passed **180 tests in 57.35 seconds, no skips**:
41 original baseline tests, 68 native engine tests, 41 prior dispatch tests and
30 new tests. It is not the full live repository. The local native fixture uses
the exact live-profile JSON override. Remote CI must compile the live profile
and run the complete repository; its result is reported in the PR discussion.
No expected glyph output was regenerated. The unchanged inherited suite includes
the 261 frozen forms, 1,606 conjunct/vowel contexts and join-control regressions.

The physically Python-free Linux test root also passed: no Python interpreter,
HarfBuzz library or word cache was present during TeX execution, shell escape
was disabled, original text extracted, all seven glyph fields matched the
reference outside the root, and installed assets remained unchanged. The
capability page took 0.793 seconds; that is not a throughput benchmark or an
untrusted-TeX security claim. The existing mixed-language specimen compiled twice
and was rendered and visually inspected; it is not a new human approval.

## Paired local measurements, memoization off

Identical source bytes and fixed font/profile; fresh TeX process per pass. Existing
`tools/native_performance.py` uses 96 tokens/page, Bengali stems plus five Bengali
digits, and explicit page breaks. Every token is distinct in these cases. This is
synthetic, not representative book prose. Measurements are serial, on a shared
host; OS caches were not flushed and there are no statistical confidence bounds.

| Pages | Distinct tokens | Parent seconds | Candidate seconds |
| --- | ---: | --- | --- |
| 1 | 96 | 2.767 / 2.666 | 1.956 / 2.023 |
| 10 | 960 | 25.014 / 24.744 | 17.672 / 18.309 |
| 100 | 9,600 | 250.267 (one pass) | 179.529 (one pass) |

Mean-time reductions for 1/10 pages are 26.8%/27.7%; the single 100-page comparison
is 28.3% less time. This is approximately 1.37--1.39x throughput, not another 6x
improvement over already-optimized main. All paired PDFs are byte-identical,
expected page counts and all token extractions pass, and font entries stay at
three. Peak RSS ranges from 55,552 to 55,808 KiB in these document runs. Asset
hashes are unchanged and recorder audits contain no forbidden runtime inputs.
The 100-page runs used a 600-second budget and **still fail the 90-second target**.

A separate 10-page control used 960 distinct four-component strings with NO
digits and memoization off. Parent: 14.272 / 14.255 seconds. Candidate: 11.577 /
11.986 seconds (17.4% less mean time). Paired PDFs are byte-identical and extraction
passes. These generated strings are not asserted to be valid dictionary words.
The deterministic components and generation are:

```python
syllables = ['ক','খ','গ','ঘ','কা','কি','কু','কে',
             'ক্র','প্র','গ্র','ত্র','ক্ষ','জ্ঞ','দ্ব','স্ব']
words = [''.join(syllables[(i // (16**j)) % 16] for j in range(4))
         for i in range(960)]
```

The same generated 10-page/96-token template is used after replacing its known
synthetic tokens with these strings. This fixed-fixture operation is not an
arbitrary TeX parser. Full measurements, source hashes, generated digit-free
source and an exact reproduction script accompany the private review artifacts.

Diagnostic phase timers are separate from the document measurements: inclusive
GSUB time fell from 0.663 to 0.521 seconds, initial reordering from 0.215 to 0.150,
and total diagnostic time from 1.754 to 1.464 seconds. Phase timers have overhead
and are not mutually exclusive; do not sum them as an exact wall-time partition.

## Reproduce and install

Export a fresh complete installation using the current package, pinned profile
and separately installed font. No document vocabulary enters the exporter. Do
not copy individual updated .def files into an old installation.

```sh
BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 python -m pytest -q
python tools/native_performance.py \
  --installation baseline=/path/to/parent-installation \
  --installation candidate=/path/to/new-installation \
  --out build/first-use-small --pages 1 10 --modes distinct \
  --memo off --passes 2 --timeout 120 --profile
python tools/native_performance.py \
  --installation baseline=/path/to/parent-installation \
  --installation candidate=/path/to/new-installation \
  --out build/first-use-large --pages 100 --modes distinct \
  --memo off --passes 1 --timeout 600
```

Body text still uses `\bnNative{...}`. Reordering traces and glyph dumps remain
available. New text always executes the native shaper unless the separately
loaded, unchanged memo package legitimately reuses that run within the process.
Actual Overleaf/second-user/native-human review, practical long-document latency,
and distribution decisions remain pending. No font files, publication or global
script-routing feature are included in this change.
