#!/usr/bin/env python3
"""Reject accidental font/secrets/build files in a reviewed source tree.

This filename-based check is NOT a comprehensive secret/content scanner.
"""
from pathlib import Path
import subprocess
import sys

FORBIDDEN={'.ttf','.otf','.ttc','.pfb','.pfa','.tfm','.vf','.enc','.pl','.map','.key','.pem'}
SKIP={'.git','.venv','__pycache__','.pytest_cache','build','dist'}


def main():
    root=Path(__file__).resolve().parents[1]
    git=subprocess.run(['git','-C',str(root),'ls-files','-z'],capture_output=True,check=False)
    tracked=[root/p.decode('utf8') for p in git.stdout.split(b'\x00') if p] if git.returncode==0 else []
    if tracked:
        files=tracked
    else:
        files=[p for p in root.rglob('*') if p.is_file() and not (set(p.relative_to(root).parts)&SKIP)
               and not any(x.endswith('.egg-info') for x in p.relative_to(root).parts)]
    bad=[str(p.relative_to(root)) for p in files if p.suffix.lower() in FORBIDDEN
         or p.name in {'.env','.env.local','credentials.json','id_rsa','id_ed25519','bntex-cache.tex','bntex-manifest.json'}]
    if bad:
        print('Refusing release: forbidden files:\n'+'\n'.join(bad),file=sys.stderr);return 1
    print(f'Filename audit passed for {len(files)} source files. Review content/secrets separately.')
    return 0

if __name__=='__main__':raise SystemExit(main())
