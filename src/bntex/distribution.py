"""Maintainer-only deterministic TDS assembly; never called by document authors.

This builds local, complete runtime trees from the two audited font inputs.
It never downloads files, submits to CTAN, changes a live TeX tree, or declares
human/distribution acceptance complete. Font-containing outputs remain local.
"""
from __future__ import annotations
import argparse
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import re
import sys
import tempfile
import zipfile

from .authoring_export import export_authoring, BOLD_PROFILE_SHA
from .native_project import installation_manifest, read_json
from .tex_export import FONT_SHA, PROFILE_SHA, MODULES
from .native_profile import PINNED_BOLD_SHA256

VERSION = '0.2.0-alpha'
OFL_SHA256 = 'f71d138f6a823c98a093ca5eb559464edc2085701b5a8694e585dac71002befd'
TEX_DIR = 'tex/latex/bntex'
DOC_DIR = 'doc/latex/bntex'
SOURCE_DIR = 'source/latex/bntex'
FONT_DIRS = {'.ttf':'fonts/truetype/public/bntex',
             '.tfm':'fonts/tfm/public/bntex', '.enc':'fonts/enc/dvips/bntex'}
EXTRA_MODULES = ('bntex.sty', 'bntex-cached.sty', 'bntex-distribution.sty')
CHECK = re.compile(r'\\BnTeXNativeCheckFile\{([A-Za-z0-9_.-]+)\}\{([0-9A-F]{32})\}')
MAP = re.compile(r'\\pdfmapline\{\+([A-Za-z0-9_-]+) ([A-Za-z0-9_-]+) <([A-Za-z0-9_.-]+) <([A-Za-z0-9_.-]+)\}')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_resource(name: str) -> bytes:
    return files('bntex').joinpath('data',name).read_bytes()


