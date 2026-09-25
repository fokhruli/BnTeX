# Native decode-once span transport

## Scope and baseline

This change is based on PR #19, commit
`e8e4ff6b98e65198e86b4471532a2c083102de6a`. At development time that PR was
still open. Review this as a dependent PR, then retarget to main after #19 is
merged and rerun the merge checks. No main update or release is implied.

The old `\bnNative` path decoded the entire literal passage and then decoded
each word again. The new path invokes the SAME strict decoder once per passage
and collects per-word input records during that pass. Public authoring is
unchanged. This is not automatic script routing, a word dictionary, or a new
shaping algorithm. No Python code executes during document compilation.

## Implementation and invariants

Within the existing local command group, the scalar-emission sink is temporarily
replaced by a bounded word collector. The original UTF-8 state machine, token
validation, 4096-byte input bound and failure policy are unchanged. Only validated
scalars reach the collector. U+0020 SPACE is the sole delimiter, matching the
existing raw-word splitting policy. NBSP is not treated as ordinary SPACE.

At each completed word, the collector saves scalar, byte-offset and byte-length
sequences with supported expl3 sequence-copy operations. Offsets start at zero
for EACH word. Record control-sequence names are numbered, locally defined and
reused on later calls; the explicit ceiling is 2048 records, also constrained
by the original 4096-byte span limit. TeX may intern those bounded names, but
state cannot grow with document vocabulary. No persistent files are added.

Nothing is shaped or rendered until the WHOLE literal UTF-8 input succeeds.
A malformed byte sequence at the end cannot render its valid prefix. As before,
well-encoded but unsupported shaping-domain input is rejected by the shaper;
this is not a newly promised transactional whole-paragraph shaping check.

The original scalar sink is restored before shaping. The original string is
split using the established SPACE policy, and its nonempty-word count must
match the decoded records. Each word then supplies its validated sequences and
EXACT original UTF-8 hex to the existing native execution path. The shaper still
normalizes a separate working sequence; source encodings, joiners, ActualText,
font/profile rules, feature order and operation limits are untouched.

The new private `\__bn_shape_word:n` executes the supplied record only under a
locally scoped trusted-input flag. Public `\BnTeXNativeShape` and
`\BnTeXNativeShapeHex` always execute their own full decoder. No new public
already-decoded-input API is introduced. The internal view supplies only fields
consumed by the shaper; it is not advertised as the public decoder's complete
byte-buffer result. Existing grouped public decoder state is restored afterward.

The optional memo package calls the private hook on misses, with reuse disabled,
or during tracing. It retains its exact ORIGINAL-byte keys and existing bounded
positioned-run cache. Hits still render at the current size and color. All calls
validate the whole input even when subsequent words are cache hits. Neither
normalized source keys nor a persistent word cache are introduced.

## Tests and experimental controls

The baseline four-word example made five literal-decoder calls, or four with
memoization enabled. The same new test requires exactly ONE in both modes.
Forty-eight runtime regressions cover original scalars/offsets/lengths/hex,
all 261 unchanged frozen forms through multiword input, full stage traces versus
standalone shaping, canonical-equivalent but byte-distinct encodings, joiners,
spaces, malformed tails, macro non-expansion, input limits, public literal/hex
independence, memo hits/misses/evictions/tracing, grouping and record lifetime.
Six additional tests validate benchmark fixture identity and diagnostic timing.

The actual full-repository CI count must be read from the completed workflow,
not inferred from local collection. Local development uses a reconstructed
subset with an exact live-profile JSON override. The override bytes match
`f6294540099a3b6f622f2cdd9e863050390f75fd0576495d5a2316903f8cfb42`;
this does not mean the live compiler was executed locally. Remote CI must run
the actual compiler and complete repository without that override.

The final collector passed the physically Python-free Linux capability gate:
no Python interpreter, HarfBuzz library or word cache inside the runtime;
shell execution disabled; exact glyph fields checked outside afterward;
original text extracted and installed assets unchanged. This is not a security
sandbox, an Overleaf session, or human typography approval.

## Measured results: modest and workload-dependent

