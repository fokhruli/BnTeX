"""Versioned Bengali corpus, pinned HarfBuzz oracle, and explicit human review.

Run ``python -m bntex.corpus --help``. This module never implements native
shaping, downloads fonts, calls a shell, or turns generated results into reviews.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata
from typing import Any

from fontTools import __version__ as fonttools_version
from fontTools.ttLib import TTLibError
from .build import inspect_font
from .harfbuzz import HarfBuzz
from . import harfbuzz as adapter

SCHEMA = 1
FIELDS = ['gid', 'cluster', 'x_advance', 'y_advance', 'x_offset', 'y_offset', 'flags']
CONFIG = {'direction': 'ltr', 'script': 'Beng', 'language': 'bn',
          'cluster_level': 0, 'cluster_units': 'utf8-bytes', 'buffer_flags': 0,
          'features': 'HarfBuzz defaults', 'face_index': 0,
          'scale': 'upem', 'font_funcs': 'ot', 'normalization': 'HarfBuzz internal; source preserved'}
EXPECT = {'shape', 'invalid-utf8', 'empty', 'nul', 'missing-glyph'}
IDENT = re.compile(r'[a-z][a-z0-9-]{0,79}\Z')
HEX = re.compile(r'(?:[0-9a-f]{2})*\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
MAX_FILE = 8 * 1024 * 1024


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f'Duplicate JSON key: {key!r}')
        result[key] = value
    return result


def read_json(path: Path) -> tuple[dict, str]:
    require(path.stat().st_size <= MAX_FILE, 'JSON input exceeds 8 MiB.')
    raw = path.read_bytes()
    require(len(raw) <= MAX_FILE, 'JSON input exceeds 8 MiB.')
    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                          parse_constant=lambda x: require(False, f'Non-finite JSON number: {x}'))
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('JSON must be bounded, valid UTF-8.') from exc
    require(isinstance(data, dict), 'Expected a JSON object.')
    return data, sha(raw)


def serialize(data: dict) -> bytes:
    """Stable readable header, with one case/record/entry per line."""
    lines = ['{']
    for i, key in enumerate(sorted(data)):
        value = data[key]
        prefix = '  ' + json.dumps(key) + ': '
        if key in {'cases', 'records', 'entries'} and isinstance(value, list):
            rendered = '[\n' + ',\n'.join('    ' + json.dumps(v, ensure_ascii=False,
                sort_keys=True, separators=(',', ':')) for v in value) + '\n  ]'
        else:
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).replace('\n', '\n  ')
        lines.append(prefix + rendered + (',' if i < len(data) - 1 else ''))
    return ('\n'.join(lines) + '\n}\n').encode('utf-8')


def write_output(path: Path, raw: bytes, *, force: bool = False) -> None:
    """Do not clobber existing work by default; forced writes replace atomically."""
    require(not path.is_symlink(), 'Refusing to replace a symbolic link.')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not force:
        with path.open('xb') as out:
            out.write(raw)
        return
    fd, temporary = tempfile.mkstemp(prefix='.bntex-corpus-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(raw)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_corpus(path: Path) -> tuple[dict, str]:
    data, identity = read_json(path)
    require(type(data.get('schema')) is int and data['schema'] == SCHEMA, 'Unsupported corpus schema.')
    require(isinstance(data.get('version'), str) and bool(data['version']), 'Missing corpus version.')
    categories, cases = data.get('categories'), data.get('cases')
    require(isinstance(categories, dict) and bool(categories), 'Missing category index.')
    require(all(isinstance(k, str) and IDENT.fullmatch(k) and isinstance(v, str) and v
                for k, v in categories.items()), 'Invalid category metadata.')
    require(isinstance(cases, list) and 0 < len(cases) <= 10000, 'Expected 1..10000 corpus cases.')
    ids, used, equivalents = set(), set(), {}
    for item in cases:
        require(isinstance(item, dict), 'A corpus case must be an object.')
        cid = item.get('id')
        require(isinstance(cid, str) and IDENT.fullmatch(cid) and cid not in ids, 'Invalid/duplicate case ID.')
        ids.add(cid)
        category = item.get('category')
        require(isinstance(category, str) and category in categories, f'{cid}: unknown category.')
        used.add(category)
        expected, rawhex = item.get('expect'), item.get('utf8_hex')
        require(isinstance(expected, str) and expected in EXPECT, f'{cid}: unknown expected outcome.')
        require(isinstance(rawhex, str) and HEX.fullmatch(rawhex) and len(rawhex) <= 32768,
                f'{cid}: invalid or excessive lowercase byte hex.')
        require(isinstance(item.get('notes'), str) and len(item['notes']) <= 2048, f'{cid}: missing/big notes.')
        raw = bytes.fromhex(rawhex)
        try:
            text = raw.decode('utf-8', errors='strict')
        except UnicodeDecodeError:
            require(expected == 'invalid-utf8' and 'text' not in item,
                    f'{cid}: invalid UTF-8 must be a byte-only rejection case.')
            continue
        require(expected != 'invalid-utf8', f'{cid}: rejection bytes are valid UTF-8.')
        require(item.get('text') == text, f'{cid}: text/UTF-8 mismatch; original bytes must be preserved.')
        require(len(text) <= 4096, f'{cid}: text exceeds the adapter limit.')
        outcome = 'empty' if not text else 'nul' if '\0' in text else 'shape'
        require(expected == outcome or (expected == 'missing-glyph' and outcome == 'shape'),
                f'{cid}: incorrect input rejection category.')
        if 'equivalence_group' in item:
            group = item['equivalence_group']
            require(isinstance(group, str) and IDENT.fullmatch(group) and expected == 'shape',
                    f'{cid}: invalid equivalence group.')
            equivalents.setdefault(group, []).append(text)
    require(used == set(categories), 'Every declared category must contain a case.')
    for group, texts in equivalents.items():
        require(len(set(texts)) >= 2 and len({unicodedata.normalize('NFC', t) for t in texts}) == 1,
                f'{group}: expected distinct canonically equivalent source strings.')
    return data, identity


def _run(item: dict, hb: HarfBuzz) -> dict:
    raw = bytes.fromhex(item['utf8_hex'])
    result = {'id': item['id'], 'source_sha256': sha(raw)}
    try:
        text = raw.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        return dict(result, outcome='invalid-utf8')
    if not text or '\0' in text:
        return dict(result, outcome='empty' if not text else 'nul')
    try:
        glyphs = hb.shape(text, script=CONFIG['script'], language=CONFIG['language'])
    except ValueError as exc:
        if 'Font has a missing glyph' not in str(exc):
            raise
        return dict(result, outcome='missing-glyph')
    rows = [[asdict(g)[f] for f in FIELDS] for g in glyphs]
    return dict(result, outcome='shape', glyphs=rows)


def record(corpus_path: Path, font: Path) -> dict:
    corpus, identity = load_corpus(corpus_path)
    meta = inspect_font(font)
    # A path or renamed identical font file must not alter reference identity.
    meta.pop('original_filename', None)
    with HarfBuzz(font) as hb:
        records = [_run(item, hb) for item in corpus['cases']]
        for item, row in zip(corpus['cases'], records):
            require(row['outcome'] == item['expect'], f'{item["id"]}: unexpected outcome {row["outcome"]}.')
        return {'schema': SCHEMA, 'kind': 'bntex-pinned-shaping-oracle', 'corpus_sha256': identity,
                'corpus_version': corpus['version'], 'font': meta, 'config': CONFIG.copy(),
                'glyph_fields': FIELDS.copy(), 'toolchain': {'harfbuzz': hb.version,
                'fonttools': fonttools_version, 'python_unicodedata': unicodedata.unidata_version,
                'adapter_sha256': sha(Path(adapter.__file__).read_bytes())},
                'generator_abi': 1, 'human_review': 'not-performed', 'records': records}


def load_oracle(corpus_path: Path, oracle_path: Path) -> tuple[dict, dict, str]:
    corpus, identity = load_corpus(corpus_path)
    oracle, oracle_identity = read_json(oracle_path)
    require(type(oracle.get('schema')) is int and oracle['schema'] == SCHEMA, 'Unsupported oracle schema.')
    require(oracle.get('kind') == 'bntex-pinned-shaping-oracle' and oracle.get('generator_abi') == 1,
            'Unsupported oracle kind/ABI.')
    require(oracle.get('corpus_sha256') == identity and oracle.get('corpus_version') == corpus['version'],
            'Corpus provenance mismatch. Do not silently regenerate the reference.')
    require(oracle.get('config') == CONFIG and oracle.get('glyph_fields') == FIELDS, 'Shaping configuration mismatch.')
    require(oracle.get('human_review') == 'not-performed', 'An oracle cannot certify human review.')
    font, tools, rows = oracle.get('font'), oracle.get('toolchain'), oracle.get('records')
    require(isinstance(font, dict) and isinstance(font.get('sha256'), str) and SHA.fullmatch(font['sha256']),
            'Invalid font fingerprint.')
    require(type(font.get('glyph_count')) is int and font['glyph_count'] > 0 and
            type(font.get('upem')) is int and font['upem'] > 0, 'Invalid font metric metadata.')
    require(isinstance(tools, dict) and set(tools) == {'harfbuzz','fonttools','python_unicodedata','adapter_sha256'}
            and all(isinstance(v,str) and v for v in tools.values()) and SHA.fullmatch(tools['adapter_sha256']),
            'Incomplete oracle toolchain provenance.')
    require(isinstance(rows, list) and len(rows) == len(corpus['cases']), 'Oracle case count mismatch.')
    for item, row in zip(corpus['cases'], rows):
        cid = item['id']; raw = bytes.fromhex(item['utf8_hex'])
        require(isinstance(row, dict) and row.get('id') == cid, f'{cid}: missing/reordered oracle case.')
        require(row.get('source_sha256') == sha(raw), f'{cid}: source provenance mismatch.')
        require(row.get('outcome') == item['expect'], f'{cid}: wrong oracle outcome.')
        if row['outcome'] != 'shape':
            require(set(row) == {'id','source_sha256','outcome'}, f'{cid}: rejected case contains glyph data.')
            continue
        require(set(row) == {'id','source_sha256','outcome','glyphs'}, f'{cid}: unexpected oracle fields.')
        glyphs = row.get('glyphs')
        require(isinstance(glyphs,list) and 0 < len(glyphs) <= 16384, f'{cid}: invalid glyph run.')
        offsets, position = set(), 0
        for char in item['text']:
            offsets.add(position); position += len(char.encode('utf-8'))
        last = -1
        for glyph in glyphs:
            require(isinstance(glyph,list) and len(glyph)==7 and all(type(v) is int for v in glyph),
                    f'{cid}: glyph rows require seven integer fields.')
            gid, cluster, ax, ay, dx, dy, flags = glyph
            require(0 < gid < font['glyph_count'] and cluster in offsets and cluster >= last,
                    f'{cid}: invalid GID or nonmonotone/non-byte-boundary cluster.')
            require(ay == 0 and flags >= 0 and flags <= 7 and
                    all(-(2**31) <= n < 2**31 for n in (ax,ay,dx,dy)), f'{cid}: invalid positions/flags.')
            last = cluster
    return corpus, oracle, oracle_identity


def compare(expected: dict, actual: dict) -> list[str]:
    """Exact equality with field-specific diagnostics; no tolerance or rebaseline."""
    failures = []
    for key in sorted((set(expected) | set(actual)) - {'records'}):
        if expected.get(key) != actual.get(key):
            failures.append(f'provenance.{key}: mismatch')
    erows, arows = expected.get('records', []), actual.get('records', [])
    if len(erows) != len(arows):
        failures.append('records: count mismatch')
    for e, a in zip(erows, arows):
        label = e['id']
        for field in ('id','source_sha256','outcome'):
            if e.get(field) != a.get(field):
                failures.append(f'{label}.{field}: mismatch')
        eg, ag = e.get('glyphs', []), a.get('glyphs', [])
        if len(eg) != len(ag):
            failures.append(f'{label}.glyphs: length mismatch')
        for index, (left, right) in enumerate(zip(eg, ag)):
            for field, x, y in zip(FIELDS, left, right):
                if x != y:
                    failures.append(f'{label}.glyphs[{index}].{field}: expected {x}, got {y}')
    if not failures and serialize(expected) != serialize(actual):
        failures.append('records: structural or numeric-type mismatch')
    return failures


def check(corpus_path: Path, oracle_path: Path, font: Path) -> dict:
    corpus, expected, _ = load_oracle(corpus_path, oracle_path)
    actual = record(corpus_path, font)
    failures = compare(expected, actual)
    require(not failures, 'Oracle mismatch:\n' + '\n'.join(failures[:30]))
    return {'status': 'exact-match', 'cases': len(corpus['cases']),
            'shaped': sum(c['expect']=='shape' for c in corpus['cases']), 'human_review': 'not-performed'}


def review_template(corpus_path: Path, oracle_path: Path) -> dict:
    corpus, oracle, identity = load_oracle(corpus_path, oracle_path)
    return {'schema':SCHEMA, 'kind':'bntex-human-review', 'corpus_sha256':oracle['corpus_sha256'],
            'oracle_sha256':identity, 'font_sha256':oracle['font']['sha256'],
            'entries':[{'id':c['id'], 'status':'unreviewed', 'reviewer':None, 'reviewer_kind':None,
                        'date':None, 'notes':'', 'unresolved_variants':[]} for c in corpus['cases'] if c['expect']=='shape']}


def review_status(corpus_path: Path, oracle_path: Path, review_path: Path) -> dict:
    template = review_template(corpus_path, oracle_path)
    review, _ = read_json(review_path)
    require(type(review.get('schema')) is int, 'Invalid review schema type.')
    for key, value in template.items():
        if key != 'entries':
            require(review.get(key)==value, f'Review provenance mismatch: {key}.')
    entries = review.get('entries')
    require(isinstance(entries,list) and len(entries)==len(template['entries']), 'Review case count mismatch.')
    counts = Counter()
    for expected, entry in zip(template['entries'],entries):
        require(isinstance(entry,dict) and set(entry)==set(expected) and entry.get('id')==expected['id'],
                'Invalid/missing/reordered review entry.')
        status = entry['status']; cid=entry['id']
        require(isinstance(status,str) and status in {'unreviewed','accepted','rejected','needs-discussion'}, f'{cid}: invalid review status.')
        require(isinstance(entry['notes'],str) and isinstance(entry['unresolved_variants'],list)
                and all(isinstance(x,str) and x.strip() for x in entry['unresolved_variants']), f'{cid}: invalid review notes.')
        if status=='unreviewed':
            require(all(entry[k] is None for k in ('reviewer','reviewer_kind','date')), f'{cid}: unreviewed entry has reviewer attribution.')
        else:
            require(entry['reviewer_kind']=='human' and isinstance(entry['reviewer'],str) and entry['reviewer'].strip()
                    and isinstance(entry['date'],str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',entry['date'])
                    and entry['notes'].strip(), f'{cid}: a human reviewer, ISO date, and notes are required.')
            date.fromisoformat(entry['date'])
        require(status!='accepted' or not entry['unresolved_variants'], f'{cid}: accepted review has unresolved variants.')
        counts[status]+=1
    return {'entries':len(entries), 'counts':dict(counts), 'all_accepted':counts['accepted']==len(entries),
            'identity_verification':'Maintainer must verify reviewer attribution; JSON is not authentication.'}


def review_tex(corpus_path: Path, oracle_path: Path) -> str:
    corpus, oracle, identity = load_oracle(corpus_path, oracle_path)
    from .source import words
    lines = [r'\documentclass[11pt]{article}', r'\usepackage[margin=18mm]{geometry}',
             r'\usepackage{bntex,longtable,array}', r'\BnTeXLoadCache{bntex-cache.tex}',
             r'\setlength{\parindent}{0pt}', r'\begin{document}',
             r'\section*{BnTeX: Bengali corpus review sheet}',
             r'Machine-generated reference. Human review has not been performed.\\',
             r'Malformed probes are not recommended spellings.\\',
             r'Font SHA-256: {\ttfamily\small '+oracle['font']['sha256'][:32]+r'\allowbreak '+oracle['font']['sha256'][32:]+r'}\\',
             r'Oracle SHA-256: {\ttfamily\small '+identity[:32]+r'\allowbreak '+identity[32:]+r'}\\',
             r'\begin{longtable}{@{}>{\raggedright\arraybackslash}p{.29\linewidth}>{\raggedright\arraybackslash}p{.31\linewidth}>{\raggedright\arraybackslash}p{.34\linewidth}@{}}',
             r'Case / category & Reference rendering & Original Unicode scalars \\ \hline',
             r'\endfirsthead', r'Case / category & Reference (not human-reviewed) & Original Unicode scalars \\ \hline',
             r'\endhead']
    for c in corpus['cases']:
        label = r'{\ttfamily\scriptsize '+c['id']+r'}\newline {\scriptsize '+c['category']+'}'
        if c['expect']=='shape':
            words(c['text'])  # Refuse TeX-special characters rather than emitting unsafe source.
            require(not any(x.isspace() for x in c['text']), 'Review sheet currently requires single runs without whitespace.')
            sample = r'{\fontsize{17.28}{23}\selectfont\bn{'+c['text']+'}}'
            scalars = ' '.join(f'{ord(x):04X}' for x in c['text'])
        else:
            sample = r'{\scriptsize Expected rejection: '+c['expect']+'}'
            scalars = 'bytes: '+' '.join(c['utf8_hex'][i:i+2] for i in range(0,len(c['utf8_hex']),2))
        lines.append(label+' & '+sample+r' & {\ttfamily\scriptsize '+scalars+r'} \\[8pt]')
    lines += [r'\end{longtable}',r'\end{document}']
    return '\n'.join(lines)+'\n'



def prepare_review(corpus_path: Path, oracle_path: Path, font: Path, out: Path) -> dict:
    """Build a review project only after an exact reference/font/toolchain check."""
    from .build import prepare
    destination = out.resolve()
    for source in (corpus_path, oracle_path, font):
        require(destination != source.resolve() and destination not in source.resolve().parents,
                'Review output must not contain or replace any input.')
    check(corpus_path, oracle_path, font)
    with tempfile.TemporaryDirectory(prefix='bntex-review-source-') as directory:
        source = Path(directory) / 'review.tex'
        source.write_text(review_tex(corpus_path, oracle_path), encoding='utf-8',newline='\n')
        manifest = prepare([source], {'regular': font}, out)
    return {'output': str(out), 'reference_check': 'exact-match',
            'prepared_words': manifest['styles']['regular']['word_count'],
            'human_review': 'not-performed'}



def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('validate','record','check','review-template','review-status','review-tex','review-build'):
        p=sub.add_parser(name);p.add_argument('--corpus',type=Path,required=True)
        if name in {'record','check','review-build'}:p.add_argument('--font',type=Path,required=True)
        if name not in {'validate','record'}:p.add_argument('--oracle',type=Path,required=True)
        if name in {'record','review-template','review-tex'}:
            p.add_argument('--out',type=Path,required=True);p.add_argument('--force',action='store_true')
        if name=='review-build':p.add_argument('--out',type=Path,required=True)
        if name=='review-status':
            p.add_argument('--reviews',type=Path,required=True);p.add_argument('--require-approved',action='store_true')
    args=parser.parse_args(argv)
    try:
        if args.command=='validate':
            c,h=load_corpus(args.corpus)
            result={'version':c['version'],'sha256':h,'cases':len(c['cases']),
                    'categories':dict(Counter(x['category'] for x in c['cases']))}
        elif args.command=='check': result=check(args.corpus,args.oracle,args.font)
        elif args.command=='review-build':
            result=prepare_review(args.corpus,args.oracle,args.font,args.out)
        elif args.command=='review-status':
            result=review_status(args.corpus,args.oracle,args.reviews)
            print(json.dumps(result,indent=2))
            return 1 if args.require_approved and not result['all_accepted'] else 0
        else:
            if args.command=='record':data=serialize(record(args.corpus,args.font))
            elif args.command=='review-template':data=serialize(review_template(args.corpus,args.oracle))
            else:data=review_tex(args.corpus,args.oracle).encode('utf-8')
            protected=[args.corpus,getattr(args,'oracle',None),getattr(args,'font',None)]
            require(args.out.resolve() not in [p.resolve() for p in protected if p], 'Output must not replace an input.')
            write_output(args.out,data,force=args.force)
            result={'written':str(args.out),'bytes':len(data)}
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,RuntimeError,TTLibError) as exc:
        print(f'bntex corpus: {exc}',file=sys.stderr);return 2


if __name__=='__main__':
    raise SystemExit(main())
