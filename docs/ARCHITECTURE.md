# Architecture and feasibility

## 1. The actual engineering problem

The goal is not simply to make Bengali code points acceptable input. The pipeline
must transform logical Unicode into font-specific glyphs, positions, legal
break opportunities, and recoverable PDF text. Bengali requires syllable analysis,
reordering, GSUB substitutions and GPOS positioning [R2, R3]. pdfTeX can embed and
use TrueType fonts, but its traditional font interface does not run that shaping
pipeline for you [R1]. A package can supply the missing work without modifying the
engine. That work must happen either before compilation or in TeX macros.

**Two contracts must remain distinct:**

A. `prepare(document, fonts)` followed by `pdflatex(document)` — implemented.

B. `install(package, supported fonts)` once, then type arbitrary Bengali and run
`pdflatex(document)` only — target, not implemented.

Contract B permits *font-installation-time* compilation of font tables. It does
not permit requiring every document's vocabulary to be prepared in advance.

## 2. Current data flow

```text
                     OFFLINE PREPARATION (local Python)
 .tex with literal Bengali ──→ conservative span scanner ──→ unique words
 user-owned static TTF ──────→ HarfBuzz ───────────────────→ glyph runs
             │                                            │
             └──────── FontTools metrics + exact font ID ──┤
                                                          ↓
                         TTF + 8-bit .enc banks + .tfm + ASCII word cache
                                                          │
                     FINAL COMPILATION (pdfLaTeX, no shell)
 original .tex ──→ \bn ──→ cache lookup ──→ native positioned glyph word boxes
                                                  │
                         ordinary interword glue ─┴─→ TeX line/page breaking
                                                          ↓
                                PDF with embedded font glyphs + ActualText
```

The reusable boundary is the **glyph-run representation**. A future TeX-native
shaper can emit the same representation and reuse the renderer. The current
cache is an oracle-backed proof of the font/output layer, not a substitute for
that future shaper.

## 3. Glyph-run representation

For a font F with units-per-em U, HarfBuzz returns a sequence

`G_i = (gid_i, cluster_i, ax_i, ay_i, dx_i, dy_i, flags_i)`.

All positions are in font units. For the horizontal profile, `ay_i = 0`.
`cluster_i` is a UTF-8 **byte** offset in this adapter, not a Python character
index, a word index, or an automatically legal line-break point [R4].

At point size s, with pen `p_0 = 0`, the renderer uses:

```
X_i = s * (p_i + dx_i) / U
Y_i = s * dy_i / U
p_(i+1) = p_i + ax_i
word_width = s * sum_i(ax_i) / U
```

TeX uses points (`pt`), not PDF big points (`bp`), for these dimensions. The
compiler performs the PDF unit conversion. Do not introduce a second conversion.
The word height/depth come from the union of each positioned glyph's actual ink
bounds. Advance width and ink bounding box are different quantities: marks may
extend left/right of the advance.

The word is placed in an hbox of exactly the advance width. Every glyph is a
zero-width positioned overlay using `\rlap`, `\kern` and `\raise`, followed by
explicit word geometry. Therefore TFM rounding does not determine the shaped
word advance. Nine decimal digits in em coordinates are used in the cache;
TeX ultimately rounds dimensions to scaled points.

## 4. Why font banks solve the 8-bit interface

A traditional font instance has 256 character slots, but a document may use
multiple such instances. For glyph ID g, this implementation uses

```
bank(g) = floor(g / 256)
slot(g) = g mod 256
```

An encoding entry `/indexG` maps that slot to the actual TrueType glyph index.
Only required banks/slots are generated. The exact original TTF is copied,
not converted to outlines or renamed/modified internally. `pltotf` builds TFM
metrics from deterministic PL text; `\pdfmapline` registers each encoding/font.
This allows ligature glyphs without Unicode cmap entries to be addressed.

The font hash is part of every bank name. Swapping a font file while keeping
old GIDs can silently render unrelated glyphs; asset checks reject that mismatch.
Multiple banks do not guarantee unlimited practical size: TeX font/memory limits
and PDF duplication must still be profiled on book-length documents.

