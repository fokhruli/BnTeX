"""Deterministic font-bank and word-cache generation.

No TeX source is executed during scanning/preparation. Only the known pltotf
executable is invoked, with an argument list and no shell.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from dataclasses import asdict
from pathlib import Path
from fontTools import __version__ as fonttools_version
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from . import __version__
from .harfbuzz import HarfBuzz
from .source import STYLE, SourceError, scan, words

SCHEMA = 1


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tex_hash(text: str) -> str:
    # Cache lookup only; MD5 is not an authentication/security mechanism.
    return hashlib.md5(text.encode('utf-8'), usedforsecurity=False).hexdigest().upper()


def _num(v: float) -> str:
    return f'{v:.9f}'.rstrip('0').rstrip('.') or '0'


def inspect_font(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('A font must be a local file below 64 MiB.')
    with TTFont(path, lazy=False) as f:
        if 'glyf' not in f or 'fvar' in f:
            raise ValueError('Version 0.1 requires a static TrueType-outline font; '
                             'CFF, TTC and variable fonts are outside this profile.')
        if not {'OS/2', 'head', 'hmtx', 'name'}.issubset(f.keys()):
            raise ValueError('Font is missing required metadata/metric tables.')
        if f['OS/2'].fsType != 0:
            raise ValueError('This prototype accepts only fsType=0 fonts; '
                             'embedding/subsetting restrictions require separate review.')
        if 0x0995 not in (f.getBestCmap() or {}):
            raise ValueError('The font lacks the Bengali KA character.')
        psname = f['name'].getDebugName(6) or ''
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', psname):
            raise ValueError('Font has no safe PostScript name.')
        return {'sha256': digest(path.read_bytes()), 'postscript_name': psname,
                'family': f['name'].getDebugName(1), 'upem': f['head'].unitsPerEm,
                'glyph_count': len(f.getGlyphOrder()), 'fsType': f['OS/2'].fsType,
                'original_filename': path.name}


def _write_banks(stage: Path, path: Path, meta: dict, glyph_ids: set[int]) -> tuple[dict[int,str], list[str]]:
    """Preserve the original TTF byte-for-byte; reencode by glyph ID."""
    prefix = 'bnf' + meta['sha256'][:16]
    fontfile = prefix + '.ttf'
    shutil.copyfile(path, stage / fontfile)
    mapping: dict[int,str] = {}
    maplines: list[str] = []
    with TTFont(path) as f:
        order = f.getGlyphOrder(); upem = meta['upem']
        for bank in sorted({gid // 256 for gid in glyph_ids}):
            basename = f'{prefix}b{bank}'
            selected = {gid % 256: gid for gid in glyph_ids if gid // 256 == bank}
            entries = [f'/index{selected[i]}' if i in selected else '/.notdef' for i in range(256)]
            enc = '/' + basename + 'Encoding [\n' + '\n'.join(' '.join(entries[i:i+8]) for i in range(0,256,8)) + '\n] def\n'
            (stage / (basename + '.enc')).write_text(enc, encoding='ascii')
            pl = ['(FAMILY BNTEX)', '(CODINGSCHEME BNTEX-GLYPH-BANK)', '(DESIGNSIZE R 10.0)',
                  '(FONTDIMEN (SLANT R 0.0) (SPACE R 0.25) (STRETCH R 0.12) '
                  '(SHRINK R 0.08) (XHEIGHT R 0.5) (QUAD R 1.0))']
            for slot, gid in sorted(selected.items()):
                advance = f['hmtx'][order[gid]][0] / upem
                # Height/depth are assigned from precise word ink bounds at runtime.
                pl.append(f'(CHARACTER D {slot} (CHARWD R {_num(advance)}) '
                          '(CHARHT R 0.0) (CHARDP R 0.0))')
                mapping[gid] = basename
            plpath = stage / (basename + '.pl'); plpath.write_text('\n'.join(pl)+'\n', encoding='ascii')
            proc = subprocess.run(['pltotf', plpath.name, basename+'.tfm'], cwd=stage,
                                  text=True, capture_output=True, timeout=30, check=False)
            if proc.returncode != 0:
                raise RuntimeError('pltotf failed: ' + proc.stdout + proc.stderr)
            if 'round' in (proc.stdout + proc.stderr).lower():
                # Explicit positions do not depend on the rounded natural TFM width.
                meta.setdefault('metric_warnings', []).append((proc.stdout+proc.stderr).strip())
            maplines.append(f'\\pdfmapline{{+{basename} {meta["postscript_name"]} <{basename}.enc <{fontfile}}}')
    meta['prepared_font_filename'] = fontfile
    meta['banks'] = sorted(set(mapping.values()))
    return mapping, maplines


def _style_cache(stage: Path, alias: str, path: Path, vocabulary: list[str]) -> tuple[list[str], dict]:
    meta = inspect_font(path)
    with HarfBuzz(path) as hb, TTFont(path) as f:
        meta['harfbuzz_version'] = hb.version
        glyphset = f.getGlyphSet(); order = f.getGlyphOrder(); upem = meta['upem']
        if hb.upem != upem: raise RuntimeError('Font metrics disagree about units per em.')
        runs = {w: hb.shape(w) for w in vocabulary}
        mapping, maplines = _write_banks(stage, path, meta, {g.gid for run in runs.values() for g in run})
        space_name = f.getBestCmap().get(32)
        space = f['hmtx'][space_name][0] / upem if space_name else 0.25
        code = maplines + [f'\\BnTeXDeclareStyle{{{alias}}}{{{_num(space)}}}']
        records = []
        bounds_cache = {}
        for text, run in runs.items():
            x = 0; min_y = 0; max_y = 0; min_x = 0; max_x = 0; glyph_tex = []
            for g in run:
                if g.gid not in bounds_cache:
                    pen = BoundsPen(glyphset); glyphset[order[g.gid]].draw(pen)
                    bounds_cache[g.gid] = pen.bounds
                bounds = bounds_cache[g.gid]
                gx, gy = x + g.x_offset, g.y_offset
                if bounds:
                    a,b,c,d = bounds
                    min_y = min(min_y, gy+b); max_y = max(max_y, gy+d)
                    min_x = min(min_x, gx+a); max_x = max(max_x, gx+c)
                glyph_tex.append(f'\\BnTeXGlyph{{{mapping[g.gid]}}}{{{g.gid%256}}}'
                                 f'{{{_num(gx/upem)}}}{{{_num(gy/upem)}}}')
                x += g.x_advance
            if x <= 0: raise ValueError(f'Nonpositive word width for {text!r}.')
            key = tex_hash(text); actual = text.encode('utf-16-be').hex().upper()
            code.append(f'\\BnTeXDeclareWord{{{alias}}}{{{key}}}'
                        f'{{{_num(x/upem)}}}{{{_num(max_y/upem)}}}{{{_num(-min_y/upem)}}}'
                        f'{{{actual}}}{{' + ''.join(glyph_tex) + '}')
            records.append({'text': text, 'nfc': unicodedata.normalize('NFC',text), 'key':key,
                            'advance_fu': x, 'ink_bbox_fu': [min_x,min_y,max_x,max_y],
                            'glyphs': [asdict(g) for g in run]})
        meta['word_count'] = len(records); meta['runs'] = records
        return code, meta


def prepare(sources: list[Path], fonts: dict[str,Path], out: Path, *, package_root: Path | None = None) -> dict:
    """Write into a fresh or previously marked generated directory atomically."""
    if not shutil.which('pltotf'):
        raise RuntimeError('pltotf is missing; install a TeX distribution before preparing.')
    if 'regular' not in fonts:
        raise ValueError('A regular font style is required.')
    if any(not STYLE.fullmatch(a) or a == 'auto' for a in fonts):
        raise ValueError('Style names must match [a-z][a-z0-9-]{0,31}; auto is reserved.')
    if not sources: raise ValueError('At least one source is required.')
    reserved = {'.bntex-build', 'bntex.sty', 'bntex-cache.tex', 'bntex-manifest.json'}
    if any(p.name in reserved or p.suffix.lower() != '.tex' for p in sources):
        raise ValueError('Source inputs must be .tex files with non-reserved basenames.')
    if len({p.name for p in sources}) != len(sources):
        raise ValueError('Source basenames must be unique; automatic path rewriting is not implemented.')
    out = out.resolve()
    for p in sources + list(fonts.values()):
        if out == p.resolve() or out in p.resolve().parents:
            raise ValueError('Inputs must not live inside the generated output directory.')
    if out.exists() and not out.is_dir(): raise ValueError('Output must be a directory.')
    if out.exists() and any(out.iterdir()) and not (out/'.bntex-build').is_file():
        raise ValueError('Refusing to replace a nonempty unmarked directory.')
    vocabulary: set[str] = set(); requested_styles: set[str] = set(); source_records = []
    for src in sources:
        data = src.read_bytes()
        if len(data)>8*1024*1024: raise ValueError('Source exceeds the 8 MiB preparation limit.')
        try:
            text = data.decode('utf-8-sig', errors='strict')
        except UnicodeDecodeError as exc:
            # Locate the invalid byte after the valid decoded prefix.
            prefix = data[:exc.start].decode('utf-8-sig', errors='replace')
            raise SourceError('Invalid UTF-8 source bytes.', prefix + '\ufffd',
                              len(prefix), str(src)) from exc
        spans = scan(text, filename=str(src))
        for span in spans:
            if span.style != 'auto' and span.style not in fonts:
                raise SourceError(f'Unprepared style requested by source: {span.style!r}.',
                                  text, span.offset, str(src))
            vocabulary.update(words(span.text)); requested_styles.add(span.style)
        source_records.append({'filename':src.name,'sha256':digest(data),'span_count':len(spans)})
    missing = requested_styles - set(fonts) - {'auto'}
    if missing: raise ValueError(f'Unprepared styles requested by source: {sorted(missing)}')
    if not vocabulary: raise ValueError('No nonempty literal \\bn spans found.')
    if len(vocabulary)>100000: raise ValueError('Vocabulary exceeds prototype safety limit.')
    sty = (package_root/'tex'/'latex'/'bntex'/'bntex-cached.sty' if package_root
           else Path(__file__).resolve().parent/'data'/'bntex-cached.sty')
    if not sty.is_file(): raise FileNotFoundError('Installation is incomplete: bundled bntex-cached.sty was not found.')
    out.parent.mkdir(parents=True,exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.bntex-stage-', dir=out.parent))
    try:
        (stage/'.bntex-build').write_text('Generated BnTeX build; edits may be replaced.\n')
        shutil.copyfile(sty,stage/'bntex-cached.sty')
        (stage/'bntex.sty').write_text(
            '% Legacy prepared-project shim; installed bntex defaults to native.\n'
            r'\ProvidesPackage{bntex}[2026/09/26 Legacy prepared project]'+'\n'
            r'\RequirePackage{bntex-cached}'+'\n'+r'\endinput'+'\n', encoding='ascii')
        for src in sources: shutil.copyfile(src,stage/src.name)
        code = []; style_metadata={}
        # Identical font files for different aliases are permitted. Deduplicate map lines later.
        for alias, path in sorted(fonts.items()):
            lines, info = _style_cache(stage,alias,path,sorted(vocabulary))
            code.extend(lines); style_metadata[alias]=info
        checks=[]
        for p in sorted(stage.iterdir()):
            if p.suffix in {'.ttf','.tfm','.enc'}:
                md5=hashlib.md5(p.read_bytes(),usedforsecurity=False).hexdigest().upper()
                checks.append(f'\\BnTeXCheckFile{{{p.name}}}{{{md5}}}')
        deduped=[]; seen=set()
        for line in code:
            if line.startswith('\\pdfmapline'):
                if line in seen: continue
                seen.add(line)
            deduped.append(line)
        (stage/'bntex-cache.tex').write_text('% Generated BnTeX cache. Schema 1. No shell commands.\n'+
                                           '\n'.join(checks+deduped)+'\n',encoding='ascii')
        manifest={'schema':SCHEMA,'bntex_version':__version__,'fonttools_version':fonttools_version,
                  'normalization':'raw UTF-8 lookup; HarfBuzz internal shaping normalization',
                  'direction':'ltr','script':'Beng','language':'bn','features':'HarfBuzz defaults',
                  'sources':source_records,'styles':style_metadata,'files':{}}
        for p in sorted(stage.iterdir()):
            if p.is_file(): manifest['files'][p.name]=digest(p.read_bytes())
        (stage/'bntex-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        # Do not delete any existing build until the new one is complete.
        backup=None
        if out.exists():
            backup=Path(tempfile.mkdtemp(prefix='.bntex-backup-',dir=out.parent)); backup.rmdir()
            os.replace(out,backup)
        try: os.replace(stage,out)
        except BaseException:
            if backup is not None: os.replace(backup,out)
            raise
        if backup is not None: shutil.rmtree(backup)
        return manifest
    finally:
        if stage.exists(): shutil.rmtree(stage)


def verify(out: Path) -> dict:
    manifest=json.loads((out/'bntex-manifest.json').read_text(encoding='utf8'))
    if manifest.get('schema') != SCHEMA: raise ValueError('Unsupported cache schema.')
    for name, expected in manifest['files'].items():
        if Path(name).name != name: raise ValueError('Unsafe path in manifest.')
        p=out/name
        if not p.is_file() or digest(p.read_bytes()) != expected:
            raise ValueError(f'Prepared file changed or disappeared: {name}')
    return manifest
