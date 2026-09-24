"""Structural OpenType lookup-closure audit, NOT a font-profile compiler/shaper.

References: OpenType common layout tables, GSUB, GPOS and GDEF (Microsoft).
The union of selected language systems/features over-approximates runtime use.
Lookup order, script reordering and feature masks are NOT inferred here.
"""
from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

from fontTools import __version__ as fonttools_version
from fontTools.ttLib import TTFont
from . import __version__
from .build import inspect_font

DEFAULT_SCRIPTS = ('bng2', 'beng', 'DFLT')


def _walk(root: Any) -> Iterator[Any]:
    """Bounded iterative traversal of decoded FontTools records (no recursion)."""
    todo = [root]
    seen: set[int] = set()
    while todo:
        obj = todo.pop()
        if obj is None or isinstance(obj, (str, bytes, int, float, bool)):
            continue
        identity = id(obj)
        if identity in seen:
            continue
        seen.add(identity)
        if len(seen) > 500_000:
            raise ValueError('Layout audit object budget exceeded.')
        if isinstance(obj, dict):
            todo.extend(reversed(list(obj.values())))
        elif isinstance(obj, (tuple, list)):
            todo.extend(reversed(obj))
        elif hasattr(obj, '__dict__'):
            yield obj
            todo.extend(reversed([v for k, v in vars(obj).items() if not k.startswith('_')]))


