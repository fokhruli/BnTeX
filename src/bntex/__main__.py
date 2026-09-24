"""Command-line interface. Run with PYTHONPATH=src python -m bntex ..."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sys
import subprocess
from fontTools.ttLib import TTLibError
from .build import prepare, verify, inspect_font
from .harfbuzz import HarfBuzz
from .profile import audit_font, DEFAULT_SCRIPTS


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(prog='python -m bntex',description='Prepare Bengali glyph caches for pdfLaTeX.')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare'); p.add_argument('--source',type=Path,action='append',required=True)
    p.add_argument('--font',action='append',required=True,metavar='STYLE=STATIC_TTF')
    p.add_argument('--out',type=Path,required=True)
    v=sub.add_parser('verify'); v.add_argument('directory',type=Path)
    s=sub.add_parser('shape'); s.add_argument('--font',type=Path,required=True); s.add_argument('--text',required=True)
    f=sub.add_parser('profile', help='Audit font lookup closure; does not generate a native profile')
    f.add_argument('--font',type=Path,required=True)
    f.add_argument('--script',action='append',help='OpenType tag; repeat to audit a union (default: bng2,beng,DFLT)')
    sub.add_parser('doctor')
    args=parser.parse_args(argv)
    try:
        if args.command=='prepare':
            fonts={}
            for spec in args.font:
                alias, sep, filename=spec.partition('=')
                if not sep or alias in fonts: raise ValueError('Use unique --font STYLE=PATH arguments.')
                fonts[alias]=Path(filename)
            m=prepare(args.source,fonts,args.out)
            print(json.dumps({'output':str(args.out),'styles':list(m['styles']),
                              'words_per_style':next(iter(m['styles'].values()))['word_count']},indent=2))
        elif args.command=='verify':
            m=verify(args.directory); print(f'Verified {len(m["files"])} prepared files.')
        elif args.command=='profile':
            print(json.dumps(audit_font(args.font, scripts=tuple(args.script or DEFAULT_SCRIPTS)),
                             ensure_ascii=False, indent=2))
        elif args.command=='shape':
            inspect_font(args.font)
            with HarfBuzz(args.font) as hb:
                print(json.dumps({'text':args.text,'upem':hb.upem,'harfbuzz':hb.version,
                                  'glyphs':[asdict(g) for g in hb.shape(args.text)]},ensure_ascii=False,indent=2))
        else:
            import ctypes.util
            print(json.dumps({'python':sys.version.split()[0],'libharfbuzz':ctypes.util.find_library('harfbuzz'),
                              **{x:shutil.which(x) for x in ['pltotf','pdflatex','lualatex','pdftotext','git','gh']}},indent=2))
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError,TTLibError) as e:
        print(f'bntex: {e}',file=sys.stderr); return 2


if __name__=='__main__': raise SystemExit(main())
