# Exclusive phase profiling and the next throughput decision

This is diagnostic tooling, not a new speedup claim. The production shaper,
renderer, decoder, font tables, profiles and frozen glyph expectations are
unchanged. Automatic input (#15) and issue #7's acceptance gates stay deferred.

## Baseline and motivation

PRs #19 and #20 are now in main at `2d30db0`. The maintenance commits after that
checkpoint do not alter the native runtime. The older phase timers were inclusive:
GSUB invoked inside another phase could appear in both totals. A new optimization
must not be chosen by summing overlapping timers or by counting fewer calls alone.

`tools/native_exclusive_profile.py` inserts bounded instrumentation into its own
fixed test fixtures. Python prepares the diagnostic source, starts real pdfTeX,
and reads its completed logs; Python does not shape inside that process. The
ordinary package installation and user documents do not load this profiler.

## Timing contract

Thirteen labels share a 64-level nesting stack. Entering a child charges elapsed
time to its parent; returning charges the child and resumes the parent. Recursive
calls to the same phase are handled. Exclusive totals partition exactly the
instrumented document-body interval. Inclusive totals overlap and must not be
summed. Decode continuations are timed only until success/failure dispatch, not
through the shaping invoked by the success continuation.

The observer has overhead. Plain and instrumented runs are alternated in three
fresh processes each. The principal probes use memoization OFF; the repeated
workload also has a separately reported memo-enabled control. No regression
suite runs concurrently with the measurements.
The report retains each sample, subprocess wall time, original source hashes,
installation identity, extraction and immutability checks. These are local,
shared-host measurements, not confidence intervals or uninstrumented CPU shares.
Startup/loading and final PDF writing are included in subprocess wall time but
not attributed to the instrumented body phases. The difference is NOT a precise
startup-only measurement.

## Executed measurements

Runtime identity: PR #20's unchanged native files, exact installed font
`32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef`, typed profile
`f6294540099a3b6f622f2cdd9e863050390f75fd0576495d5a2316903f8cfb42` and table hash
`e0599bf2311d96947cac928f76ebbf4c2596de2250ee934c0d8a34ab74bd5cae`.
The local checkout is reconstructed; the exact profile override is used locally.
Remote full-suite results are reported separately in the PR, not inferred here.

| One-page fixture | Plain median seconds (range) | Instrumented median seconds (range) |
| --- | --- | --- |
| Authored prose, 105 occurrences / 94 distinct tokens | 1.423 (1.393-1.446) | 1.616 (1.614-1.729) |
| 96 distinct stem-plus-digit tokens | 1.864 (1.823-1.868) | 2.124 (2.056-2.125) |
| 96 distinct digits-free synthetic strings | 1.169 (1.104-1.174) | 1.272 (1.262-1.375) |

The existing authored prose fixture is not a representative book corpus. The
synthetic fixtures are not approved dictionary words. No new 100-page measurement
or pass of the 90-second target is asserted.

Median exclusive shares, with detailed matching/allocation instrumentation:

| Phase | Prose | Stem-plus-digit | Digits-free |
| --- | ---: | ---: | ---: |
| Substitution driver, excluding nested matcher | 22.91% | 21.19% | 23.29% |
| Contextual matching | 20.15% | 17.10% | 18.31% |
| Decode and collect | 10.39% | 7.91% | 6.21% |
| Initial reordering | 8.06% | 9.54% | 9.35% |
| Positioning | 8.24% | 8.74% | 7.90% |
| Node allocation | 3.73% | 4.94% | 4.48% |
| Rendering | 2.55% | 3.08% | 2.92% |

Other phases are preserved in the JSON, not silently assigned to one of these
rows. Component-wise medians need not sum to 100%; each individual sample does.

## Output checks

All completed pairs preserve their page count, expected text, native font data,
drawing operators/coordinates, ActualText, and installed file hashes. Adding the
observer's expl3 integer arrays shifts internal font resource identifiers, so
these PDFs are NOT byte-identical. The comparison resolves each `Tf` resource to
its complete canonical font data, then compares the actual operators and page
geometry. It does not erase font content, glyph strings or Unicode differences.
It rejects unhandled resource kinds or annotations; it is a fixed-fixture check,
not a universal PDF comparator. Tests intentionally change font, text and position
and verify rejection. Complete shaper traces are compared separately.

## Explored changes not shipped

Three local prototypes were measured: fixed-field accessors, prebuilt node
initialization/copy instructions, and merged matcher-filter predicates. On the
small paired fixtures their gains were modest, inconsistent or overlapping noise.
The matcher-filter prototype in particular did not show a dependable end-to-end
benefit. All three were reverted. No unsupported production shortcut or claimed
speedup is included just to increase the number of changes.

## Next coding target

Test one font-derived, generated matching routine against the current generic
matcher, beginning with a narrow supported lookup form. Preserve filtered glyph
visits, manual joiners, syllable/mask conditions, ordered zero-action blockers,
component ownership and charged operation limits. Keep the generic matcher as an
executable control. The exporter must consume font rules, never document text.
Expand only after exact traces and a repeatable uninstrumented end-to-end gain
pass. Do not rewrite the renderer based on its small observed share.

## Commands

```sh
python tools/native_exclusive_profile.py \
  --installation build/native-installation --out build/profile-prose \
  --kind prose --detail --repetitions 3
BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 \
  python -m pytest -q tests/test_exclusive_profile.py
```

Output paths must be new. Generated run directories contain local font copies;
share the resulting JSON/PDF evidence, not those directories. A Python-free
runtime capability was not rerun for this diagnostics-only patch; no production
runtime files changed. Browser, independent-user and native human-review gates
remain separate. This is not release authorization.

## Review follow-up: repeated vocabulary measured separately

The initial CLI omitted the repeated fixture. Review identified this coverage
gap; `--kind repeated` and an explicit `--memo` switch are now available. The
original distinct/prose measurements above are retained, not overwritten.

Three additional alternating pairs use 96 occurrences of 16 distinct tokens.
Without memoization, all 96 occurrences execute the shaper: plain median
1.812 seconds (1.790-1.861), observed 2.045 (1.996-2.058). Median exclusive shares
are 21.21% substitution driver, 17.04% matcher, 7.79% decode/collect, and 3.16%
rendering. This is consistent with the first-use cost target, not a speed gain.

With memoization explicitly enabled, both plain and observed runs report 80 hits,
16 misses, 16 stored runs and no evictions. Plain median is 0.753 seconds
(0.742-0.772), observed 0.768 (0.765-0.768). Exactly 16 shaping executions and six
whole-span decoder calls are observed. Relative phase shares change: 11.77%
substitution driver, 9.50% matcher, 26.38% decode/collect and 10.08% rendering.
These are not first-use measurements and must not be pooled with memo-off data.
Both controls pass drawing/resource equality, extraction and asset invariants.
They use the same highly repetitive synthetic fixture, not representative prose.

The final local test selection passed **29 tests in 19.12 seconds**, including
the new repeated fixture and exact memo hit/miss/execution counts. Full-repository
CI results for the updated commit must still be read from the completed job.

```sh
python tools/native_exclusive_profile.py \
  --installation build/native-installation --out build/profile-repeated \
  --kind repeated --detail --repetitions 3
python tools/native_exclusive_profile.py \
  --installation build/native-installation --out build/profile-repeated-memo \
  --kind repeated --detail --repetitions 3 --memo
```
