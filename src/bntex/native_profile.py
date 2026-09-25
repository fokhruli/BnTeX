"""Closed typed OpenType profile for the pinned Bengali font (issue #5).

Compilation uses FontTools, never HarfBuzz or document vocabulary. The independent
runtime consumes only these immutable, validated data records. Profiles contain
metrics/layout rules, not outlines or whole-word glyph caches. See
``docs/NATIVE-MODEL.md`` for supported tables and trust boundaries.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import hashlib
import json
from pathlib import Path
import types
from typing import Literal, Union, get_args, get_origin, get_type_hints

PINNED_FONT_SHA256 = '32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef'
PROFILE_ABI = 1
MAX_PROFILE_BYTES = 8 * 1024 * 1024


class ProfileError(ValueError):
    """Unsupported or malformed font/profile; never silently skip a rule."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ProfileError(message)


@dataclass(frozen=True, slots=True)
class Value:
    x_placement: int = 0
    y_placement: int = 0
    x_advance: int = 0
    y_advance: int = 0


@dataclass(frozen=True, slots=True)
class Anchor:
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class Single:
    kind: Literal['single']
    entries: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class Multiple:
    kind: Literal['multiple']
    entries: tuple[tuple[int, tuple[int, ...]], ...]


@dataclass(frozen=True, slots=True)
class Ligature:
    kind: Literal['ligature']
    # Ordered records: first matching rule wins, not longest match across rules.
    entries: tuple[tuple[tuple[int, ...], int], ...]


@dataclass(frozen=True, slots=True)
class Chain:
    kind: Literal['chain']
    backtrack: tuple[tuple[int, ...], ...]  # nearest glyph first, OpenType order
    inputs: tuple[tuple[int, ...], ...]
    lookahead: tuple[tuple[int, ...], ...]
    actions: tuple[tuple[int, int], ...]  # input-sequence index, lookup index


@dataclass(frozen=True, slots=True)
class PairGlyph:
    kind: Literal['pair-glyph']
    value1_present: bool
    value2_present: bool
    entries: tuple[tuple[int, int, Value, Value], ...]


@dataclass(frozen=True, slots=True)
class PairClass:
    kind: Literal['pair-class']
    value1_present: bool
    value2_present: bool
    coverage: tuple[int, ...]
    class1: tuple[tuple[int, int], ...]
    class2: tuple[tuple[int, int], ...]
    # Missing class definitions mean class zero, not no match.
    matrix: tuple[tuple[tuple[Value, Value], ...], ...]


@dataclass(frozen=True, slots=True)
class MarkBase:
    kind: Literal['mark-base']
    class_count: int
    marks: tuple[tuple[int, int, Anchor], ...]
    bases: tuple[tuple[int, tuple[Anchor | None, ...]], ...]


@dataclass(frozen=True, slots=True)
class MarkMark:
    kind: Literal['mark-mark']
    class_count: int
    marks: tuple[tuple[int, int, Anchor], ...]
    bases: tuple[tuple[int, tuple[Anchor | None, ...]], ...]


Subtable = Single | Multiple | Ligature | Chain | PairGlyph | PairClass | MarkBase | MarkMark


@dataclass(frozen=True, slots=True)
class Lookup:
    index: int
    flags: int
    mark_filter_set: int | None
    subtables: tuple[Subtable, ...]


@dataclass(frozen=True, slots=True)
class Feature:
    tag: str
    lookups: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class FontProfile:
    kind: Literal['bntex-fixed-font-profile']
    abi: int
    font_sha256: str
    script: Literal['bng2']
    language: Literal['dflt']
    glyph_count: int
    upem: int
    cmap: tuple[tuple[int, int], ...]
    advances: tuple[int, ...]
    bounds: tuple[tuple[int, int, int, int] | None, ...]
    glyph_classes: tuple[int, ...]
    mark_attach_classes: tuple[int, ...]
    mark_filter_sets: tuple[tuple[int, ...], ...]
    gsub_features: tuple[Feature, ...]
    gpos_features: tuple[Feature, ...]
    gsub: tuple[Lookup, ...]
    gpos: tuple[Lookup, ...]


