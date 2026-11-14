# Changelog

## Unreleased — CTAN preparation

- Copy and search in PDF viewers that ignore `/ActualText`, such as Overleaf's
  preview and Firefox's built-in viewer (PDF.js), now give real Bengali text
  instead of font codes. A new generated module, `bntex-native-tounicode.def`,
  gives each glyph its Unicode text. In those viewers, vowel signs drawn to the
  left of a consonant and reph still come out on the side where they are drawn.
  Viewers that read `/ActualText` keep the exact text. Checked with PDF.js 4.10.
- Installed MiKTeX packages now work: unzip `bntex.tds.zip` into a folder
  registered as a MiKTeX root. MiKTeX's pdfTeX cannot checksum files under
  `fonts/`, so on MiKTeX only, BnTeX finds them through MiKTeX's font search and
  checks every metric file against the checked shaping tables instead. Tested
  with MiKTeX 25.4 in a registered root.
- CTAN archive: no file is stored twice. `bntex-native-profile.tex` now inputs
  `bntex-default-profile.def`, and the browsing tree omits `source/bntex/data/`,
  which repeats `tex/`; the TDS archive inside it keeps everything.
- Release archives no longer depend on the build machine's line endings or zip
  settings. The Overleaf starter is byte-identical whether built on Windows or
  Linux; the TDS and CTAN archives also contain the compiled manual, whose PDF
  bytes depend on the TeX installation that builds it.

## 0.2.0-alpha — first public alpha (release candidate)

What document authors get:

- `\usepackage{bntex}`: write Bengali directly in pdfLaTeX, mixed with English,
  with no wrapper commands, preprocessing, shell escape or external programs.
- Real Noto Serif Bengali Bold for `\textbf`; `[synthetic-italic]` opts in to a
  declared slant for italic and emphasis. Headings, contents, footnotes,
  captions, tables, underline, `ulem`, colour, sizes and hyperref strings work.
- Three release archives: `bntex.tds.zip` for TeX Live, `bntex-overleaf-starter.zip`
  to upload as an Overleaf project (also usable with MiKTeX), and a CTAN-style
  candidate. They bundle the unmodified fonts under the SIL OFL 1.1.
- A word cache (`\jobname.bnc`) makes recompiles fast: on Overleaf a 5,000-word
  document went from 37.8 s to 2.5 s. `[no-word-cache]` disables it.
- Known limits: only the two bundled fonts; no true italic; no hyphenation
  inside Bengali words; installed MiKTeX trees are not supported (use the
  project-folder files); not yet on CTAN.

Release preparation: user-facing README (the developer README moved to
`docs/DEVELOPMENT.md`), Python tools versioned 0.2.0a1, an Overleaf starter
archive in the release build, and an Overleaf test record in `docs/reviews/`.

Detailed development notes for this release follow.

## Installable-distribution and authoring development notes

- Require a closed release inventory independently of editable manifest entries;
  reject omitted profiles, banks, notices, manuals and build sources.
- Add maintainer reproduction from shipped sources with exact manual, manifest
  and archive comparisons, without access to the development checkout.

- Public `bntex` defaults to automatic input and default-profile loading.
- Explicit `cached` option and `bntex-cached` retain legacy preparation; generated
  cached projects receive a labelled compatibility shim without source rewriting.
- Maintainer-only TDS/browsing archive assembly, asset inventory, checked font
  paths reused for rendering, and document-only relocation tests.
- Restricted input-read policy, real Overleaf, naming/rights and release approval
  are still pending. No fonts are added to the source distribution.
- Windows: the distribution builder and verifier compare POSIX-style relative
  paths, so assembly no longer reports a complete tree as incomplete.
- When no `$TEXMF...` root resolves, runtime assets are found by bare name beside
  the document (project upload) under the same pinned MD5 check. MiKTeX does not
  expand `$TEXMF...` roots and its input search does not reach `fonts/`, so a
  real MiKTeX TDS installation is still unresolved.
- Add `bntex-native-reuse`, loaded by `bntex` by default (`no-word-cache`
  disables it): constant-time glyph-run reuse within a compilation and across
  compilations through `\jobname.bnc`, keyed on the installation's profile
  loader MD5 with per-line MD5 checks. On Windows/MiKTeX a 4,984-word document
  went from 37–50 s to 2.8 s on recompilation, a 623-word one from 5.1 s to
  0.9 s; PDF page content is identical with the cache cold, warm or disabled.
  For automatic input, a cache hit skips the second UTF-8 decode in `\bnNative`.

- Add opt-in `bntex-auto`: literal Bengali in ordinary mixed text, commands,
  headings and PDF strings without per-passage wrappers.
- Add the exact Noto Serif Bengali Bold profile and NFSS weight selection.
  Shared substitutions are structurally checked; bold metrics/positioning are
  independent. Reuse keys include the full face identity.
- Add explicit synthetic-italic consent and standard decoration regressions.
  No genuine italic face, generic font support or Overleaf certification claimed.
- Record prior regular-specimen acceptance narrowly; new styles need review.
- The maintainer has activated #15/#25; the earlier deferral is superseded.

## Consolidated native development checkpoint

- Consolidate existing corpus, inventory, decoder, independent shaping model,
  native expl3 engine and document integration into main, preserving history.
- Add conservative indexed font-rule dispatch and integer dimension scaling;
  preserve original references, profile identity and fallback scan semantics.
- Retain optional bounded process-local memoization and declared-text PDF strings.
- Add a current README/contributor contract, preserve the original roadmap, and
  distinguish cached/native editing and deferred automatic routing.
- Add a PDF manual source, complete source-distribution manifest, mechanical
  preflight tests and a private release dry run. Pending acceptance blocks ready
  status. No font files, public release, CTAN/PyPI upload or version promotion.

## 0.1.0a2 — private bootstrap review

- Import the native-glyph cached pdfLaTeX backend and development documentation.
- Add source filename, line, Unicode-scalar column, excerpt and caret diagnostics.
- Reject invalid source UTF-8 and unprepared explicit styles with source locations.
- Add deterministic GSUB/GPOS dependency-closure audit, including extensions,
  filtering/GDEF requirements, original wire formats and cycle reporting.
- Add synthetic and real-font regression tests; native shaping remains unimplemented.

## 0.1.0a1 — initial local prototype

HarfBuzz preparation, static TrueType glyph banks, pdfLaTeX rendering, Unicode
ActualText, integrity safeguards, documentation and local integration tests.
