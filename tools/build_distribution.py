#!/usr/bin/env python3
"""Maintainer build of a complete LOCAL installable candidate. Never an upload.

Authors use the installed bntex package; they do not run this build tool.
No build outputs (especially font-containing archives) belong in source review.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from bntex.distribution import assemble, pack, fresh

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--regular-font',type=Path,default=Path('/usr/share/fonts/truetype/noto/NotoSerifBengali-Regular.ttf'))
    p.add_argument('--bold-font',type=Path,default=Path('/usr/share/fonts/truetype/noto/NotoSerifBengali-Bold.ttf'))
    a=p.parse_args();fresh(a.out)
    engine=shutil.which('pdflatex')
    if not engine:p.error('Maintainer TeX toolchain is missing')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.bntex-release-build-',dir=a.out.parent) as temp:
        temp=Path(temp);stage=temp/'result';stage.mkdir();manual=temp/'manual';manual.mkdir()
        source=ROOT/'docs/distribution/bntex-installation.tex'
        for _ in range(2):
            proc=subprocess.run([engine,'-no-shell-escape','-halt-on-error','-interaction=nonstopmode',
                                 '-output-directory='+str(manual.resolve()),str(source)],
                                cwd=ROOT,env=dict(os.environ,SOURCE_DATE_EPOCH='1767225600',FORCE_SOURCE_DATE='1',TZ='UTC'),
                                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
            if proc.returncode:raise RuntimeError(proc.stdout.decode(errors='replace')[-5000:])
        result=assemble(a.regular_font,a.bold_font,stage/'texmf',
            license_file=ROOT/'licenses/OFL-1.1.txt',manual_pdf=manual/'bntex-installation.pdf',
            manual_source=source,example=ROOT/'examples/installed/main.tex',
            readme=ROOT/'docs/distribution/README.md',notices=ROOT/'licenses/FONT-NOTICES.md',
            code_license=ROOT/'LICENSE',third_party_notices=ROOT/'THIRD-PARTY-NOTICES.md')
        report=pack(stage/'texmf',stage/'archives')
        report['runtime_files']=len(result['files'])
        (stage/'build-report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',newline='\n')
        stage.rename(a.out)
    print(json.dumps(report,sort_keys=True,indent=2))

if __name__=='__main__':main()
