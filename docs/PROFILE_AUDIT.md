# Structural font-profile audit

`profile` is a **read-only requirements audit**, not a profile compiler or a
Bengali shaper. It does not produce TeX rules or permit unseen words to compile.

```bash
python -m bntex profile --font /path/to/NotoSerifBengali-Regular.ttf > profile.json
python -m bntex profile --font /path/to/font.ttf --script bng2 --script beng
```

The default scope is the union of `bng2`, `beng`, and `DFLT`, including every
language system and every exposed feature. This conservatively over-approximates
possible requirements. It is NOT the order of feature execution in an Indic
shaper. A font may have no matching script; the empty selected-system list is
explicit and must not be read as success of a native shaper.

## What it records

The report fingerprints the exact font and tool versions. It follows
ScriptList/LangSys to required/optional features, root lookup indices, and
transitive contextual lookup references. Both GSUB extension type 7 and GPOS
extension type 9 are unwrapped. Lookup flags, GDEF dependencies and mark filtering
indices are checked. Reachable, nested-only and unreachable lookups are separate.
A bounded iterative walk and visited lookup set handle recursive graphs; DFS back
edges witness cycles, but do not enumerate every possible cycle or execute one.

FontTools normalizes some subtable representations and discards their `Format`
attribute. The audit therefore also reads the ORIGINAL binary subtable headers,
recording `outer_format` and `effective_format` rather than guessing the original
wire format from a normalized mapping. `decoded_format` may legitimately be null.
`effective_type_counts` counts subtables, not distinct lookup records.

Advanced device adjustments, variation indices, point-index anchors and feature
variations are reported rather than implemented. The native-support flag is
always `false` in this revision. A structurally traversable font graph is not a
complete font validator, a font license determination, or an executable profile.

## Tests and first observed result

Synthetic tests cover transitive references, unreachable nodes, required and
language-specific features, GSUB/GPOS extension wrappers, cycles, broken indices,
GDEF filtering dependencies, reserved flags, mixed extension types and truncated
headers. Three installed static Bengali font faces are audited deterministically.

For the exact regular Noto Serif Bengali font recorded in BOOTSTRAP-VALIDATION.md,
59 GSUB lookups were reachable: 34 direct roots and 25 nested-only dependencies.
Its six GPOS lookups were direct roots. These numbers belong to that binary, not
every version of Noto Serif Bengali.

## Next engineering steps

1. Freeze the font hash and review the corpus in issue #3.
2. Define a versioned, typed profile IR that serializes required lookup content,
   flags, coverage/classes and positioning records in semantic order.
3. Reject every required construct outside that IR. Do not interpret this audit's
   lookup-type inventory as evidence that the interpreter is implemented.
4. Build a traceable Python model, compare it with a pinned HarfBuzz reference,
   then port validated rules into expl3. Reuse the native glyph-bank renderer.

References: Microsoft OpenType [common layout tables](https://learn.microsoft.com/en-us/typography/opentype/spec/chapter2),
[GSUB](https://learn.microsoft.com/en-us/typography/opentype/spec/gsub),
[GPOS](https://learn.microsoft.com/en-us/typography/opentype/spec/gpos), and
[GDEF](https://learn.microsoft.com/en-us/typography/opentype/spec/gdef).
