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
import os
import shutil
import subprocess
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
GENERATED_MODULES = ('bntex-default-profile.def', 'bntex-native-profile.tex',
                     'bntex-native-tables.def', 'bntex-native-matchers.def',
                     'bntex-native-bold.def')
SOURCE_MODULES = ('__init__.py', '__main__.py', 'authoring_export.py', 'build.py',
                  'corpus.py', 'distribution.py', 'harfbuzz.py', 'inventory.py',
                  'mining.py', 'native.py', 'native_layout.py', 'native_model.py',
                  'native_profile.py', 'native_project.py', 'profile.py',
                  'source.py', 'tex_export.py')
DOC_FILES = ('README.md', 'bntex-manual.pdf', 'bntex-manual.tex',
             'bntex-example.tex', 'OFL-1.1.txt', 'FONT-NOTICES.md',
             'LICENSE', 'THIRD-PARTY-NOTICES.md')
REBUILD_GUIDE = rb"""# Maintainer reproduction from an installed BnTeX distribution

This is release-maintainer documentation, not document-author setup.
Authors load \usepackage{bntex} in an installed TeX distribution.

From this directory (source/latex/bntex in the TDS tree), run:

    python -B -m bntex.distribution rebuild --root ../../.. --out /a/fresh/output

The -B flag keeps bytecode caches out of the immutable installed source tree.
Use trusted, unmodified distribution sources and the matching maintainer
Python/FontTools/TeX toolchain. Required executables: pdflatex and pltotf.
FontTools 4.63.0 reproduces the pinned font profiles. No network is used.
The root must contain the entire TDS distribution, including its two exact
font binaries, license notices, original manual source and reference manual PDF.
The rebuild re-compiles the manual twice with shell execution disabled, checks
its exact bytes against the supplied PDF, runs the actual profile compilers,
and requires an identical distribution manifest. Different toolchain output
fails explicitly; existing output paths are never overwritten.

This command executes trusted manual source. It is not a sandbox for hostile
TeX. It never modifies the input installation, publishes files, or authorizes
publication. Its complete font-containing archives remain maintainer outputs.
"""

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


