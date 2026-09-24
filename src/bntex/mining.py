"""Bounded local corpus mining. Counts describe a scanned prefix, never all Bangla.

No downloader, font renderer, syllable parser, linguistic validator or shaper.
Original Unicode is retained; normalization is only a separate grouping key.
"""
from __future__ import annotations
import argparse
import bz2
from collections import Counter
from contextlib import ExitStack
from dataclasses import asdict, dataclass
import gzip
import hashlib
import json
import lzma
from pathlib import Path
import re
import sys
import unicodedata
from .corpus import require, write_output, serialize
from .inventory import load_inventory, requirements

# Script candidates only: Bengali-block text is not necessarily Bengali language.
TOKEN = re.compile(r'[\u0980-\u09ff\u200c\u200d]+')
CONSONANTS = 'কখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহড়ঢ়য়'
ATOM = '[' + CONSONANTS + r']\u09bc?'
CHAIN = re.compile(ATOM + '(?:\u09cd[\u200c\u200d]?' + ATOM + ')+')


@dataclass(frozen=True)
class Limits:
    records: int = 10000
    decoded_bytes: int = 16 * 1024 * 1024
    line_bytes: int = 1024 * 1024
    word_scalars: int = 256
    unique_words: int = 100000
    examples: int = 3
    top_words: int = 1000

    def validate(self) -> None:
        require(all(type(v) is int and 0 < v <= 2**40 for v in asdict(self).values()), 'Limits must be positive bounded integers.')
        require(self.line_bytes <= 8 * 1024 * 1024 and self.word_scalars <= 4096,
                'Line/word limits exceed safe parser bounds (8 MiB / 4096 scalars).')
        require(self.unique_words <= 1000000 and self.examples <= 20 and self.top_words <= 10000,
                'Vocabulary/example/output limits are too large.')


def chain_spans(text: str) -> list[dict]:
    """Maximal encoded C(+nukta)(virama+optional joiner+C(+nukta))+ candidates.

    These are not necessarily ligatures or valid orthographic syllables.
    Byte offsets refer to the supplied original text, not normalized text.
    """
    offsets = [0]
    for char in text:
        offsets.append(offsets[-1] + len(char.encode('utf-8')))
    return [{'text': m.group(), 'start_byte': offsets[m.start()], 'end_byte': offsets[m.end()],
             'join_controls': [f'U+{ord(c):04X}' for c in m.group() if c in '\u200c\u200d']}
            for m in CHAIN.finditer(text)]


def _open(path: Path, stack: ExitStack):
    require(path.is_file(), 'Input must be a regular local file, not a directory or URL.')
    if path.suffix == '.gz': return stack.enter_context(gzip.open(path, 'rb'))
    if path.suffix == '.xz': return stack.enter_context(lzma.open(path, 'rb'))
    if path.suffix == '.bz2': return stack.enter_context(bz2.open(path, 'rb'))
    return stack.enter_context(path.open('rb'))


def _text(raw: bytes, fmt: str, text_field: str, text_column: int, line: int) -> str:
    try:
        decoded = raw.decode('utf-8', errors='strict')
        if fmt == 'text': return decoded
        if fmt == 'tsv':
            columns = decoded.rstrip('\r\n').split('\t')
            require(0 <= text_column < len(columns), f'Line {line}: missing TSV text column.')
            return columns[text_column]
        def pairs(items):
            out = {}
            for k, v in items:
                require(k not in out, f'Line {line}: duplicate JSON key.')
                out[k] = v
            return out
        data = json.loads(decoded, object_pairs_hook=pairs,
                          parse_constant=lambda _: require(False, f'Line {line}: non-finite JSON number.'))
        require(isinstance(data, dict) and isinstance(data.get(text_field), str),
                f'Line {line}: expected JSON object with text field {text_field!r}.')
        data[text_field].encode('utf-8', errors='strict')
        return data[text_field]
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f'Line {line}: invalid UTF-8 or JSON; no automatic repair.') from exc