Paired runs used identical source bytes and verified installations, fresh pdfTeX
processes, alternating A/B and B/A order, and three samples per version. The
following values are MEDIANS (minimum--maximum), in seconds. The long benchmark
and regression suite were not run together. The host is shared, OS caches were
not flushed, and three samples are not confidence intervals.

| Workload | PR #19 | Decode once |
| --- | --- | --- |
| 1 page, 96 distinct digit-suffixed tokens, memo off | 2.632 (2.563--2.717) | 2.437 (2.383--2.514) |
| 10 pages, 960 distinct digit-suffixed tokens, memo off | 23.318 (23.237--24.898) | 23.225 (21.953--23.434) |
| 10 pages, 960 distinct digits-free synthetic strings, memo off | 15.438 (14.681--16.623) | 13.503 (13.467--13.877) |
| 1 page, authored prose, memo off | 2.103 (2.041--2.114) | 1.987 (1.866--2.337) |
| 10 pages, authored prose repeated per page, memo off | 26.234 (24.888--28.685) | 20.460 (18.007--22.716) |
| 10 pages, repeated tokens, memo on | 4.710 (4.648--4.936) | 4.622 (4.382--4.854) |

The main 10-page digit-suffixed result is essentially unchanged (0.4% median
reduction), not a meaningful universal speed claim. The digits-free case has
12.5% lower median; the prose case has 22.0% lower median. Prose is ORIGINAL
AUTHORED fixture text with 105 occurrences and 94 distinct tokens per page,
repeated across pages. It is not a corpus-derived, balanced or independently
reviewed workload. Memoization is OFF for both first-use controls. With memo on,
ranges overlap; no reliable improvement is claimed from the 1.9% median change.

Every paired document PDF is byte-identical. Actual page counts, expected token
extraction, three Bengali font entries and installation hashes pass. Measured
peak RSS spans 55,296--56,064 KiB across these workloads. The 100-page workload
was NOT remeasured here and the existing 90-second acceptance gate remains open.
Do not extrapolate these small measurements into meeting that gate.

## Why no renderer-setup change is included

A separate instrumented 64-word/eight-span probe reduced calls from 72 to 8.
Its renderer interval was only about 2% of the timed block. The collector executes
inside the decoder callback, so its reported decoder interval INCLUDES record
construction and must not be called pure UTF-8 decoding time. That one probe's
total increased (76,656 to 85,248 timer ticks); it does not show uniform gains.
A prior post-decode slicing experiment halved decoding work but added rebuilding
overhead and showed little document benefit; it was discarded.

Renderer code is byte-for-byte unchanged. A font-handle experiment is deferred
until representative exclusive profiling identifies a worthwhile renderer cost.
Do not claim that repeated font declarations necessarily reload physical fonts.

## Reproduction

Export fresh installations from the exact parent and candidate versions using
the documented pinned font/profile. Do not mix files from old exports. Installed
assets contain your LOCAL font and must not be committed or redistributed.

```sh
BNTEX_REQUIRE_INTEGRATION=1 BNTEX_REQUIRE_ORACLE=1 python -m pytest -q
python tools/native_decode_benchmark.py \
  --baseline /path/to/pr19-installation --candidate /path/to/new-installation \
  --out build/decode-once-check --pages 1 10 \
  --kinds distinct digits-free prose --repetitions 3 --timeout 120 --probe
python tools/native_decode_benchmark.py \
  --baseline /path/to/pr19-installation --candidate /path/to/new-installation \
  --out build/decode-once-memo --pages 10 --kinds repeated \
  --repetitions 3 --memo --timeout 120
```

The Python driver launches the actual pdfLaTeX child. Installation generation and
postcompile extraction are outside the timed interval. It retains JSON evidence
and marks failures/timeouts instead of treating partial output as success.
Installation hashes establish asset identities; the operator must bind them to
the source revisions, not infer a Git identity from an arbitrary directory name.
Only evidence JSON and output PDFs are shareable, not font-containing run folders.

User text still uses `\bnNative{...}` and needs no preparation after new words.
Automatic input (#15), additional fonts, human/browser acceptance and publication
remain deferred or pending; no release gate is changed by this optimization.