def required_files() -> set[str]:
    """The release schema, not its editable inventory, defines completeness."""
    names = {tds_path(n) for n in (*MODULES, *EXTRA_MODULES, *GENERATED_MODULES)}
    for fingerprint in (FONT_SHA, PINNED_BOLD_SHA256):
        prefix = 'bnf' + fingerprint[:16]
        names.add(tds_path(prefix + '.ttf'))
        for bank in range(3):
            names.update(tds_path(f'{prefix}b{bank}{suffix}') for suffix in ('.tfm', '.enc'))
    names.update(DOC_DIR + '/' + n for n in DOC_FILES)
    names.update(SOURCE_DIR + '/bntex/' + n for n in SOURCE_MODULES)
    names.update(SOURCE_DIR + '/bntex/data/' + n for n in (*EXTRA_MODULES, *MODULES))
    names.add(SOURCE_DIR + '/REPRODUCING.md')
    return names


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
        actual_sources = {f.name for f in source.iterdir() if f.name.endswith('.py')}
        if actual_sources != set(SOURCE_MODULES):
            raise ValueError('Maintainer source inventory changed; update the release schema')
        for name in SOURCE_MODULES:
            p=tree/SOURCE_DIR/'bntex'/name;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(source.joinpath(name).read_bytes())
        (tree/SOURCE_DIR/'REPRODUCING.md').write_bytes(REBUILD_GUIDE)
        for n,raw in assets.items():
            if n in (*EXTRA_MODULES,*MODULES):
                p=tree/SOURCE_DIR/'bntex'/'data'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        records={p.relative_to(tree).as_posix():sha(p.read_bytes()) for p in sorted(tree.rglob('*')) if p.is_file()}
        if set(records) != required_files():
            raise ValueError('Incomplete or unexpected assembled distribution')
        manifest={'schema':1,'kind':'bntex-complete-local-tds','version':VERSION,
                  'font_sha256':FONT_SHA,'bold_font_sha256':PINNED_BOLD_SHA256,
                  'regular_profile_sha256':PROFILE_SHA,'bold_profile_sha256':family['bold_profile_sha256'],
                  'font_delivery':'audited unchanged outlines in the complete maintainer-built distribution',
                  'author_setup':'usepackage{bntex}; no profile compiler or manual profile loading',
                  'runtime_python':False,'runtime_shell':False,'vocabulary':None,
                  'read_policy':'TeX Live default input policy; restrictive openin_any=p is engine-dependent and separately probed',
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
            or m.get('vocabulary','missing') is not None
            or m.get('version') != VERSION or m.get('runtime_python') is not False
            or m.get('runtime_shell') is not False or m.get('publication_authorized') is not False
            or m.get('browser_test') != 'not-performed'):
        raise ValueError('Unsupported distribution identities')
    # A missing file AND a removed manifest entry must not turn a broken
    # installation into a verified archive. This schema is deliberately closed.
    if set(m['files']) != required_files():
        raise ValueError('Incomplete or unexpected distribution inventory')
    paths = list(root.rglob('*'))
    if any(p.is_symlink() for p in paths):
        raise ValueError('Symlinks are not distribution assets')
    actual={p.relative_to(root).as_posix() for p in paths if p.is_file()}
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
    if sha(_read(root/DOC_DIR/'OFL-1.1.txt')) != OFL_SHA256:
        raise ValueError('Complete pinned font license text is required')
    if not _read(root/DOC_DIR/'bntex-manual.pdf').startswith(b'%PDF-'):
        raise ValueError('Compiled PDF manual is required')
    for name in (*EXTRA_MODULES, *MODULES):
        if _read(root/TEX_DIR/name) != _read(root/SOURCE_DIR/'bntex/data'/name):
            raise ValueError(f'Runtime/source module mismatch: {name}')
    if _read(root/TEX_DIR/'bntex-default-profile.def') != _read(root/TEX_DIR/'bntex-native-profile.tex'):
        raise ValueError('Default/explicit installed loaders differ')
    return m


OVERLEAF_README = b"""# BnTeX starter project

Upload this ZIP with Overleaf's New Project > Upload Project, keep the compiler
set to pdfLaTeX, and edit main.tex. Write Bengali and English directly in the
text; no wrapper commands are needed.

Keep the bntex*.sty, *.def, *.tex, *.tfm, *.enc and *.ttf files in the
project's top folder: BnTeX looks for them beside main.tex and checks each one
against the MD5 recorded for this release. Do not edit them.

The first compile shapes every distinct word (about 100 words per second);
later compiles reuse the shaped words stored in main.bnc and only shape new
ones. Deleting main.bnc is always safe.

The same files work locally beside any document (TeX Live or MiKTeX).
Fonts: Noto Serif Bengali Regular and Bold, SIL Open Font License 1.1; code:
MIT. See licenses/.
"""


def overleaf_starter(runtime: dict[str, bytes]) -> dict[str, bytes]:
    """Flat project layout: runtime files beside main.tex, as an upload needs.

    The installed resolver's bare-name fallback finds and MD5-checks them.
    """
    items = {}
    for name, raw in runtime.items():
        if name.startswith(TEX_DIR + '/') or any(name.startswith(d + '/') for d in FONT_DIRS.values()):
            base = name.rsplit('/', 1)[1]
            if base in items:
                raise ValueError('Starter project path collision')
            items[base] = raw
    items['main.tex'] = runtime[DOC_DIR + '/bntex-example.tex']
    items['README.md'] = OVERLEAF_README
    for n in ('OFL-1.1.txt', 'FONT-NOTICES.md', 'LICENSE', 'THIRD-PARTY-NOTICES.md'):
        items['licenses/' + n] = runtime[DOC_DIR + '/' + n]
    return items