def mine(path: Path, inventory_path: Path, *, source_id: str, revision: str,
         fmt: str = 'text', text_field: str = 'text', text_column: int = 1,
         limits: Limits = Limits()) -> dict:
    limits.validate()
    require(fmt in {'text','jsonl','tsv'}, 'Unsupported input format.')
    require(type(text_column) is int and text_column >= 0, 'text_column must be a nonnegative integer.')
    require(all(isinstance(x, str) and x.strip() and len(x) <= 512 for x in (source_id, revision)),
            'A bounded source ID and exact source revision are required.')
    inventory, inventory_hash = load_inventory(inventory_path)
    patterns = sorted({r['text'] for r in requirements(inventory)})
    listed_chains = {x for _, group in inventory['conjunct_groups'] for x in group.split()}
    frequency: Counter[str] = Counter(); doc_frequency: Counter[str] = Counter()
    forms: Counter[str] = Counter(); form_docs: Counter[str] = Counter()
    chains: Counter[str] = Counter(); samples: dict[str, list[dict]] = {}
    processed = records = long_tokens = tokens = 0
    prefix = hashlib.sha256(); eof = False; stop = 'record-limit'
    with ExitStack() as stack:
        stream = _open(path, stack)
        for line in range(1, limits.records + 1):
            remaining = limits.decoded_bytes - processed
            if remaining == 0:
                stop = 'byte-limit'; break
            raw = stream.readline(min(limits.line_bytes, remaining) + 1)
            if not raw:
                eof = True; stop = 'eof'; break
            if len(raw) > remaining:
                stop = 'byte-limit'; break
            require(len(raw) <= limits.line_bytes, f'Line {line}: decoded line limit exceeded.')
            text = _text(raw, fmt, text_field, text_column, line)
            records += 1; processed += len(raw); prefix.update(raw)
            seen_words: set[str] = set(); seen_forms: set[str] = set()
            for match in TOKEN.finditer(text):
                word = match.group()
                if len(word) > limits.word_scalars:
                    long_tokens += 1; continue
                if word not in frequency:
                    require(len(frequency) < limits.unique_words, 'Unique-word limit exceeded; no partial result emitted.')
                frequency[word] += 1; tokens += 1; seen_words.add(word)
                for pattern in patterns:
                    count = word.count(pattern)  # non-overlapping within each token
                    if not count: continue
                    forms[pattern] += count; seen_forms.add(pattern)
                    examples = samples.setdefault(pattern, [])
                    if len(examples) < limits.examples and not any(e['word'] == word for e in examples):
                        examples.append({'word': word, 'source_line': line,
                            'text_field': text_field if fmt == 'jsonl' else None,
                            'text_column': text_column if fmt == 'tsv' else None,
                            'record_sha256': hashlib.sha256(raw).hexdigest(),
                            'word_start_byte_in_text': len(text[:match.start()].encode('utf-8'))})
                for candidate in chain_spans(word):
                    require(candidate['text'] in chains or len(chains) < limits.unique_words,
                            'Unique-chain limit exceeded; no partial result emitted.')
                    chains[candidate['text']] += 1
            doc_frequency.update(seen_words); form_docs.update(seen_forms)
    top = sorted(frequency, key=lambda w: (-frequency[w], w))[:limits.top_words]
    return {'schema': 1, 'kind': 'bntex-corpus-mining-report', 'source_id': source_id,
        'revision': revision, 'input_name': path.name, 'format': fmt,
        'text_field': text_field if fmt == 'jsonl' else None,
        'text_column': text_column if fmt == 'tsv' else None,
        'limits': asdict(limits), 'inventory_sha256': inventory_hash,
        'processed_records': records, 'processed_decoded_bytes': processed,
        'processed_prefix_sha256': prefix.hexdigest(), 'full_input_consumed': eof,
        'stop_reason': stop, 'script_tokens': tokens, 'unique_script_tokens': len(frequency),
        'overlong_tokens_excluded': long_tokens, 'python_unicodedata': unicodedata.unidata_version,
        'counts_scope': 'Accepted script tokens in processed records; not global language frequencies.',
        'language_detection': False, 'human_review': 'not-performed',
        'normalization': 'Original strings retained; NFC is only a separate grouping key.',
        'patterns': [{'text': p, 'occurrences': forms[p], 'records': form_docs[p],
                      'examples': samples.get(p, [])} for p in patterns],
        'maximal_chain_candidates': [{'text': p, 'occurrences': chains[p],
            'listed_exactly': p in listed_chains, 'has_join_control': any(c in p for c in '\u200c\u200d')}
            for p in sorted(chains, key=lambda w: (-chains[w], w))],
        'top_tokens': [{'text': w, 'utf8_hex': w.encode().hex(), 'nfc_group_key': unicodedata.normalize('NFC', w),
                        'occurrences': frequency[w], 'records': doc_frequency[w]} for w in top]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--source-id', required=True); parser.add_argument('--revision', required=True)
    parser.add_argument('--format', choices=['text','jsonl','tsv'], default='text')
    parser.add_argument('--text-field', default='text'); parser.add_argument('--text-column', type=int, default=1)
    parser.add_argument('--max-records', type=int, default=10000)
    parser.add_argument('--max-bytes', type=int, default=16*1024*1024)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        require(args.out.resolve() not in {args.input.resolve(), args.inventory.resolve()}, 'Output must not replace an input.')
        require(not args.out.exists() and not args.out.is_symlink(), 'Output already exists; choose a new report filename.')
        result = mine(args.input, args.inventory, source_id=args.source_id, revision=args.revision,
            fmt=args.format, text_field=args.text_field, text_column=args.text_column,
            limits=Limits(records=args.max_records, decoded_bytes=args.max_bytes))
        write_output(args.out, serialize(result))
        print(json.dumps({k:result[k] for k in ('processed_records','script_tokens','stop_reason','full_input_consumed')}, indent=2))
        return 0
    except (OSError, ValueError, EOFError, lzma.LZMAError) as exc:
        print(f'bntex mining: {exc}', file=sys.stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())
