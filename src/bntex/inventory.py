"""Explicit user-form requirements and coverage, not a Bengali shaping algorithm."""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import sys
import unicodedata
from .corpus import load_corpus, read_json, require, serialize, write_output


def load_inventory(path: Path) -> tuple[dict, str]:
    data, identity = read_json(path)
    require(type(data.get('schema')) is int and data['schema'] == 1, 'Invalid inventory schema.')
    require(data.get('human_review') == 'not-performed', 'Input inventory is not typography approval.')
    require(isinstance(data.get('source'), str) and data['source'], 'Inventory source is required.')
    for name, width in [('vowels', 3), ('consonant_groups', 2), ('attached_forms', 5), ('conjunct_groups', 2)]:
        rows = data.get(name)
        require(isinstance(rows, list) and 0 < len(rows) <= 256, f'Invalid {name}.')
        for row in rows:
            require(isinstance(row, list) and len(row) == width, f'Invalid {name} row.')
            for index, value in enumerate(row):
                if name == 'vowels' and index == 1 and value is None:
                    continue
                require(isinstance(value, str) and 0 < len(value) <= 4096, f'Invalid {name} value.')
                require(not any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value), 'Unsafe inventory character.')
    for row in data['attached_forms']:
        require(row[2] in {'prefix', 'suffix'}, 'Invalid attached-form orientation.')
    for name in ('tricky_forms', 'irregular_vowels', 'digits'):
        require(isinstance(data.get(name), str) and 0 < len(data[name]) <= 4096, f'Invalid {name}.')
    # Round-trip validation also catches lone surrogates in the metadata.
    serialize(data)
    return data, identity


def requirements(data: dict) -> list[dict]:
    """Retain category membership/duplicates; raw strings are never normalized."""
    out: list[dict] = []
    def add(section: str, texts: list[str], label: str = '', probe: bool = False):
        for text in texts:
            out.append({'section': section, 'label': label, 'text': text,
                        'standalone_probe': probe, 'utf8_hex': text.encode('utf-8').hex()})
    for letter, sign, sample in data['vowels']:
        add('vowels', [letter]); add('ka-vowel-forms', [sample])
        if sign is not None:
            add('vowel-signs', [sign], probe=True)
    for label, texts in data['consonant_groups']:
        add('alphabet-consonants-and-signs', texts.split(), label)
    for label, pattern, orientation, forms, words in data['attached_forms']:
        add('attached-patterns', [pattern], label + ' / ' + orientation, True)
        add('attached-examples', forms.split(), label)
        add('example-words', words.split(), label)
    for label, texts in data['conjunct_groups']:
        add('conjuncts', texts.split(), label)
    add('tricky-forms', data['tricky_forms'].split())
    add('irregular-vowels', data['irregular_vowels'].split())
    add('digits', list(data['digits']))
    return out


def make_corpus(inventory_path: Path) -> dict:
    data, identity = load_inventory(inventory_path)
    by_text: dict[str, list[dict]] = {}
    for item in requirements(data):
        by_text.setdefault(item['text'], []).append(item)
    cases = []
    for text, items in by_text.items():
        category = items[0]['section']
        # Stable identity derives from the exact code points, not row position.
        cid = 'u-' + '-'.join(f'{ord(c):x}' for c in text)
        require(len(cid) <= 80, 'Inventory case ID exceeds corpus schema limit.')
        cases.append({'id': cid, 'category': category, 'expect': 'shape',
            'text': text, 'utf8_hex': text.encode().hex(),
            'notes': 'User-supplied example, not rendered-output approval. '
                + ('Standalone sign/fragment is a behavior probe, not a complete orthographic syllable. '
                   if any(x['standalone_probe'] for x in items) else '')
                + 'Groups: ' + ', '.join(sorted({x['section'] for x in items}))})
    categories = {c['category']: 'User inventory: ' + c['category'] + '; no human typography approval.' for c in cases}
    return {'schema': 1, 'version': '1.0.0', 'categories': categories, 'cases': cases,
            'curation': data['source'], 'inventory_sha256': identity,
            'references': {'unicode': 'https://www.unicode.org/versions/Unicode17.0.0/core-spec/chapter-12/',
            'bengali-shaping': 'https://learn.microsoft.com/en-us/typography/script-development/bengali'}}