def tds_path(name: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.(?:sty|def|tex|ttf|tfm|enc)',name):
        raise ValueError(f'Unexpected runtime asset name: {name}')
    return (FONT_DIRS.get(Path(name).suffix,TEX_DIR))+'/'+name


def installed_loader(raw: bytes, assets: dict[str, bytes]) -> bytes:
    """Translate only the audited loader protocol, not arbitrary TeX source."""
    checks = set(); maps = 0; out = []
    for line in raw.decode('ascii').splitlines():
        m = CHECK.fullmatch(line)
        if m:
            name, expected = m.groups()
            if name not in assets or hashlib.md5(assets[name]).hexdigest().upper()!=expected:
                raise ValueError('Loader check does not match asset bytes')
            checks.add(name)
            if Path(name).suffix in FONT_DIRS:
                line = rf'\BnTeXInstalledAsset{{{name}}}{{{tds_path(name)}}}{{{expected}}}'
        m = MAP.fullmatch(line)
        if m:
            bank, ps, enc, font = m.groups()
            if any(n not in checks for n in (bank+'.tfm',enc,font)):
                raise ValueError('Font map precedes its checked assets')
            line = rf'\BnTeXInstalledMap{{{bank}}}{{{ps}}}{{{enc}}}{{{font}}}'
            maps += 1
        elif r'\pdfmapline' in line or (r'\BnTeXNativeCheckFile' in line and not CHECK.fullmatch(line)):
            raise ValueError('Unsupported loader syntax')
        out.append(line)
    required = {n for n in assets if Path(n).suffix in FONT_DIRS}
    if not required.issubset(checks) or maps != 6:
        raise ValueError('Incomplete audited family loader')
    extra_checks = [rf'\BnTeXNativeCheckFile{{{n}}}{{{hashlib.md5(assets[n]).hexdigest().upper()}}}'
                    for n in EXTRA_MODULES]
    # The public entry loads the resolver before the first font check.
    return ('% Installed family loader, no author profile setup.\n'+r'\RequirePackage{bntex-distribution}'+'\n'+
            '\n'.join(extra_checks+out)+'\n').encode('ascii')


def fresh(path: Path) -> None:
    if path.exists() or path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('Output must be a fresh nonsymlink directory')


def _read(path: Path, limit: int = 16*1024*1024) -> bytes:
    if not path.is_file() or any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('Expected a regular nonsymlink input')
    if path.stat().st_size>limit: raise ValueError('Input exceeds resource limit')
    return path.read_bytes()


def assemble(regular_font: Path, bold_font: Path, out: Path, *,
             license_file: Path, manual_pdf: Path, manual_source: Path,
             example: Path, readme: Path, notices: Path, code_license: Path, third_party_notices: Path) -> dict:
    """Build a complete local TDS tree; each file is hash-inventoried.

    Source archives intentionally remain font-free. This function's output is a
    maintainer build workspace, not automatically a shareable/public release.
    """
    out=Path(out); fresh(out)
    license_raw=_read(license_file)
    if sha(license_raw)!=OFL_SHA256:
        raise ValueError('Complete pinned font license text is required')
    pdf=_read(manual_pdf)
    if not pdf.startswith(b'%PDF-'): raise ValueError('Compiled PDF manual is required')
    doc = {'README.md':_read(readme),'bntex-manual.pdf':pdf,
           'bntex-manual.tex':_read(manual_source),'bntex-example.tex':_read(example),
           'OFL-1.1.txt':license_raw,'FONT-NOTICES.md':_read(notices),
           'LICENSE':_read(code_license),'THIRD-PARTY-NOTICES.md':_read(third_party_notices)}
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.bntex-dist-',dir=out.parent) as temp:
        temp=Path(temp); flat=temp/'flat'
        family=export_authoring(Path(regular_font),Path(bold_font),flat)
        installation_manifest(flat)
        assets={n:_read(flat/n) for n in family['files']}
        for n in EXTRA_MODULES: assets[n]=source_resource(n)
        loader=installed_loader(assets['bntex-native-profile.tex'],assets)
        assets['bntex-default-profile.def']=loader
        # The public default is self-loading; explicit profile loading also works
        # when the caller has already loaded the distribution resolver.
        assets['bntex-native-profile.tex']=loader
        tree=temp/'tds'; tree.mkdir()
        for n,raw in sorted(assets.items()):
            p=tree/tds_path(n);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        for n,raw in doc.items():
            p=tree/DOC_DIR/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        # Exporters are auditable build sources, not runtime dependencies.
        source=files('bntex')
        for f in source.iterdir():
            if f.name.endswith('.py'):
                p=tree/SOURCE_DIR/'bntex'/f.name;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(f.read_bytes())
        for n,raw in assets.items():
            if n in (*EXTRA_MODULES,*MODULES):
                p=tree/SOURCE_DIR/'bntex'/'data'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        records={str(p.relative_to(tree)):sha(p.read_bytes()) for p in sorted(tree.rglob('*')) if p.is_file()}
        manifest={'schema':1,'kind':'bntex-complete-local-tds','version':VERSION,
                  'font_sha256':FONT_SHA,'bold_font_sha256':PINNED_BOLD_SHA256,
                  'regular_profile_sha256':PROFILE_SHA,'bold_profile_sha256':family['bold_profile_sha256'],
                  'font_delivery':'audited unchanged outlines in the complete maintainer-built distribution',
                  'author_setup':'usepackage{bntex}; no profile compiler or manual profile loading',
                  'runtime_python':False,'runtime_shell':False,'vocabulary':None,
                  'read_policy':'TeX Live default input policy; restrictive openin_any=p not yet supported',
                  'browser_test':'not-performed','publication_authorized':False,'files':records}
        mp=tree/DOC_DIR/'distribution-manifest.json'
        mp.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
        tree.rename(out)
    return manifest


def verify(root: Path) -> dict:
    root=Path(root)
    _read(root/DOC_DIR/'distribution-manifest.json')
    m=read_json(root/DOC_DIR/'distribution-manifest.json')
    if type(m.get('schema')) is not int or m['schema']!=1 or m.get('kind')!='bntex-complete-local-tds' or not isinstance(m.get('files'),dict):
        raise ValueError('Unsupported distribution manifest')
    if (m.get('font_sha256')!=FONT_SHA or m.get('bold_font_sha256')!=PINNED_BOLD_SHA256
            or m.get('regular_profile_sha256')!=PROFILE_SHA or m.get('bold_profile_sha256')!=BOLD_PROFILE_SHA
            or m.get('vocabulary','missing') is not None):
        raise ValueError('Unsupported distribution identities')
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    allowed=set(m['files'])|{DOC_DIR+'/distribution-manifest.json','ls-R'}
    if actual-allowed: raise ValueError('Unlisted distribution files')
    if not 20<=len(m['files'])<=512: raise ValueError('Invalid file count')
    total = 0
    for name,expected in m['files'].items():
        if (not re.fullmatch(r'[A-Za-z0-9_./-]+',name) or
            any(x in ('','..','.') for x in name.split('/')) or name.startswith('/')):
            raise ValueError('Unsafe distribution path')
        if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):
            raise ValueError('Invalid asset hash')
        data = _read(root/name); total += len(data)
        if total > 16*1024*1024: raise ValueError('Distribution exceeds total resource limit')
        if sha(data)!=expected: raise ValueError(f'Distribution asset changed: {name}')
    if sha(_read(root/FONT_DIRS['.ttf']/('bnf'+FONT_SHA[:16]+'.ttf')))!=FONT_SHA:
        raise ValueError('Wrong regular outlines')
    if sha(_read(root/FONT_DIRS['.ttf']/('bnf'+PINNED_BOLD_SHA256[:16]+'.ttf')))!=PINNED_BOLD_SHA256:
        raise ValueError('Wrong bold outlines')
    return m


