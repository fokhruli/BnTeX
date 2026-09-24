# Issue #5: typed fixed-font rules and an independent Bengali shaping model

## Status and boundary

Implemented in Python: a closed font-profile compiler and a traceable Bengali
`bng2` shaping model. The shape operation consumes either Unicode text or issue
#4's decoded scalars/byte mappings, and returns the existing seven-field glyph IR.
It does **not** call HarfBuzz, load a font, use FontTools, read a word dictionary,
or launch an external program. Python itself is still the development runtime.

Not implemented here: the expl3 shaping/positioning port (#6), a replacement for
`\bn`, or preprocessing-free pdfLaTeX compilation. Existing renderer, preparer,
font-bank sources, word caches, and frozen corpus files are unchanged. This is
not generic OpenType support or an arbitrary-font claim.

## Reproduce

Run from the current feature checkout, with dependencies from README installed.
Use the exact static font below. No font files are supplied by BnTeX.

```bash
PYTHONPATH=src python -m bntex.native compile \
  --font /usr/share/fonts/truetype/noto/NotoSerifBengali-Regular.ttf \
  --out build/native-profile.json

# The profile is built without any document or corpus input.
# Reuse it for previously unseen text; shape needs only stdlib Python + BnTeX.
PYTHONPATH=src python -m bntex.native shape \
  --profile build/native-profile.json --text 'আত্মবিশ্বাস'

PYTHONPATH=src python -m bntex.native shape \
  --profile build/native-profile.json --text 'কর্মে' --trace \
  --out build/native-trace.json

PYTHONPATH=src python -m bntex.native check \
  --profile build/native-profile.json \
  --corpus corpus/bengali-v1.json \
  --oracle corpus/oracles/noto-serif-bengali-regular-hb10.2.0.json
```

Output paths are create-only: choose a new path rather than overwriting input or
previous evidence. A compiled profile cannot be pointed at a different font.

The check command compares shaped cases, naming the original corpus's ten input
rejection cases separately as **not compared**. It does not execute an oracle
engine, regenerate fixtures, insert expected glyphs into the model, or turn
matching results into human approvals. The original source/font/configuration
identities are checked first. A mismatch returns nonzero.

The supplementary corpus uses the existing inventory tools to expand its frozen
reference before the same `check` command:

```bash
python -m bntex.inventory build \
  --inventory corpus/inventories/user-alphabet-v1.json \
  --out build/user-forms.json
python -m bntex.inventory unpack-oracle \
  --oracle corpus/oracles/user-forms-noto-hb10.2.0.json.gz \
  --out build/user-forms-oracle.json
python -m bntex.native check --profile build/native-profile.json \
  --corpus build/user-forms.json --oracle build/user-forms-oracle.json
```

## Identity

Font SHA-256:
`32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef`

ABI-1 compiled profile SHA-256:
`f6294540099a3b6f622f2cdd9e863050390f75fd0576495d5a2316903f8cfb42`

The shape runtime verifies the compiled-rule digest, not merely a caller's claim
about its font hash. Rule edits, even structurally valid ones, require an explicit
version/profile review. This detects accidental or unapproved profile changes;
it is not a signed release or protection against someone editing the program.

The profile has 640 glyph metrics, 173 cmap entries, **54 reachable GSUB lookups**
(29 direct roots plus 25 nested dependencies), and six GPOS lookups. This is the
selected **bng2 / default-language** closure, not the earlier 59-lookup union of
legacy `beng` and `bng2` systems. The compiled JSON is 121,814 bytes.

## Data structures and compiler

`native_profile.py` owns frozen, tagged dataclasses and strict JSON decoding:

| Record | Preserved data |
| --- | --- |
| `FontProfile` | ABI, exact font identity, selected system, cmap, advances, ink bounds and GDEF arrays |
| `Single`, `Multiple`, `Ligature` | Glyph mappings and ordered component rules; no word strings |
| `Chain` | Format-3 input/backtrack/lookahead coverage and ordered nested lookup actions |
| `PairGlyph`, `PairClass` | Pair adjustments including value presence and default class zero |
| `MarkBase`, `MarkMark` | Static anchors, mark classes and null base anchors |
| `Lookup`, `Feature` | Stable original indices, flags, filtering sets and selected feature references |

Extraction traverses nested dependencies. Original ligature/subtable priority is
preserved; this is not longest-word matching. Context coverage may contain
redundant source entries and is not confused with an indexed mapping.

Supported required font structures: GSUB single/multiple/ligature and chaining
context format 3; GPOS pair formats 1/2, mark-to-base and mark-to-mark format 1;
static format-1 anchors; GDEF class/mark-attachment/filtering data. Extension
wrappers are checked and flattened. Unknown lookup types, inappropriate table
kinds, cycles/depth, invalid references, reserved flags, empty substitutions,
variation/device adjustments and nonstatic anchors are errors.

The initial public compiler rejects any different font binary **before parsing**.
It is a fixed-profile compiler, not a claim that all fonts containing those
lookup types can be handled. Output contains metrics/rules, not outlines or a
redistributed TTF. Font rights remain a separate concern.

## Executable model

`native_model.py` performs working normalization, character classification,
longest-prefix orthographic segmentation, dynamic font-form detection, base
selection, reph/matra reordering, masks and phase scheduling.

`native_layout.py` executes ordered lookups on mutable glyph records. Contextual
matches retain target identities when nested substitutions change run length.
Ligature/component provenance prevents unrelated marks from forming a ligature.
GSUB input and context have different join-control skipping semantics. GPOS uses
class-zero pair lookup, GDEF filters, parent-relative attachment and final pen
positions. Default-ignorable glyphs retain source provenance but have zero output
advance. Source text is never reconstructed from glyph IDs.

The order is:

```text
DecodedInput (immutable original scalars / bytes)
  -> normalized working sequence and script classes
  -> orthographic syllables and broken-sequence policy
  -> dynamic font forms, base and initial reordering
  -> ordered nukt/akhn/rphf/blwf/half/pstf/cjct stages
  -> final reordering and init masks
  -> presentation GSUB with default-feature/context semantics
  -> pair and mark GPOS, attachment resolution
  -> original-source glyph clusters, advances, offsets and flags
```

`ShapeResult.glyphs` has `(gid, cluster, x_advance, y_advance, x_offset,
y_offset, flags)` in integer font units; clusters are original UTF-8 **byte**
offsets. Flags are comparison metadata, not permission to break words. Trace
snapshots show source scalars, working glyphs, classes, syllables, positions,
feature masks, substitutions and positioning stages. Normal runs return no trace.

This is source-informed, independently executing code, not a newly invented
shaping theory or a second independent typography authority. See
`THIRD-PARTY-NOTICES.md` for the pinned HarfBuzz adaptation and attribution.

## Consuming issue #4 output

The Python API accepts exactly the arrays the TeX decoder exposes:

```python
from bntex.native_profile import load_profile
from bntex.native_model import NativeShaper, DecodedInput

model = NativeShaper(load_profile('build/native-profile.json'))
source = DecodedInput(
    scalars=(2453, 2509, 2487),
    byte_offsets=(0, 3, 6),
    byte_lengths=(3, 3, 3),
    utf8_hex='E0A695E0A78DE0A6B7',
)
run = model.shape_decoded(source)  # logical input: KA + VIRAMA + SSA
```

`--decoded path.json` accepts the same four fields as arrays/hex. Every scalar,
offset and byte length is checked against the original byte string. This is a
testable interface for the later port, **not** a Python subprocess called by TeX.
The integration test runs the actual native decoder under pdfLaTeX, reads its
ASCII diagnostics in the test harness, and passes those values to the model.

## Input domain and explicit exclusions

The first model handles the pinned font's Bengali-block characters, danda,
double danda, join controls, supported ASCII punctuation/digits, NBSP and dotted
circle. Missing cmap entries and other scripts/Latin letters fail explicitly;
keep English itemization outside this experimental Bengali run. Success does not
certify Bengali spelling, grammar, or Assamese-language support.

Broken orthographic sequences are rejected by default. `--allow-broken` enables
specified diagnostic dotted-circle behavior so isolated supplied signs and the
existing malformed probes can be compared. **ZWJ inside a broken or standalone
placeholder/dotted-circle cluster remains explicitly unsupported**, including
cases such as `U+200D U+09C2`. This boundary was added after generated malformed
probes exposed a positioning difference. Ordinary consonant + ZWJ/ZWNJ sequences
are not removed or replaced and have dedicated exact comparisons.

Bounds: 4,096 source bytes per call, 64 working scalars per orthographic syllable,
8 MiB profile JSON, 32 contextual recursion/dependency depth, 8,192 intermediate
glyphs, two million counted layout operations. Trace recording allows at most
256 events and 65,536 glyph-snapshot cells. These are engineering ceilings, not a
proof of constant time or a security sandbox for arbitrary Python/TeX. File and
output limits are enforced without truncating successful output.

## Validation and next gate

See `NATIVE-MODEL-VALIDATION.md` for executed evidence and CI scope. Existing
reviewed corpus/oracle data are immutable. Native model output matching the
reviewed glyph IR is strong regression evidence, but not a new human review of
all generated strings. Do not describe generated probes as real dictionary words.

Next: review this independent model, then port its supported stages to expl3
(#6), reusing the tested decoder and glyph renderer. Only that later no-cache,
no-Python, no-shell pdfLaTeX test establishes the user's final authoring workflow.

Primary references:
- https://learn.microsoft.com/en-us/typography/script-development/bengali
- https://learn.microsoft.com/en-us/typography/opentype/spec/gsub
- https://learn.microsoft.com/en-us/typography/opentype/spec/gpos
- https://www.unicode.org/versions/Unicode17.0.0/core-spec/chapter-12/
- https://github.com/harfbuzz/harfbuzz/tree/7b27c8edd46c674e01dd226fa9e1aa7549f5c436
