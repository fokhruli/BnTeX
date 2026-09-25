# Bengali corpus v1

See [the milestone guide](../docs/CORPUS.md) for schemas, reference pins, commands,
review instructions, CI, and limitations.

- `bengali-v1.json`: 138 original cases in 18 categories; raw UTF-8 preserved.
- `oracles/noto-serif-bengali-regular-hb10.2.0.json`: frozen mechanical results.
- `reviews/noto-serif-bengali-regular.pending.json`: 128 explicit unreviewed cases.

**No human typography approval has been recorded.** The 10 rejection cases are
engineering checks. Malformed sequence probes do not assert valid spelling.
Changing the corpus/oracle/font invalidates the corresponding review ledger.
Do not commit fonts, generated review builds, or regenerated reference data as an
unreviewed automatic response to a failing test.
