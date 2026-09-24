# User inventory coverage and corpus discovery

## Status and scope

This supplements milestone #3 on top of `feat/corpus-oracle`. It does not replace
`corpus/bengali-v1.json`, the original oracle, or its pending review ledger.
The user supplied examples, not approval of rendered output. No native shaper is
implemented. No large external corpus was downloaded or mined in this change.

The machine-readable source is `corpus/inventories/user-alphabet-v1.json`.
It retains the six-section inventory, including all 146 explicitly listed
conjuncts, 11 vowels, the 39 traditionally grouped consonants/signs, all seven
attached-form descriptions, nine irregular vowel combinations, and ten digits.
Phonetic transliterations are not used to determine glyphs.

## Definition layers

Keep pedagogical and technical classifications separate. In the supplied list,
39 consonants/signs comprise 35 consonant-letter entries, khanda ta, and three
marks (anusvara, visarga, candrabindu). The native shaper must distinguish these
roles rather than treating all 39 as interchangeable bases. Hasant (U+09CD), nukta
(U+09BC), vowel signs, and ZWJ/ZWNJ are separate inputs [U, B].

`ক্ষ` is KA + HASANT + SSA, not one separately encoded Unicode letter. Similarly,
`জ্ঞ` is JA + HASANT + NYA. Phala names are pedagogical labels for contextual
forms; they are not independent code points or a single universal rendering rule.
Reph uses initial RA + HASANT in a syllable; ra-phala follows a preceding base.
The exact glyph sequence and positions depend on the chosen font and context [U, B].

The vowel in bare `ক` is inherent: do not insert an independent `অ` character.
Keep original precomposed/decomposed nukta encodings separate even where their
working normalization agrees. Khanda ta is not simply normalized to ordinary TA
plus a hasant. Traditional versus unligated consonant-vowel shapes are documented
variants, not universally identical outlines [U].

An encoded consonant chain, a grapheme cluster, an orthographic syllable, a
font glyph, and a grammatical verb conjugation are different concepts.
UniMorph forms such as different verb inflections can provide test words, but a
renderer does not need a tense/person model to typeset them.

## Measured gap in the old corpus

Coverage here means an exact standalone raw-Unicode rendering case anywhere in
the corpus, not merely a substring in a longer word. Canonical-only and embedded-only
coverage are reported separately. This avoids claiming standalone digit tests from
one long digit sequence, or claiming conjunct coverage from an incidental word.

| User group | Required | Exact in original corpus | Exact after supplement |
|---|---:|---:|---:|
| Independent vowels | 11 | 11 | 11 |
| Listed consonants and signs | 39 | 27 | 39 |
| KA + vowel / inherent-vowel forms | 11 | 11 | 11 |
| Explicit conjunct list | 146 | 18 | 146 |
| Attached-form examples | 21 | 6 | 21 |
| Irregular vowel combinations | 9 | 0 | 9 |
| Individual digits | 10 | 0 | 10 |

The old conjunct list contains 14 dedicated examples, but four more standalone
conjunct strings appear in other categories; hence the exact count of 18 above.
Of the remaining 128, eight occur only as substrings and 120 do not occur at all.
There are **261 distinct raw strings** in the complete new inventory. Duplicate
membership across user categories is retained in the requirements, but the
supplement shapes each distinct string once. Isolated marks and attached fragments
are behavior probes, not recommended complete spellings or syllables.

## Reproduce the supplement and review sheet

The original corpus tooling is reused unchanged. Only the compact source inventory
and a compactly packed frozen oracle are checked in; the readable derived
corpus and oracle are generated into `build/`. The oracle is frozen data, not
regenerated automatically by tests. The packed file contains every frozen glyph
row plus reference metadata. Case IDs encode the original Unicode scalars, so
redundant source hashes can be reconstructed without invoking a shaper or reading
a mutable corpus. The entire expanded ordinary oracle is checked against a fixed
digest. This is data decompression, not re-recording expected glyphs.
Its expanded SHA-256 is:

`9466f84a8117d992b034392ba4992e1d745e31c67561160153e67cb49753782f`

Use the pinned toolchain described in CORPUS.md for an exact shaping comparison.

