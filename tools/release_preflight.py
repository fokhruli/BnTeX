#!/usr/bin/env python3
"""Audit and optionally build a PRIVATE source-review archive; never publish.

Only Git-tracked regular files are eligible. A passed mechanical audit does not
approve typography, licenses, browser behavior or public distribution.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import zipfile

FORBIDDEN = {'.ttf','.otf','.ttc','.woff','.woff2','.pfb','.pfa','.tfm','.vf',
             '.enc','.pl','.map','.key','.pem','.pyc','.aux','.log','.out','.toc',
             '.zip','.whl','.tar','.tgz'}
NAMES = {'.env','.env.local','credentials.json','id_rsa','id_ed25519',
         'bntex-cache.tex','bntex-manifest.json','native-installation.json'}
REQUIRED = {'README.md','LICENSE','THIRD-PARTY-NOTICES.md','pyproject.toml',
            'docs/manual/bntex-manual.tex','docs/RELEASE-READINESS.json'}
GATES = {'overleaf_browser','second_user','native_visual_review',
         'interactive_performance','font_distribution_review','package_name_review',
         'public_release_authorization'}


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.PIPE)


def unique(pairs):
    result = {}
    for k,v in pairs:
        if k in result: raise ValueError('duplicate JSON key')
        result[k] = v
    return result


def readiness(raw: bytes) -> dict:
    data = json.loads(raw, object_pairs_hook=unique)
    if (set(data) != {'schema','purpose','gates'} or type(data['schema']) is not int
            or data['schema'] != 1 or data['purpose'] != 'private-release-readiness'
            or not isinstance(data['gates'],list)):
        raise ValueError('invalid readiness schema')
    seen = set(); blockers = []
    for gate in data['gates']:
        if not isinstance(gate,dict) or set(gate) != {'id','status','evidence','detail'}:
            raise ValueError('invalid gate record')
        key = gate['id']
        if not isinstance(key,str) or key not in GATES or key in seen:
            raise ValueError('unknown or duplicate gate')
        seen.add(key)
        if gate['status'] not in ('pending','blocked','passed'):
            raise ValueError('unknown gate status')
        if not isinstance(gate['detail'],str) or not gate['detail'].strip():
            raise ValueError('gate detail required')
        if gate['evidence'] is not None and not isinstance(gate['evidence'],str):
            raise ValueError('invalid gate evidence')
        if gate['status'] == 'passed' and (not gate['evidence'] or not gate['evidence'].strip()):
            raise ValueError('passed gate needs evidence, not an empty claim')
        if gate['status'] != 'passed': blockers.append(key)
    if seen != GATES: raise ValueError('missing required gate')
    return {'recorded_gates_complete':not blockers,'blockers':sorted(blockers),
            'evidence_authentication':'not performed; maintainer must verify recorded evidence'}


def collect(root: Path) -> tuple[dict[str,bytes],dict]:
    root = root.resolve()
    if git(root,'rev-parse','--show-toplevel').decode().strip() != str(root):
        raise ValueError('root must be repository top level')
    if git(root,'status','--porcelain','--untracked-files=no').strip():
        raise ValueError('tracked working tree must be clean')
    tracked = [p.decode('utf-8') for p in git(root,'ls-files','-z').split(b'\0') if p]
    if not tracked or len(tracked)>10000: raise ValueError('invalid tracked file count')
    assets = {}; folded = set(); total = 0
    for name in sorted(tracked):
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or name.casefold() in folded:
            raise ValueError('unsafe or case-colliding source path')
        folded.add(name.casefold())
        path = root/name
        if any(q.is_symlink() for q in (path,*path.parents)) or not path.is_file():
            raise ValueError('source must be a regular, non-symlink file: '+name)
        if (path.suffix.lower() in FORBIDDEN or path.name in NAMES
                or set(p.parts)&{'.git','.venv','__pycache__','build','dist'}):
            raise ValueError('forbidden source artifact: '+name)
        if path.stat().st_size>16*1024*1024: raise ValueError('oversized source file')
        raw = path.read_bytes(); total += len(raw)
        if raw[:4] in {b'\x00\x01\x00\x00',b'OTTO',b'ttcf',b'wOFF',b'wOF2'}:
            raise ValueError('possible renamed font binary: '+name)
        if path.suffix.lower()=='.gz' and name!='corpus/oracles/user-forms-noto-hb10.2.0.json.gz':
            raise ValueError('unreviewed compressed source: '+name)
        if total>64*1024*1024: raise ValueError('source archive exceeds 64 MiB')
        if re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',raw):
            raise ValueError('possible private key in '+name)
        assets[name] = raw
    if not REQUIRED<=assets.keys(): raise ValueError('missing release documentation or license')
    modules = [p for p in assets if p.startswith('tex/latex/bntex/') and Path(p).suffix in {'.sty','.def'}]
    if not modules: raise ValueError('no authoritative TeX modules')
    for path in modules:
        if assets.get('src/bntex/data/'+Path(path).name) != assets[path]:
            raise ValueError('source/resource mismatch: '+path)
    gates = readiness(assets['docs/RELEASE-READINESS.json'])
    report = {'schema':1,'kind':'bntex-private-source-review',
              'source_commit':git(root,'rev-parse','HEAD').decode().strip(),
              'mechanical_audit':'passed','tracked_files':len(assets),
              'tex_resource_pairs':len(modules),'source_bytes':total,
              'public_upload_performed':False, 'fonts_redistributed':False,
              'gate_status':gates,
              'scope':'filename/resource/basic-content checks, not a complete security or legal audit',
              'files':{n:hashlib.sha256(b).hexdigest() for n,b in assets.items()}}
    return assets, report


def write_new(path: Path, raw: bytes):
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('symlink output rejected')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream: stream.write(raw)


def archive(path: Path, assets: dict[str,bytes], report: dict, manual: Path):
    if any(p.is_symlink() for p in (path,*path.parents,manual,*manual.parents)):
        raise ValueError('symlink archive/manual path rejected')
    if manual.stat().st_size>16*1024*1024: raise ValueError('manual PDF too large')
    pdf = manual.read_bytes()
    if not pdf.startswith(b'%PDF-'): raise ValueError('manual must be a compiled PDF')
    members = dict(assets)
    if 'SOURCE-REVIEW.json' in members or 'docs/manual/bntex-manual.pdf' in members:
        raise ValueError('compiled manual must be supplied separately, not tracked')
    members['docs/manual/bntex-manual.pdf'] = pdf
    members['SOURCE-REVIEW.json'] = (json.dumps(report,sort_keys=True,indent=2)+'\n').encode()
    path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,raw in sorted(members.items()):
            info = zipfile.ZipInfo('bntex-source-review/'+name,(1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644<<16
            z.writestr(info,raw)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--archive',type=Path);p.add_argument('--manual-pdf',type=Path)
    p.add_argument('--require-ready',action='store_true')
    a=p.parse_args(argv)
    try:
        if bool(a.archive)!=bool(a.manual_pdf): raise ValueError('archive requires manual PDF')
        targets=[x for x in (a.out,a.archive) if x]
        if len({x.resolve() for x in targets})!=len(targets): raise ValueError('distinct outputs required')
        if any(x.exists() or x.is_symlink() for x in targets): raise ValueError('outputs must be new')
        assets,report=collect(a.root)
        if a.archive:
            report['archive_sha256']=archive(a.archive,assets,report,a.manual_pdf)
        write_new(a.out,(json.dumps(report,sort_keys=True,indent=2)+'\n').encode())
        print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2))
        return 1 if a.require_ready and not report['gate_status']['recorded_gates_complete'] else 0
    except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError) as exc:
        print('bntex preflight: '+str(exc),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
