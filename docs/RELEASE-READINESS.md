# Release readiness

## 0.2.0-alpha status (2026-11-13)

The installable `\usepackage{bntex}` package, the project-folder (Overleaf)
layout and the word cache are on `main`. The release build produces the TDS,
CTAN-candidate and Overleaf-starter archives, and Linux CI passes the full
oracle-gated suite. The maintainer compiled the starter documents on Overleaf
(TeX Live 2026) with and without the word cache; see
[reviews/2026-11-13-overleaf.json](reviews/2026-11-13-overleaf.json).

Every gate in `RELEASE-READINESS.json` is still `pending` or `blocked`: the
new-word edit and visual review on Overleaf, a second user, the long-document
performance target, font distribution, the package name, and the decision to
publish. Each gate's status is the maintainer's call; this document does not
change any of them.

## Earlier checkpoint notes

This was a review checkpoint, not a release or an upload authorization. The
original cached backend and the experimental fixed-profile native path coexist.
The automatic `bntex-auto` interface and audited regular/bold family are described
in [AUTOMATIC-AUTHORING.md](AUTOMATIC-AUTHORING.md). The earlier automatic-input
deferral is superseded; ordinary authoring no longer requires language wrappers.
The package-name, font/profile distribution policy, browser reproduction,
independent user, native visual review and long-document interaction target
remain separately recorded in `RELEASE-READINESS.json`.

## Mechanical preflight

Use a clean tracked checkout. The new preflight rejects unsupported artifacts,
renamed font signatures, symlinks, missing documentation/licenses, dirty tracked
sources and mismatched authoritative/wheel TeX resources. It reads only tracked
regular files, so adjacent local secrets/build directories are not archived.
This is a basic source check, not comprehensive security or legal analysis.

```
mkdir -p build/manual
pdflatex -no-shell-escape -halt-on-error -interaction=nonstopmode \
  -output-directory=build/manual docs/manual/bntex-manual.tex
pdflatex -no-shell-escape -halt-on-error -interaction=nonstopmode \
  -output-directory=build/manual docs/manual/bntex-manual.tex
python tools/release_preflight.py --out build/source-review.json \
  --manual-pdf build/manual/bntex-manual.pdf \
  --archive build/bntex-source-review.zip
```

The ZIP contains complete tracked sources plus the generated manual PDF and its
source under `bntex-source-review/`. It is a **private developer review archive**,
not a CTAN-ready distribution: public naming, directory/dependency decisions,
font rights and private-reference cleanup still require review. No automatic
publication command exists. Fonts in the user-owned installation are not included.

`python tools/release_preflight.py --out build/readiness.json --require-ready`
returns 1 while gates are blocked/pending (2 on a mechanical/schema error).
Ordinary mechanical review mode can return 0 despite pending human gates; its
report lists those gates explicitly. A `passed` entry requires an evidence field,
but JSON does not authenticate that evidence. A maintainer must verify it.

## Source and wheel packaging

The updated source manifest includes `.def` modules, authoritative TeX sources,
tests, corpus fixtures, tools, documentation and examples, plus both licenses.
The Python wheel continues to package `.sty` and `.def` runtime resources.
The dry-run workflow builds source/wheel distributions, checks resource identity,
compiles the manual and audits the full clean tree. It uploads no package/font
artifacts and does not create releases. Dry-run packages are not publication.

## Actual browser and second-user checks

No Overleaf integration was available to this implementation session. No browser
success or independent person is claimed. Use the staged automatic-authoring example
from AUTOMATIC-AUTHORING.md (or the separately scoped legacy native-project example),
its no-shell `latexmkrc`, the guide in `OVERLEAF-NATIVE.md`, and a new Overleaf
project with pdfLaTeX selected. Record TeX Live version, source revision, log,
PDF and installation identity, then add a word only after import and recompile.
Verify headings/bookmarks and copy/paste. Do not regenerate vocabulary.

A second person must install from the complete source-review archive rather than
from a developer working tree. The agent running another local directory does
not count as a second person. Their actual name/date/evidence belongs in a new
review record, not a fabricated update to old per-case ledgers.

## Primary guidance

CTAN requires an informative README, license, complete clean archive, readable
PDF documentation and its source. Handwritten package files are valid source;
`.dtx` is not universally mandatory. These are packaging requirements, not an
acceptance guarantee: https://ctan.org/help/upload-pkg

Overleaf's compiler and TeX Live selections are project-specific settings:
https://docs.overleaf.com/getting-started/recompiling-your-project/selecting-a-tex-live-version-and-latex-compiler

The original roadmap remains design provenance. Current supported interfaces
and unresolved gates are in README.md and AUTOMATIC-AUTHORING.md. Wrapper-free
input and standard styles are implemented with their documented limits; browser,
new-style visual and independent-user acceptance remain separate. No public
release is scheduled or authorized.

## Installable-distribution candidate

The requested public author interface is now `\usepackage{bntex}`. The
maintainer-only `tools/build_distribution.py` assembles prebuilt data, outlines,
licenses, a manual and sources into a complete local TDS tree and browsing ZIP.
It never uploads them. Source-review ZIPs remain font-free and are not those
font-containing installation archives.

The old generic-font-file lookup failure is addressed for normal TeX Live roots
under its default read policy. Strict `openin_any=p` is engine-dependent:
the local pdfTeX 1.40.26 rejects symbolic-root checksums while the CI TeX Live
2023 engine permits them. A separate primitive probe determines the expected
package outcome and tests corruption rejection for readable installations.
No policy is changed or check skipped. See docs/distribution/README.md. Browser
and distribution-maintainer review must establish whether the target environment
accepts this mechanism; current package readiness is not inferred from local
TDS success. No gate in RELEASE-READINESS.json is marked passed.
