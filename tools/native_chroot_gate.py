#!/usr/bin/env python3
"""Optional Linux proof: execute only pdfTeX in a temporary Python-free root.

Requires CAP_SYS_CHROOT. It copies the already-built installation plus the exact
LaTeX inputs observed in a vocabulary-neutral priming compile, the pdfTeX binary,
and its shared libraries. It is a trusted test fixture, NOT an untrusted-TeX
security sandbox. No system installation is changed. Font files stay local and
are not copied to the result directory; only a PDF and an evidence JSON survive.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def document(words):
    intro = r'''\documentclass[12pt]{article}
\usepackage[margin=25mm]{geometry}
\usepackage{bntex-native}
\BnTeXNativeLoadProfile{bntex-native-profile.tex}
\begin{document}
\ifnum\pdfshellescape=0\else\errmessage{Shell execution is enabled}\fi
\section*{BnTeX: native pdfLaTeX acceptance}
This page was compiled in a temporary root containing pdfTeX and its required
LaTeX files, but no Python interpreter, HarfBuzz library, or word cache.
The font installation was completed before these words were introduced.
\par\bigskip
'''
    for i, text in enumerate(words):
        intro += '\\typeout{CASE|'+str(i)+'}\\BnTeXNativeShape{'+text+'}\\BnTeXNativeDump\n'
        intro += '\\noindent\\bnNative{'+text+'}\\par\\medskip\n'
    return intro + '\\end{document}\n'


def gate(installation: Path, out: Path, font: Path):
    if not hasattr(os, 'chroot'): raise RuntimeError('Linux/POSIX chroot is required.')
    if out.exists() or out.is_symlink(): raise ValueError('Result directory must not exist.')
    manifest=json.loads((installation/'native-installation.json').read_text())
    for name,h in manifest['files'].items():
        if Path(name).name != name or digest(installation/name)!=h: raise ValueError('Installation identity mismatch.')
    if manifest['vocabulary'] is not None: raise ValueError('Vocabulary-bearing installation rejected.')
    exe=shutil.which('pdflatex')
    if not exe: raise RuntimeError('pdflatex is required.')
    exe=Path(exe).absolute()
    engine=exe.resolve()
    libraries=subprocess.check_output(['ldd',str(engine)],text=True)
    library_paths=set(re.findall(r'(?<!\S)(/[^\s()]+)',libraries))
    if any('harfbuzz' in p.lower() or 'python' in p.lower() for p in library_paths):
        raise RuntimeError('Engine links a prohibited helper library.')
    with tempfile.TemporaryDirectory(prefix='bntex-chroot-') as temp:
        base=Path(temp);prime=base/'prime';prime.mkdir()
        for name in manifest['files']:shutil.copy2(installation/name,prime/name)
        (prime/'main.tex').write_text(document(['বাংলা','ক্ষ','স্বাস্থ্য','০১২৩৪৫৬৭৮৯']),encoding='utf-8')
        env=dict(os.environ,PATH='/no-executables',TEXINPUTS='.:',max_print_line='10000',
                 MKTEXPK='0',MKTEXTFM='0',SOURCE_DATE_EPOCH='1',FORCE_SOURCE_DATE='1')
        command=[str(exe),'-no-shell-escape','-halt-on-error','-interaction=nonstopmode','-recorder','main.tex']
        first=subprocess.run(command,cwd=prime,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
        if first.returncode: raise RuntimeError(first.stdout.decode(errors='replace')[-5000:])
        jail=base/'root';work=jail/'work';work.mkdir(parents=True)
        def copy_absolute(source):
            src=Path(source)
            if not src.is_absolute() or not src.is_file(): raise ValueError(f'Invalid dependency: {src}')
            dst=jail/str(src).lstrip('/');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        for name in manifest['files']:shutil.copy2(installation/name,work/name)
        inputs=set()
        for line in (prime/'main.fls').read_text().splitlines():
            if line.startswith('INPUT /'): inputs.add(line[6:])
        for src in sorted(inputs):copy_absolute(src)
        copy_absolute(engine)
        for src in sorted(library_paths):copy_absolute(src)
        # Explicit search directories avoid depending on an external ls-R database.
        dirs=sorted({str(Path(p).parent) for p in inputs})
        search='/work:'+':'.join(dirs)
        for key in ('TEXINPUTS','TFMFONTS','T1FONTS','TEXFONTMAPS','ENCFONTS','TEXFORMATS','TEXMFCNF'):
            env[key]=search
        runtime_files={str(p.relative_to(jail)):digest(p) for p in jail.rglob('*') if p.is_file()}
        forbidden=[p for p in runtime_files if re.search(r'python|harfbuzz|\.py$|bntex-cache|corpus/',p,re.I)]
        if forbidden:raise RuntimeError(f'Unexpected helper/cache in root: {forbidden}')
        # New input is introduced only after the complete root/image is built.
        words=['অণুজীবপ্রযুক্তিগত','পুনর্বিন্যাসসমূহ','শিক্ষকসম্মেলনের','দূরনিয়ন্ত্রণযোগ্যতা',
               'মহাকাশপ্রযুক্তিবিষয়ক','ত্রিমাত্রিকীকরণসমূহ','কো কো','ক্\u200dষ ক্\u200cষ','ড় ড়']
        before={name:digest(work/name) for name in manifest['files']}
        (work/'main.tex').write_text(document(words),encoding='utf-8')
        def enter_root():
            os.chroot(jail);os.chdir('/work')
        t0=time.monotonic()
        try:
            run=subprocess.run([str(engine),'-progname=pdflatex','-fmt=pdflatex',*command[1:]],
                               preexec_fn=enter_root,env=env,stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
        except subprocess.SubprocessError as exc:
            raise RuntimeError('Cannot enter temporary root: CAP_SYS_CHROOT is required.') from exc
        elapsed=time.monotonic()-t0
        log=run.stdout.decode('utf-8',errors='replace')
        if run.returncode:raise RuntimeError(log[-8000:])
        actual=[]
        for line in log.splitlines():
            if line.startswith('CASE|'):actual.append([])
            elif line.startswith('BNTEX-GLYPH|'):actual[-1].append(list(map(int,line.split('|')[1:])))
        # The independent reference is executed OUTSIDE the root, after pdfTeX exits.
        from bntex.harfbuzz import HarfBuzz
        with HarfBuzz(font) as hb:
            if hb.version!='10.2.0':raise RuntimeError('Exact post-run reference requires HarfBuzz 10.2.0.')
            expected=[[list(asdict(g).values()) for g in hb.shape(t)] for t in words]
        if actual!=expected:raise RuntimeError('Native output differs from the pinned reference.')
        if before!={name:digest(work/name) for name in before}:raise RuntimeError('Installation changed during compilation.')
        extracted=subprocess.check_output(['pdftotext','-enc','UTF-8',str(work/'main.pdf'),'-']).decode()
        for text in words:
            for word in text.split():
                if word not in extracted:raise RuntimeError(f'ActualText extraction failed for {word!r}.')
        out.mkdir(parents=True)
        shutil.copy2(work/'main.pdf',out/'native-unseen.pdf')
        evidence={'status':'passed','root_contains_python':False,'root_contains_harfbuzz':False,
                  'root_contains_word_cache':False,'shell_escape':False,'profile_sha256':manifest['profile_sha256'],
                  'font_sha256':manifest['font_sha256'],'tables_sha256':manifest['tables_sha256'],
                  'runtime_files':runtime_files,'holdout_text':words,'glyph_runs':actual,
                  'elapsed_seconds':elapsed,'installation_unchanged':True,'text_extraction':'passed',
                  'reference':'HarfBuzz 10.2.0, outside root after engine execution',
                  'note':'Trusted Linux test root, not an untrusted-input security sandbox.'}
        (out/'native-unseen-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
        return evidence


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installation',type=Path,required=True)
    parser.add_argument('--font',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    report=gate(args.installation.resolve(),args.out.resolve(),args.font.resolve())
    print(json.dumps({k:v for k,v in report.items() if k not in {'runtime_files','glyph_runs'}},ensure_ascii=False,indent=2))