def pack(root: Path, out: Path) -> dict:
    """Create complete local TDS, browsing and Overleaf-starter archives.

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
        zipwrite(stage/'bntex-overleaf-starter.zip',overleaf_starter(runtime))
        report={'kind':'local-complete-distribution-candidate','files':len(runtime),
                'contains_font_binaries':True,'publication_performed':False,
                'release_ready':False,'reason':'Uncompleted human/platform/read-policy/release gates',
                'archives':{p.name:sha(p.read_bytes()) for p in sorted(stage.glob('*.zip'))}}
        (stage/'build-report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
        stage.rename(out)
    return report


def rebuild(root: Path, out: Path) -> dict:
    """Reproduce trusted release sources without a development checkout.

    This explicit maintainer action compiles TeX source; verify() alone never
    executes it. Matching toolchain output is required, not silently rebaselined.
    """
    root, out = Path(root).resolve(), Path(out)
    original = verify(root)
    fresh(out)
    if out.resolve().is_relative_to(root):
        raise ValueError('Rebuild output must be outside its source installation')
    package = files('bntex')
    for name in SOURCE_MODULES:
        if package.joinpath(name).read_bytes() != _read(root/SOURCE_DIR/'bntex'/name):
            raise ValueError('Run rebuild using the sources shipped with this distribution')
    engine = shutil.which('pdflatex')
    if not engine:
        raise ValueError('Maintainer pdfLaTeX toolchain is missing')
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.bntex-rebuild-', dir=out.parent) as temp:
        temp=Path(temp); manual=temp/'manual'; manual.mkdir()
        source=manual/'bntex-installation.tex'
        source.write_bytes(_read(root/DOC_DIR/'bntex-manual.tex'))
        env=dict(os.environ, SOURCE_DATE_EPOCH='1767225600', FORCE_SOURCE_DATE='1', TZ='UTC')
        for _ in range(2):
            proc=subprocess.run([engine, '-no-shell-escape', '-halt-on-error',
                                 '-interaction=nonstopmode', source.name], cwd=manual,
                                env=env, capture_output=True, timeout=90)
            if proc.returncode:
                raise ValueError('Manual rebuild failed: '+proc.stdout.decode(errors='replace')[-3000:])
        pdf=manual/'bntex-installation.pdf'
        if _read(pdf) != _read(root/DOC_DIR/'bntex-manual.pdf'):
            raise ValueError('Manual differs: use the matching source-build TeX toolchain')
        stage=temp/'result'; stage.mkdir()
        doc=root/DOC_DIR
        reproduced=assemble(
            root/tds_path('bnf'+FONT_SHA[:16]+'.ttf'),
            root/tds_path('bnf'+PINNED_BOLD_SHA256[:16]+'.ttf'), stage/'texmf',
            license_file=doc/'OFL-1.1.txt', manual_pdf=pdf,
            manual_source=doc/'bntex-manual.tex', example=doc/'bntex-example.tex',
            readme=doc/'README.md', notices=doc/'FONT-NOTICES.md',
            code_license=doc/'LICENSE', third_party_notices=doc/'THIRD-PARTY-NOTICES.md')
        if reproduced != original:
            raise ValueError('Rebuilt distribution differs from the recorded manifest')
        report=pack(stage/'texmf', stage/'archives')
        report.update(runtime_files=len(reproduced['files']), source_rebuild='exact-match')
        (stage/'build-report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
        # Verify the original before committing the new output tree.
        if verify(root) != original:
            raise ValueError('Input distribution changed during rebuild')
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
    a=sub.add_parser('rebuild');a.add_argument('--root',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    args=p.parse_args(argv)
    try:
        if args.cmd=='verify':result=verify(args.root)
        elif args.cmd=='pack':result=pack(args.root,args.out)
        elif args.cmd=='rebuild':result=rebuild(args.root,args.out)
        else:
            d=vars(args).copy();d.pop('cmd');result=assemble(**d)
        print(json.dumps(result,sort_keys=True,indent=2));return 0
    except (OSError,ValueError,RuntimeError) as e:
        print(f'bntex distribution: {e}',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
