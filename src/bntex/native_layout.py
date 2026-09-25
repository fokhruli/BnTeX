"""Bounded GSUB/GPOS interpreter over BnTeX's typed font records.

No shaping library or FontTools is imported here. Rules are data; there is no
word dictionary. Bengali script analysis is in native_model, not in the font.
"""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from .native_profile import (FontProfile, Lookup, Single, Multiple, Ligature, Chain,
                             PairGlyph, PairClass, MarkBase, MarkMark, Value)


class ShapingError(ValueError):
    """Explicit unsupported input, stage failure, or resource limit."""


@dataclass(slots=True)
class Item:
    gid: int
    cp: int
    cluster: int
    category: str = 'X'
    position: int = 15
    syllable: int = 0
    masks: set[str] = field(default_factory=set)
    unsafe: bool = False
    ligated: bool = False
    multiplied: bool = False
    substituted: bool = False
    lig_id: int = 0
    component: int = 0
    num_components: int = 1
    advance: int = 0
    x_offset: int = 0
    y_offset: int = 0
    attachment: tuple[int, int, int] | None = None

    def is_category(self, *cats):
        return not self.ligated and self.category in cats


class Buffer:
    def __init__(self, items: list[Item], *, trace: bool = False, max_operations: int = 2_000_000):
        self.items = items
        self.trace_enabled = trace
        self.events: list[dict] = []
        self.operations = 0
        self.max_operations = max_operations
        self.ligature_serial = 0
        self.trace_cells = 0

    def tick(self, amount=1):
        self.operations += amount
        if self.operations > self.max_operations:
            raise ShapingError('layout: operation budget exceeded')
        if len(self.items) > 8192:
            raise ShapingError('layout: glyph expansion limit exceeded')

    def unsafe_span(self, start: int, end: int):
        if end <= start: return
        clusters = [g.cluster for g in self.items[max(0, start):end]]
        if clusters:
            first = min(clusters)
            for g in self.items[max(0, start):end]:
                if g.cluster != first: g.unsafe = True

    def merge(self, start: int, end: int):
        if end <= start: return
        start = max(0, start); end = min(len(self.items), end)
        old = [g.cluster for g in self.items[start:end]]
        if not old: return
        lowest = min(old)
        # Extend to complete equal-cluster groups at each edge, as required by
        # monotone-grapheme cluster semantics.
        left, right = start, end
        while left and self.items[left - 1].cluster == self.items[start].cluster: left -= 1
        while right < len(self.items) and self.items[right].cluster == self.items[end - 1].cluster: right += 1
        for g in self.items[left:right]:
            if g.cluster != lowest: g.cluster = lowest; g.unsafe = False

    def snapshot(self, stage: str, **metadata):
        if not self.trace_enabled: return
        self.trace_cells += len(self.items)
        if len(self.events) >= 256 or self.trace_cells > 65536:
            raise ShapingError('trace: bounded snapshot budget exceeded')
        self.events.append({'stage': stage, **metadata, 'glyphs': [
            {'gid': g.gid, 'scalar': g.cp, 'cluster': g.cluster, 'category': g.category,
             'position': g.position, 'syllable': g.syllable, 'masks': sorted(g.masks),
             'unsafe_to_break': g.unsafe, 'ligated': g.ligated, 'multiplied': g.multiplied, 'advance': g.advance,
             'x_offset': g.x_offset, 'y_offset': g.y_offset} for g in self.items]})


