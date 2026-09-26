# Fixed-profile IgnoreMarks pair specialization

Baseline: merged main `1f6f8fa38a0092909204010d0bd36c707bb24e12` (PR #23).
The full 141-file source snapshot was verified against Git tree
`a622647f826b6109af3fd7772596494bf9097b0d`; no local profile override is used.
This is an incremental native-runtime experiment for issue #7, not automatic
input (#15), an additional font, a word cache, or release authorization.

## Selected family and evidence

Specialize GSUB ligature rules with exactly two input glyphs and lookup flags
exactly 8 (IgnoreMarks), only when the existing call uses manual join-control
mode. There are 54 such rules in the pinned profile. Separate call counting on
one-page, memo-disabled fixtures found 330 of 456 attempted ligature rules in the
distinct/repeated stem-plus-digit fixtures, 242 of 332 in the digits-free fixture,
and 335 of 448 in the original prose fixture in this family. These are attempted
ligature-rule counts, not shares of total shaping time or successful ligations.

## Implementation and equivalence conditions

The installation exporter generates one small forwarding macro per eligible font
rule. Glyph IDs and lookup identity are integer-validated static arguments. The
start position, syllable restriction and feature mask remain runtime arguments.
It never reads document text or vocabulary. Other rule lengths, flags, lookup
kinds and nonmanual join-control calls retain the original generic matcher.

Under manual input mode with context/positioning disabled, the generic matcher's
two ignore queries reduce to the same static font-derived IgnoreMarks predicate.
The specialized matcher therefore skips those glyphs, checks each of the two
literal glyph IDs, then checks the unchanged syllable and mask predicates. It
preserves matched positions, global ignore/success state, and one charged tick
per skipped or examined glyph. It freezes arguments before entering its scratch
variable group. Tail iteration through ignored marks is tested at the full
8,192-node internal buffer bound. This test is not a claim that a user may bypass
the existing per-syllable or UTF-8 span limits.

Lookup candidate order, first-input checks, zero-action contextual blockers,
ligature component compatibility/ownership, substitution actions, normalization,
reordering, GPOS, original Unicode and rendering are unchanged. The generic
matcher remains executable. Tests can force it with a locally grouped setting:

```tex
\ExplSyntaxOn
\bool_set_false:N\l__bn_mark_pair_enabled_bool
\ExplSyntaxOff
```

This is an internal test control, not a stable public package option. Ordinary
users continue to use `\bnNative{...}`. The optional memo package is unchanged.
There is no document-specific preparation or Python execution inside pdfTeX.

## Installation format

`bntex-native-matchers.def` is a separate generated, checksummed asset (6,064
bytes). Keeping it separate preserves the original font-rule table bytes exactly:

- Font SHA-256: `32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef`.
- Typed profile: `f6294540099a3b6f622f2cdd9e863050390f75fd0576495d5a2316903f8cfb42`.
- Original tables: `e0599bf2311d96947cac928f76ebbf4c2596de2250ee934c0d8a34ab74bd5cae`.
- Generated matchers: `c60b0552e4bc1f4b449dd3b9cfa32b459989c8ee60a91cd7c95e29c95a35eaee`.

The exporter includes the new asset in runtime file checks and the installation
manifest. Missing/changed matchers fail before rendering. Export a fresh complete
installation after updating; do not splice individual modules into an old one.
Font binaries and generated installations remain local and are not committed.

## Tests actually executed locally

With both integration and exact-reference gates mandatory, the unchanged full
baseline passed **717 tests in 155.86 seconds** and the candidate full repository
passed **747 tests in 164.19 seconds, no skips**. These are local suite durations,
not compilation-performance results or a substitute for final remote CI.
The actual font-profile compiler ran in both suites, without a reconstruction
patch or profile override. No expected glyph fixture was regenerated.

Thirty new tests include exact generation for all 54 rules; guarded fallback;
all 261 frozen input forms versus the generic path; complete stage traces for
curated and 96 seeded conjunct cases; and 810 adversarial internal-buffer cases
(1,620 fast/generic observations). Buffers cover missing/wrong glyphs, skipped
marks, out-of-range starts, syllable boundaries, masks and join-control metadata.
Tests preserve failure state and charged operation limits, exercise the optimized
path, check grouping, stress 8,192 nodes, and detect missing/altered generated
assets. Inherited tests also compare against the pinned HarfBuzz reference.

The exclusive profiler instruments the specialized helper under the same match
phase as the generic helper. Otherwise faster matching could be misattributed to
the substitution driver's self time. Instrumentation is not loaded by users.

## Paired uninstrumented measurements

Same font/profile and source bytes. Three fresh processes per version, alternating
A/B order; no test suite ran concurrently. Shared host, no OS-cache flush, no
confidence intervals. The following are medians (minimum--maximum), in seconds.

| Workload, memo OFF | Baseline | Specialized |
| --- | --- | --- |
| 1 page, 96 distinct digit-suffixed tokens | 1.798 (1.798--1.804) | 1.810 (1.798--1.823) |
| 10 pages, 960 distinct digit-suffixed tokens | 16.842 (16.335--16.966) | 15.986 (15.916--16.015) |
| 1 page, 96 distinct digits-free strings | 1.098 (1.095--1.116) | 1.042 (1.023--1.070) |
| 10 pages, 960 distinct digits-free strings | 10.310 (10.035--10.358) | 10.063 (9.924--10.091) |
| 1 page, 65-word authored prose | 0.857 (0.849--0.894) | 0.855 (0.809--0.882) |
| 10 different paragraphs, 623 occurrences / 392 distinct words | 6.721 (6.612--6.733) | 6.348 (6.238--6.368) |
| 1 page, repeated tokens | 1.809 (1.782--1.814) | 1.729 (1.720--1.766) |
| 10 pages, repeated tokens | 17.006 (16.877--17.031) | 15.921 (15.828--16.780) |

The 10-page distinct and varied-prose medians are 5.1% and 5.5% lower. The
10-page digits-free change is 2.4%, with overlapping ranges. The one-page
stem-plus-digit median is 0.7% higher; one-page prose is essentially flat.
Do not claim a universal speedup, a halved total cost, or a new 90-second pass.

With memo explicitly ON, repeated tokens are essentially unchanged: 1 page
0.714 (0.709--0.741) versus 0.715 (0.704--0.758), and 10 pages 3.275
(3.244--3.278) versus 3.297 (3.213--3.348). These cache-hit workloads must not
be pooled with first-use costs. Every completed pair has byte-identical PDFs,
expected page counts and extracted words, three Bengali font entries, unchanged
installation hashes and no forbidden runtime inputs.

`examples/benchmark-prose-v1.json` contains ten different assistant-authored
paragraphs. They are not mined, independently reviewed, or representative of
Bengali books. The 100-page form cycles those ten paragraphs; it does not create
100 pages of unique prose. Old synthetic/prose fixtures keep their original
bytes. Timing evidence must always report actual occurrences and distinct words.

An earlier loop-based helper and an inline-table layout were pilot experiments;
the table above measures the final separate-asset tail-iteration implementation.
Pilot results are not substituted for final measurements. Longer-run and real-use
results are recorded separately in the PR's final validation comment.

## Reproduction

```sh
BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 PYTHONPATH=src python -m pytest -q
python -m bntex.tex_export --profile build/profile.json \
  --font /path/to/NotoSerifBengali-Regular.ttf --out build/new-installation
python tools/native_decode_benchmark.py \
  --baseline /path/to/main-installation --candidate build/new-installation \
  --out build/matcher-pairs --pages 1 10 \
  --kinds distinct digits-free varied-prose repeated --repetitions 3 --timeout 120
python tools/native_decode_benchmark.py \
  --baseline /path/to/main-installation --candidate build/new-installation \
  --out build/matcher-memo --pages 1 10 --kinds repeated --memo --repetitions 3
```

All output directories must be new. Run-folder font copies must not be committed
or shared as source artifacts. Keep JSON evidence and rendered PDFs separately.
Real Overleaf import/editing, a second person installing the package, and scoped
native typography approval remain independent acceptance tasks. Automated local
reproduction or a successful source-archive dry-run does not complete them.
