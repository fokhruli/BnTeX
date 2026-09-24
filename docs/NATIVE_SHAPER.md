# Road to a genuinely pdfLaTeX-only Bengali package

**Status: design specification; no native Bengali shaper is implemented.**
The existing output backend is the working base. Version 0.1.0a2 adds structural
lookup auditing in `src/bntex/profile.py`; see PROFILE_AUDIT.md. That audit is not
a font-profile compiler or interpreter. Issues #3–#6 track the remaining core work.

## Objective and first supported profile

After installing one supported font profile, a user can type a previously unseen
Bengali word inside `\bn{...}` and compile with `pdflatex -no-shell-escape`. No
per-document Python step, cached vocabulary, cloud request or background process
is allowed in the acceptance test. Start with one exact static Noto Serif Bengali
font version and upright text. Add other fonts only after a profile compiler can
prove it supports all required lookups for them.

A one-time **font-profile compiler** is compatible with this goal. It turns a
licensed font and versioned Unicode data into TeX-readable tables plus font
banks. Users of a published supported profile should not need to run that
compiler. Redistribution/licensing of each profile must be settled independently.

## A. Establish an intermediate representation and oracle first

Keep the glyph-run schema documented in ARCHITECTURE. Add trace records for:
original code points; normalized working sequence; syllable boundaries; classes;
base selection; feature masks; glyph sequence after each lookup phase; positions;
cluster provenance and unsafe-to-break flags. Preserve the original logical text
separately for PDF semantics. Do not derive the Unicode string from rendered GIDs.

Implement a Python **model of the proposed native algorithm** first. Compare it
with pinned HarfBuzz output before porting it into expl3. This isolates language
logic from TeX token/expansion bugs. HarfBuzz is the behavior reference for the
chosen font/profile, not proof that every orthographic tradition is correct.

## B. Build a closed, inspectable font-profile compiler

Existing audit and proposed implementation files:

```
src/bntex/profile.py        # implemented structural audit, not a compiler
src/bntex/font_ir.py        # proposed typed profile serialization
src/bntex/native_model.py   # proposed Python model of the macro algorithm
tex/latex/bntex/bntex-utf8.def
tex/latex/bntex/bntex-syllables.def
tex/latex/bntex/bntex-shape.def
tex/latex/bntex/bntex-position.def
tex/latex/bntex/profiles/<font-sha>.def
```

`tools/font_report.py` inventories actual GSUB/GPOS lookup types, feature tags and
script/language systems. `python -m bntex profile` adds transitive structural
closure. Use those reports to design the first profile; do not assume every
Bengali font uses identical tables. A tag such as `half` or `rphf` is not an
algorithm, and the same feature may contain several lookup types.

Compile relevant cmap mappings; font metrics; script/language feature order;
GSUB substitutions/context rules; GPOS positioning; GDEF classes/attachment
filters; and dynamic character classifications used by the Indic model. Decide
explicitly whether device adjustments, variation tables and mark filtering sets
are supported. Reject an unsupported required construct at profile build time.
No silent lookup skipping is acceptable.

For the first font, list the required GSUB/GPOS subtable formats from its actual
report, then implement only a **closed** set that fully covers that profile.
Do not claim arbitrary-font support from one successful font. Font modification
or instancing can alter GIDs and metrics; regenerate every dependent table.

## C. UTF-8 front end in pdfTeX

Inside a controlled literal-text command, decode UTF-8 byte tokens into code-point
integers. Validate continuation bytes and reject invalid/overlong encodings,
surrogates and out-of-range scalars. Preserve original bytes and code-point-to-byte
mapping. Explore expl3 string conversion facilities, but establish tests for their
behavior under pdfTeX instead of assuming Unicode-engine semantics.

Avoid activating an entire Bengali Unicode block globally in the first iteration.
That can interact with moving arguments, verbatim, URLs and other packages.
Start with `\bn`, then a dedicated paragraph environment, then an opt-in global
script dispatcher only after the front-end contract is stable.

## D. Script analysis and glyph substitution

The conceptual pipeline is:

```
decode(original) -> working normalization -> script itemization
 -> classify characters -> find orthographic syllables
 -> determine font-dependent forms and base
 -> initial reordering -> ordered GSUB stages with masks
 -> final reordering -> GPOS -> positioned glyph IR
```

Unicode Indic properties provide character categories; the Bengali shaping model
provides more than a generic Unicode grapheme segmenter. Font-derived dynamic
properties also affect reordering [R2]. Treat malformed sequences explicitly,
including isolated matras, virama tails, nukta, repeated combining marks, and
ZWJ/ZWNJ. Do not erase join controls to simplify tests. Preserve original strings
when equivalent normalized working sequences share shaped output [R3].

Reph, pre-base vowel signs, split vowel signs and consonant forms need tests at
each intermediate stage. Port a documented Bengali-specific pipeline, not an
entire cross-script shaping engine, and avoid claiming feature completeness
until differential tests cover its actual inputs and font tables.

## E. Positioning and output

Implement required advance and offset adjustments, mark-to-base/ligature/mark
attachments, and GDEF filtering according to the supported profile. Track pen
positions separately from glyph drawing offsets. Reuse the current native font
bank and word-box renderer. Keep vertical extents based on positioned ink bounds.

First use a word as the unit of shaping/output to keep line breaking stable.
Later use legal Unicode line-break opportunities and language-appropriate
hyphenation, reshaping affected fragments when necessary. **A HarfBuzz cluster
boundary is not by itself permission to break a line.** Arabic-style assumptions
or Latin letter-discretionary assumptions must not be imported without analysis.

## F. Differential acceptance gates

1. Exact glyph IDs and cluster provenance for the pinned font/profile on curated
   and generated corpora; normalized-equivalence cases documented.
2. Advances/offsets match the chosen HarfBuzz version to the expected integer
   font-unit precision, with explicit tolerances only where rounding occurs.
3. Native pdfLaTeX and cache-backed output have matching measured word geometry.
4. Native-speaker review of curated real words and uncommon conjuncts; record
   reviewer judgments rather than relying on a raster similarity score alone.
5. A fresh, previously unseen valid word compiles **after Python and all word
   caches are removed**, with shell execution disabled. This is the decisive
   distinction from the current prototype.
6. No unsupported font table or malformed input silently produces approximate
   typography. Diagnostics identify the stage, sequence and font fingerprint.
7. Long random/fuzz inputs are bounded and do not exceed documented resource
   limits or crash the TeX process. Complexity and cache growth are measured.

## G. Where optimization belongs

Correctness precedes speed. Avoid repeatedly expanding large token lists for each
lookup. Use integer-indexed tables, compact rule dispatch, bounded worklists, and
memoization keyed by complete shaping identity. A trie of previously seen words
is a performance optimization, not a replacement for arbitrary-input shaping.

Assess whether a restricted fixed-font macro model is maintainable before
building a generic OpenType interpreter in expl3. If generic support becomes too
costly, publish a clearly scoped fixed-profile native package plus the general
cached backend rather than weakening the correctness claim.

## What not to promise

A complete dictionary of Bengali words cannot cover arbitrary new text. A finite
list of common conjuncts cannot replace contextual shaping for all fonts. A
font's GSUB data alone do not contain every script-engine reordering decision.
Turning glyphs into paths does not solve searchable text or accessibility. Passing
one font and one PDF viewer does not establish universal compatibility.

References: [R2–R5] in REFERENCES.md. This document proposes an implementation
program; it does not assert that a full native implementation is already proven.