def pack(root: Path, out: Path) -> dict:
    """Create complete local TDS and browsing archives for maintainer review.

    Font-containing archives are build outputs, never source attachments. This
    function cannot authorize or perform a public upload.
    """
    root, out = Path(root), Path(out); manifest=verify(root);fresh(out)
    if out.resolve().is_relative_to(root.resolve()):
        raise ValueError('Archive output must be outside the TDS input')
    runtime={name:_read(root/name) for name in manifest['files']}
    runtime[DOC_DIR+'/distribution-manifest.json']=_read(root/DOC_DIR/'distribution-manifest.json')
    out.parent.mkdir(parents=True,exist_ok=True)
    def zipwrite(path, items):
        with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED) as z:
            for name,raw in sorted(items.items()):
                info=zipfile.ZipInfo(name,(2026,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
                z.writestr(info,raw)
    with tempfile.TemporaryDirectory(prefix='.bntex-pack-',dir=out.parent) as temp:
        stage=Path(temp)/'archives';stage.mkdir()
        zipwrite(stage/'bntex.tds.zip',runtime)
        browse={}
        for name,raw in runtime.items():
            if name.startswith(TEX_DIR+'/'):dest='bntex/tex/'+name[len(TEX_DIR)+1:]
            elif name.startswith(DOC_DIR+'/'):dest='bntex/'+name[len(DOC_DIR)+1:]
            elif name.startswith(SOURCE_DIR+'/'):dest='bntex/source/'+name[len(SOURCE_DIR)+1:]
            elif name.startswith('fonts/'):dest='bntex/'+name
            else:raise ValueError('Unknown TDS destination')
            if dest in browse:raise ValueError('Browsing path collision')
            browse[dest]=raw
        browse['bntex.tds.zip']=(stage/'bntex.tds.zip').read_bytes()
        zipwrite(stage/'bntex-ctan-candidate.zip',browse)
        report={'kind':'local-complete-distribution-candidate','files':len(runtime),
                'contains_font_binaries':True,'publication_performed':False,
                'release_ready':False,'reason':'Uncompleted human/platform/read-policy/release gates',
                'archives':{p.name:sha(p.read_bytes()) for p in sorted(stage.glob('*.zip'))}}
        (stage/'build-report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
        stage.rename(out)
    return report


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('assemble')
    for name in ('regular-font','bold-font','out','license-file','manual-pdf','manual-source',
                 'example','readme','notices','code-license','third-party-notices'):
        a.add_argument('--'+name,type=Path,required=True)
    a=sub.add_parser('verify');a.add_argument('--root',type=Path,required=True)
    a=sub.add_parser('pack');a.add_argument('--root',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    args=p.parse_args(argv)
    try:
        if args.cmd=='verify':result=verify(args.root)
        elif args.cmd=='pack':result=pack(args.root,args.out)
        else:
            d=vars(args).copy();d.pop('cmd');result=assemble(**d)
        print(json.dumps(result,sort_keys=True,indent=2));return 0
    except (OSError,ValueError,RuntimeError) as e:
        print(f'bntex distribution: {e}',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