def _pairs_unique(entries, label):
    keys = [entry[0] for entry in entries]
    require(len(keys) == len(set(keys)), f'{label}: duplicate mapping key')


def validate(profile: FontProfile) -> FontProfile:
    """Validate references and ranges in addition to the typed JSON structure."""
    require(type(profile) is FontProfile and profile.kind == 'bntex-fixed-font-profile', 'Invalid profile record')
    require(type(profile.abi) is int and profile.abi == PROFILE_ABI, 'Unsupported profile ABI')
    require(profile.font_sha256 == PINNED_FONT_SHA256, 'Unsupported font fingerprint')
    require(profile.script == 'bng2' and profile.language == 'dflt', 'Unsupported script/language')
    n = profile.glyph_count
    require(type(n) is int and type(profile.upem) is int and 0 < n <= 65535 and 16 <= profile.upem <= 16384, 'Invalid font dimensions')
    for seq in (profile.advances, profile.bounds, profile.glyph_classes, profile.mark_attach_classes):
        require(len(seq) == n, 'Metric/GDEF arrays must cover every glyph')
    def gid(g): require(type(g) is int and 0 <= g < n, f'Invalid glyph ID: {g!r}')
    def coverage(seq):
        # Coverage is used as membership here. Preserve redundant source entries.
        for g in seq: gid(g)
    def position(v):
        require(all(type(x) is int and -(1 << 31) <= x < (1 << 31)
                    for x in asdict(v).values()), 'Invalid position/anchor value')
    _pairs_unique(profile.cmap, 'cmap')
    for cp, g in profile.cmap:
        require(type(cp) is int and 0 <= cp <= 0x10FFFF and not 0xD800 <= cp <= 0xDFFF, 'Invalid cmap scalar'); gid(g)
    require(all(type(a) is int and 0 <= a <= 65535 for a in profile.advances), 'Invalid advance')
    for b in profile.bounds:
        require(b is None or (all(-(1 << 15) <= x < (1 << 15) for x in b)
                              and b[0] <= b[2] and b[1] <= b[3]), 'Invalid ink bounds')
    require(all(type(c) is int and 0 <= c <= 4 for c in profile.glyph_classes), 'Invalid GDEF glyph class')
    require(all(type(c) is int and 0 <= c <= 65535 for c in profile.mark_attach_classes), 'Invalid mark attachment class')
    for s in profile.mark_filter_sets: coverage(s)
    for tag, lookups, features in [('GSUB', profile.gsub, profile.gsub_features),
                                    ('GPOS', profile.gpos, profile.gpos_features)]:
        mapping = {l.index: l for l in lookups}
        require(len(mapping) == len(lookups) and all(type(k) is int and 0 <= k <= 65535 for k in mapping), 'Invalid lookup index')
        require(len({f.tag for f in features}) == len(features), 'Duplicate selected feature tag')
        roots = set()
        for f in features:
            require(len(f.tag) == 4 and f.tag.isascii(), 'Invalid feature tag')
            for k in f.lookups:
                require(k in mapping, f'{tag}/{f.tag}: dangling lookup reference'); roots.add(k)
        edges = {i: set() for i in mapping}
        for l in lookups:
            require(type(l.flags) is int and 0 <= l.flags <= 65535 and not (l.flags & 0xE0), 'Reserved lookup flags')
            # This initial runtime does not support right-to-left cursive attachment.
            require(not (l.flags & 1), 'RightToLeft lookup flag is not supported')
            if l.flags & 16:
                require(type(l.mark_filter_set) is int and 0 <= l.mark_filter_set < len(profile.mark_filter_sets),
                        'Invalid mark filtering set')
            else:
                require(l.mark_filter_set is None, 'Unexpected mark filtering set')
            require(0 < len(l.subtables) <= 4096, 'Empty/excessive lookup')
            require(len({s.kind for s in l.subtables}) == 1 or
                    {s.kind for s in l.subtables} <= {'pair-glyph', 'pair-class'}, 'Mixed lookup types')
            for s in l.subtables:
                require((tag == 'GSUB') == isinstance(s, (Single, Multiple, Ligature, Chain)), 'Wrong table kind')
                if isinstance(s, (Single, Multiple)):
                    _pairs_unique(s.entries, s.kind)
                    for a, b in s.entries:
                        gid(a)
                        if isinstance(s, Single): gid(b)
                        else:
                            require(bool(b), 'Deletion substitutions are unsupported')
                            for g in b: gid(g)
                elif isinstance(s, Ligature):
                    _pairs_unique(s.entries, s.kind)
                    for pattern, out in s.entries:
                        require(len(pattern) >= 2, 'Ligature must have at least two components')
                        for g in pattern: gid(g)
                        gid(out)
                elif isinstance(s, Chain):
                    require(bool(s.inputs), 'Context requires input')
                    for c in s.backtrack + s.inputs + s.lookahead:
                        require(bool(c), 'Empty context coverage'); coverage(c)
                    for slot, ref in s.actions:
                        require(0 <= slot < len(s.inputs) and ref in mapping, 'Dangling contextual reference')
                        edges[l.index].add(ref)
                elif isinstance(s, PairGlyph):
                    require(len({(a, b) for a, b, _, _ in s.entries}) == len(s.entries), 'Duplicate pair')
                    for a, b, v1, v2 in s.entries: gid(a); gid(b); position(v1); position(v2)
                elif isinstance(s, PairClass):
                    coverage(s.coverage)
                    require(bool(s.matrix) and bool(s.matrix[0]), 'Empty pair matrix')
                    rows, cols = len(s.matrix), len(s.matrix[0])
                    for classes, bound in [(s.class1, rows), (s.class2, cols)]:
                        _pairs_unique(classes, 'pair class')
                        for g, c in classes:
                            gid(g); require(0 <= c < bound, 'Invalid pair class')
                    for row in s.matrix:
                        require(len(row) == cols, 'Ragged pair matrix')
                        for v1, v2 in row: position(v1); position(v2)
                else:
                    require(0 < s.class_count <= 256, 'Invalid mark class count')
                    _pairs_unique(s.marks, 'marks'); _pairs_unique(s.bases, 'bases')
                    for g, c, a in s.marks:
                        gid(g); require(0 <= c < s.class_count, 'Invalid mark class'); position(a)
                    for g, anchors in s.bases:
                        gid(g); require(len(anchors) == s.class_count, 'Incorrect anchor arity')
                        for a in anchors:
                            if a is not None: position(a)
        visited, active = set(), set()
        def visit(k):
            require(len(active) < 32, 'Contextual dependency depth exceeds 32')
            require(k not in active, 'Cyclic contextual lookup dependency')
            if k in visited: return
            active.add(k)
            for child in edges[k]: visit(child)
            active.remove(k); visited.add(k)
        for k in roots: visit(k)
        require(visited == set(mapping), f'{tag}: unreachable extra lookup')
    return profile


