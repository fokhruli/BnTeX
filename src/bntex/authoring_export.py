"""Install the two audited native faces and wrapper-free authoring modules once.

No document, word list, shaper process, or network is accepted by this exporter.
Font binaries stay in the caller's private generated installation, never source.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

from .native_profile import compile_profile, serialize, PINNED_BOLD_SHA256
from .tex_export import export, emit_tables, FONT_SHA, PROFILE_SHA

BOLD_PROFILE_SHA = 'e3a798be7b57bb363c041cb7252a97c2c565c59215db868e837c069ed117b0f8'
DECLARATION = re.compile(r'\\cs_gset:cpn \{__bnp_([a-zA-Z0-9_]+)\}\{([-0-9a-zA-Z_,.]*)\}')
# Only glyph metrics, explicit pair membership, or numeric GPOS adjustments
# may differ. All shaping,
# filtering, candidates, coverage, masks, grammar, and rule identities must agree.
DELTA_KEY = re.compile(r'(?:m_[0-9]+_(?:a|x0|y0|x1|y1)|t_[0-9]+_(?:pair_[0-9]+_[0-9]+(?:_[01]_(?:dx|dy|ax|ay))?|mark_[0-9]+_[xy]|base_[0-9]+_[0-9]+_[xy]))\Z')


def style_delta(regular: dict, bold: dict) -> tuple[bytes, int]:
    """Prove shared substitution structure, then compile bold-specific metrics."""
    for key in ('glyph_count', 'upem', 'cmap', 'glyph_classes', 'mark_attach_classes',
                'mark_filter_sets', 'gsub_features', 'gpos_features', 'gsub'):
        if regular[key] != bold[key]:
            raise ValueError(f'The audited faces no longer share {key}')
    r = dict(DECLARATION.findall(emit_tables(regular).decode('ascii')))
    b = dict(DECLARATION.findall(emit_tables(bold).decode('ascii')))
    if r.keys() - b.keys():
        raise ValueError('Bold table structure differs; a new face architecture is required')
    delta = {key: value for key, value in b.items() if value != r.get(key)}
    if not delta or any(not DELTA_KEY.fullmatch(key) for key in delta):
        raise ValueError('Unexpected structural difference in bold profile')
    lines = ['% Exact audited Bold metrics/GPOS delta. Not a synthesized font.', r'\ExplSyntaxOn']
    lines += [rf'\cs_gset:cpn {{__bnb_{key}}}{{{value}}}' for key, value in sorted(delta.items())]
    lines += [r'\ExplSyntaxOff', rf'\BnTeXNativeBoldReady{{{PINNED_BOLD_SHA256}}}{{{BOLD_PROFILE_SHA}}}', r'\endinput']
    return ('\n'.join(lines)+'\n').encode('ascii'), len(delta)


def export_authoring(regular_font: Path, bold_font: Path, out: Path) -> dict:
    regular_font, bold_font, out = map(Path, (regular_font, bold_font, out))
    if out.exists() or out.is_symlink() or any(p.is_symlink() for p in out.parents):
        raise ValueError('Output must be a fresh nonsymlink path')
    regular, bold = compile_profile(regular_font), compile_profile(bold_font)
    if regular.font_sha256 != FONT_SHA or hashlib.sha256(serialize(regular)).hexdigest() != PROFILE_SHA:
        raise ValueError('Wrong regular font/profile')
    if bold.font_sha256 != PINNED_BOLD_SHA256 or hashlib.sha256(serialize(bold)).hexdigest() != BOLD_PROFILE_SHA:
        raise ValueError('Wrong bold font/profile')
    delta, count = style_delta(asdict(regular), asdict(bold))
    from .build import inspect_font, _write_banks
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.bntex-authoring-', dir=out.parent) as temp:
        root = Path(temp); profile = root/'regular.json'; profile.write_bytes(serialize(regular))
        stage = root/'installation'
        manifest = export(profile, regular_font, stage)
        meta = inspect_font(bold_font)
        _, maps = _write_banks(stage, bold_font, meta, set(range(bold.glyph_count)))
        if hashlib.sha256((stage/meta['prepared_font_filename']).read_bytes()).hexdigest() != PINNED_BOLD_SHA256:
            raise ValueError('Bold font changed while exporting')
        for p in stage.glob('*.pl'): p.unlink()
        (stage/'bntex-native-bold.def').write_bytes(delta)
        manifest_path = stage/'native-installation.json'
        loader_path = stage/'bntex-native-profile.tex'
        loader = loader_path.read_text('ascii')
        insertion = ['\\RequirePackage{bntex-native-styles}']
        for p in sorted(stage.iterdir()):
            if p.name not in manifest['files'] and p != manifest_path:
                insertion.append(r'\BnTeXNativeCheckFile{'+p.name+'}{'+hashlib.md5(p.read_bytes()).hexdigest().upper()+'}')
        insertion += maps + [r'\input{bntex-native-bold.def}']
        loader = loader.replace(r'\endinput', '\n'.join(insertion)+'\n'+r'\endinput')
        loader_path.write_text(loader, encoding='ascii',newline='\n')
        manifest.update(bold_font_sha256=PINNED_BOLD_SHA256, bold_profile_sha256=BOLD_PROFILE_SHA,
                        bold_delta_entries=count, bold_delta_bytes=len(delta), authoring_abi=1,
                        italic_policy='strict by default; explicit synthetic-italic option', vocabulary=None)
        manifest['files'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted(stage.iterdir()) if p != manifest_path}
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2)+'\n',newline='\n')
        stage.rename(out)
    return manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--regular-font', type=Path, required=True)
    parser.add_argument('--bold-font', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    a=parser.parse_args(argv)
    try:
        print(json.dumps(export_authoring(a.regular_font, a.bold_font, a.out), indent=2)); return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'bntex authoring export: {exc}', file=sys.stderr); return 2

if __name__ == '__main__': raise SystemExit(main())
