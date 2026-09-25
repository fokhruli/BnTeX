#!/usr/bin/env python3
"""Paired, serial native pdfTeX measurements; no preparation at compile time.

Accepts trusted font installations only. Copies manifest-listed files into fresh
run directories. Does not download anything, execute a shell, or change a font.
Runtime directories contain local font copies and MUST NOT be redistributed.
Only the returned JSON and rendered document PDFs are suitable evidence outputs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import time

STEMS = ('বাংলা ভাষা গবেষণা প্রযুক্তি শিক্ষা মানুষ পদ্ধতি ফলাফল '
         'পরীক্ষা গণিত বিজ্ঞান তথ্য সমাজ স্বাস্থ্য উন্নয়ন আলোচনা').split()
PHASES = {'normalize': '__bn_normalize:', 'syllables': '__bn_syllables:',
          'initial_reorder': '__bn_initial:', 'final_reorder': '__bn_final:',
          'position': '__bn_position:', 'render': '__bn_render:'}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tool(name: str) -> str:
    value = shutil.which(name)
    if not value:
        raise ValueError(f'required program is missing: {name}')
    return os.path.abspath(value)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate manifest key')
        result[key] = value
    return result


def installation(path: Path) -> tuple[dict[str, bytes], dict]:
    """Validate bounded, flat installed assets; never infer a source vocabulary."""
    if not path.is_dir() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('installation must be a non-symlink directory')
    manifest = path / 'native-installation.json'
    if manifest.is_symlink() or manifest.stat().st_size > 1024 * 1024:
        raise ValueError('unsafe installation manifest')
    meta = json.loads(manifest.read_text(encoding='utf-8'), object_pairs_hook=_unique)
    if (type(meta.get('abi')) is not int or meta['abi'] != 1 or 'vocabulary' not in meta
            or meta['vocabulary'] is not None or not isinstance(meta.get('files'), dict)
            or not 1 <= len(meta['files']) <= 64):
        raise ValueError('expected a vocabulary-free native ABI-1 installation')
    assets = {}
    for name, digest in meta['files'].items():
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', name)
                or name in {'.', '..'} or not re.fullmatch(r'[a-f0-9]{64}', digest)
                or Path(name).suffix not in {'.sty', '.def', '.tex', '.enc', '.tfm', '.ttf'}):
            raise ValueError('invalid installation filename or hash')
        source = path / name
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('missing or unsafe installation file')
        raw = source.read_bytes()
        if sha(raw) != digest:
            raise ValueError(f'installation asset changed: {name}')
        assets[name] = raw
    if not {'bntex-native.sty', 'bntex-native-profile.tex', 'bntex-native-tables.def'} <= assets.keys():
        raise ValueError('missing native installation components')
    return assets, meta


def source(pages: int, tokens: int, mode: str, memo: bool) -> tuple[str, dict, list[str]]:
    if type(pages) is not int or not 1 <= pages <= 100:
        raise ValueError('pages must be 1..100')
    if type(tokens) is not int or not 16 <= tokens <= 256 or type(memo) is not bool:
        raise ValueError('tokens must be 16..256 and memo must be Boolean')
    if mode not in {'repeated', 'distinct'}:
        raise ValueError('invalid token mode')
    numerals = str.maketrans('0123456789', '০১২৩৪৫৬৭৮৯')
    lines = [r'\documentclass[11pt]{article}', r'\usepackage[margin=25mm]{geometry}',
             r'\usepackage{bntex-native}']
    if memo:
        lines.append(r'\usepackage{bntex-native-memo}')
    lines += [r'\BnTeXNativeLoadProfile{bntex-native-profile.tex}',
              r'\begin{document}',
              r'\ifnum\pdfshellescape=0\else\errmessage{shell enabled}\fi', r'\raggedright']
    words = []
    for page in range(pages):
        lines.append(f'\\noindent Native benchmark page {page+1}.\\par\\medskip')
        for first in range(0, tokens, 16):
            batch = []
            for slot in range(first, min(first+16, tokens)):
                index = page*tokens+slot if mode == 'distinct' else slot % 16
                word = STEMS[slot % 16] + f'{index:05d}'.translate(numerals)
                batch.append(word)
                words.append(word)
            lines.append('\\noindent\\bnNative{' + ' '.join(batch) + '}\\par\\medskip')
        lines.append(r'\clearpage')
    if memo:
        lines.append(r'\BnTeXNativeMemoStats')
    lines.append(r'\end{document}')
    text = '\n'.join(lines) + '\n'
    spec = {'pages_requested': pages, 'tokens_per_page': tokens,
            'token_occurrences': len(words), 'distinct_tokens': len(set(words)),
            'mode': mode, 'memo_enabled': memo, 'source_sha256': sha(text.encode()),
            'workload': 'Bengali stems plus five Bengali digits; synthetic, not representative book prose.'}
    return text, spec, words


def run_bounded(argv: list[str], root: Path, env: dict, timeout: float):
    if not math.isfinite(timeout) or not 0 < timeout <= 7200:
        raise ValueError('timeout must be 0..7200 seconds')
    start = time.monotonic()
    process = subprocess.Popen(argv, cwd=root, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=(os.name == 'posix'))
    try:
        output, _ = process.communicate(timeout=timeout)
        return process.returncode, output, False, time.monotonic()-start
    except subprocess.TimeoutExpired:
        try:
            if os.name == 'posix':
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        output, _ = process.communicate()
        return None, output, True, time.monotonic()-start


def compile_run(root: Path, assets: dict[str, bytes], words: list[str], passes: int, timeout: float):
    engine = tool('pdflatex')
    records = []
    env = dict(os.environ, PATH='/no-bntex-executables', TEXINPUTS='.:',
               TEXMFHOME='/no-bntex-texmfhome', TEXMFCONFIG='/no-bntex-config',
               TEXMFVAR='/no-bntex-texmfvar', max_print_line='10000',
               openin_any='p', openout_any='p', MKTEXPK='0', MKTEXTFM='0',
               SOURCE_DATE_EPOCH='1', FORCE_SOURCE_DATE='1')
    for iteration in range(passes):
        timer = Path('/usr/bin/time')
        argv = [engine, '-no-shell-escape', '-halt-on-error', '-interaction=nonstopmode',
                '-recorder', 'main.tex']
        measure = root / f'measure-{iteration}.txt'
        if platform.system() == 'Linux' and timer.is_file():
            argv = [str(timer), '-f', '%M %U %S', '-o', measure.name, *argv]
        code, output, timed_out, elapsed = run_bounded(argv, root, env, timeout)
        (root / f'pass-{iteration}.stdout').write_bytes(output)
        log = (root / 'main.log').read_text(errors='replace') if (root / 'main.log').is_file() else ''
        (root / f'pass-{iteration}.log').write_text(log)
        fls = (root / 'main.fls').read_text(errors='replace') if (root / 'main.fls').is_file() else ''
        inputs = sorted({x[6:] for x in fls.splitlines() if x.startswith('INPUT ')})
        forbidden = [x for x in inputs if Path(x).suffix in {'.py', '.pyc', '.lua', '.json', '.jsonl', '.gz'}
                     or 'bntex-cache' in x or '/corpus/' in x]
        unchanged = all((root/n).is_file() and sha((root/n).read_bytes()) == sha(raw) for n, raw in assets.items())
        result = {'pass': iteration+1, 'phase': 'first' if iteration == 0 else 'recompile',
                  'status': 'timeout' if timed_out else 'compiled' if code == 0 else 'compile-error',
                  'wall_seconds': round(elapsed, 6), 'timeout_seconds': timeout, 'returncode': code,
                  'peak_rss_kib': None, 'user_seconds': None, 'system_seconds': None,
                  'shell_execution_disabled': True, 'forbidden_runtime_inputs': forbidden,
                  'immutable_assets_unchanged': unchanged, 'recorded_input_count': len(inputs)}
        if measure.is_file():
            m = re.search(r'^(\d+) ([0-9.]+) ([0-9.]+)$', measure.read_text(), re.M)
            if m:
                result.update(peak_rss_kib=int(m[1]), user_seconds=float(m[2]), system_seconds=float(m[3]))
        for key, pattern in {'tex_memory_words': r'(\d+) words of memory out of',
                             'tex_string_characters': r'(\d+) string characters out of',
                             'tex_control_sequences': r'(\d+) multiletter control sequences out of',
                             'tex_font_instances': r'words of font info for (\d+) fonts, out of'}.items():
            m = re.search(pattern, log)
            result[key] = int(m[1]) if m else None
        result['warnings'] = {key: len(re.findall(pattern, log)) for key, pattern in {
            'missing_character': r'Missing character:', 'font': r'LaTeX Font Warning:',
            'overfull': r'Overfull \\[hv]box', 'underfull': r'Underfull \\[hv]box'}.items()}
        hits = re.findall(r'BNTEX-MEMO\|hits=(\d+)\|misses=(\d+)\|entries=(\d+)\|glyphs=(\d+)\|evictions=(\d+)', log)
        result['memo'] = dict(zip(('hits','misses','entries','glyphs','evictions'), map(int,hits[-1]))) if hits else None
        if code == 0 and (forbidden or not unchanged or result['warnings']['missing_character']):
            result['status'] = 'validation-error'
        records.append(result)
        if result['status'] != 'compiled':
            result['diagnostic_tail'] = output.decode(errors='replace')[-1600:]
            break
    report = {'status': records[-1]['status'], 'runs': records, 'pdf_pages': None,
              'pdf_bytes': None, 'bengali_font_entries': None, 'fonts': [], 'all_tokens_extracted': None}
    if report['status'] == 'compiled':
        pdf = root / 'main.pdf'
        text = subprocess.check_output([tool('pdftotext'), '-enc', 'UTF-8', '-layout', str(pdf), '-'], timeout=30).decode('utf-8')
        (root/'extracted.txt').write_text(text)
        listing = subprocess.check_output([tool('pdffonts'), str(pdf)], timeout=30).decode()
        fonts = [x.strip() for x in listing.splitlines()[2:] if x.strip()]
        missing = [w for w in set(words) if w not in text]
        report.update(pdf_pages=text.count('\f'), pdf_bytes=pdf.stat().st_size,
                      pdf_sha256=sha(pdf.read_bytes()), fonts=fonts,
                      bengali_font_entries=sum('NotoSerifBengali' in x for x in fonts),
                      all_tokens_extracted=not missing, missing_token_count=len(missing))
        if missing:
            report['status'] = 'extraction-error'
    return report


def profile_source():
    """Inclusive phase timers: GSUB called within a phase is counted twice."""
    code = [r'\ExplSyntaxOn', r'\int_new:N\l__bnperf_start_int']
    for name, macro in PHASES.items():
        code += [rf'\int_new:N\g__bnperf_{name}_int',
                 rf'\cs_new_eq:NN\__bnperf_{name}:\{macro}',
                 rf'\cs_set_protected:Npn\{macro}'+'{'+
                 r'\group_begin:\int_set:Nn\l__bnperf_start_int{\pdfelapsedtime}'+
                 rf'\__bnperf_{name}:\int_gadd:Nn\g__bnperf_{name}_int'+
                 r'{\pdfelapsedtime-\l__bnperf_start_int}\group_end:}']
    code += [r'\int_new:N\g__bnperf_gsub_int',
             r'\cs_new_eq:NN\__bnperf_gsub:nnnn\__bn_gsub_run:nnnn',
             r'\cs_set_protected:Npn\__bn_gsub_run:nnnn#1#2#3#4{\group_begin:\int_set:Nn\l__bnperf_start_int{\pdfelapsedtime}\__bnperf_gsub:nnnn{#1}{#2}{#3}{#4}\int_gadd:Nn\g__bnperf_gsub_int{\pdfelapsedtime-\l__bnperf_start_int}\group_end:}', r'\ExplSyntaxOff']
    words = ['বাংলা','স্বাস্থ্য','অণুজীবপ্রযুক্তিগত','পুনর্গঠনযোগ্যতার','শিক্ষকসম্মেলনের','ক্ষেত্রে','কল্প','গান','কো','কর্ম']*8
    stats = r'\ExplSyntaxOn'+''.join(rf'\iow_term:x{{PERF|{n}|\int_use:N\g__bnperf_{n}_int}}' for n in [*PHASES, 'gsub'])+r'\ExplSyntaxOff'
    text = (r'\documentclass{article}\usepackage{bntex-native}\BnTeXNativeLoadProfile{bntex-native-profile.tex}'+'\n'+'\n'.join(code)+
            r'\begin{document}\ifnum\pdfshellescape=0\else\errmessage{shell enabled}\fi'+'\n'+
            '\n'.join(r'\bnNative{'+w+'}' for w in words)+'\n'+stats+r'\end{document}'+'\n')
    return text, words


def benchmark(installations: dict[str, Path], out: Path, *, pages=(1,10,100), tokens=96,
              modes=('repeated','distinct'), memo_modes=(False,), passes=2, timeout=90, profile=False):
    if type(passes) is not int or not 1 <= passes <= 4 or not math.isfinite(timeout) or not 0 < timeout <= 7200:
        raise ValueError('invalid passes or timeout')
    if not pages or len(set(pages)) != len(pages) or not modes or len(set(modes)) != len(modes):
        raise ValueError('empty or duplicate page/mode list')
    if not memo_modes or len(set(memo_modes)) != len(memo_modes):
        raise ValueError('empty or duplicate memo list')
    if not installations or any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,31}', n) for n in installations):
        raise ValueError('invalid installation label')
    for n in pages:
        for mode in modes:
            for memo in memo_modes:
                source(n, tokens, mode, memo)
    if out.exists() or any(p.is_symlink() for p in (out, *out.parents)):
        raise ValueError('output must be new, without symlink ancestors')
    if any(p.resolve() == out.resolve() or p.resolve() in out.resolve().parents for p in installations.values()):
        raise ValueError('output cannot be inside an installation')
    data = {name: installation(path) for name, path in installations.items()}
    identities = {(m['font_sha256'], m['profile_sha256']) for _, m in data.values()}
    if len(identities) != 1:
        raise ValueError('paired measurement requires identical font and typed profile')
    if True in memo_modes and any('bntex-native-memo.sty' not in a for a, _ in data.values()):
        raise ValueError('memo-on measurement requires the optional memo package')
    for program in ('pdflatex', 'pdftotext', 'pdffonts'):
        tool(program)
    out.mkdir(parents=True)
    result = {'schema': 1, 'platform': platform.platform(), 'driver_python': platform.python_version(),
              'engine': subprocess.check_output([tool('pdflatex'),'--version']).decode().splitlines()[0],
              'installations': {n: {'manifest_sha256':sha((installations[n]/'native-installation.json').read_bytes()),
                                   'files': m['files'], 'font_sha256': m['font_sha256'],
                                   'profile_sha256': m['profile_sha256'], 'tables_sha256':m['tables_sha256']}
                                for n, (_,m) in data.items()},
              'serial': True, 'timing_note':'Serial fresh-process runs; OS caches not flushed; no confidence intervals.',
              'overleaf_verified': False, 'rows': [], 'profiles': []}
    def save():
        (out/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    def prepare(name, label, text):
        root=out/label; root.mkdir()
        assets,_=data[name]
        for file,raw in assets.items(): (root/file).write_bytes(raw)
        (root/'main.tex').write_text(text,encoding='utf-8')
        return root, assets
    if profile:
        text, words = profile_source()
        for name in data:
            root, assets = prepare(name, f'profile-{name}', text)
            row = compile_run(root,assets,words,1,timeout)
            log=(root/'main.log').read_text(errors='replace')
            row.update(installation=name, source_sha256=sha(text.encode()), word_occurrences=len(words),
                       inclusive_phases_seconds={n:int(v)/65536 for n,v in re.findall(r'PERF\|([a-z_]+)\|(\d+)',log)})
            result['profiles'].append(row);save()
    for n in pages:
        for mode in modes:
            for memo in memo_modes:
                text, spec, words = source(n,tokens,mode,memo)
                for name in data:
                    label=f'{name}-{mode}-{n:03d}-memo-{int(memo)}'
                    root,assets=prepare(name,label,text)
                    row=compile_run(root,assets,words,passes,timeout)
                    if row['status']=='compiled' and row['pdf_pages']!=n:
                        row['status']='unexpected-page-count'
                    row.update(installation=name, workload=spec, directory=label)
                    result['rows'].append(row);save()
                    print(label, row['status'], [r['wall_seconds'] for r in row['runs']], flush=True)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installation', action='append', required=True, metavar='LABEL=PATH')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--pages',type=int,nargs='+',default=[1,10,100])
    parser.add_argument('--tokens-per-page',type=int,default=96)
    parser.add_argument('--modes',choices=['repeated','distinct'],nargs='+',default=['repeated','distinct'])
    parser.add_argument('--memo',choices=['off','on','both'],default='off')
    parser.add_argument('--passes',type=int,default=2);parser.add_argument('--timeout',type=float,default=90)
    parser.add_argument('--profile',action='store_true')
    args=parser.parse_args(argv)
    try:
        installs={}
        for item in args.installation:
            label,sep,path=item.partition('=')
            if not sep or not path or label in installs: raise ValueError('use distinct LABEL=PATH installations')
            installs[label]=Path(path)
        benchmark(installs,args.out,pages=args.pages,tokens=args.tokens_per_page,modes=args.modes,
                  memo_modes=(False,True) if args.memo=='both' else (args.memo=='on',),
                  passes=args.passes,timeout=args.timeout,profile=args.profile)
        return 0
    except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError) as exc:
        print(f'bntex performance: {exc}',file=__import__('sys').stderr)
        return 2


if __name__=='__main__': raise SystemExit(main())
