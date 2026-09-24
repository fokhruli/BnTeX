# Trust and safety boundaries

Do not execute untrusted TeX documents or font files outside an appropriate
sandbox. The preparer scans literal source and invokes pltotf with an argument
list; it does not expand TeX or use shell commands. pdfLaTeX compilation remains
execution of the document's TeX macros; disabling shell escape is not a complete
untrusted-document sandbox.

Use exact font hashes: glyph IDs have meaning only in that font. MD5 word keys
and runtime asset checks detect ordinary mismatches, not malicious changes.
SHA-256 manifests are unsigned integrity records, not authenticated releases.
Do not promise security based on hashes alone.

Generated output directories must be empty or explicitly marked; inputs may not
live inside a replaced build directory. Maintain an authoritative source outside
build/. Review overwrite operations and font permissions. No credentials or
font binaries belong in Git. Filename audits are not full content/secret scanners.

CI uses read-only contents permission, no deployment/publication steps and no
PR secrets. Keep source/docs-only workflow artifacts. Do not add unrestricted
shell execution to make Overleaf work. Bound font/source/shaping lengths and
raise errors for unsupported input instead of silently substituting output.

The layout audit uses bounded traversal and rejects certain malformed references;
it is not a security validator for all possible OpenType fonts. Native shaping,
font serialization and PDF structural accessibility require their own reviews.