## 5. Cache identity and provenance

The manifest stores SHA-256 of source files, exact original fonts, and generated
assets; BnTeX/FontTools/HarfBuzz versions; script `Beng`; language `bn`; default
features; units-per-em; glyph runs; original strings and their NFC equivalents.
Original text is **not replaced with NFC** before hashing or ActualText generation.
Equivalent input encodings can be shaped identically while remaining distinct
source/cache keys. That preserves copy/paste fidelity to the original authoring.

The lookup uses MD5(original UTF-8 bytes) plus style because pdfTeX exposes a
matching primitive. This is a lookup convenience, **not cryptographic
authentication**. Runtime asset MD5 checks detect accidental changes, not a
malicious coordinated rewrite. Python verification uses SHA-256, but the manifest
itself is unsigned. A signed release would need a separate trust mechanism.

A future cache format must include variation axes, feature values, language,
shaper version, font version and renderer ABI in its full identity. This snapshot
supports one fixed shaping configuration and one cache per document.

## 6. Unicode text in the PDF

Glyph order can differ from Unicode order; a ligature can represent multiple
characters, and a glyph can have different contextual meanings. A naive GID →
Unicode map is therefore insufficient for general reconstruction. This prototype
wraps each word's content in PDF marked content with a UTF-16BE `/ActualText`
string in original logical order. Poppler extraction is tested.

This does **not** create a structural tagged-PDF tree, accessible headings,
reading order across arbitrary columns, correct bookmarks, or PDF/UA compliance.
`hyperref` strings and PDF tagging require explicit separate work. Viewer search
and selection behavior must be checked in several viewers; one extractor is not
all PDF readers. Do not silently advertise accessibility as completed.

## 7. Paragraph and TeX semantics

The initial safe boundary is a whitespace-delimited word. Normal TeX glue between
word hboxes permits wrapping and ordinary justification through spaces. No break
is inserted within a word, syllable or cluster. This sacrifices hyphenation and
fine-grained punctuation rules but avoids corrupting connected forms.

The scanner is intentionally **not a complete TeX parser**. It recognizes literal
spans, skips common comments/verbatim uses, and rejects nested commands within a
span. It does not expand macros, run conditionals, follow included files, infer
custom category codes, or discover text generated by bibliography/index tools.
Pass all relevant source `.tex` files explicitly with repeated `--source` options.
They currently need distinct basenames and already compatible relative paths.

Color and font size are inherited; regular/bold are resolved at execution time.
All prepared styles cache every source word, since a static scanner cannot
reliably determine the surrounding font context. Sans-serif inheritance, italic,
math style sizes, heading PDF strings and global language switches need separate
NFSS/LaTeX integration. A Bengali text span is text, not a math alphabet.

## 8. Alternative architectures and decision

| Architecture | Benefit | Cost / limitation | Decision |
|---|---|---|---|
| Offline shaping + native glyphs | Modern font shaping; final compile needs no external program | New vocabulary requires preparation | Implemented first |
| TeX-native script rules + compiled font tables | Arbitrary new text with pdfLaTeX alone | Substantial shaping/compiler work; font compatibility needs rigorous gates | Main next milestone |
| Runtime external HarfBuzz helper | Easier full shaping reuse while editing | External executable/runtime and safe invocation must be available | Optional local developer mode, not default |
| Pre-rendered word images/PDFs | Fast visual proof | Poor font/text semantics and usually weak editing/line-break integration | Not the package backend |
| Xe/Lua with established language packages | Reference typography; useful baseline | Does not meet the user's chosen pdfLaTeX engine requirement | Test oracle, not proposed replacement |

Do not copy a list of conjuncts into `\DeclareUnicodeCharacter` and call that a
shaper. Character decoding, script reordering, font-dependent substitutions and
mark positioning are separate responsibilities.

References: identifiers resolve in [REFERENCES.md](REFERENCES.md).
