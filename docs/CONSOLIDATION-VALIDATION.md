# Consolidation and extended performance validation

This record separates actual GitHub merges, complete remote tests, local timing
and still-unperformed acceptance. It does not approve a public release.

## Repository consolidation

The maintainer authorized consolidation, performance integration, issue #7
checks and release preparation. PR #16 was retargeted to main and merged with
history preserved as `256254fe25ea7b091df02cba5117069f8ba2604e`.
Its proposed merge tree exactly equaled the previously tested integration tree
`6f171f682669f3a089cbab8838190b2a1e15318f`. Overlapping PRs #13 and #14 were closed
as superseded with explanations; their original implementation commits remain
in main's ancestry. No feature branches were deleted or reset.

Performance PR #17 was a separate PR on main. The exact runtime/test/tool files
from the supplied performance patch were imported without replacing live
integration interfaces with older attached variants. It merged as
`8d4561d81b0484176ebfca243e219632bcd9e748` after the complete pinned job reported
**551 passed in 82.79 seconds, no skips** (run 36080806480, job 107902114426).
Standard workflow 36080806483 also passed, including geometry and filename audit.
No unresolved review threads were returned at the merge check.

## Extended-budget measurements actually completed

The optimized installation's runtime code matches PR #17. The benchmark runs
serial TeX processes with shell execution disabled, nonexistent executable PATH,
no process-local memo package, unchanged installed assets and recorder checks.
Each requested page contains 96 synthetic Bengali-stem-plus-digit tokens.
Repeated mode has 16 distinct tokens; distinct mode has 96 times the page count.
The local measurement budget was explicitly increased to 600 seconds per pass.
That is not an optimization or a pass of the previous 90-second target.

| Requested / actual pages | Mode | First / second pass seconds | PDF bytes |
| --- | --- | --- | --- |
| 1 / 1 | repeated | 2.632065 / 2.652310 | 36478 |
| 1 / 1 | distinct | 2.676065 / 2.681878 | 37989 |
| 10 / 10 | repeated | 24.797271 / 26.570837 | 49823 |
| 10 / 10 | distinct | 25.676485 / 26.431043 | 65211 |
| 100 / 100 | repeated | 250.915203 / 256.338352 | 165145 |
| 100 / 100 | distinct | 252.342912 / 252.539928 | 318194 |

All runs completed. All expected tokens were recovered by Poppler. Each PDF has
three Bengali font entries; every pass reported 55,680 KiB peak RSS. No missing
characters, font warnings, overfull or underfull boxes were counted. Installation
hashes stayed unchanged and recorder audits found no forbidden runtime inputs.
The 100-page distinct case contains 9,600 distinct synthetic tokens, not an
independently reviewed book. OS caches were not flushed. Short documentation/test
work overlapped on the shared host; these are measurements, not confidence
intervals or guarantees for Overleaf hardware.

The full local JSON includes source/installation hashes, environment, per-pass
resource metrics and PDF identities. SHA-256 of that report:
`154557e46ffc30b7d85bd33c080dd91a26e2397205a52409a001e18da467559e`.

## Explicit remaining gates

Actual Overleaf browser import/new-word editing, independent second-user
reproduction and scoped native-output visual review remain unperformed. A
connector search returned no Overleaf integration. Local compilation or a fresh
agent-created directory does not substitute for those checks.

Issue #7 remains open: completed throughput measurement does not satisfy the
interactive long-document target. Issue #8 proceeds with source packaging,
manual, resource audits and a private dry-run workflow while distribution rights,
naming, human acceptance and explicit publication decisions remain pending.
Automatic Bengali routing stays deferred under #15. No public release, CTAN/PyPI
upload, visibility change or font redistribution was performed.
