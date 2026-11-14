# BnTeX 0.2.1-alpha — Bengali in pdfLaTeX

Write `\usepackage{bntex}` and type ordinary Bengali and English text in a
pdfLaTeX document. Bold uses the real Noto Serif Bengali Bold face.
`[synthetic-italic]` explicitly enables a declared slant for italic and
emphasis; the fonts have no true italic. Underline, colour and sizes use normal
LaTeX commands. Compilation needs no profile loader, word preparation, Python,
network access or shell escape. See `bntex-manual.pdf` and `bntex-example.tex`.

This is an alpha release. It supports only the bundled Noto Serif Bengali
Regular and Bold fonts.

Home page and source: <https://github.com/fokhruli/BnTeX>. Please report
problems at <https://github.com/fokhruli/BnTeX/issues>.

## Installing

- **TeX Live:** unzip `bntex.tds.zip` into `TEXMFHOME` (see
  `kpsewhich -var-value TEXMFHOME`) or another TEXMF tree.
- **MiKTeX:** unzip `bntex.tds.zip` into a folder of your own and register it
  as a root, in MiKTeX Console (*Settings → Directories*) or with
  `initexmf --register-root=<folder>`. In a root that is already registered,
  run `initexmf --update-fndb` after unzipping.
- **Overleaf or any single project:** place the runtime files (`tex/latex/bntex/*`
  and `fonts/*/*/bntex/*`) in the document's own folder. The release's
  `bntex-overleaf-starter.zip` is such a project, ready to upload to Overleaf;
  the same layout works locally with TeX Live or MiKTeX.

The resolver first looks for each runtime asset in the standard TEXMF roots. If
none resolves, it checks the asset by bare name, which finds copies beside the
document, against the same pinned MD5. MiKTeX's pdfTeX expands no `$TEXMF...`
roots and cannot checksum files under `fonts/`. On MiKTeX only, BnTeX therefore
finds installed font files through MiKTeX's font search and compares every
metric file, glyph by glyph, with the MD5-checked shaping tables; the encoding
and TrueType files cannot be checked there. Do not copy only the `.sty` files or
rebuild profiles as a document author: a missing or changed asset stops
compilation with an error.

Copy and search: every word carries its original text as `/ActualText`, which
viewers such as Poppler's return exactly. Viewers that ignore it, including
Overleaf's preview and Firefox's built-in viewer (PDF.js), use each glyph's
Unicode text: the letters are right, but vowel signs drawn left of their
consonant and reph come out in drawing order.

Restrictive `openin_any=p` behaviour differs between engines. The tests probe
each checksum primitive, then require either correct rendering with corruption
rejected, or a clear read-policy error. The package never changes security
settings or disables integrity checks.

## Word cache (`\jobname.bnc`)

`bntex` loads `bntex-native-reuse`, which shapes each distinct word once per
compilation and writes the positioned glyph runs to `\jobname.bnc` next to the
`.aux` file. The next compilation reuses them, so only new or changed words are
shaped again. The file is an accelerator, not a word list: deleting it only makes
the next compilation slower. It is ignored unless it was written by the same
installation (keyed on the MD5 of the profile loader, which pins every module and
font), and every line carries an MD5 so a truncated or damaged line is shaped
again instead of used. Output is identical with or without the cache. Use
`\usepackage[no-word-cache]{bntex}` to disable it, `\BnTeXCacheNoFile` in the
preamble to keep it in memory only, and `\BnTeXCacheStats` to print hit counts.
At most 15,000 distinct word forms are cached per document; further words are
shaped normally.

## Licenses

Original code: MIT (LICENSE), with retained THIRD-PARTY-NOTICES.md for the
algorithms adapted from HarfBuzz. Fonts and font-derived data: SIL OFL 1.1
(OFL-1.1.txt and FONT-NOTICES.md). The fonts are the unmodified Noto Serif
Bengali Regular and Bold binaries; only their external file names are changed.

## Complete inventory and source reproduction

The verifier requires the fixed release file set independently of the manifest's
hash list. Removing a required profile, font bank, notice, manual or build source
and deleting its manifest entry does not produce a verified distribution. It
also checks the original OFL text, corresponding runtime/source modules, matching
installed loaders, and absence of symlinks or unlisted files. These are consistency
checks on trusted distributions, not signatures or hostile-input authentication.

The complete TDS archive includes `source/latex/bntex/REPRODUCING.md`. A maintainer
can run the recorded `python -B -m bntex.distribution rebuild` command from that
source directory. It re-compiles the manual twice, runs the real font-profile
compilers, and requires the same manifest and archive bytes. The `-B` flag prevents
bytecode files from modifying the installed source tree. This reproduction tool
is not part of document authoring, and it neither downloads nor publishes files.

## Read-policy version note

Do not infer read-policy behavior from `openin_any=p` alone or change the host
policy to manufacture a pass. The upstream Kpathsea manual documents that the
input-name checks became no-ops in 2026; older libraries can still enforce them.
The package uses the configured engine unchanged and tests its actual primitive
capability.
Source: https://tug.org/texinfohtml/kpathsea.html#Safe-filenames
Change: https://ftp.tug.org/pipermail/tex-live-commits/2026-January/035883.html
