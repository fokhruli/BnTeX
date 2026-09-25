# Development roadmap and acceptance gates

The repository is private at `fokhruli/BnTeX`. Bootstrap changes are reviewed on
`feat/bootstrap-profile-audit`; main is not the development scratch branch.
This roadmap is dependency-ordered, not a promised calendar schedule.

## Product contract

Current: prepare literal Unicode Bengali with HarfBuzz, then compile native font
glyphs with pdfLaTeX and shell execution disabled. Target: install a supported
font profile once, type unseen Bengali words, and compile with pdfLaTeX alone.
A per-document word cache does not satisfy the target. Preserve the current
glyph-run interface so both backends can share rendering and PDF text semantics.

## Maintained issue map

| Issue | Priority | Deliverable | Status at bootstrap |
|---|---|---|---|
| #1 | P0 | Source-located preparation errors | Implemented in review branch |
| #2 | P0 | Transitive structural GSUB/GPOS audit | Implemented in review branch |
| #3 | P0 | Pinned corpus, oracle and native-speaker review | Open |
| #4 | P0 | Strict pdfTeX UTF-8 decoder | Open |
| #5 | P0 | Typed font-profile IR and independent Python model | Open; depends on #2 and #3 |
| #6 | P0 | expl3 shaper and unseen-word gate | Open; depends on #3–#5 |
| #7 | P1 | Overleaf, integration and long-document tests | Open |
| #8 | P1 | Reviewed CTAN release preparation | Open; publication separately authorized |

Each issue contains its scope, dependencies and acceptance tests. Issues #1/#2
should close only when their PR is merged. An issue's existence is not evidence
that its implementation or validation is complete.

## Gate A — stable cached renderer

Implemented: static TrueType glyph banks, deterministic HarfBuzz preparation,
positioned native glyphs, original-order ActualText, font identity/integrity checks,
source errors, and regression tests. Run with integration prerequisites required.
Maintain the original Unicode and the exact font SHA-256. No bitmap/path fallback.

Next: second-user reproduction and explicit multi-source manifest; source
filename/line errors already landed in the bootstrap review. Do not replace the
literal scanner with a claim to parse arbitrary TeX. Generated bibliography/index
text will need an explicit dictionary/manifest interface or separately designed
safe runtime collection. Do not execute arbitrary TeX during preparation.

Acceptance: a clean checkout plus installed dependencies reproduces the example;
a missing word/font/style is an error, never silent approximate shaping.

## Gate B — close the fixed-font requirement set

The implemented audit follows script/language features to root lookups and their
contextual dependencies, including extensions, filtering requirements and wire
formats. It reports cycles and unsupported advanced constructs. It is not a
serializer, interpreter or complete font validator; native support is always false.

Select one exact static font hash. Build a versioned typed IR for required cmap,
metrics, GSUB/GPOS/GDEF structures and filtering/lookup order. Explicitly reject
required constructs that cannot be represented. Never infer runtime support from
lookup-type counts alone. See PROFILE_AUDIT.md and issue #5.

Acceptance: every required construct is representable and tested or rejected;
no silent skipping. No font binary is committed or implicitly licensed by an audit.

## Gate C — reviewed corpus and independent algorithm

Curate common/uncommon conjuncts, pre-base/split matras, reph, phalas, nukta,
candrabindu, digits/danda, join controls, normalized equivalents and malformed
sequences. Store original strings, exact tool/font/configuration versions and
reference glyph runs. Record human review separately from generated oracle data.

Implement script classification, syllable analysis, dynamic font-dependent forms,
base selection, reordering, feature masks, substitutions and positioning first in
an inspectable Python model. HarfBuzz produces the reference, not the model's own
result. Match GIDs, byte-cluster provenance and integer font-unit positions for the
declared domain. See NATIVE_SHAPER.md, issues #3 and #5.

Acceptance: differential tests plus native-speaker review pass for the declared
scope. Preserve original logical Unicode even when the working sequence normalizes.

## Gate D — pdfLaTeX-only unseen-word test

Port the validated model incrementally into expl3, using the strict UTF-8 decoder
from #4 and the existing native glyph renderer. Validate invalid continuation
bytes, overlong encodings, surrogates, truncation and out-of-range scalars. Start
with an explicit command, not globally active Bengali characters.

Decisive test: install the supported font profile; remove Python and all word
caches; type previously unseen valid words; compile with `pdflatex -no-shell-escape`.
The output must match the reference, without a subprocess, network request, Lua
execution or a hidden vocabulary dictionary. Memoization is only an optimization.

Bound resource use for long/malformed inputs. Profile time/memory before expanding
to generic fonts. A fixed-font package with an honest scope is a valid result;
a finite dictionary mislabeled as a shaper is not.

## Gate E — authoring integration and typography

Add paragraph support, optional script switching, real family/weight selection,
headings/TOC/captions/footnotes/tables, math-text sizing, bibliography/index handling
and Unicode bookmarks in small tested changes. Test article/report/book, TikZ,
Beamer and publisher classes individually. Never silently change Latin typography.

Benchmark 1/10/100 pages, unique vocabulary versus repeated words, preparation and
compilation time, memory, font count and PDF size. Perform an actual clean-room
Overleaf browser import with pdfLaTeX. Local no-shell success is not that test.

Add legal punctuation/line-break opportunities only with Unicode and language
review. A HarfBuzz cluster boundary is not permission to break a line. Keep breaks
inside words disabled until a justified policy and reshaping strategy exist.

## Gate F — release and long-term maintenance

Test text extraction/search in multiple PDF engines. Treat bookmarks, structural
tagging, reading order and PDF/UA as separate targets, not consequences of
ActualText. Audit source/cache trust, malformed fonts, giant inputs and checksums.

Finalize supported versions, license/dependency inventory, manual PDF and source,
installation/TDS layout, changelog, source commit and actual CI evidence. Obtain
second-user installation review. Follow CTAN.md; a useful cached alpha can precede
the native shaper only with an explicit preparation requirement.

No public release, CTAN/PyPI upload or repository visibility change is authorized
by this roadmap. These require a separate maintainer decision.

## First coding-agent session after bootstrap

Read AGENTS.md and the architecture/native-shaper/audit documents. Run the current
suite and demo unchanged, recording versions and results. Start issue #3's corpus
schema and one reproducible oracle fixture with human-review status unset. Add a
failing test for corrupted provenance before implementing serialization. Do not
start by rewriting the renderer or globally activating Unicode input.