def _compile_font(font, digest: str) -> FontProfile:
    """Internal extraction; public entry point first enforces the binary pin."""
    names = font.getGlyphOrder(); gids = {name: i for i, name in enumerate(names)}
    def g(name):
        require(name in gids, f'Unknown glyph name: {name}'); return gids[name]
    def cov(table): return tuple(g(name) for name in table.glyphs)
    def anchor(a):
        if a is None: return None
        require(a.Format == 1, 'Only static format-1 anchors are supported (no point/device/variation data)')
        return Anchor(a.XCoordinate, a.YCoordinate)
    def val(v, fmt):
        require(type(fmt) is int and 0 <= fmt <= 65535 and fmt & ~0xF == 0, 'Device/variation/reserved ValueRecord fields are unsupported')
        if not v: return Value()
        require(set(vars(v)) <= {'XPlacement','YPlacement','XAdvance','YAdvance'}, 'Unsupported value field')
        return Value(*(getattr(v, k, 0) for k in ('XPlacement','YPlacement','XAdvance','YAdvance')))
    def extract(s, tag, depth=0):
        require(depth <= 1, 'Nested extension subtable is unsupported')
        name = type(s).__name__
        if name in {'ExtensionSubst', 'ExtensionPos'}:
            require(s.Format == 1, 'Unsupported extension format')
            wire_types = {'SingleSubst': 1, 'MultipleSubst': 2, 'LigatureSubst': 4, 'ChainContextSubst': 6} if tag == 'GSUB' else {'PairPos': 2, 'MarkBasePos': 4, 'MarkMarkPos': 6}
            require(s.ExtensionLookupType == wire_types.get(type(s.ExtSubTable).__name__), 'Invalid/unsupported extension target type')
            return extract(s.ExtSubTable, tag, depth + 1)
        if name == 'SingleSubst':
            return Single('single', tuple(sorted((g(a), g(b)) for a, b in s.mapping.items())))
        if name == 'MultipleSubst':
            return Multiple('multiple', tuple(sorted((g(a), tuple(g(x) for x in b)) for a, b in s.mapping.items())))
        if name == 'LigatureSubst':
            return Ligature('ligature', tuple((tuple([g(a)] + [g(x) for x in l.Component]), g(l.LigGlyph))
                                  for a, ls in s.ligatures.items() for l in ls))
        if name == 'ChainContextSubst':
            require(s.Format == 3, 'Only chaining format-3 coverage contexts are supported')
            return Chain('chain', tuple(cov(c) for c in s.BacktrackCoverage), tuple(cov(c) for c in s.InputCoverage),
                         tuple(cov(c) for c in s.LookAheadCoverage),
                         tuple((r.SequenceIndex, r.LookupListIndex) for r in s.SubstLookupRecord))
        if name == 'PairPos':
            require(s.Format in (1, 2), 'Unsupported pair format')
            if s.Format == 1:
                require(len(s.Coverage.glyphs) == len(s.PairSet), 'Bad PairSet count')
                return PairGlyph('pair-glyph', bool(s.ValueFormat1), bool(s.ValueFormat2),
                    tuple((g(a), g(r.SecondGlyph), val(r.Value1, s.ValueFormat1), val(r.Value2, s.ValueFormat2))
                          for a, ps in zip(s.Coverage.glyphs, s.PairSet) for r in ps.PairValueRecord))
            return PairClass('pair-class', bool(s.ValueFormat1), bool(s.ValueFormat2), cov(s.Coverage),
                tuple(sorted((g(a), b) for a, b in s.ClassDef1.classDefs.items())),
                tuple(sorted((g(a), b) for a, b in s.ClassDef2.classDefs.items())),
                tuple(tuple((val(r.Value1, s.ValueFormat1), val(r.Value2, s.ValueFormat2))
                            for r in row.Class2Record) for row in s.Class1Record))
        if name in {'MarkBasePos', 'MarkMarkPos'}:
            require(s.Format == 1, 'Unsupported mark attachment format')
            mb = name == 'MarkBasePos'
            mc = s.MarkCoverage if mb else s.Mark1Coverage
            ma = s.MarkArray if mb else s.Mark1Array
            bc = s.BaseCoverage if mb else s.Mark2Coverage
            records = s.BaseArray.BaseRecord if mb else s.Mark2Array.Mark2Record
            require(len(mc.glyphs) == len(ma.MarkRecord) and len(bc.glyphs) == len(records), 'Bad anchor count')
            marks = tuple((g(c), m.Class, anchor(m.MarkAnchor)) for c, m in zip(mc.glyphs, ma.MarkRecord))
            require(all(a is not None for _, _, a in marks), 'Null mark anchor')
            bases = tuple((g(c), tuple(anchor(a) for a in (r.BaseAnchor if mb else r.Mark2Anchor)))
                          for c, r in zip(bc.glyphs, records))
            return (MarkBase if mb else MarkMark)('mark-base' if mb else 'mark-mark', s.ClassCount, marks, bases)
        raise ProfileError(f'{tag}: unsupported required subtable {name}/{getattr(s, "Format", None)}')
    def layout(tag):
        require(tag in font, f'Missing {tag}')
        table = font[tag].table
        require(getattr(table, 'FeatureVariations', None) is None, 'Feature variations are unsupported')
        script = next((s.Script for s in table.ScriptList.ScriptRecord if s.ScriptTag == 'bng2'), None)
        require(script is not None and script.DefaultLangSys is not None, 'Missing bng2 default language')
        lang = script.DefaultLangSys
        require(lang.ReqFeatureIndex == 65535, 'Required-language feature needs an explicit runtime stage')
        features = []
        for index in lang.FeatureIndex:
            f = table.FeatureList.FeatureRecord[index]
            require(f.Feature.FeatureParams is None, 'FeatureParams are unsupported')
            features.append(Feature(f.FeatureTag, tuple(f.Feature.LookupListIndex)))
        pending = {i for f in features for i in f.lookups}; result = {}
        while pending:
            i = min(pending); pending.remove(i)
            if i in result: continue
            require(0 <= i < len(table.LookupList.Lookup), 'Invalid lookup reference')
            l = table.LookupList.Lookup[i]
            wire_types = {'SingleSubst': 1, 'MultipleSubst': 2, 'LigatureSubst': 4, 'ChainContextSubst': 6, 'ExtensionSubst': 7} if tag == 'GSUB' else {'PairPos': 2, 'MarkBasePos': 4, 'MarkMarkPos': 6, 'ExtensionPos': 9}
            require(all(l.LookupType == wire_types.get(type(s).__name__) for s in l.SubTable), 'Unsupported/inconsistent required lookup type')
            subs = tuple(extract(s, tag) for s in l.SubTable)
            result[i] = Lookup(i, l.LookupFlag, getattr(l, 'MarkFilteringSet', None) if l.LookupFlag & 16 else None, subs)
            for s in subs:
                if isinstance(s, Chain): pending.update(ref for _, ref in s.actions if ref not in result)
        return tuple(features), tuple(result[i] for i in sorted(result))
    require('GDEF' in font, 'Missing GDEF')
    gd = font['GDEF'].table
    require(getattr(gd, 'VarStore', None) is None, 'GDEF variation store unsupported')
    def classes(name):
        table = getattr(gd, name, None); mapping = table.classDefs if table else {}
        return tuple(mapping.get(n, 0) for n in names)
    ms = getattr(gd, 'MarkGlyphSetsDef', None)
    require(ms is None or ms.MarkSetTableFormat == 1, 'Unsupported MarkGlyphSets format')
    gsf, gs = layout('GSUB'); gpf, gp = layout('GPOS')
    bounds = []
    for name in names:
        gl = font['glyf'][name]
        if gl.numberOfContours == 0: bounds.append(None)
        else:
            if not hasattr(gl, 'xMin'): gl.recalcBounds(font['glyf'])
            bounds.append((gl.xMin, gl.yMin, gl.xMax, gl.yMax))
    p = FontProfile('bntex-fixed-font-profile', PROFILE_ABI, digest, 'bng2', 'dflt', len(names), font['head'].unitsPerEm,
                    tuple(sorted((cp, g(name)) for cp, name in font.getBestCmap().items())),
                    tuple(font['hmtx'].metrics[name][0] for name in names), tuple(bounds),
                    classes('GlyphClassDef'), classes('MarkAttachClassDef'),
                    tuple(cov(c) for c in ms.Coverage) if ms else (), gsf, gpf, gs, gp)
    return validate(p)


