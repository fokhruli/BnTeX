# Bengali corpus sources: discovery inputs, not shaping specifications

Reviewed 24 September 2026 against publisher/maintainer pages. No dataset account
was connected, agreement accepted, or external corpus downloaded in this change.
Access and licensing notes must be rechecked before use. Corpus totals spanning
multiple languages must not be presented as Bengali word counts. Tokens, words,
rows, bytes, and sentences are different units.

| Source | Use in BnTeX | Verified caveat / next step |
|---|---|---|
| [IndicCorp v2 / IndicBERT](https://github.com/AI4Bharat/IndicBERT) | Large-scale Bengali word/context discovery | Maintainer links the corpus on Hugging Face. Pin Bengali subset and revision; do not use a multilingual total as a Bengali count. |
| [Sangraha](https://huggingface.co/datasets/ai4bharat/sangraha) | Additional web, document, and rare-form examples | Separates verified, unverified and synthetic subsets. Keep their provenance separate. The card's Bengali code is `ben`; romanized/synthetic data are not interchangeable with original Bengali orthography. |
| [CulturaX](https://huggingface.co/datasets/uonlp/CulturaX) | Cross-source web-text stress testing | Gated agreement; derived from mC4/OSCAR and retains their licensing considerations. Do not assume it is independent of OSCAR or unrestricted to redistribute. |
| [OSCAR-2301](https://huggingface.co/datasets/oscar-corpus/OSCAR-2301) | Optional existing-authorized-data source | Card currently says new access is temporarily suspended. CC0 notice covers metadata/annotations, not all crawled text. Do not bypass gating. |
| [CC-100](https://data.statmt.org/cc-100/) | Straightforward local compressed-text pilot | `bn` is distinct from `bn_rom`; paragraph lines and blank-line document separators are documented. Download size is not word count. Crawled-source rights remain separate. |
| [Bangla2B+ / BanglaBERT](https://github.com/csebuetnlp/banglabert) | Bangladesh-focused examples | Maintainer requires an access request; this is not an immediate open download. Repository has noncommercial/share-alike terms. Review actual corpus terms and normalization before using examples. |
| [Bengali Wikipedia](https://dumps.wikimedia.org/bnwiki/) | Reproducible encyclopedic text sample | Pin a dated dump, revision/page provenance and extraction settings. Dump XML/wikitext needs conversion. [Wikimedia text reuse conditions](https://dumps.wikimedia.org/legal.html) apply. |
| [Sketch Engine](https://www.sketchengine.eu/corpora-and-languages/bengali-text-corpora/) | Interactive concordance and spelling checks | Concordance/word-list tools are documented. Do not assume licensed access, export rights, or that a specific corpus-size claim was verified. |
| [Leipzig](https://wortschatz.uni-leipzig.de/en/download) | Sentence/word-list sampling | Download endpoint returned a bot check in this session. No specific Bengali download or license was verified; no bypass attempted. |
| [LDC-IL Bengali](https://data.ldcil.org/a-gold-standard-bengali-raw-text-corpus) | Literary/register-specific examples | Catalogue states 4,237,440 words and Unicode XML with metadata. Domain distribution is 95.29% aesthetics, so do not assume balanced modern-domain coverage. Resource terms/undertakings apply. |
| [UniMorph Bengali](https://github.com/unimorph/ben) | Inflected word forms with labels | Maintainer supplies a TSV file and lists CC BY-SA 3.0. Inflection is not conjunct shaping. Scope/quality of individual paradigms still needs review. |
| [Wiktionary Bengali verbs](https://en.wiktionary.org/wiki/Category:Bengali_verbs) and [DSAL dictionaries](https://dsal.uchicago.edu/dictionaries/) | Targeted word checks | Useful leads, not a blanket machine-readable corpus license. Wiktionary page retrieval failed here; DSAL index was accessible. Dictionary-specific terms and entry provenance require review. |
| [BanglaDial paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12597015/) | Dialect-spelling stress tests | Authors report 60,729 entries, eleven regional dialects plus Standard Bangla, with imbalanced labels. Their preprocessing removes punctuation/special characters and normalizes some spelling; it is not an untouched typography oracle. |

## Decisions

Start with explicit alphabet/form requirements and small authorized CC-100 or
Wikipedia-text exports, then a source-stratified IndicCorp/Sangraha sample.
Preserve Bengali/Assamese language identity rather than filtering only by Unicode
block. Keep human-written and synthetic subsets separate. Frequency coverage is
not type completeness, native shaping support, or linguistic correctness.

A local run requires `--source-id` and `--revision`. Record acquisition date, exact
shard checksum, source license and converter settings alongside it. The miner's
processed-prefix hash is not a full-source checksum. Source code can be MIT while
third-party text is governed by a different license; do not silently relicense
corpus extracts as package code. No large data dump or font binary belongs in Git.

Future exporters should be read-only, explicit about network/byte limits, pinned
to a revision, and fail on missing/ambiguous text fields. They must not accept
agreements, run remote dataset scripts, or silently normalize the source. Human
review of promoted examples remains required.
