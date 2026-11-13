"""Explicit native-project staging, integrity checks and bounded pdfLaTeX runs.

No TeX parsing/expansion occurs in staging. The manifest is an explicit file list.
Only trusted local projects/installations are accepted; this is not a TeX sandbox.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import zipfile
from .tex_export import FONT_SHA, PROFILE_SHA, MODULES

MAX_BYTES = 16 * 1024 * 1024
EXTENSIONS = {'.tex', '.bib', '.bst', '.sty', '.cls', '.png', '.jpg', '.pdf'}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> dict:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('JSON exceeds 16 MiB')
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out: raise ValueError('Duplicate JSON key')
            out[k] = v
        return out
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    if not isinstance(value, dict): raise ValueError('Expected JSON object')
    return value


def relative(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', name):
        raise ValueError('Project paths must use portable ASCII names')
    p = PurePosixPath(name)
    if (p.is_absolute() or any(x in {'', '.', '..'} for x in name.split('/'))
            or any(x.startswith('.') for x in p.parts) or len(name) > 180):
        raise ValueError('Unsafe relative project path')
    return name


def local_file(root: Path, name: str) -> Path:
    relative(name)
    p = root / name
    if any(x.is_symlink() for x in (p, *p.parents)):
        raise ValueError('Symlink inputs are not supported')
    if not p.is_file() or not p.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Missing/outside project file: {name}')
    if p.stat().st_size > MAX_BYTES: raise ValueError('File exceeds 16 MiB')
    return p


def fresh_output(path: Path, protected: list[Path]) -> None:
    if path.exists() or any(x.is_symlink() for x in (path, *path.parents)):
        raise ValueError('Output must be a fresh non-symlink path')
    for p in protected:
        if path.resolve() == p.resolve() or path.resolve().is_relative_to(p.resolve()):
            raise ValueError('Output must not be inside an input project/installation')


def installation_manifest(root: Path) -> dict:
    meta = read_json(local_file(root, 'native-installation.json'))
    if (type(meta.get('abi')) is not int or meta['abi'] != 1 or meta.get('font_sha256') != FONT_SHA
            or meta.get('profile_sha256') != PROFILE_SHA or meta.get('vocabulary', 0) is not None):
        raise ValueError('Not the supported native installation')
    files = meta.get('files')
    if not isinstance(files, dict) or not 1 <= len(files) <= 64:
        raise ValueError('Invalid installation file list')
    required = set(MODULES) | {'bntex-native-tables.def', 'bntex-native-profile.tex'}
    if not required.issubset(files): raise ValueError('Incomplete installation modules')
    total = 0
    for name, expected in files.items():
        relative(name)
        if '/' in name or 'cache' in name.lower() or Path(name).suffix not in {'.sty','.def','.tex','.tfm','.enc','.ttf'}:
            raise ValueError('Unexpected installation filename')
        raw = local_file(root, name).read_bytes(); total += len(raw)
        if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected) or digest(raw) != expected:
            raise ValueError(f'Installation asset changed: {name}')
    if total > MAX_BYTES: raise ValueError('Installation exceeds 16 MiB')
    return meta


def stage(manifest: Path, installation: Path, out: Path) -> dict:
    """Copy exactly declared sources and verified installation assets atomically."""
    root = manifest.parent
    data = read_json(manifest)
    if set(data) != {'schema', 'backend', 'main', 'files'} or type(data['schema']) is not int or data['schema'] != 1 or data['backend'] != 'native':
        raise ValueError('Expected schema-1 native project manifest')
    files = data['files']; main = relative(data['main'])
    if not isinstance(files, list) or not 1 <= len(files) <= 128 or any(not isinstance(x, str) for x in files):
        raise ValueError('Expected 1--128 explicitly named source files')
    if len(files) != len(set(files)) or len(files) != len({x.casefold() for x in files}):
        raise ValueError('Duplicate or case-colliding source paths')
    if main not in files or Path(main).suffix != '.tex': raise ValueError('Main .tex must be listed')
    assets = installation_manifest(installation)
    reserved = {x.casefold() for x in assets['files']} | {'native-installation.json','bntex-project.json'}
    source = {}; total = 0
    for name in files:
        p = local_file(root, name)
        if name.casefold() in reserved or (p.suffix not in EXTENSIONS and name != 'latexmkrc'):
            raise ValueError('Source collides with installation or has unsupported file type')
        raw = p.read_bytes(); total += len(raw)
        if p.suffix in {'.tex','.bib','.bst','.sty','.cls'} or name == 'latexmkrc': raw.decode('utf-8', errors='strict')
        source[name] = raw
    if total > MAX_BYTES: raise ValueError('Source project exceeds 16 MiB')
    fresh_output(out, [root, installation]); out.parent.mkdir(parents=True, exist_ok=True)
    meta = {'schema':1, 'backend':'native', 'main':main,
            'source_manifest_sha256':digest(manifest.read_bytes()),
            'initial_sources':{n:digest(b) for n,b in sorted(source.items())},
            'font_sha256':FONT_SHA,'profile_sha256':PROFILE_SHA,
            'installation_sha256':digest((installation/'native-installation.json').read_bytes()),
            'document_word_preparation':False, 'overleaf_browser_test':'not-performed'}
    with tempfile.TemporaryDirectory(prefix='.bntex-project-', dir=out.parent) as tmp:
        result = Path(tmp)/'project'; result.mkdir()
        for name in [*assets['files'], 'native-installation.json']:
            shutil.copyfile(installation/name, result/name)
        for name, raw in source.items():
            p = result/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
        (result/'bntex-project.json').write_text(json.dumps(meta,sort_keys=True,indent=2)+'\n')
        result.rename(out)
    return meta


def verify(root: Path) -> dict:
    meta = read_json(local_file(root, 'bntex-project.json'))
    if type(meta.get('schema')) is not int or meta['schema'] != 1 or meta.get('backend') != 'native':
        raise ValueError('Unsupported staged project')
    installation_manifest(root)
    if digest((root/'native-installation.json').read_bytes()) != meta.get('installation_sha256'):
        raise ValueError('Installation manifest changed since staging')
    sources = meta.get('initial_sources')
    if not isinstance(sources, dict) or not 1 <= len(sources) <= 128:
        raise ValueError('Invalid staged source list')
    changed = []
    for name, expected in sources.items():
        actual = digest(local_file(root,name).read_bytes())
        if actual != expected: changed.append(name)
    if meta.get('main') not in sources: raise ValueError('Invalid staged main document')
    return {'status':'verified', 'installation_intact':True,
            'modified_sources':sorted(changed), 'source_edits_require_preparation':False,
            'overleaf_browser_test':'not-performed'}


def pack(root: Path, out: Path) -> dict:
    """Build an upload ZIP on the user's machine, including their installed font.

    Never call this to redistribute third-party font files from a development
    environment. The source distribution itself contains no font binaries.
    """
    verify(root); meta = read_json(root/'bntex-project.json'); inst = installation_manifest(root)
    names = sorted(set(meta['initial_sources']) | set(inst['files']) | {'bntex-project.json','native-installation.json'})
    fresh_output(out,[root]); out.parent.mkdir(parents=True,exist_ok=True)
    try:
        with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED) as z:
            for name in names:
                info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=0o100644<<16; z.writestr(info,local_file(root,name).read_bytes())
    except BaseException:
        out.unlink(missing_ok=True); raise
    return {'zip':str(out),'files':len(names),'sha256':digest(out.read_bytes()),
            'contains_user_installed_font':True,'overleaf_browser_test':'not-performed'}


def _tool(name: str) -> str:
    path = shutil.which(name)
    if not path: raise ValueError(f'Required tool missing: {name}')
    return str(Path(path).absolute())


def inspect_pdf(path: Path) -> dict:
    def run(name,args):
        p=subprocess.run([_tool(name),*args],capture_output=True,timeout=30)
        if p.returncode: raise ValueError(f'{name} failed on output PDF')
        return p.stdout.decode('utf-8',errors='replace')
    info=run('pdfinfo',[str(path)])
    match=re.search(r'^Pages:\s+(\d+)$',info,re.M)
    if not match: raise ValueError('Could not read PDF page count')
    fonts=run('pdffonts',[str(path)]).splitlines()[2:]
    text=run('pdftotext',['-enc','UTF-8',str(path),'-'])
    return {'pages':int(match.group(1)),'pdf_bytes':path.stat().st_size,
            'font_count':len(fonts),'bengali_font_count':sum('NotoSerifBengali' in x for x in fonts),
            'fonts':fonts, 'pdf_info':info,'extracted_text':text}


def compile_once(root: Path, main: str, *, timeout: float = 60, tag: str = 'compile') -> dict:
    """Run only pdfLaTeX in a child with shell disabled and no executable PATH.

    GNU time is a host-side measurement wrapper, not a TeX-invoked helper.
    The child process group is reaped on timeout. Inputs must be trusted.
    """
    relative(main); local_file(root, main)
    if not re.fullmatch(r'[A-Za-z0-9-]+',tag): raise ValueError('Invalid run tag')
    if not 0 < timeout <= 3600: raise ValueError('Timeout must be within (0,3600] seconds')
    engine=_tool('pdflatex'); clock=Path('/usr/bin/time')
    env=dict(os.environ,PATH='/bntex-no-executables',TEXINPUTS='.:',
             openin_any='p',openout_any='p',MKTEXPK='0',MKTEXTFM='0',
             SOURCE_DATE_EPOCH='1',FORCE_SOURCE_DATE='1',max_print_line='10000')
    cmd=[engine,'-no-shell-escape','-halt-on-error','-interaction=nonstopmode','-recorder',main]
    resources=root/f'{tag}-resources.txt'; stdout=root/f'{tag}-stdout.txt'
    if resources.exists() or stdout.exists(): raise ValueError('Run output tag already exists')
    if clock.is_file(): cmd=[str(clock),'-f','%M %U %S %x','-o',str(resources.absolute()),*cmd]
    started=time.monotonic(); timed_out=False
    with stdout.open('xb') as log:
        child=subprocess.Popen(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try: child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out=True
            os.killpg(child.pid,signal.SIGTERM)
            try: child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL);child.wait()
    elapsed=time.monotonic()-started
    output=stdout.read_text(encoding='utf-8',errors='replace')
    report={'status':'timeout' if timed_out else 'success' if child.returncode==0 else 'compile-error',
            'returncode':child.returncode,'timeout_s':timeout,'wall_s':round(elapsed,6),
            'max_rss_kib':None,'user_cpu_s':None,'system_cpu_s':None,
            'shell_escape':False,'executable_path':'empty','engine':engine,
            'warnings': [x for x in output.splitlines() if any(k in x for k in ('Warning:','Overfull','Underfull','Missing character:'))]}
    if resources.exists():
        m=re.search(r'^(\d+) ([0-9.]+) ([0-9.]+) (\d+)$',resources.read_text(),re.M)
        if m: report.update(max_rss_kib=int(m[1]),user_cpu_s=float(m[2]),system_cpu_s=float(m[3]))
    for label,pattern in {'tex_memory_words':r'(\d+) words of memory',
                          'tex_string_chars':r'(\d+) string characters',
                          'tex_control_sequences':r'(\d+) multiletter control sequences',
                          'tex_fonts':r'(\d+) fonts'}.items():
        log_path=root/(Path(main).stem+'.log')
        found=re.search(pattern,log_path.read_text(errors='replace')) if log_path.exists() else None
        report[label]=int(found[1]) if found else None
    hits=re.findall(r'BNTEX-MEMO\|hits=(\d+)\|misses=(\d+)\|entries=(\d+)\|glyphs=(\d+)\|evictions=(\d+)',output)
    report['memo'] = dict(zip(('hits','misses','entries','glyphs','evictions'),map(int,hits[-1]))) if hits else None
    fls=root/(Path(main).stem+'.fls')
    inputs=[x[6:] for x in fls.read_text(errors='replace').splitlines() if x.startswith('INPUT ')] if fls.exists() else []
    forbidden=[x for x in inputs if Path(x).suffix in {'.py','.json','.jsonl','.gz'} or ('bntex-cache' in x and Path(x).name != 'bntex-cached.sty')]
    report['recorder_forbidden_inputs']=forbidden
    report['recorder_input_count']=len(set(inputs))
    report['engine_banner']=output.splitlines()[0] if output else ''
    if report['status']=='success':
        if forbidden or any('Missing character:' in x for x in report['warnings']):
            report['status']='validation-error'
        report.update(inspect_pdf(root/(Path(main).stem+'.pdf')))
    else: report['diagnostic_tail']=output[-2500:]
    return report


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('stage');p.add_argument('--manifest',type=Path,required=True);p.add_argument('--installation',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('verify');p.add_argument('--project',type=Path,required=True)
    p=sub.add_parser('pack');p.add_argument('--project',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('run');p.add_argument('--project',type=Path,required=True);p.add_argument('--passes',type=int,default=3);p.add_argument('--timeout',type=float,default=60)
    a=parser.parse_args(argv)
    try:
        if a.command=='stage': result=stage(a.manifest,a.installation,a.out)
        elif a.command=='verify': result=verify(a.project)
        elif a.command=='pack': result=pack(a.project,a.out)
        else:
            verify(a.project); meta=read_json(a.project/'bntex-project.json')
            if not 1<=a.passes<=5: raise ValueError('Run 1--5 passes')
            result={'runs':[],'browser_test':'not-performed'}
            for i in range(a.passes):
                row=compile_once(a.project,meta['main'],timeout=a.timeout,tag=f'pass-{i+1}')
                row.pop('extracted_text',None);result['runs'].append(row)
                if row['status']!='success': break
            result['installation']=verify(a.project)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return int(a.command=='run' and any(x['status']!='success' for x in result['runs']))
    except (OSError,ValueError,KeyError,TypeError,RecursionError) as exc:
        print(f'bntex native project: {exc}',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