def compile_profile(font_path: str | Path) -> FontProfile:
    """Compile one exact static font; accepts no document or corpus argument."""
    from io import BytesIO
    from fontTools.ttLib import TTFont, TTLibError
    path = Path(font_path)
    require(path.stat().st_size <= 64 * 1024 * 1024, 'Font exceeds 64 MiB')
    raw = path.read_bytes()
    require(len(raw) <= 64 * 1024 * 1024, 'Font exceeds 64 MiB')
    digest = hashlib.sha256(raw).hexdigest()
    require(digest == PINNED_FONT_SHA256, 'Unsupported font: exact pinned Noto Serif Bengali Regular is required')
    try:
        with TTFont(BytesIO(raw), lazy=False) as font:
            require('glyf' in font and not any(t in font for t in ('fvar', 'CFF ', 'CFF2')), 'Static TrueType only')
            return _compile_font(font, digest)
    except (TTLibError, KeyError, AttributeError, IndexError) as exc:
        raise ProfileError(f'Malformed font table: {exc}') from exc


def serialize(profile: FontProfile) -> bytes:
    validate(profile)
    return (json.dumps(asdict(profile), ensure_ascii=True, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')


_TYPES = {c.__name__: c for c in (Value, Anchor, Single, Multiple, Ligature, Chain, PairGlyph, PairClass,
                                 MarkBase, MarkMark, Lookup, Feature, FontProfile)}


def _decode(value, tp, depth=0):
    require(depth < 64, 'Profile nesting exceeds limit')
    origin, args = get_origin(tp), get_args(tp)
    if tp is type(None):
        require(value is None, 'Expected null'); return None
    if tp in (int, str, bool):
        require(type(value) is tp, f'Expected {tp.__name__}, got {type(value).__name__}'); return value
    if origin is Literal:
        require(type(value) is str and value in args, 'Unknown record kind or selected system'); return value
    if origin in (Union, types.UnionType):
        if value is None and type(None) in args: return None
        for option in args:
            if option is type(None): continue
            if option in (int, str, bool) and type(value) is option: return value
            if isinstance(value, dict) and hasattr(option, '__dataclass_fields__'):
                hints = get_type_hints(option)
                if 'kind' in hints and value.get('kind') not in get_args(hints['kind']): continue
                return _decode(value, option, depth + 1)
            if get_origin(option) is tuple and isinstance(value, list): return _decode(value, option, depth + 1)
        raise ProfileError('Invalid union record')
    if origin is tuple:
        require(isinstance(value, list), 'Expected JSON array')
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode(v, args[0], depth + 1) for v in value)
        require(len(value) == len(args), 'Incorrect record arity')
        return tuple(_decode(v, t, depth + 1) for v, t in zip(value, args))
    require(hasattr(tp, '__dataclass_fields__') and isinstance(value, dict), 'Expected typed record')
    require(set(value) == {f.name for f in fields(tp)}, f'Unknown/missing fields in {tp.__name__}')
    hints = get_type_hints(tp)
    return tp(**{k: _decode(v, hints[k], depth + 1) for k, v in value.items()})


def load_profile(path: str | Path) -> FontProfile:
    path = Path(path)
    require(path.stat().st_size <= MAX_PROFILE_BYTES, 'Profile exceeds size limit')
    raw = path.read_bytes()
    require(len(raw) <= MAX_PROFILE_BYTES, 'Profile exceeds size limit')
    def pairs(items):
        d = {}
        for k, v in items:
            require(k not in d, f'Duplicate JSON key: {k}'); d[k] = v
        return d
    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda v: require(False, f'Invalid JSON constant: {v}'))
        return validate(_decode(data, FontProfile))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProfileError(f'Invalid profile JSON: {exc}') from exc
