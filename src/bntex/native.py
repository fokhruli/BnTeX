"""Compile a font profile or run the independent Bengali model.

Examples: python -m bntex.native compile --font FONT.ttf --out profile.json
          python -m bntex.native shape --profile profile.json --text 'কর্মে' --trace
The shape command needs only Python's standard library and these native modules.
It does not load a font, HarfBuzz, FontTools, or a vocabulary cache.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from .native_profile import compile_profile, load_profile, serialize
from .native_model import NativeShaper, DecodedInput
from .native_layout import ShapingError


def read_json(path: Path, maximum: int = 8 * 1024 * 1024):
    if path.stat().st_size > maximum: raise ValueError('JSON exceeds size limit')
    raw = path.read_bytes()
    if len(raw) > maximum: raise ValueError('JSON exceeds size limit')
    def unique(pairs):
        d = {}
        for key, value in pairs:
            if key in d: raise ValueError(f'duplicate JSON key: {key}')
            d[key] = value
        return d
    def bad(value): raise ValueError(f'nonfinite JSON number: {value}')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=bad)
    if not isinstance(value, dict): raise ValueError('expected JSON object')
    return value, hashlib.sha256(raw).hexdigest()


def write_new(path: Path, raw: bytes, protected: list[Path]):
    """Never replace inputs or existing user work; remove a failed partial write."""
    if path.is_symlink() or path.resolve() in {p.resolve() for p in protected}:
        raise ValueError('output must not replace an input or symbolic link')
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open('xb')
    try:
        with stream: stream.write(raw)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def check_reference(shaper: NativeShaper, corpus_path: Path, oracle_path: Path):
    """Compare frozen shaped cases without importing or executing an oracle engine.

    The ten input-rejection cases of the original corpus are separate contracts;
    this report names them as not compared, never as matched glyph runs.
    """
    corpus, digest = read_json(corpus_path)
    oracle, _ = read_json(oracle_path)
    if not isinstance(oracle.get('font'), dict) or not isinstance(oracle.get('toolchain'), dict):
        raise ValueError('reference font/toolchain metadata must be objects')
    if (type(oracle.get('schema')) is not int or oracle['schema'] != 1
            or type(oracle.get('generator_abi')) is not int or oracle['generator_abi'] != 1
            or oracle['toolchain'].get('harfbuzz') != '10.2.0'):
        raise ValueError('reference schema or pinned shaper version mismatch')
    if (oracle.get('kind') != 'bntex-pinned-shaping-oracle' or oracle.get('corpus_sha256') != digest
            or oracle.get('corpus_version') != corpus.get('version')
            or oracle.get('font', {}).get('sha256') != shaper.profile.font_sha256):
        raise ValueError('reference source/font provenance mismatch')
    config = oracle.get('config', {})
    required = {'direction': 'ltr', 'script': 'Beng', 'language': 'bn', 'cluster_level': 0,
                'cluster_units': 'utf8-bytes', 'buffer_flags': 0, 'features': 'HarfBuzz defaults',
                'face_index': 0, 'scale': 'upem', 'font_funcs': 'ot',
                'normalization': 'HarfBuzz internal; source preserved'}
    fields = ['gid','cluster','x_advance','y_advance','x_offset','y_offset','flags']
    if (config != required or oracle.get('glyph_fields') != fields
            or any(type(config[k]) is not type(v) for k, v in required.items())):
        raise ValueError('reference shaping configuration mismatch')
    cases, rows = corpus.get('cases'), oracle.get('records')
    if not isinstance(cases, list) or not isinstance(rows, list) or not 0 < len(cases) <= 10000 or len(rows) != len(cases):
        raise ValueError('invalid reference case counts')
    compared = 0; rejected = 0; failures = []; ids = set()
    for case, row in zip(cases, rows):
        if not isinstance(case, dict) or not isinstance(row, dict):
            raise ValueError('reference cases and rows must be objects')
        cid = case.get('id')
        if not isinstance(cid, str) or cid in ids or row.get('id') != cid:
            raise ValueError('duplicate/reordered reference IDs')
        ids.add(cid)
        raw = bytes.fromhex(case['utf8_hex'])
        if row.get('source_sha256') != hashlib.sha256(raw).hexdigest() or row.get('outcome') != case.get('expect'):
            raise ValueError(f'{cid}: reference source/outcome mismatch')
        if case['expect'] != 'shape':
            if case['expect'] not in {'invalid-utf8','empty','nul','missing-glyph'}:
                raise ValueError('unknown rejection outcome')
            rejected += 1; continue
        text = raw.decode('utf-8')
        if case.get('text') != text: raise ValueError(f'{cid}: source byte/text mismatch')
        expected = row.get('glyphs')
        if not isinstance(expected, list) or not expected or any(
                not isinstance(g, list) or len(g) != 7 or any(type(x) is not int for x in g) for g in expected):
            raise ValueError(f'{cid}: invalid reference glyph rows')
        try:
            result = shaper.shape(text, allow_broken=True)
            actual = [[getattr(g, name) for name in fields] for g in result.glyphs]
            if actual != expected: failures.append({'id':cid,'expected':expected,'actual':actual})
        except ShapingError as exc:
            failures.append({'id':cid,'error':str(exc)})
        compared += 1
    return {'status':'mismatch' if failures else 'exact-match', 'compared_shaped_cases':compared,
            'input_rejection_cases_not_compared':rejected, 'mismatches':len(failures),
            'details':failures[:20], 'reference_engine_executed':False,
            'model':'bntex-bengali-model-v1', 'font_sha256':shaper.profile.font_sha256,
            'profile_sha256':shaper.identity, 'human_review':'not-implied', 'tex_native':False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('compile'); p.add_argument('--font',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
    p = sub.add_parser('shape'); p.add_argument('--profile',type=Path,required=True)
    source = p.add_mutually_exclusive_group(required=True); source.add_argument('--text'); source.add_argument('--decoded',type=Path)
    p.add_argument('--trace',action='store_true'); p.add_argument('--allow-broken',action='store_true'); p.add_argument('--out',type=Path)
    p = sub.add_parser('check'); p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--corpus',type=Path,required=True); p.add_argument('--oracle',type=Path,required=True); p.add_argument('--out',type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'compile':
            profile = compile_profile(args.font); raw = serialize(profile)
            write_new(args.out, raw, [args.font])
            print(json.dumps({'profile':str(args.out),'sha256':hashlib.sha256(raw).hexdigest(),
                  'font_sha256':profile.font_sha256,'gsub_lookups':len(profile.gsub),'gpos_lookups':len(profile.gpos),
                  'document_input':False,'tex_native':False},indent=2)); return 0
        shaper = NativeShaper(load_profile(args.profile)); protected = [args.profile]
        if args.command == 'shape':
            if args.decoded:
                data, _ = read_json(args.decoded, 256*1024); protected.append(args.decoded)
                if set(data) != {'scalars','byte_offsets','byte_lengths','utf8_hex'}:
                    raise ValueError('decoded input requires exactly scalars, byte_offsets, byte_lengths, utf8_hex')
                result = shaper.shape_decoded(DecodedInput(**data),trace=args.trace,allow_broken=args.allow_broken)
            else: result = shaper.shape(args.text,trace=args.trace,allow_broken=args.allow_broken)
            obj = result.to_dict(); code = 0
        else:
            protected += [args.corpus,args.oracle]
            obj = check_reference(shaper,args.corpus,args.oracle); code = int(obj['status']!='exact-match')
        raw = (json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        if args.out: write_new(args.out,raw,protected)
        else: print(raw.decode('utf-8'),end='')
        return code
    except (OSError,ValueError,TypeError,KeyError,RecursionError) as exc:
        print(f'bntex native: {exc}',file=sys.stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())
