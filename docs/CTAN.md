# CTAN and release preparation

## Status and claims

The repository is a private development alpha, not a CTAN submission. BnTeX and
bntex-preparer are working names, not a claim to name reservation or registry
availability. Check naming/confusion with BangTeX and document prior art [R6–R9].
Do not advertise this as the first Bengali LaTeX or pdfTeX package.

A defensible cached-release description is: prepare Unicode Bengali with HarfBuzz,
then typeset native font glyphs with pdfLaTeX without shell execution during final
compilation. Add 'no per-document preprocessing' only after issue #6's unseen-word
gate passes. List exact tested versions, fonts, inputs and unsupported contexts.

## Packaging checklist

Follow current CTAN guidance [R15,R16]. Include an English UTF-8 README, requirements,
license and installation instructions, readable PDF documentation with its source,
and a complete clean archive rather than a patch. Use a named top-level directory
and appropriate optional TDS placement for code, documentation, fonts and scripts.
Confirm Python-helper/generated-profile placement with maintainers.

A handwritten .sty is source; .dtx/.ins is a useful documented-source workflow, not
a universal prerequisite to begin development. When using .dtx, follow the current
rules about generated files. The development Git tree is not automatically the
right upload archive. Exclude logs, .aux files, credentials and build clutter.

Have another person install from the archive without access to the development
machine. Test the wheel's bundled renderer, local TeX installation and project-local
installation. Version the support matrix, source commit, dependency/font hashes,
changelog and actual CI evidence. Filename checks do not replace content review.

## Licensing and font assets

Original source/documentation in this repository uses MIT. Third-party software and
fonts retain their own licenses. CTAN accepts multiple licenses; adopting LPPL for
new LaTeX work would require reviewing its maintenance/modified-file obligations,
not silently relicensing other people's code [R17].

No font binaries are included in the repository. Generated local builds use an
unchanged user-supplied font. `fsType=0` is a technical prototype filter, not legal
permission to distribute that font. Review its actual license: embedding, copying,
modification, reserved names and redistribution are separate questions. A variable
font instance needs its own provenance/license review and rebuilt dependent tables.

Prefer a separately installed font dependency or a deliberately reviewed profile
distribution. Do not bundle an arbitrary commercial font for convenience. Seek
appropriate legal advice for uncertain licensing situations.

## Distribution and accessibility

CTAN submission is not a guarantee of acceptance, TeX Live/MiKTeX inclusion or
immediate availability in a selected Overleaf image. Preserve manual installation
instructions. Publisher-specific rules may impose additional restrictions.

Test extraction/search in multiple PDF engines. Original-order ActualText is not
structural tagging, reading order, accessible headings, bookmarks or PDF/UA.
Keep each of these as a separate, evidence-backed support claim.

## Release gate and authorization

Private alpha -> independent reproduction -> complete cached-package documentation
-> native-profile feasibility decision -> reviewed candidate -> licensing/archive
checks -> separately authorized submission -> maintainer feedback -> distribution
verification and maintenance.

Issue #8 tracks preparation only. Do not create a public release, change repository
visibility or upload to CTAN/PyPI without a separate maintainer decision. No automatic
publication action is part of ordinary CI.