def coverage(inventory_path: Path, corpus_paths: list[Path]) -> dict:
    data, identity = load_inventory(inventory_path)
    available: dict[str, list[str]] = {}
    sources = []
    for path in corpus_paths:
        corpus, digest = load_corpus(path)
        sources.append({'name': path.name, 'sha256': digest})
        for case in corpus['cases']:
            if case['expect'] == 'shape':
                available.setdefault(case['text'], []).append(path.name + ':' + case['id'])
    normalized = {unicodedata.normalize('NFC', t) for t in available}
    groups: dict[str, dict] = {}
    rows = []
    for item in requirements(data):
        text = item['text']
        exact = text in available
        equivalent = not exact and unicodedata.normalize('NFC', text) in normalized
        embedded = not exact and not equivalent and any(text in other for other in available)
        status = 'exact' if exact else 'canonical-only' if equivalent else 'embedded-only' if embedded else 'absent'
        row = dict(item, status=status, case_ids=available.get(text, []))
        rows.append(row)
        group = groups.setdefault(item['section'], dict(required=0, exact=0, **{'canonical-only':0,'embedded-only':0,'absent':0}))
        group['required'] += 1; group[status] += 1
    return {'schema': 1, 'inventory_sha256': identity, 'corpora': sources,
            'groups': groups, 'requirements': rows,
            'all_exact': all(r['status'] == 'exact' for r in rows),
            'human_review': 'not-performed', 'native_shaping_proven': False,
            'note': 'Standalone raw-string test coverage. Embedded/equivalent forms are reported, not counted as exact.'}


def unpack_oracle(path: Path) -> bytes:
    """Expand frozen glyph rows; never call a shaper or infer glyphs from text.

    Code-point IDs losslessly carry the original text. Redundant per-row source
    hashes are reconstructed from those IDs, not from a mutable corpus file.
    A pinned digest checks the entire reconstructed ordinary oracle JSON.
    """
    import hashlib
    with gzip.open(path, 'rb') as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    require(len(raw) <= 8 * 1024 * 1024, 'Reference exceeds 8 MiB decoded limit.')
    def unique(pairs):
        out = {}
        for k, v in pairs:
            require(k not in out, 'Duplicate packed-reference JSON key.')
            out[k] = v
        return out
    try:
        packed = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
            parse_constant=lambda _: require(False, 'Non-finite packed-reference number.'))
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('Packed reference must be valid bounded UTF-8 JSON.') from exc
    require(isinstance(packed, dict) and set(packed) == {'kind','decoded_sha256','metadata','runs'}
            and packed['kind'] == 'bntex-packed-oracle-v1', 'Invalid packed reference.')
    meta, runs = packed['metadata'], packed['runs']
    require(isinstance(meta, dict) and 'records' not in meta and isinstance(runs, list)
            and 0 < len(runs) <= 10000, 'Invalid packed metadata or rows.')
    rows, seen = [], set()
    for item in runs:
        require(isinstance(item, list) and len(item) == 2 and isinstance(item[0], str),
                'Invalid packed reference row.')
        cid, glyphs = item
        require(cid.startswith('u-') and len(cid) <= 80 and cid not in seen, 'Invalid/duplicate packed ID.')
        parts = cid[2:].split('-')
        require(all(p and len(p) <= 6 and all(c in '0123456789abcdef' for c in p) for p in parts),
                'Invalid code-point ID.')
        try:
            source = ''.join(chr(int(p, 16)) for p in parts).encode('utf-8')
        except (ValueError, UnicodeError) as exc:
            raise ValueError('Invalid Unicode in packed ID.') from exc
        require(isinstance(glyphs, list) and 0 < len(glyphs) <= 16384 and
                all(isinstance(g, list) and len(g) == 7 and all(type(v) is int for v in g)
                    for g in glyphs), 'Packed glyph rows require seven integer fields.')
        seen.add(cid)
        rows.append({'id': cid, 'source_sha256': hashlib.sha256(source).hexdigest(),
                     'outcome': 'shape', 'glyphs': glyphs})
    decoded = serialize(dict(meta, records=rows))
    require(hashlib.sha256(decoded).hexdigest() == packed['decoded_sha256'],
            'Reconstructed oracle digest mismatch; reference is corrupted.')
    return decoded


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'coverage', 'unpack-oracle'])
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--oracle', type=Path)
    parser.add_argument('--corpus', type=Path, action='append', default=[])
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'unpack-oracle':
            require(args.oracle is not None and args.out is not None, 'unpack-oracle requires --oracle and --out.')
            require(args.out.resolve() != args.oracle.resolve(), 'Output must not replace an input.')
            write_output(args.out, unpack_oracle(args.oracle))
            return 0
        require(args.inventory is not None, '--inventory is required.')
        if args.command == 'build':
            require(args.out is not None, 'build requires --out.')
            result = make_corpus(args.inventory)
        else:
            require(bool(args.corpus), 'coverage requires --corpus.')
            result = coverage(args.inventory, args.corpus)
        if args.out is not None:
            require(args.out.resolve() not in {p.resolve() for p in [args.inventory, *args.corpus]}, 'Output must not replace an input.')
            write_output(args.out, serialize(result))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, UnicodeError, EOFError) as exc:
        print(f'bntex inventory: {exc}', file=sys.stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())