```bash
python -m bntex.inventory build \
  --inventory corpus/inventories/user-alphabet-v1.json \
  --out build/user-forms.json
python -m bntex.inventory unpack-oracle \
  --oracle corpus/oracles/user-forms-noto-hb10.2.0.json.gz \
  --out build/user-forms-oracle.json
python -m bntex.inventory coverage \
  --inventory corpus/inventories/user-alphabet-v1.json \
  --corpus corpus/bengali-v1.json --corpus build/user-forms.json \
  --out build/coverage.json
python -m bntex.corpus review-build \
  --corpus build/user-forms.json --oracle build/user-forms-oracle.json \
  --font /path/to/NotoSerifBengali-Regular.ttf --out build/user-review
(cd build/user-review && pdflatex -no-shell-escape -halt-on-error review.tex)
(cd build/user-review && pdflatex -no-shell-escape -halt-on-error review.tex)
python -m bntex.corpus review-template \
  --corpus build/user-forms.json --oracle build/user-forms-oracle.json \
  --out build/user-forms-reviews.json
```

All 261 reviews start unreviewed. Add actual reviewer attribution only after review.
The local PDF has 12 pages; no overfull or missing-character log messages, with one
introductory underfull-box message. Layout inspection does not approve typography.

## Bounded mining: implemented

`python -m bntex.mining` accepts a local UTF-8 text file, JSONL text field, or TSV
column. Plain, gzip, xz, and bz2 input are supported. It never downloads data,
requests credentials, calls a shell, or executes dataset-supplied code.

```bash
python -m bntex.mining \
  --input /path/to/authorized-bengali.txt.xz \
  --inventory corpus/inventories/user-alphabet-v1.json \
  --source-id cc100-bn --revision ACTUAL-SNAPSHOT-AND-SHARD-ID \
  --max-records 10000 --max-bytes 16777216 \
  --out build/cc100-bn-sample.json
```

For local Sangraha/IndicCorp/CulturaX JSONL exports, use `--format jsonl --text-field
text`. For OSCAR's different text key use `--text-field content`, but only on data
already lawfully obtained; this is not a way around its access controls. For the
UniMorph three-column TSV format, use `--format tsv --text-column 1` (zero-based).
CSV/XML/Parquet are not parsed by this miner. Export text through a separately
reviewed adapter first. In particular, do not mine raw Wikipedia XML or wikitext
as if it were already clean article prose. A future adapter must record both the
original shard identity and the exact conversion settings.

The report contains per-pattern occurrences and record frequencies; a bounded
number of first-observed example words with record hash, line and byte offset;
raw versus NFC grouping keys; maximal encoded consonant-chain candidates; and an
explicit scan-scope statement. Candidate chains containing join controls are kept
distinct. They are not assumed to be visually ligated.

The complete decoded bytes of processed records are hashed, not the entire
compressed file. `full_input_consumed=false` means a prefix was scanned, even if
a limit happened to fall at the last record without an observed EOF. Oversized
records, invalid UTF-8/JSON, duplicate JSON keys and excessive vocabulary fail.
Overlong tokens are excluded with an explicit count. No original normalization or
join-control deletion is performed. All counts refer only to accepted script
tokens in processed records. For plain CC-100 text, one line is a record/paragraph,
not necessarily a whole document.

The tokenizer is script-based, **not a language identifier**. Bengali-block text
may belong to other languages, including Assamese. The chain regex is a limited
candidate extractor for the listed Bangla consonants, not the future Indic
syllable parser. The algorithm is O(tokens * inventory-size * token-length), and
memory is bounded by configured vocabulary/chain/example limits. Defaults are for
small pilots, not a performance claim for billions of words. Compression-library
internal memory and untrusted font parsing require their own safeguards.

## Discovery workflow and next scale-up

Maintain separate layers: explicit regression requirements; mined usage evidence;
synthetic interaction probes; and human-approved renderings. A million common
words must not replace one missing rare structural case. Tests already exercise
146 listed conjunct bases with no matra or each of the ten listed matras: 1,606
repeatable HarfBuzz behavior probes. These are not 1,606 approved words and not an
independent shaping proof.

First run a small pilot on a pinned authorized source; inspect invalid records,
join-control retention, duplicate rates and source bias. Then add dataset-specific
exporters, a disk-backed counter, deterministic document sampling and deduplication,
source-stratified frequency summaries, and a holdout split grouped by raw/NFC
word identity. Keep common-case coverage and rare-case coverage separate.
Promote a mined candidate only with source/revision and a reviewed expected result.
Store original third-party corpora outside Git; examples require their own reuse
review. Cleaners that remove punctuation or normalize spellings can erase exactly
the edge cases this project needs.

Source access notes are maintained in DATA-SOURCES.md. The current change tests
mining on original small fixtures only; it does not claim any full-source run,
exhaustive Bengali coverage, accepted human reviews, or native TeX shaping.

## References

[U] Unicode 17, Bengali section: https://www.unicode.org/versions/Unicode17.0.0/core-spec/chapter-12/

[B] Microsoft Bengali shaping model: https://learn.microsoft.com/en-us/typography/script-development/bengali
