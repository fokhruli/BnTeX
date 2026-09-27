#!/usr/bin/env python3
"""Python-free runtime gate for wrapper-free regular/bold/slanted input.

Font setup happens beforehand; reference shaping runs only after the isolated
pdfTeX process exits. Shares the established filesystem gate, not a sandbox for
untrusted TeX. No font files are copied to the result directory.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from native_chroot_gate import gate


def document(words):
    source=r'''\documentclass[12pt]{article}
\usepackage[margin=25mm]{geometry}
\usepackage[synthetic-italic]{bntex-auto}
\BnTeXNativeLoadProfile{bntex-native-profile.tex}
\ExplSyntaxOn
\cs_new_eq:NN\__auto_gate_render:\__bn_render:
\cs_set_protected:Npn\__bn_render:
 {\typeout{CASE|automatic}\BnTeXNativeDump\__auto_gate_render:}
\ExplSyntaxOff
\begin{document}
\ifnum\pdfshellescape=0\else\errmessage{Shell enabled}\fi
\section*{Automatic Bengali / Python-free test}
Each row shows regular, real bold and explicitly simulated slanted input.
These words were introduced after the runtime was constructed. No per-word
Bengali wrapper is used; the dump hook only observes already-shaped output.
\par\bigskip
'''
    for word in words:
        source+=word+r'\quad\textbf{'+word+r'}\quad\textit{'+word+r'}\par\medskip'+'\n'
    return source+r'\end{document}'+'\n'


def run(installation: Path, out: Path, regular: Path, bold: Path):
    from bntex.harfbuzz import HarfBuzz
    from bntex.native_profile import PINNED_BOLD_SHA256
    import hashlib
    manifest=json.loads((installation/'native-installation.json').read_text())
    if manifest.get('bold_font_sha256')!=PINNED_BOLD_SHA256 or hashlib.sha256(bold.read_bytes()).hexdigest()!=PINNED_BOLD_SHA256:
        raise ValueError('The exact audited bold installation is required')
    def reference(words):
        expected=[]
        with HarfBuzz(regular) as reg, HarfBuzz(bold) as strong:
            if reg.version!='10.2.0' or strong.version!='10.2.0':
                raise RuntimeError('HarfBuzz 10.2.0 reference required')
            for text in words:
                for face in (reg,strong,reg):
                    for word in text.split():
                        expected.append([list(asdict(g).values()) for g in face.shape(word)])
        return expected
    result=gate(installation,out,regular,build_document=document,reference=reference)
    result.update(authoring='wrapper-free',styles=['regular','real-bold','explicit-synthetic-slant'],
                  bold_font_sha256=manifest['bold_font_sha256'],bold_profile_sha256=manifest['bold_profile_sha256'])
    (out/'native-unseen-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--installation',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--regular-font',type=Path,required=True)
    p.add_argument('--bold-font',type=Path,required=True)
    a=p.parse_args()
    report=run(a.installation.resolve(),a.out.resolve(),a.regular_font.resolve(),a.bold_font.resolve())
    print(json.dumps({k:v for k,v in report.items() if k not in ('runtime_files','glyph_runs')},ensure_ascii=False,indent=2))
