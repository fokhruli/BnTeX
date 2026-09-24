# Learning path: from LaTeX user to Bengali package author

Use the primary references in REFERENCES.md alongside these exercises. Each step
should produce a small checkable result, not only notes about a specification.

## 1. TeX layout and expansion

Learn tokens, category codes, expansion, grouping, boxes, glue, kerns, dimensions,
paragraph breaking, protected commands, moving arguments and auxiliary files.
Read the LaTeX class/package author guide [R11] and the pdfTeX font/PDF sections
[R1]. Study TeX's documented source or a lawfully obtained TeXbook for fundamentals.

Exercise: place two glyphs at controlled offsets inside an hbox with explicit
width/height/depth. Change font size/color and print the measured dimensions.
Distinguish advance width from visible ink bounds and overhang. Reproduce the
existing renderer's word geometry before modifying it.

## 2. LaTeX package interfaces and expl3

Study ProvidesPackage, option handling, NFSS family/series/shape, protected document
commands, expl3 strings/token lists/sequences/properties/integers and diagnostics.
Use `texdoc clsguide`, `texdoc interface3` and l3build [R11,R12].

Exercise: implement an explicit style registry and test body text, headings,
footnotes and TOC use. Keep the surrounding English font unchanged. Understand
why a protected typesetting command is not itself a Unicode PDF bookmark string.

## 3. Bengali Unicode and orthography

Read Unicode's Bengali section, normalization and join controls [R3]. Distinguish
code point, UTF-8 byte, grapheme cluster, orthographic syllable, glyph and ligature.
Study virama, nukta, reph, ya-/ra-phala and pre-base/split vowel signs.

Exercise: inspect code points and UTF-8 bytes for `কি`, `কো`, `ক্ষ`, `কর্ম`, `ড়`,
`ক্\u200dষ` and `ক্\u200cষ` (interpret the escapes as join controls in the test).
Compare logical order, NFC/NFD and displayed output. Preserve original source
bytes; do not strip invisible join controls to make a test easier. Classify
malformed mark sequences and mark cases needing human judgment.

## 4. Bengali shaping and OpenType

Read the Bengali shaping model [R2], HarfBuzz concepts/clusters [R4,R5] and the
OpenType common-layout, GSUB, GPOS and GDEF specifications linked below. Learn
cmap/head/hmtx/glyf, script/language systems, lookup order, contextual dependencies,
feature masks, filtering and attachments. GSUB tables alone are not an Indic
script-reordering algorithm.

Exercise:

```bash
python -m bntex shape --font /path/to/font.ttf --text 'স্বাস্থ্য'
python -m bntex profile --font /path/to/font.ttf > profile.json
```

Relate each GID, advance, offset and UTF-8 byte cluster to the word. Compare two
font faces. Find a nested-only lookup in the audit and trace the contextual lookup
that calls it. Explain why the report's union of features is not execution order.

## 5. Font metrics and pdfTeX embedding

Study TFM metrics, encoding vectors, glyph IDs, font maps, embedded outlines and
positioning [R1,R13]. A ligature glyph may have no Unicode cmap entry; several
256-slot font instances can expose a larger glyph set.

Exercise: inspect generated .enc/.pl/.tfm banks, run `pdffonts` and `pdftotext`,
and compare widths using tools/compare_reference.py. Change a generated asset
and confirm integrity checks reject it. Never commit local font binaries.

## 6. Validation of typography

Compilation, glyph choice, geometric positioning, natural typography, original
text extraction and structural accessibility are different tests. Read Unicode
line breaking [R14] and HarfBuzz cluster semantics [R4].

Exercise: curate the issue #3 corpus with category, original Unicode, font hash,
reference run and separate human-review fields. Include normalized equivalents,
join controls and intentional malformed inputs. Corrupt an expected GID and
ensure differential tests fail. A raster similarity score alone cannot establish
correct Unicode or natural typography.

## 7. Native shaping implementation

Follow NATIVE_SHAPER.md and issues #4–#6. Develop a typed font-profile IR and a
traceable independent Python model before porting it into expl3. Test intermediate
classification, syllables, reordering, masked GSUB and GPOS, not just final words.

Exercise: implement one bounded construct with tests against a pinned oracle;
then port that same construct into TeX. The final milestone is an unseen word in
a cache-free pdfLaTeX project, not an expanded cached vocabulary.

## 8. Distribution and maintenance

Study CTAN upload/TDS guidance [R15,R16], l3build [R12], and actual dependency/font
licenses [R17]. Learn reproducible builds, release archives, support matrices,
regression fixtures, issue triage and contributor review.

Exercise: build a source-only archive, install it on a clean environment, reproduce
the example, and record missing dependencies. Include manual PDF and source for a
release. Do not infer CTAN/TeX Live/Overleaf availability from a successful upload.

## OpenType reference additions

- https://learn.microsoft.com/en-us/typography/opentype/spec/chapter2
- https://learn.microsoft.com/en-us/typography/opentype/spec/gsub
- https://learn.microsoft.com/en-us/typography/opentype/spec/gpos
- https://learn.microsoft.com/en-us/typography/opentype/spec/gdef