class Layout:
    def __init__(self, profile: FontProfile):
        self.profile = profile
        self.gsub = {l.index: l for l in profile.gsub}
        self.gpos = {l.index: l for l in profile.gpos}
        self.gsub_features = {f.tag: f.lookups for f in profile.gsub_features}
        self.gpos_features = {f.tag: f.lookups for f in profile.gpos_features}
        self.maps = {}
        for lookup in profile.gsub + profile.gpos:
            for s in lookup.subtables:
                if isinstance(s, (Single, Multiple)):
                    self.maps[id(s)] = dict(s.entries)
                elif isinstance(s, Ligature):
                    d = {}
                    for pattern, result in s.entries: d.setdefault(pattern[0], []).append((pattern, result))
                    self.maps[id(s)] = d
                elif isinstance(s, PairGlyph):
                    self.maps[id(s)] = {(a, b): (v1, v2) for a, b, v1, v2 in s.entries}
                elif isinstance(s, PairClass):
                    self.maps[id(s)] = (frozenset(s.coverage), dict(s.class1), dict(s.class2))
                elif isinstance(s, (MarkBase, MarkMark)):
                    self.maps[id(s)] = ({g: (c, a) for g, c, a in s.marks}, dict(s.bases))

    def ignored(self, g: Item, lookup: Lookup, auto_joiners=False):
        if auto_joiners and g.cp in (0x200C, 0x200D) and not g.ligated: return True
        cls = self.profile.glyph_classes[g.gid]
        flag = {1: 2, 2: 4, 3: 8}.get(cls, 0)
        if flag & lookup.flags: return True
        if cls == 3:
            if lookup.flags & 16:
                return g.gid not in self.profile.mark_filter_sets[lookup.mark_filter_set]
            attach = lookup.flags >> 8
            if attach:
                return self.profile.mark_attach_classes[g.gid] != attach
        return False

    def match(self, buf: Buffer, index: int, covers, lookup: Lookup, *, step=1,
              mask: str | None = None, syllable: int | None = None,
              auto_joiners=False, context=False):
        matched = []
        for coverage in covers:
            while 0 <= index < len(buf.items):
                buf.tick(); g = buf.items[index]
                if self.ignored(g, lookup):
                    index += step; continue
                can_match = (g.gid in coverage and (not mask or mask in g.masks)
                             and (syllable is None or g.syllable == syllable))
                # Default-ignorable characters are soft skips: a rule explicitly
                # mentioning one may still match it. GSUB input never skips ZWNJ;
                # context always skips ZWJ, but skips ZWNJ only for automatic features.
                soft_skip = (not g.ligated and ((g.cp == 0x200D and (context or auto_joiners))
                                               or (g.cp == 0x200C and context and auto_joiners)))
                if can_match: break
                if soft_skip: index += step; continue
                return None
            else: return None
            matched.append(index); index += step
        return matched

    def would_substitute(self, feature: str, glyphs: tuple[int, ...]) -> bool:
        # Bengali bng2 dynamic classification requires zero external context.
        for k in self.gsub_features.get(feature, ()):
            for s in self.gsub[k].subtables:
                if isinstance(s, Ligature) and any(pattern == glyphs for pattern, _ in s.entries): return True
                if isinstance(s, Single) and len(glyphs) == 1 and glyphs[0] in self.maps[id(s)]: return True
                if isinstance(s, Multiple) and len(glyphs) == 1 and glyphs[0] in self.maps[id(s)]: return True
                if isinstance(s, Chain) and not s.backtrack and not s.lookahead and len(s.inputs) == len(glyphs):
                    if all(g in c for g, c in zip(glyphs, s.inputs)): return True
        return False

    def compatible_components(self, buf: Buffer, indices: list[int], lookup: Lookup) -> bool:
        """Do not combine marks belonging to unrelated ligature components."""
        first = buf.items[indices[0]]
        for i in indices[1:]:
            other = buf.items[i]
            if first.lig_id and first.component:
                if (other.lig_id, other.component) != (first.lig_id, first.component):
                    j = indices[0] - 1
                    while j >= 0 and buf.items[j].lig_id == first.lig_id and buf.items[j].component:
                        j -= 1
                    if (j < 0 or buf.items[j].lig_id != first.lig_id or
                            not self.ignored(buf.items[j], lookup)):
                        return False
            elif other.lig_id and other.component and other.lig_id != first.lig_id:
                return False
        return True

    def substitute(self, buf: Buffer, index: int, lookup_index: int, *, mask=None,
                   per_syllable=True, auto_joiners=False, depth=0):
        """Return next cursor on application, None on no match."""
        buf.tick()
        if depth >= 32: raise ShapingError('GSUB: contextual recursion limit')
        if not 0 <= index < len(buf.items): return None
        lookup = self.gsub[lookup_index]; g = buf.items[index]
        if self.ignored(g, lookup) or (mask and mask not in g.masks): return None
        syl = g.syllable if per_syllable else None
        for s in lookup.subtables:
            buf.tick()
            if isinstance(s, (Single, Multiple)):
                result = self.maps[id(s)].get(g.gid)
                if result is None: continue
                if isinstance(s, Single):
                    g.gid = result; g.substituted = True
                    return index + 1
                generated = [replace(g, gid=k, multiplied=True, substituted=True,
                                     masks=set(g.masks), component=j) for j, k in enumerate(result)]
                buf.items[index:index+1] = generated
                buf.tick()
                return index + len(generated)
            if isinstance(s, Ligature):
                for pattern, result in self.maps[id(s)].get(g.gid, ()):
                    buf.tick()
                    rest = self.match(buf, index + 1, tuple((k,) for k in pattern[1:]), lookup,
                                      mask=mask, syllable=syl, auto_joiners=auto_joiners)
                    if rest is None: continue
                    indices = [index] + rest
                    if not self.compatible_components(buf, indices, lookup): continue
                    buf.merge(index, indices[-1] + 1)
                    classes = [self.profile.glyph_classes[buf.items[i].gid] for i in indices]
                    all_marks = all(c == 3 for c in classes)
                    base_marks = classes[0] == 1 and all(c == 3 for c in classes[1:])
                    is_ligature = not (all_marks or base_marks)
                    old_ids = [buf.items[i].lig_id for i in indices]
                    old_counts = [buf.items[i].num_components for i in indices]
                    total = sum(old_counts)
                    serial = 0
                    if is_ligature:
                        buf.ligature_serial += 1
                        serial = buf.ligature_serial
                        so_far = old_counts[0]
                        for part, (left, right) in enumerate(zip(indices, indices[1:])):
                            count = old_counts[part]
                            for j in range(left + 1, right):
                                mark = buf.items[j]
                                component = mark.component or count
                                mark.lig_id = serial
                                mark.component = so_far - count + min(component, count)
                            so_far += old_counts[part + 1]
                        g.lig_id = serial; g.component = 0; g.num_components = total
                    if not all_marks and old_ids[-1]:
                        for mark in buf.items[indices[-1] + 1:]:
                            if mark.lig_id != old_ids[-1] or not mark.component: break
                            mark.lig_id = serial
                            mark.component = total - old_counts[-1] + min(mark.component, old_counts[-1])
                    g.gid = result; g.ligated = True; g.multiplied = False; g.substituted = True
                    for j in reversed(rest): del buf.items[j]
                    return index + 1
            elif isinstance(s, Chain):
                indices = self.match(buf, index, s.inputs, lookup, mask=mask, syllable=syl,
                                     auto_joiners=auto_joiners)
                if indices is None or not self.compatible_components(buf, indices, lookup): continue
                back = self.match(buf, index - 1, s.backtrack, lookup, step=-1, auto_joiners=auto_joiners, context=True)
                ahead = self.match(buf, indices[-1] + 1, s.lookahead, lookup, auto_joiners=auto_joiners, context=True)
                if back is None or ahead is None: continue
                buf.unsafe_span(back[-1] if back else index, (ahead[-1] if ahead else indices[-1]) + 1)
                # Track object identities so nested substitutions changing glyph
                # count do not make later actions target stale numeric offsets.
                targets = [buf.items[i] for i in indices]
                cursor_end = indices[-1] + 1
                for slot, ref in s.actions:
                    obj = targets[slot]
                    pos = next((j for j, x in enumerate(buf.items) if x is obj), None)
                    if pos is None: continue  # target consumed by a preceding action
                    before = len(buf.items)
                    new_cursor = self.substitute(buf, pos, ref, mask=mask, per_syllable=per_syllable,
                                                 auto_joiners=auto_joiners, depth=depth+1)
                    if new_cursor is not None:
                        if not any(x is obj for x in buf.items) and pos < len(buf.items): targets[slot] = buf.items[pos]
                        cursor_end += len(buf.items) - before
                return max(index + 1, cursor_end)
        return None

    def apply_gsub(self, buf: Buffer, feature_tags: tuple[str, ...], *, per_syllable=True,
                   auto_joiners=False):
        selected = {}
        for tag in feature_tags:
            for k in self.gsub_features.get(tag, ()): selected.setdefault(k, set()).add(tag)
        masked = {'rphf', 'pref', 'blwf', 'abvf', 'half', 'pstf', 'init'}
        for k in sorted(selected):
            tags = selected[k]
            # None means a global feature enables the whole lookup.
            mask = next(iter(tags)) if len(tags) == 1 and tags <= masked else None
            lookup_auto_joiners = auto_joiners or bool(tags & {'rclt', 'calt', 'clig', 'rlig', 'locl', 'ccmp'})
            lookup_per_syllable = per_syllable and not bool(tags & {'rclt', 'calt', 'clig', 'rlig'})
            cursor = 0
            before = [(g.gid, g.cluster) for g in buf.items] if buf.trace_enabled else None
            while cursor < len(buf.items):
                result = self.substitute(buf, cursor, k, mask=mask, per_syllable=lookup_per_syllable,
                                         auto_joiners=lookup_auto_joiners)
                cursor = cursor + 1 if result is None else result
            if buf.trace_enabled and before != [(g.gid, g.cluster) for g in buf.items]:
                buf.snapshot('GSUB', lookup=k, features=sorted(tags))

    @staticmethod
    def _value(g: Item, v: Value):
        g.x_offset += v.x_placement; g.y_offset += v.y_placement
        g.advance += v.x_advance
        if v.y_advance: raise ShapingError('GPOS: vertical advance outside horizontal profile')

    def apply_gpos(self, buf: Buffer):
        # All selected positioning features share one lookup-index-ordered stage.
        # No enabled table is silently skipped in the pinned profile.
        selected = sorted({k for f in self.profile.gpos_features for k in f.lookups})
        for g in buf.items:
            g.advance = self.profile.advances[g.gid]
            g.x_offset = g.y_offset = 0; g.attachment = None
        for k in selected:
            lookup = self.gpos[k]; i = 0
            while i < len(buf.items):
                buf.tick(); g = buf.items[i]
                if self.ignored(g, lookup, auto_joiners=True): i += 1; continue
                next_cursor = i + 1
                for s in lookup.subtables:
                    if isinstance(s, (PairGlyph, PairClass)):
                        j = i + 1
                        while j < len(buf.items) and self.ignored(buf.items[j], lookup, auto_joiners=True): j += 1
                        if j >= len(buf.items): continue
                        data = self.maps[id(s)]
                        if isinstance(s, PairGlyph): values = data.get((g.gid, buf.items[j].gid))
                        else:
                            cov, c1, c2 = data
                            values = s.matrix[c1.get(g.gid, 0)][c2.get(buf.items[j].gid, 0)] if g.gid in cov else None
                        if values is None: continue
                        self._value(g, values[0]); self._value(buf.items[j], values[1])
                        buf.unsafe_span(i, j + 1)
                        next_cursor = j + 1 if s.value2_present else j
                        break
                    elif isinstance(s, (MarkBase, MarkMark)):
                        marks, bases = self.maps[id(s)]
                        if g.gid not in marks: continue
                        cls, ma = marks[g.gid]; j = i - 1
                        if isinstance(s, MarkBase):
                            while j >= 0 and (self.profile.glyph_classes[buf.items[j].gid] == 3 or
                                              (buf.items[j].cp in (0x200C, 0x200D) and not buf.items[j].ligated)):
                                j -= 1
                        else:
                            while j >= 0 and self.ignored(buf.items[j], lookup, auto_joiners=True): j -= 1
                            if j >= 0 and self.profile.glyph_classes[buf.items[j].gid] != 3: continue
                            if j >= 0 and (g.lig_id != buf.items[j].lig_id and g.lig_id and buf.items[j].lig_id): continue
                        if j < 0 or buf.items[j].gid not in bases: continue
                        ba = bases[buf.items[j].gid][cls]
                        if ba is None: continue
                        g.x_offset = ba.x - ma.x; g.y_offset = ba.y - ma.y
                        g.attachment = (j, g.x_offset, g.y_offset)
                        buf.unsafe_span(j, i + 1)
                        break
            
                i = next_cursor
            buf.snapshot('GPOS', lookup=k)
        # Resolve attachment chains after all pair advances/placements are known.
        pen = [0]
        for g in buf.items: pen.append(pen[-1] + g.advance)
        for i, g in enumerate(buf.items):
            if g.attachment:
                j, dx, dy = g.attachment
                if not 0 <= j < i: raise ShapingError('GPOS: invalid attachment graph')
                g.x_offset = dx + buf.items[j].x_offset - (pen[i] - pen[j])
                g.y_offset = dy + buf.items[j].y_offset
