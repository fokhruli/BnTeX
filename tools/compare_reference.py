#!/usr/bin/env python3
"""Compare backend word widths to LuaLaTeX-HarfBuzz with the exact same local font.

Both paths use HarfBuzz. This validates output geometry/configuration, not
independent orthographic correctness. Temporary font copies are never exported.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from bntex.build import prepare

WORDS=['বাংলা','স্বাস্থ্য','প্রযুক্তি','স্বাধীনতা','ক্ষ','জ্ঞ','কি','কী','কু','কূ','কৃ','কে','কৈ','কো','কৌ',
       'কাঁ','কর্ম','অর্থ','সূর্য','দৃষ্টি','ড়','ঢ়','য়','০১২৩৪৫৬৭৮৯','ক্\u200dষ','ক্\u200cষ']


def run(engine: str, cwd: Path) -> dict[int,float]:
    result=subprocess.run([engine,'-no-shell-escape','-halt-on-error','-interaction=nonstopmode','input.tex'],
       cwd=cwd,capture_output=True,text=True,errors='replace',timeout=90)
    if result.returncode:
        raise RuntimeError(engine+' failed:\n'+result.stdout[-5000:])
    return {int(i):float(v) for i,v in re.findall(r'BNTEXWIDTH(\d+)=([0-9.]+)pt',result.stdout)}


def compare(font: Path, tolerance: float=0.02) -> dict:
    for command in ['pdflatex','lualatex','pltotf']:
        if not shutil.which(command):raise RuntimeError('Missing '+command)
    with tempfile.TemporaryDirectory(prefix='bntex-reference-') as tmp:
        root=Path(tmp);source=root/'input.tex'
        body='\n'.join(r'\sbox{\measure}{\bn{'+w+r'}}\typeout{BNTEXWIDTH'+str(i)+r'=\the\wd\measure}'
                     for i,w in enumerate(WORDS))
        source.write_text(r'''\documentclass{article}
\usepackage{bntex}\BnTeXLoadCache{bntex-cache.tex}
\newsavebox{\measure}
\begin{document}\fontsize{12}{16}\selectfont
'''+body+'\n'+r'\mbox{}\end{document}',encoding='utf8')
        prepare([source],{'regular':font},root/'native')
        native=run('pdflatex',root/'native')
        ref=root/'reference';ref.mkdir();shutil.copyfile(font,ref/'font.ttf')
        refbody='\n'.join(r'\sbox{\measure}{'+w+r'}\typeout{BNTEXWIDTH'+str(i)+r'=\the\wd\measure}'
                        for i,w in enumerate(WORDS))
        (ref/'input.tex').write_text(r'''\documentclass{article}
\usepackage{fontspec}
\setmainfont[Renderer=HarfBuzz,Script=Bengali,Language=Bengali,Path=./]{font.ttf}
\newsavebox{\measure}
\begin{document}\fontsize{12}{16}\selectfont
'''+refbody+'\n'+r'\mbox{}\end{document}',encoding='utf8')
        reference=run('lualatex',ref)
        if len(native)!=len(WORDS) or len(reference)!=len(WORDS):
            raise RuntimeError('Incomplete width measurements.')
        rows=[{'text':w,'pdftex_pt':native[i],'luahbtex_pt':reference[i],
               'absolute_difference_pt':abs(native[i]-reference[i])} for i,w in enumerate(WORDS)]
        maximum=max(r['absolute_difference_pt'] for r in rows)
        return {'test':'word advance at 12pt; same font, two HarfBuzz-backed paths',
                'font_filename':font.name,'word_count':len(WORDS),'tolerance_pt':tolerance,
                'max_difference_pt':maximum,'passed':maximum<=tolerance,'measurements':rows}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font',required=True,type=Path)
    parser.add_argument('--tolerance',type=float,default=0.02)
    args=parser.parse_args()
    result=compare(args.font.resolve(),args.tolerance)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