def _index(value: Any, count: int, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < count:
        raise ValueError(f'{context}: invalid index {value!r}; expected 0..{count - 1}.')
    return value


def _wire_formats(raw: bytes | None, tag: str, lookup_count: int) -> dict:
    """Read original subtable format headers; FontTools normalizes some away."""
    if raw is None:
        return {}
    def read(offset: int, fmt: str = '>H') -> int:
        if offset < 0 or offset + struct.calcsize(fmt) > len(raw):
            raise ValueError(f'{tag}: truncated layout header at byte {offset}.')
        return struct.unpack_from(fmt, raw, offset)[0]
    base = read(8)  # LookupListOffset in both GSUB and GPOS
    if not base or read(base) != lookup_count:
        raise ValueError(f'{tag}: inconsistent original LookupList header.')
    result = {}
    for i in range(lookup_count):
        lookup = base + read(base + 2 + 2 * i)
        kind, count = read(lookup), read(lookup + 4)
        for j in range(count):
            sub = lookup + read(lookup + 6 + 2 * j)
            record = {'outer_format': read(sub), 'effective_format': read(sub)}
            if kind == (7 if tag == 'GSUB' else 9):
                record['effective_format'] = read(sub + read(sub + 4, '>I'))
            result[i, j] = record
    return result


def _cycle_edges(graph: dict[int, list[int]]) -> list[list[int]]:
    """DFS back edges witness cycles; this is not an enumeration of all cycles."""
    colors: dict[int, int] = {}
    result = []
    for root in sorted(graph):
        if colors.get(root):
            continue
        colors[root] = 1
        stack = [(root, iter(graph[root]))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                colors[node] = 2
                stack.pop()
            elif colors.get(child) == 1:
                result.append([node, child])
            elif not colors.get(child):
                colors[child] = 1
                stack.append((child, iter(graph[child])))
    return result


def audit_layout(table: Any, tag: str, scripts: tuple[str, ...] = DEFAULT_SCRIPTS,
                 *, gdef: Any = None, raw: bytes | None = None) -> dict:
    """Trace feature roots and contextual references; reject broken references.

    This is a structural inventory, not a complete malformed-font validator or
    a support certificate. All languages and all exposed features are included.
    """
    if tag not in {'GSUB', 'GPOS'}:
        raise ValueError('Layout tag must be GSUB or GPOS.')
    if not scripts or any(len(s) != 4 or not s.isascii() for s in scripts):
        raise ValueError('OpenType script tags must contain exactly four ASCII characters.')
    lookups = table.LookupList.Lookup if table.LookupList else []
    features = table.FeatureList.FeatureRecord if table.FeatureList else []
    records = table.ScriptList.ScriptRecord if table.ScriptList else []
    roots: set[int] = set()
    selected = []
    for record in records:
        if record.ScriptTag not in scripts:
            continue
        languages = [('default', record.Script.DefaultLangSys)]
        languages += [(r.LangSysTag, r.LangSys) for r in record.Script.LangSysRecord]
        for language, system in languages:
            if system is None:
                continue
            indices = list(system.FeatureIndex)
            required = system.ReqFeatureIndex
            if required != 0xFFFF:
                indices.insert(0, required)
            entries = []
            for index in indices:
                _index(index, len(features), f'{tag}/{record.ScriptTag}/{language} feature')
                feature = features[index]
                ids = list(feature.Feature.LookupListIndex)
                for item in ids:
                    roots.add(_index(item, len(lookups), f'{tag} feature {feature.FeatureTag} lookup'))
                entries.append({'index': index, 'tag': feature.FeatureTag,
                                'required': index == required, 'lookups': ids})
            selected.append({'script': record.ScriptTag, 'language': language, 'features': entries})
    formats = _wire_formats(raw, tag, len(lookups))
    pending = sorted(roots, reverse=True)
    done: dict[int, dict] = {}
    extension = 7 if tag == 'GSUB' else 9
    maximum = 8 if tag == 'GSUB' else 9
    while pending:
        index = pending.pop()
        if index in done:
            continue
        lookup = lookups[index]
        kind, flags = lookup.LookupType, lookup.LookupFlag
        where = f'{tag} lookup {index}'
        if not isinstance(kind, int) or not 1 <= kind <= maximum:
            raise ValueError(f'{where}: unknown lookup type {kind!r}.')
        if not isinstance(flags, int) or not 0 <= flags <= 65535 or flags & 0x00E0:
            raise ValueError(f'{where}: invalid or reserved lookup flags {flags!r}.')
        dependencies = []
        if flags & 0x000E or flags & 0xFF10:
            dependencies.append('GlyphClassDef')
        if flags & 0xFF00:
            dependencies.append('MarkAttachClassDef')
        if flags & 0x0010:
            dependencies.append('MarkGlyphSetsDef')
        for dependency in dependencies:
            if gdef is None or getattr(gdef, dependency, None) is None:
                raise ValueError(f'{where}: required GDEF.{dependency} is missing.')
        markset = None
        if flags & 0x0010:
            markset = getattr(lookup, 'MarkFilteringSet', None)
            coverages = getattr(gdef.MarkGlyphSetsDef, 'Coverage', [])
            _index(markset, len(coverages), where + ' MarkFilteringSet')
        if not lookup.SubTable:
            raise ValueError(f'{where}: empty subtable list.')
        references: set[int] = set()
        subtables = []
        advanced: set[str] = set()
        effective_types: set[int] = set()
        for number, original in enumerate(lookup.SubTable):
            sub, effective = original, kind
            if kind == extension:
                effective = getattr(original, 'ExtensionLookupType', None)
                sub = getattr(original, 'ExtSubTable', None)
                if (getattr(original, 'Format', None) != 1 or sub is None or
                        not isinstance(effective, int) or not 1 <= effective <= maximum or effective == extension):
                    raise ValueError(f'{where}: malformed extension subtable {number}.')
            effective_types.add(effective)
            wire = formats.get((index, number), {})
            subtables.append({'index': number, 'effective_type': effective,
                              'decoded_format': getattr(sub, 'Format', None), **wire})
            for obj in _walk(sub):
                if hasattr(obj, 'LookupListIndex'):
                    target = _index(obj.LookupListIndex, len(lookups), where + ' nested lookup')
                    references.add(target)
                name = type(obj).__name__
                if name == 'Device':
                    advanced.add('variation-index' if getattr(obj, 'DeltaFormat', None) == 0x8000 else 'device-adjustment')
                if name == 'Anchor' and getattr(obj, 'Format', None) == 2:
                    advanced.add('point-index-anchor')
        if len(effective_types) != 1:
            raise ValueError(f'{where}: mixed effective extension types.')
        done[index] = {'index': index, 'type': kind, 'flags': flags, 'subtables': subtables,
                       'references': sorted(references), 'gdef_dependencies': dependencies,
                       'mark_filtering_set': markset, 'advanced_constructs': sorted(advanced)}
        pending.extend(sorted(references - done.keys(), reverse=True))
    graph = {i: r['references'] for i, r in done.items()}
    reachable = sorted(done)
    return {'selected_systems': selected, 'total_lookup_count': len(lookups),
            'root_lookups': sorted(roots), 'reachable_lookups': reachable,
            'nested_only_lookups': sorted(done.keys() - roots),
            'unreachable_lookups': sorted(set(range(len(lookups))) - done.keys()),
            'lookups': [done[i] for i in reachable],
            'effective_type_counts': dict(sorted(Counter(str(s['effective_type'])
                for item in done.values() for s in item['subtables']).items())),
            'cycle_back_edges': _cycle_edges(graph),
            'has_feature_variations': getattr(table, 'FeatureVariations', None) is not None}


def audit_font(path: Path, *, scripts: tuple[str, ...] = DEFAULT_SCRIPTS) -> dict:
    """Fingerprint a local static font and audit selected layout closures."""
    metadata = inspect_font(path)
    with TTFont(path, lazy=False) as font:
        gdef = font['GDEF'].table if 'GDEF' in font else None
        tables = {tag: audit_layout(font[tag].table, tag, scripts, gdef=gdef, raw=font.reader[tag])
                  if tag in font else None for tag in ('GSUB', 'GPOS')}
        return {'schema': 1, 'kind': 'bntex-structural-layout-audit', 'font': metadata,
                'bntex_version': __version__, 'fonttools_version': fonttools_version,
                'requested_scripts': list(scripts), 'tables': tables,
                'native_runtime_supported': False,
                'limitations': ['No native shaper or executable font profile is generated.',
                    'Selected language-system feature union is a conservative structural inventory.',
                    'Feature execution order, masks, Unicode reordering and positioning are not implemented.',
                    'Cycles are reported, not executed; advanced constructs are not implemented.',
                    'Not a full OpenType font validator; no font binary is emitted.']}
